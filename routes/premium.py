from datetime import datetime, timedelta

@router.post("/buy-premium")
async def buy_premium(user_id: int, pack_id: str):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        now = datetime.now()
        
        # --- PACK 1: LEGEND (1000 Stars -> 300k WPT) ---
        if pack_id == "pack_legend":
            amount_wpt = 300000
            c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (amount_wpt, user_id))
            msg = f"💎 LEGENDARY! +{amount_wpt} WPT added to your wallet."

        # --- PACK 2: TURBO RECHARGE (99 Stars -> 3x Speed for 24h) ---
        elif pack_id == "turbo_boost":
            expiry = now + timedelta(hours=24)
            # On stocke la date d'expiration dans une nouvelle colonne 'turbo_until'
            c.execute("UPDATE users SET turbo_until = %s WHERE user_id = %s", (expiry, user_id))
            msg = "⚡ TURBO ACTIVATED! Your energy refills 3x faster for 24h."

        # --- PACK 3: AUTO-MINER (150 Stars -> 7 Days) ---
        elif pack_id == "auto_miner":
            expiry = now + timedelta(days=7)
            c.execute("UPDATE users SET miner_until = %s WHERE user_id = %s", (expiry, user_id))
            msg = "🤖 AUTO-MINER ONLINE! Collecting WPT while you sleep for 7 days."

        else:
            return {"ok": False, "error": "Unknown Pack"}

        conn.commit()
        return {"ok": True, "message": msg}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()
