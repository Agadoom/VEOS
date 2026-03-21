import time
import config
from database import get_db_conn

def get_badge_info(score):
    if score >= 500: return "💎 Diamond", 1000, "#00D1FF"
    if score >= 150: return "🥇 Gold", 500, "#FFD700"
    if score >= 50:  return "🥈 Silver", 150, "#C0C0C0"
    return "🥉 Bronze", 50, "#CD7F32"

async def register_user(uid, name, ref_id):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
    if not c.fetchone():
        c.execute("""INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, staked_amount, streak) 
                     VALUES (%s, %s, %s, %s, %s, 0, 0)""", 
                  (uid, name, ref_id if ref_id != uid else None, config.MAX_ENERGY, int(time.time())))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
    conn.commit(); c.close(); conn.close()
async def process_boost_energy(uid, max_energy):
    conn = get_db_conn()
    c = conn.cursor()
    # Vérifier le solde total
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users WHERE user_id=%s", (uid,))
    balance = c.fetchone()[0] or 0
    
    if balance >= 50: # Prix du boost
        # On déduit le prix (réparti sur les 3 assets) et on remet l'énergie au max
        c.execute("""UPDATE users SET 
                     p_genesis=p_genesis-17, p_unity=p_unity-17, p_veo=p_veo-16, 
                     energy=%s, last_energy_update=%s 
                     WHERE user_id=%s""", (max_energy, int(time.time()), uid))
        conn.commit()
        success = True
    else:
        success = False
    
    c.close(); conn.close()
    return success

async def claim_referral_rewards(uid):
    conn = get_db_conn()
    c = conn.cursor()
    
    # Récupérer le nombre total d'invités et ceux déjà payés
    c.execute("SELECT ref_count, ref_claimed FROM users WHERE user_id=%s", (uid,))
    res = c.fetchone()
    if not res: return 0, "User not found"
    
    total_refs = res[0] or 0
    already_claimed = res[1] or 0
    
    # Calculer combien de nouveaux amis n'ont pas encore été payés
    pending_refs = total_refs - already_claimed
    
    if pending_refs > 0:
        reward = pending_refs * 10  # 10 assets par ami
        # On ajoute la récompense au Genesis et on met à jour le compteur de claims
        c.execute("""UPDATE users SET 
                     p_genesis = p_genesis + %s, 
                     ref_claimed = ref_claimed + %s 
                     WHERE user_id = %s""", (reward, pending_refs, uid))
        conn.commit()
        c.close(); conn.close()
        return reward, f"Success: +{reward} Assets!"
    
    c.close(); conn.close()
    return 0, "No pending referrals to claim"

from datetime import datetime, timedelta

def process_daily_login(uid):
    conn = get_db_conn()
    c = conn.cursor()
    
    # Récupérer les infos actuelles
    c.execute("SELECT streak, last_login_date FROM users WHERE user_id=%s", (uid,))
    res = c.fetchone()
    if not res: return 0, 0
    
    current_streak = res[0] or 0
    last_login = res[1] # Format '2026-03-21'
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Si déjà réclamé aujourd'hui
    if last_login == today:
        return 0, current_streak
    
    # Calcul du nouveau streak
    new_streak = 1
    if last_login == yesterday:
        new_streak = current_streak + 1
    elif last_login is None:
        new_streak = 1
    else:
        # Trop tard, on repart à 1
        new_streak = 1
        
    # Calcul de la récompense (ex: 5, 10, 15... max 100)
    reward = min(new_streak * 5, 100)
    if new_streak == 7: reward = 150 # Bonus spécial jour 7
    
    # Mise à jour DB
    c.execute("""UPDATE users SET 
                 p_genesis = p_genesis + %s, 
                 streak = %s, 
                 last_login_date = %s 
                 WHERE user_id = %s""", (reward, new_streak, today, uid))
    conn.commit()
    c.close(); conn.close()
    
    return reward, new_streak


