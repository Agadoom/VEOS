import asyncio, uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from telegram.ext import ApplicationBuilder

# Importation de tes modules
import config
from routes import mine, launcher, user

app = FastAPI()

# Autoriser le Cross-Origin
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- INDEXATION DES MODULES ---
app.include_router(mine.router)     # Connecte /api/mine
app.include_router(launcher.router) # Connecte /api/launcher
app.include_router(user.router)     # Connecte /api/user

@app.get("/", response_class=HTMLResponse)
async def index():
    # Ton gros bloc HTML/JS ici (ou lis-le depuis un fichier index.html)
    with open("index.html", "r") as f:
        return f.read()

async def main():
    # Setup du Bot
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    # Ajoute tes handlers de paiement ici...
    
    await bot_app.initialize()
    await bot_app.start()
    
    # Lancement du serveur Web
    conf = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    server = uvicorn.Server(conf)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
