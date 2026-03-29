from datetime import datetime, timedelta

@router.get("/buy-premium")
async def buy_premium(user_id: int, pack_id: str):
    print(f"💰 Premium Buy: User {user_id} -> {pack_id}")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        msg = ""
        now = datetime.now()

        if pack_id == "pack_legend":
            amount = 300000.0
            c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (amount, user_id))
            msg = "300,000 WPT added! You are now a Legend. 💎"

        elif pack_id == "turbo_boost":
            # On ajoute 24h de boost (Assure-toi d'avoir la colonne turbo_until dans ta table users)
            expiry = (now + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            c.execute("UPDATE users SET turbo_until = %s WHERE user_id = %s", (expiry, user_id))
            msg = "Turbo activated! Energy refills 3x faster for 24h. ⚡"

        else:
            return {"ok": False, "error": "Unknown Pack ID"}

        conn.commit()
        return {"ok": True, "message": msg}
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error Buy: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()
