import psycopg2
import os
import time

def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db_structure():
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # 1. Création de la table users (avec la virgule corrigée)
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            p_genesis DOUBLE PRECISION DEFAULT 0,
            p_unity DOUBLE PRECISION DEFAULT 0,
            p_veo DOUBLE PRECISION DEFAULT 0,
            energy INTEGER DEFAULT 100,
            last_energy_update INTEGER,
            last_click_time BIGINT,
            streak INTEGER DEFAULT 0,
            referrer_id BIGINT,
            last_login_date TXT
        )""")

        # 2. SÉCURITÉ : Ajouter la colonne referrer_id si elle n'existe pas encore
        # (Indispensable si la table a été créée avant l'ajout du système de parrainage)
        try:
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_id BIGINT")
        except:
            pass 

        # 3. Table des tokens communautaires
        c.execute("""CREATE TABLE IF NOT EXISTS community_tokens (
            id SERIAL PRIMARY KEY, 
            creator_id BIGINT, 
            name TEXT NOT NULL, 
            symbol TEXT NOT NULL, 
            description TEXT,
            logo_url TEXT,
            banner_url TEXT,
            website TEXT,
            twitter_x TEXT,
            price DOUBLE PRECISION DEFAULT 0.0001, 
            mcap DOUBLE PRECISION DEFAULT 0, 
            volume DOUBLE PRECISION DEFAULT 0, 
            created_at BIGINT
        )""")

        # 4. Table des actifs possédés
        c.execute("""CREATE TABLE IF NOT EXISTS user_community_assets (
            user_id BIGINT,
            token_id INTEGER,
            amount DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (user_id, token_id)
        )""")

        # 5. Table de l'activité
        c.execute("""CREATE TABLE IF NOT EXISTS token_activity (
            id SERIAL PRIMARY KEY,
            token_id INTEGER,
            user_id BIGINT,
            user_name TEXT,
            type TEXT,
            amount_wpt DOUBLE PRECISION,
            created_at INTEGER
        )""")
        
        conn.commit()
        print("🚀 Database structure verified and updated!")
    except Exception as e:
        print(f"DB Error Init: {e}")
    finally:
        c.close(); conn.close()

# --- FONCTIONS UTILISATEURS ---

def get_user_full(uid):
    conn = get_db_conn(); c = conn.cursor()
    try:
        # J'ai ajouté referrer_id (index 9) et p_genesis à la sélection
        c.execute("""SELECT p_genesis, p_unity, p_veo, 0, name, energy, 
                     last_energy_update, streak, 0, referrer_id FROM users WHERE user_id=%s""", (uid,))
        res = c.fetchone()
        if not res: 
            c.execute("INSERT INTO users (user_id, name, energy, last_energy_update) VALUES (%s, 'New Citizen', 100, %s)", (uid, int(time.time())))
            conn.commit()
            return (0, 0, 0, 0, 'New Citizen', 100, int(time.time()), 0, 0, None)
        return res
    finally:
        c.close(); conn.close()

# ... (Garde tes fonctions deploy_token et buy_token telles quelles, elles sont bonnes) ...

def add_referral_reward(new_user_id, referrer_id):
    conn = get_db_conn(); c = conn.cursor()
    try:
        # On vérifie si le parrain existe
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (referrer_id,))
        if c.fetchone():
            # Le parrain gagne 500 WPT, le nouvel ami gagne 100 WPT
            c.execute("UPDATE users SET p_genesis = p_genesis + 500 WHERE user_id = %s", (referrer_id,))
            c.execute("UPDATE users SET p_genesis = p_genesis + 100, referrer_id = %s WHERE user_id = %s", (referrer_id, new_user_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Referral Error: {e}")
        conn.rollback()
    finally:
        c.close(); conn.close()
    return False


def get_community_tokens():
    conn = get_db_conn(); c = conn.cursor()
    try:
        # Vérifie bien l'ordre ici : id(0), name(1), symbol(2), price(3), mcap(4), logo(5), banner(6)
        c.execute("""SELECT id, name, symbol, price, mcap, logo_url, 
                     banner_url, description, website, twitter_x 
                     FROM community_tokens ORDER BY mcap DESC""")
        res = c.fetchall()
        return [
            {
                "id": r[0], 
                "name": r[1], 
                "sym": r[2], 
                "price": float(r[3] or 0), 
                "mcap": float(r[4] or 0), 
                "logo": r[5] if r[5] else "", # Si pas de logo, évite le crash
                "banner": r[6] if r[6] else "",
                "desc": r[7], "web": r[8], "x": r[9]
            } for r in res
        ]
    finally:
        c.close(); conn.close()

