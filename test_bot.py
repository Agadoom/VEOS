import os
import psycopg2
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)

# On récupère la variable DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

# DEBUG : Apparaît dans les logs Railway
print(f"--- DEBUG DATABASE ---")
if DATABASE_URL:
    print(f"URL Trouvée: Oui (Début: {DATABASE_URL[:15]}...)")
else:
    print("URL Trouvée: NON (Vérifiez vos variables d'environnement Railway)")

def get_db_conn():
    """Établit une connexion à la base de données PostgreSQL."""
    url = os.getenv("DATABASE_URL")
    if not url:
        logging.error("DATABASE_URL manquante.")
        return None
    try:
        # sslmode='require' est nécessaire pour Railway
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        logging.error(f"Erreur PG Connection: {e}")
        return None

def init_db():
    """Initialise la base de données et applique les migrations de colonnes."""
    conn = get_db_conn()
    if not conn:
        logging.error("Échec initialisation : DATABASE_URL non accessible.")
        return
    try:
        c = conn.cursor()
        
        # 1. Création de la table USERS (structure complète par défaut)
        # On inclut wallet_address, staked_amount, streak et last_streak_date pour plus de sécurité
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id BIGINT PRIMARY KEY, 
                      name TEXT, 
                      p_genesis REAL DEFAULT 0, 
                      p_unity REAL DEFAULT 0, 
                      p_veo REAL DEFAULT 0, 
                      ref_count INTEGER DEFAULT 0,
                      last_daily INTEGER DEFAULT 0,
                      total_clicks INTEGER DEFAULT 0,
                      referred_by BIGINT,
                      energy INTEGER DEFAULT 100,
                      last_energy_update INTEGER,
                      staked_amount DOUBLE PRECISION DEFAULT 0,
                      streak INTEGER DEFAULT 0,
                      last_streak_date TEXT,
                      wallet_address TEXT)''')
        
        # 2. MIGRATIONS : Ajout des colonnes au cas où la table existe déjà sans elles
        # On utilise ALTER TABLE ... ADD COLUMN IF NOT EXISTS (PostgreSQL 9.6+)
        migrations = [
            ("ref_count", "INTEGER DEFAULT 0"),
            ("last_daily", "INTEGER DEFAULT 0"),
            ("total_clicks", "INTEGER DEFAULT 0"),
            ("referred_by", "BIGINT"),
            ("energy", "INTEGER DEFAULT 100"),
            ("last_energy_update", "INTEGER"),
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("streak", "INTEGER DEFAULT 0"),
            ("last_streak_date", "TEXT"),
            ("wallet_address", "TEXT") # <-- NOUVELLE COLONNE WALLET
        ]

        for col, dtype in migrations:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {dtype}")
            except Exception as e:
                logging.warning(f"Note migration : {col} - {e}")

        # 3. Création de la table LOGS (pour historique si besoin)
        c.execute('''CREATE TABLE IF NOT EXISTS logs 
                     (id SERIAL PRIMARY KEY, 
                      user_id BIGINT, 
                      token TEXT, 
                      amount REAL, 
                      timestamp INTEGER)''')
        
        conn.commit()
        logging.info("✅ Base PostgreSQL synchronisée : Wallet, Staking et Parrainage OK.")
        
    except Exception as e:
        logging.error(f"Erreur init_db: {e}")
    finally:
        if conn:
            c.close()
            conn.close()

if __name__ == "__main__":
    # Permet de tester l'initialisation en lançant le script directement
    init_db()
