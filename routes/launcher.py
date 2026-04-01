from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import database
import time
import asyncio

router = APIRouter(prefix="/api/launcher", tags=["Launcher"])

# --- CONFIGURATION ADMIN (Machine à Cash) ---
ADMIN_ID = 1414016840 # Ton Telegram ID pour recevoir les taxes

class TradeRequest(BaseModel):
    user_id: int
    token_id: int
    amount: float 

class DeployRequest(BaseModel):
    user_id: int
    name: str
    symbol: str
    description: str = ""
    website_url: str = ""
    twitter_url: str = ""
    logo_b64: str
    banner_b64: str = ""

# --- 📋 LISTE UNIFIÉE (Recherche + Onglets) ---
@router.get("/list")
async def list_tokens(q: str = None, filter: str = "new", uid: int = 0):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        query = """
            SELECT id, name, symbol, logo, banner, price, 
                   description, website_url, twitter_url 
            FROM community_tokens
        """
        params = []
        where_clauses = []
        
        if q:
            where_clauses.append("(name ILIKE %s OR symbol ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])
            
        if filter == "my" and uid > 0:
            where_clauses.append("creator_id = %s")
            params.append(uid)
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        if filter == "hot":
            query += " ORDER BY price DESC"
        else:
            query += " ORDER BY id DESC"
            
        query += " LIMIT 50"
        
        c.execute(query, tuple(params))
        res = c.fetchall()

        return [{
            "id": r[0], "name": r[1], "symbol": r[2], 
            "logo": r[3], "banner": r[4], "price": float(r[5] or 0),
            "description": r[6] or "No description provided.",
            "website_url": r[7] or "",
            "twitter_url": r[8] or ""
        } for r in res]
    except Exception as e:
        print(f"❌ Erreur SQL List: {e}")
        return []
    finally:
        c.close(); conn.close()

# --- 🚀 ACHAT (BUY) AVEC TAXE 1% ---
@router.post("/buy")
async def buy_token(req: TradeRequest, request: Request):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérification solde
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        u = c.fetchone()
        if not u or float(u[0]) < req.amount:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Insufficient WPT Balance"})

        # 2. Calcul Taxe (1%)
        fee = req.amount * 0.01
        net_amount = req.amount - fee

        c.execute("SELECT price, name, symbol, creator_id FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        if not t: return JSONResponse(status_code=404, content={"ok": False, "error": "Token not found"})
            
        current_price, t_name, t_symbol, creator_id = float(t[0]), t[1], t[2], t[3]
        qty_to_receive = net_amount / current_price

        # 3. Transferts WPT
        # Débit acheteur
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount, req.user_id))
        # Crédit Admin (Taxe Protocol)
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (fee, ADMIN_ID))
        
        # 4. Crédit Assets
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + %s
        """, (req.user_id, req.token_id, qty_to_receive, qty_to_receive))
        
        # Pump de 1%
        new_price = current_price * 1.01
        c.execute("UPDATE community_tokens SET price = %s WHERE id = %s", (new_price, req.token_id))

        c.execute("INSERT INTO token_price_history (token_id, price, timestamp) VALUES (%s, %s, %s)", 
                  (req.token_id, new_price, int(time.time())))
        
        conn.commit()

        # Notification Pump
        bot = request.app.state.bot 
        if creator_id and bot:
            msg = f"🚀 <b>PUMP ALERT!</b>\n\nSomeone bought <b>{t_name}</b> (${t_symbol})!\nNew Price: <code>{new_price:.6f}</code> WPT\nFee to Protocol: {fee:.2f} WPT"
            asyncio.create_task(bot.send_message(chat_id=creator_id, text=msg, parse_mode="HTML"))

        return {"ok": True, "received": qty_to_receive, "fee": fee}

    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

# --- 📉 VENTE (SELL) AVEC TAXE 1% ---
@router.post("/sell")
async def sell_token(req: TradeRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT amount FROM user_community_assets WHERE user_id = %s AND token_id = %s", (req.user_id, req.token_id))
        res = c.fetchone()
        if not res or float(res[0]) < req.amount:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Not enough tokens"})

        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        current_price = float(c.fetchone()[0])
        gross_wpt = req.amount * current_price

        # Taxe 1% sur la vente
        fee = gross_wpt * 0.01
        net_wpt = gross_wpt - fee

        # Exécution
        c.execute("UPDATE user_community_assets SET amount = amount - %s WHERE user_id = %s AND token_id = %s", 
                  (req.amount, req.user_id, req.token_id))
        
        # Utilisateur reçoit le net, Admin reçoit la taxe
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (net_wpt, req.user_id))
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (fee, ADMIN_ID))
        
        new_price = current_price * 0.99
        c.execute("UPDATE community_tokens SET price = %s WHERE id = %s", (new_price, req.token_id))
        c.execute("INSERT INTO token_price_history (token_id, price, timestamp) VALUES (%s, %s, %s)", 
                  (req.token_id, new_price, int(time.time())))

        conn.commit()
        return {"ok": True, "received": net_wpt, "fee": fee}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

# --- 🏗️ DEPLOY (FEE 5000 WPT -> ADMIN) ---
@router.post("/deploy")
async def deploy_token(req: DeployRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        fee = 5000.0
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        u = c.fetchone()
        if not u or float(u[0]) < fee:
            return JSONResponse(status_code=400, content={"ok": False, "error": "5000 WPT required."})

        c.execute("""
            INSERT INTO community_tokens (name, symbol, description, website_url, twitter_url, logo, banner, price, creator_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (req.name, req.symbol, req.description, req.website_url, req.twitter_url, req.logo_b64, req.banner_b64, 0.0001, req.user_id))
        
        new_id = c.fetchone()[0]
        # On prélève chez l'utilisateur
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (fee, req.user_id))
        # On donne à l'ADMIN
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (fee, ADMIN_ID))
        
        c.execute("INSERT INTO token_price_history (token_id, price, timestamp) VALUES (%s, %s, %s)", 
                  (new_id, 0.0001, int(time.time())))
        conn.commit()
        return {"ok": True, "token_id": new_id}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

# Routes de lecture (History, Stats, Balance, Portfolio)
@router.get("/history/{tid}")
async def get_token_history(tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT price FROM token_price_history WHERE token_id = %s ORDER BY timestamp ASC LIMIT 50", (tid,))
        return [float(r[0]) for r in c.fetchall()] or [0.0001]
    finally:
        c.close(); conn.close()

@router.get("/stats/{tid}")
async def get_token_stats(tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(DISTINCT user_id) FROM user_community_assets WHERE token_id = %s", (tid,))
        holders = (c.fetchone()[0] or 0) + 1 
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (tid,))
        price = float(c.fetchone()[0] or 0.0001)
        return {"holders": holders, "mcap": round(price * 1000000000, 2)}
    finally:
        c.close(); conn.close()

@router.get("/balance/{uid}/{tid}")
async def get_user_token_balance(uid: int, tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT amount FROM user_community_assets WHERE user_id = %s AND token_id = %s", (uid, tid))
        res = c.fetchone()
        return {"ok": True, "balance": float(res[0]) if res else 0.0}
    finally:
        c.close(); conn.close()

@router.get("/portfolio/{uid}")
async def get_user_portfolio(uid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT t.id, t.name, t.symbol, t.logo, a.amount, t.price, 
                   t.description, t.website_url, t.twitter_url 
            FROM user_community_assets a
            JOIN community_tokens t ON a.token_id = t.id
            WHERE a.user_id = %s AND a.amount > 0
            ORDER BY (a.amount * t.price) DESC
        """, (uid,))
        res = c.fetchall()
        return [{
            "id": r[0], "name": r[1], "symbol": r[2], "logo": r[3], 
            "amount": float(r[4]), "price": float(r[5]),
            "description": r[6], "website_url": r[7], "twitter_url": r[8]
        } for r in res]
    finally:
        c.close(); conn.close()


# Dans routes/launcher.py

@router.post("/burn")
async def burn_wpt(user_id: int, amount: float):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On retire à l'user
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (amount, user_id))
        
        # On ajoute au compteur global (ID 1 est la ligne par défaut)
        c.execute("UPDATE global_stats SET total_burned = total_burned + %s", (amount,))
        
        conn.commit() # <--- TRÈS IMPORTANT : C'est ça qui "sauvegarde" sur le disque
        return {"ok": True, "burned": amount}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()



@router.get("/total-burned")
async def get_total_burned():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. On tente de récupérer le score
        c.execute("SELECT total_burned FROM global_stats LIMIT 1")
        res = c.fetchone()
        
        if res:
            return {"total_burned": float(res[0])}
        else:
            # 2. SI LA TABLE EST VIDE : On crée la ligne initiale à 0
            c.execute("INSERT INTO global_stats (total_burned) VALUES (0)")
            conn.commit()
            return {"total_burned": 0.0}
            
    except Exception as e:
        print(f"Erreur Burn Stats: {e}")
        return {"total_burned": 0.0}
    finally:
        c.close(); conn.close()


# --- 🔄 SWAP (WPT -> TOKEN) ---
@router.post("/swap")
async def swap_wpt_to_token(req: TradeRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier le solde WPT de l'user
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        user_wpt = c.fetchone()
        if not user_wpt or float(user_wpt[0]) < req.amount:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Insufficient WPT balance for Swap"})

        # 2. Prendre le prix actuel du Token
        c.execute("SELECT price, symbol FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        if not t: return JSONResponse(status_code=404, content={"ok": False, "error": "Token not found"})
        
        current_price = float(t[0])
        fee = req.amount * 0.01  # Taxe de 1%
        net_wpt = req.amount - fee
        qty_to_receive = net_wpt / current_price

        # 3. Mouvements financiers
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount, req.user_id))
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (fee, ADMIN_ID))

        # 4. Créditer les assets
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + %s
        """, (req.user_id, req.token_id, qty_to_receive, qty_to_receive))

        # 5. Faire Pumper le prix (Impact de marché du Swap)
        new_price = current_price * 1.005 # Petit pump de 0.5%
        c.execute("UPDATE community_tokens SET price = %s WHERE id = %s", (new_price, req.token_id))

        conn.commit()
        return {"ok": True, "swapped": qty_to_receive, "new_price": new_price}

    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

# --- 📋 PORTFOLIO (Version Nettoyée pour le JS) ---
@router.get("/portfolio/{uid}")
async def get_user_portfolio(uid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On ne sélectionne QUE les tokens où l'utilisateur a un solde > 0
        c.execute("""
            SELECT t.id, t.name, t.symbol, t.logo, a.amount, t.price, 
                   t.description, t.website_url, t.twitter_url 
            FROM user_community_assets a
            JOIN community_tokens t ON a.token_id = t.id
            WHERE a.user_id = %s AND a.amount > 0.00000001
            ORDER BY (a.amount * t.price) DESC
        """, (uid,))
        res = c.fetchall()
        return [{
            "id": r[0], "name": r[1], "symbol": r[2], "logo": r[3], 
            "amount": float(r[4]), "price": float(r[5]),
            "description": r[6], "website_url": r[7], "twitter_url": r[8]
        } for r in res]
    finally:
        c.close(); conn.close()
