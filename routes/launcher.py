from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import database
import time
import asyncio

router = APIRouter(prefix="/api/launcher", tags=["Launcher"])

# --- CONFIGURATION ---
ADMIN_ID = 1414016840 

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

# --- 📋 LISTE DES TOKENS ---
@router.get("/list")
async def list_tokens(q: str = None, filter: str = "new", uid: int = 0):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        query = "SELECT id, name, symbol, logo, banner, price, description, website_url, twitter_url FROM community_tokens"
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
        query += " ORDER BY id DESC LIMIT 50"
        c.execute(query, tuple(params))
        res = c.fetchall()
        return [{"id": r[0], "name": r[1], "symbol": r[2], "logo": r[3], "banner": r[4], "price": float(r[5] or 0.0001), "description": r[6], "website_url": r[7], "twitter_url": r[8]} for r in res]
    finally:
        c.close(); conn.close()

# --- 🔄 SWAP (WPT -> TOKEN) ---
@router.post("/swap")
async def swap_wpt_to_token(req: TradeRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        u = c.fetchone()
        if not u or float(u[0]) < req.amount:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Insufficient WPT balance"})

        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        if not t: return JSONResponse(status_code=404, content={"ok": False, "error": "Token not found"})
        
        current_price = float(t[0])
        fee = req.amount * 0.01
        net_wpt = req.amount - fee
        qty = net_wpt / current_price

        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount, req.user_id))
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (fee, ADMIN_ID))
        
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + EXCLUDED.amount
        """, (req.user_id, req.token_id, qty))

        c.execute("UPDATE community_tokens SET price = price * 1.005 WHERE id = %s", (req.token_id,))
        conn.commit()
        return {"ok": True, "received": qty}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

# --- 🏗️ DEPLOY ---
@router.post("/deploy")
async def deploy_token(req: DeployRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        if float(c.fetchone()[0]) < 5000:
            return JSONResponse(status_code=400, content={"ok": False, "error": "5000 WPT required"})
        
        c.execute("""
            INSERT INTO community_tokens (name, symbol, description, website_url, twitter_url, logo, banner, price, creator_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0001, %s) RETURNING id
        """, (req.name, req.symbol, req.description, req.website_url, req.twitter_url, req.logo_b64, req.banner_b64, req.user_id))
        tid = c.fetchone()[0]
        c.execute("UPDATE users SET p_genesis = p_genesis - 5000 WHERE user_id = %s", (req.user_id,))
        conn.commit()
        return {"ok": True, "token_id": tid}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

# --- 📋 PORTFOLIO (Version Unique et Propre) ---
@router.get("/portfolio/{uid}")
async def get_user_portfolio(uid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On récupère la quantité possédée par l'user (a.amount) 
        # ET le prix actuel du token (t.price)
        c.execute("""
            SELECT t.id, t.name, t.symbol, t.logo, a.amount, t.price, t.description 
            FROM user_community_assets a
            JOIN community_tokens t ON a.token_id = t.id
            WHERE a.user_id = %s AND a.amount > 0
        """, (uid,))
        res = c.fetchall()
        return [{
            "id": r[0], "name": r[1], "symbol": r[2], "logo": r[3], 
            "amount": float(r[4]), "price": float(r[5]), "description": r[6]
        } for r in res]
    finally:
        c.close(); conn.close()


# --- 🔥 BURN & STATS ---
@router.get("/total-burned")
async def get_total_burned():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT total_burned FROM global_stats LIMIT 1")
        res = c.fetchone()
        return {"total_burned": float(res[0]) if res else 0.0}
    finally:
        c.close(); conn.close()

@router.get("/stats/{tid}")
async def get_token_stats(tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On compte les holders et la somme totale des tokens possédés
        c.execute("SELECT COUNT(user_id), SUM(amount) FROM user_community_assets WHERE token_id = %s", (tid,))
        res = c.fetchone()
        holders = res[0] or 0
        circulating_supply = float(res[1] or 0)
        
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (tid,))
        price = float(c.fetchone()[0] or 0.0001)
        
        # MCAP Réel = Ce qui appartient aux gens * le prix
        real_mcap = circulating_supply * price
        
        return {
            "holders": holders, 
            "mcap": round(real_mcap, 2),
            "supply": circulating_supply
        }
    finally:
        c.close(); conn.close()



@router.post("/sell")
async def sell_token(req: TradeRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier si l'utilisateur possède vraiment les tokens
        c.execute("SELECT amount FROM user_community_assets WHERE user_id = %s AND token_id = %s", (req.user_id, req.token_id))
        res = c.fetchone()
        
        if not res or float(res[0]) < req.amount:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Insufficient token balance"})

        # 2. Récupérer le prix actuel
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t_res = c.fetchone()
        if not t_res:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Token not found"})
            
        current_price = float(t_res[0])
        gross_wpt = req.amount * current_price
        
        # 3. Taxe 1%
        fee = gross_wpt * 0.01
        net_wpt = gross_wpt - fee

        # 4. EXÉCUTION DES MOUVEMENTS
        # Retrait des assets
        c.execute("UPDATE user_community_assets SET amount = amount - %s WHERE user_id = %s AND token_id = %s", 
                  (req.amount, req.user_id, req.token_id))
        
        # Crédit WPT (Genesis) à l'utilisateur et taxe à l'Admin
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (net_wpt, req.user_id))
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (fee, ADMIN_ID))
        
        # Impact sur le prix (Baisse de 1% par vente pour simuler le marché)
        new_price = current_price * 0.99
        c.execute("UPDATE community_tokens SET price = %s WHERE id = %s", (new_price, req.token_id))

        conn.commit()
        return {"ok": True, "received": net_wpt}

    except Exception as e:
        conn.rollback()
        print(f"❌ SELL CRASH: {e}") # Regarde ça dans tes logs Railway !
        return JSONResponse(status_code=500, content={"ok": False, "error": "Internal Server Error"})
    finally:
        c.close(); conn.close()




@router.get("/market")
async def get_market(filter: str = "new", search: str = ""):
    try:
        query = {}
        if search:
            query["name"] = {"$regex": search, "$options": "i"}
            
        # On récupère les tokens. 
        # Si filter == 'my', il faudrait ajouter une condition sur l'user_id
        tokens = list(db.tokens.find(query).sort("created_at", -1))
        
        for t in tokens:
            t["_id"] = str(t["_id"]) # Convertit l'ID MongoDB en texte pour le JS
            
        return tokens # Doit retourner une liste [{}, {}]
    except Exception as e:
        print(f"Erreur DB: {e}")
        return []


