# launcher.py
import database

def save_token_intent(uid, name, symbol, twitter, logo_data, banner_data):
    """Enregistre l'intention de création de token dans la DB"""
    try:
        conn = database.get_db_conn()
        c = conn.cursor()
        # On déduit les 500 WPT ici si on veut
        c.execute("UPDATE users SET p_genesis = p_genesis - 500 WHERE user_id = %s AND p_genesis >= 500", (uid,))
        # On pourrait insérer dans une table community_tokens ici
        conn.commit()
        c.close()
        conn.close()
        return True
    except:
        return False
