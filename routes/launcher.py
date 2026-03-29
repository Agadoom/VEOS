from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import database
from pydantic import BaseModel
import time

# On définit le préfixe une seule fois ici
router = APIRouter(prefix="/api/launcher", tags=["Launcher"])

# Modèle de données unique pour les transactions
class TradeRequest(BaseModel):
    user_id: int
    token_id: int
    amount: float  # 'amount' sera utilisé pour le montant WPT (achat) ou QUANTITÉ (vente)

# --- DANS ROUTES/LAUNCHER.PY ---

@router.get("/list")
async def list_tokens():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT id, name, symbol, logo, banner, price, 
                   description, website_url, twitter_url 
            FROM community_tokens 
            ORDER BY id DESC
        """)
        res = c.fetchall()
        return [{
            "id": r[0], "name": r[1], "symbol": r[2], 
            "logo": r[3], "banner": r[4], "price": float(r[5]),
            "description": r[6] or "No description provided.",
            "website": r[7] or "",
            "twitter": r[8] or ""
        } for r in res]
    except Exception as e:
        print(f"❌ Erreur SQL List: {e}")
        return [] # Retourne une liste vide au lieu de faire planter le script
    finally:
        c.close(); conn.close()




@router.post("/buy")
async def buy_token(req: TradeRequest, request: Request): # On ajoute 'request: Request'
    print(f"📥 Buy Attempt: User {req.user_id} -> Token {req.token_id}")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérification du solde et infos du Token / Créateur
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        u = c.fetchone()
        if not u or float(u[0]) < req.amount:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Insufficient WPT Balance"})

        # On récupère le prix MAIS AUSSI le nom et le créateur
        c.execute("SELECT price, name, symbol, creator_id FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        if not t:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Token not found"})
            
        current_price, t_name, t_symbol, creator_id = float(t[0]), t[1], t[2], t[3]
        qty_to_receive = req.amount / current_price

        # 2. Exécution financière
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount, req.user_id))
        
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + %s
        """, (req.user_id, req.token_id, qty_to_receive, qty_to_receive))
        
        # Pump de 1%
        new_price = current_price * 1.01
        c.execute("UPDATE community_tokens SET price = %s WHERE id = %s", (new_price, req.token_id))

        # Historique
        c.execute("INSERT INTO token_price_history (token_id, price, timestamp) VALUES (%s, %s, %s)", 
                  (req.token_id, new_price, int(time.time())))
        
        conn.commit()

        # --- 🚀 NOTIFICATION PUMP ALERT ---
        # On récupère le bot stocké dans l'application FastAPI
        bot = request.app.state.bot 
        if creator_id and bot:
            try:
                # On prépare un message stylé
                msg = (
                    f"🚀 <b>PUMP ALERT!</b>\n\n"
                    f"Someone just bought <b>{t_name}</b> (${t_symbol})!\n"
                    f"New Price: <code>{new_price:.6f}</code> WPT\n\n"
                    f"Keep mining and sharing! 🔥"
                )
                # On utilise asyncio pour ne pas bloquer la réponse de l'API
                import asyncio
                asyncio.create_task(bot.send_message(chat_id=creator_id, text=msg, parse_mode="HTML"))
            except Exception as e:
                print(f"🔔 Notification Error: {e}")

        return {"ok": True, "received": qty_to_receive}

    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()


@router.post("/sell")
async def sell_token(req: TradeRequest):
    print(f"📉 Sell Attempt: User {req.user_id} -> Token {req.token_id} Amount: {req.amount}")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier si l'utilisateur possède bien ces tokens (req.amount est ici la quantité de tokens)
        c.execute("SELECT amount FROM user_community_assets WHERE user_id = %s AND token_id = %s", (req.user_id, req.token_id))
        res = c.fetchone()
        
        if not res or float(res[0]) < req.amount:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Not enough tokens to sell"})

        # 2. Récupérer le prix actuel
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        current_price = float(t[0])
        total_wpt_earned = req.amount * current_price

        # 3. Exécution : Retirer tokens -> Ajouter WPT -> Baisser le prix (Dump)
        c.execute("UPDATE user_community_assets SET amount = amount - %s WHERE user_id = %s AND token_id = %s", 
                  (req.amount, req.user_id, req.token_id))
        
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (total_wpt_earned, req.user_id))
        
        # Le prix baisse de 1% par vente
        new_price = current_price * 0.99
        c.execute("UPDATE community_tokens SET price = %s WHERE id = %s", (new_price, req.token_id))

        # Historique
        c.execute("INSERT INTO token_price_history (token_id, price, timestamp) VALUES (%s, %s, %s)", 
                  (req.token_id, new_price, int(time.time())))

        conn.commit()
        return {"ok": True, "received": total_wpt_earned} # 'received' ici est le WPT gagné
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

@router.get("/history/{tid}")
async def get_token_history(tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT price FROM token_price_history WHERE token_id = %s ORDER BY timestamp ASC LIMIT 50", (tid,))
        prices = [float(r[0]) for r in c.fetchall()]
        return prices if prices else [0.0001]
    finally:
        c.close(); conn.close()

@router.get("/stats/{tid}")
async def get_token_stats(tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On compte les holders + on ajoute 1 (le créateur)
        c.execute("SELECT COUNT(DISTINCT user_id) FROM user_community_assets WHERE token_id = %s", (tid,))
        holders = (c.fetchone()[0] or 0) + 1 
        
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (tid,))
        price = float(c.fetchone()[0] or 0.0001)
        
        # Market Cap basé sur 1 milliard de supply
        mcap = price * 1000000000
        
        return {"holders": holders, "mcap": round(mcap, 2)}
    finally:
        c.close(); conn.close()




class DeployRequest(BaseModel):
    user_id: int
    name: str
    symbol: str
    description: str = ""
    website_url: str = "" # AJOUTÉ
    twitter_url: str = "" # AJOUTÉ
    logo_b64: str
    banner_b64: str = ""

@router.post("/deploy")
async def deploy_token(req: DeployRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        fee = 5000.0
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        u = c.fetchone()
        if not u or float(u[0]) < fee:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Frais de 5000 WPT requis."})

        # Ajout des colonnes website_url et twitter_url dans l'INSERT
        c.execute("""
            INSERT INTO community_tokens (name, symbol, description, website_url, twitter_url, logo, banner, price, creator_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (req.name, req.symbol, req.description, req.website_url, req.twitter_url, req.logo_b64, req.banner_b64, 0.0001, req.user_id))
        
        new_token_id = c.fetchone()[0]
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (fee, req.user_id))
        c.execute("INSERT INTO token_price_history (token_id, price, timestamp) VALUES (%s, %s, %s)", 
                  (new_token_id, 0.0001, int(time.time())))
        conn.commit()
        return {"ok": True, "token_id": new_token_id}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

@router.get("/balance/{uid}/{tid}")
async def get_user_token_balance(uid: int, tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT amount FROM user_community_assets WHERE user_id = %s AND token_id = %s", (uid, tid))
        res = c.fetchone()
        balance = float(res[0]) if res else 0.0
        return {"ok": True, "balance": balance}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()



@router.get("/portfolio/{uid}")
async def get_user_portfolio(uid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On joint la table des assets avec celle des infos tokens
        c.execute("""
            SELECT t.name, t.symbol, t.logo, a.amount, t.price 
            FROM user_community_assets a
            JOIN community_tokens t ON a.token_id = t.id
            WHERE a.user_id = %s AND a.amount > 0
            ORDER BY (a.amount * t.price) DESC
        """, (uid,))
        res = c.fetchall()
        
        portfolio = []
        for r in res:
            portfolio.append({
                "name": r[0],
                "symbol": r[1],
                "logo": r[2],
                "amount": float(r[3]),
                "price": float(r[4])
            })
        return portfolio
    except Exception as e:
        print(f"Portfolio Error: {e}")
        return []
    finally:
        c.close(); conn.close()

@router.get("/listings")
async def get_listings():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On utilise les colonnes : id, name, symbol, logo, price
        c.execute("SELECT id, name, symbol, logo, price FROM community_tokens ORDER BY id DESC LIMIT 20")
        rows = c.fetchall()
        
        # On renvoie un format propre que le JS peut lire sans erreur
        return [
            {
                "id": r[0], 
                "name": r[1], 
                "symbol": r[2], 
                "logo": r[3],  # On garde le nom 'logo' pour être cohérent
                "price": float(r[4])
            } 
            for r in rows
        ]
    except Exception as e:
        print(f"❌ Erreur Listings: {e}")
        return []
    finally:
        c.close(); conn.close()


@router.get("/search")
async def search_tokens(q: str = ""):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Recherche insensible à la casse dans le nom ou le symbole
        query = f"%{q}%"
        c.execute("""
            SELECT id, name, symbol, price, creator_id 
            FROM community_tokens 
            WHERE name ILIKE %s OR symbol ILIKE %s 
            ORDER BY price DESC LIMIT 20
        """, (query, query))
        
        rows = c.fetchall()
        return [{"id": r[0], "name": r[1], "symbol": r[2], "price": r[3]} for r in rows]
    finally:
        c.close(); conn.close()



