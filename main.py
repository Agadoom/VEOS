import asyncio, uvicorn, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config, database, missions

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Initialisation DB
database.init_db_structure()

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    last_update = r[6] or now
    minutes_passed = (now - last_update) // 60
    
    # Calcul de l'énergie régénérée
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + (minutes_passed * config.REGEN_RATE))
    
    # Calcul du gain passif (ex: 0.01 par minute pour 100 assets stakés)
    staked = r[8] or 0
    offline_reward = 0
    if staked >= 100 and minutes_passed > 0:
        offline_reward = round((staked / 100) * 0.01 * minutes_passed, 2)
        # On met à jour la DB immédiatement pour éviter le double-claim
        conn = database.get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET p_genesis=p_genesis+%s, last_energy_update=%s, energy=%s WHERE user_id=%s", 
                  (offline_reward, now, current_e, uid))
        conn.commit()
        c.close(); conn.close()

    # On récupère les données fraîches pour le score total
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0) + offline_reward
    badge, next_goal, b_color = missions.get_badge_info(score)
    
    # On ajoute 'off_rw' dans le JSON pour que le JS puisse l'afficher
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "badge": badge,
        "score": round(score, 2), "off_rw": offline_reward, "min_off": minutes_passed,
        "top": [...], # Ton code leaderboard actuel
        # ... reste des données
    }


    
    now = int(time.time())
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - (r[6] or now)) // 60) * config.REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, next_goal, b_color = missions.get_badge_info(score)
    
    top_raw = database.get_leaderboard()
    top = [{"n": x[0], "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in top_raw]
    
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "badge": badge, "next_goal": next_goal, "badge_color": b_color,
        "top": top, "jackpot": round(database.get_total_network_score() * 0.1, 2), "score": round(score, 2),
        "multiplier": round(1.0 + ((r[8] or 0) / 100) * 0.1 + (score / 1000), 2),
        "streak": r[7] or 0, "staked": r[8] or 0, "pending_refs": max(0, (r[3] or 0) - (r[9] or 0))
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, staked_amount, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    now = int(time.time())
    current_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now - (res[1] or now)) // 60) * config.REGEN_RATE)
    
    if current_e >= 1:
        mult = 1.0 + ((res[2] or 0) / 100) * 0.1 + ((res[3] or 0) / 1000)
        c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=%s, last_energy_update=%s WHERE user_id=%s", (0.05*mult, current_e-1, now, uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

@app.post("/api/boost/energy")
async def api_boost_energy(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    success = await missions.process_boost_energy(uid, config.MAX_ENERGY)
    if success:
        return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False, "error": "Pas assez d'assets"})



@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E93; --green: #34C759; --purple: #A259FF; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; color: var(--gold); font-weight: bold; }
        
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .badge-tag { font-size: 9px; padding: 2px 6px; border-radius: 6px; background: #222; border: 1px solid #333; }

        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; border: 1px solid #333; }
        .energy-fill { background: linear-gradient(90deg, #FFD700, #FFA500); height: 100%; width: 0%; transition: width 0.5s; }
        
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; font-size: 11px; cursor: pointer; }
        .btn:active { transform: scale(0.95); }
        .btn:disabled { opacity: 0.5; }

        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 100; }
        .nav-item { font-size: 20px; opacity: 0.4; cursor: pointer; } 
        .nav-item.active { opacity: 1; color: var(--gold); }

        .rank-item { display: flex; justify-content: space-between; align-items: center; width: 100%; }


@keyframes energyFlash {
    0% { filter: brightness(1); shadow: none; }
    50% { filter: brightness(2); box-shadow: 0 0 20px var(--gold); }
    100% { filter: brightness(1); shadow: none; }
}
.energy-boost-anim {
    animation: energyFlash 0.8s ease-out;
}

#offline-modal {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.9); z-index: 2000;
    display: none; align-items: center; justify-content: center;
}
.modal-content {
    background: var(--card); border: 2px solid var(--gold);
    padding: 30px; border-radius: 30px; text-align: center; width: 80%;
}
.modal-content h2 { color: var(--gold); margin-top: 0; }
.reward-val { font-size: 32px; font-weight: 900; margin: 15px 0; color: #FFF; }


    </style>
</head>
<body>
    <div class="header-ticker">
        <span>👥 REFS: <span id="u-ref-top">0</span></span>
        <span>🔥 JACKPOT: <span id="jack-val">0</span></span>
    </div>
    
    <div class="profile-bar">
        <div>
            <div id="u-name" style="font-weight:700; font-size:14px;">...</div>
            <div id="u-badge" class="badge-tag">...</div>
        </div>
        <button class="btn" style="background:var(--gold)" onclick="share()">🚀 INVITE</button>
    </div>

<div id="offline-modal">
    <div class="modal-content">
        <div style="font-size: 40px;">😴</div>
        <h2>Welcome Back!</h2>
        <p style="color:var(--text); font-size: 12px;">Your nodes were mining while you were away</p>
        <div class="reward-val">+ <span id="rw-amt">0</span> WPT</div>
        <button class="btn" style="background:var(--gold); width:100%; padding:15px;" onclick="closeModal()">COLLECT</button>
    </div>
</div>


    <div id="p-mine">
        <div class="balance">
            <small style="color:var(--text)">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:45px; margin:8px 0;">0.00</h1>
            <div id="u-mult" style="font-size:10px; color:var(--green)">⚡ Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine(event, 'genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine(event, 'unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine(event, 'veo')" style="background:var(--purple); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">$WPT PILLARS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Unity Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Veo AI Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Genesis Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div id="p-leader" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">RANKING</h3>
        <div id="rank-list"></div>
    </div>

    <div id="p-mission" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">STAKING & NODES</h3>
        <div class="card">
            <div><b>Active Staking</b><br><small>Streak: <span id="u-streak">0</span> Days</small></div>
            <div id="staked-val" style="color:var(--gold)">0 Staked</div>
        </div>
        <div class="card">
            <div><b>Lock 100 Assets</b><br><small>+0.1x Multiplier</small></div>
            <button class="btn" id="stake-btn" onclick="alert('Insufficient balance')">LOCK</button>
        </div>
        <div class="card">
            <div><b>Community Hub</b></div>
            <button class="btn" onclick="tg.openLink('https://t.me/owpc_co')">JOIN</button>
        </div>
<div class="card">
    <div><b>Energy Drink ⚡</b><br><small>Cost: 50 Assets</small></div>
    <button class="btn" id="boost-btn" onclick="buyBoost()">BUY</button>
</div>



    </div>


    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        
        async function refresh() {
    try {
        // 1. Appel à l'API pour récupérer les données utilisateur
        const response = await fetch(`/api/user/${uid}`);
        if (!response.ok) return;
        
        const data = await response.json();
        if (!data.name) return;

        // 2. Gestion du Pop-up de Bienvenue (Gains hors-ligne)
        // On vérifie si off_rw existe et est supérieur à 0
        if (data.off_rw && data.off_rw > 0) {
            document.getElementById('rw-amt').innerText = data.off_rw.toFixed(2);
            document.getElementById('offline-modal').style.display = 'flex';
            
            // Petit retour haptique pour signaler le gain
            if (window.Telegram && Telegram.WebApp.HapticFeedback) {
                Telegram.WebApp.HapticFeedback.notificationOccurred('success');
            }
        }

        // 3. Mise à jour des informations de profil
        document.getElementById('u-name').innerText = data.name;
        document.getElementById('u-badge').innerText = data.badge;
        document.getElementById('u-ref-top').innerText = data.rc; // Nombre de parrainages
        
        // 4. Mise à jour des soldes (Tokens individuels)
        document.getElementById('gv').innerText = data.g.toFixed(2); // Genesis
        document.getElementById('uv').innerText = data.u.toFixed(2); // Unity
        document.getElementById('vv').innerText = data.v.toFixed(2); // Veo AI
        
        // 5. Score Total et Multiplicateur
        document.getElementById('tot').innerText = data.score.toFixed(2);
        document.getElementById('u-mult').innerText = `⚡ Multiplier: x${data.multiplier.toFixed(2)}`;
        
        // 6. Barre d'énergie et Texte
        const energyPercent = (data.energy / data.max_energy) * 100;
        document.getElementById('e-bar').style.width = energyPercent + "%";
        document.getElementById('e-text').innerText = `⚡ ${data.energy} / ${data.max_energy}`;
        
        // Couleur de la barre d'énergie (devient rouge si basse)
        if (data.energy < 10) {
            document.getElementById('e-bar').style.background = "linear-gradient(90deg, #ff4b2b, #ff416c)";
        } else {
            document.getElementById('e-bar').style.background = "linear-gradient(90deg, #FFD700, #FFA500)";
        }

        // 7. Jackpot Global
        if (document.getElementById('jack-val')) {
            document.getElementById('jack-val').innerText = data.jackpot.toFixed(2);
        }

        // 8. Section Mission & Staking
        if (document.getElementById('u-streak')) {
            document.getElementById('u-streak').innerText = data.streak;
        }
        if (document.getElementById('staked-val')) {
            document.getElementById('staked-val').innerText = data.staked.toFixed(0) + " Staked";
        }

        // 9. Mise à jour du Leaderboard (Ranking)
        if (data.top && data.top.length > 0) {
            let rankHTML = "";
            data.top.forEach((user, index) => {
                // On met en gras si c'est l'utilisateur actuel (optionnel)
                const isMe = user.n === data.name ? "border: 1px solid var(--gold);" : "";
                
                rankHTML += `
                    <div class="card" style="${isMe}">
                        <div class="rank-item">
                            <span>${index + 1}. ${user.n} <small style="font-size:8px; opacity:0.6;">${user.b}</small></span>
                            <b style="color:var(--gold)">${user.p.toFixed(2)}</b>
                        </div>
                    </div>`;
            });
            document.getElementById('rank-list').innerHTML = rankHTML;
        }

    } catch (error) {
        console.error("Erreur lors du refresh:", error);
    }
}

// Fonction pour fermer le pop-up
function closeModal() {
    document.getElementById('offline-modal').style.display = 'none';
    if (window.Telegram && Telegram.WebApp.HapticFeedback) {
        Telegram.WebApp.HapticFeedback.impactOccurred('light');
    }
}


        function mine(e, t) {
    // Création du petit texte flottant
    const rect = e.target.getBoundingClientRect();
    const plus = document.createElement('div');
    plus.innerText = '+0.05';
    plus.style.position = 'absolute';
    plus.style.left = (e.clientX || rect.left + 20) + 'px';
    plus.style.top = (e.clientY || rect.top) + 'px';
    plus.style.color = 'var(--gold)';
    plus.style.fontWeight = 'bold';
    plus.style.pointerEvents = 'none';
    plus.style.zIndex = '1000';
    plus.animate([
        { transform: 'translateY(0)', opacity: 1 },
        { transform: 'translateY(-50px)', opacity: 0 }
    ], { duration: 600, easing: 'ease-out' });
    
    document.body.appendChild(plus);
    setTimeout(() => plus.remove(), 600);

    // Envoi à l'API
    fetch('/api/mine', {
        method:'POST', 
        headers:{'Content-Type':'application/json'}, 
        body:JSON.stringify({user_id:uid, token:t})
    });
    
    refresh(); 
    tg.HapticFeedback.impactOccurred('light');
}





        function show(p) { 
            ['mine','pillars','leader','mission'].forEach(id=>{
                document.getElementById('p-'+id).style.display=(id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active',id===p);
            });
        }
async function buyBoost() {
    const btn = document.getElementById('boost-btn');
    btn.disabled = true; // Évite le double-clic
    
    try {
        const res = await fetch('/api/boost/energy', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: uid})
        });

        if(res.ok) {
            // Effet visuel
            const bar = document.getElementById('e-bar');
            bar.classList.add('energy-boost-anim');
            
            // Simulation de remplissage fluide côté client
            bar.style.transition = "width 1s cubic-bezier(0.175, 0.885, 0.32, 1.275)";
            bar.style.width = "100%";
            
            setTimeout(() => {
                bar.classList.remove('energy-boost-anim');
                bar.style.transition = "width 0.5s"; // Retour à la normale
                refresh(); // On synchronise avec la DB
                tg.HapticFeedback.notificationOccurred('success');
            }, 1000);
            
        } else {
            tg.HapticFeedback.notificationOccurred('error');
            alert("❌ Not enough assets (Need 50)");
        }
    } catch (err) {
        console.error(err);
    } finally {
        btn.disabled = false;
    }
}


        function share() { tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}&text=🚀 Join my mining node on OWPC!`); }

        refresh(); setInterval(refresh, 8000); tg.expand();
    </script>
</body>
</html>
"""
async def notification_loop(bot_app):
    """Vérifie toutes les 5 minutes qui a son énergie pleine"""
    while True:
        await asyncio.sleep(300) # Attendre 5 minutes
        now = int(time.time())
        conn = database.get_db_conn()
        if not conn: continue
        c = conn.cursor()
        
        # On cherche les users dont l'énergie devrait être pleine (basé sur le temps passé)
        # Formule : temps_nécessaire = (MAX - énergie_actuelle) / REGEN_RATE
        c.execute("SELECT user_id, energy, last_energy_update FROM users")
        users = list(c.fetchall()) # On fait une liste pour fermer la connexion vite
        
        for uid, energy, last_up in users:
            minutes_passed = (now - (last_up or now)) // 60
            if energy < config.MAX_ENERGY and (energy + minutes_passed) >= config.MAX_ENERGY:
                try:
                    await bot_app.bot.send_message(
                        chat_id=uid, 
                        text="⚡ **Full Energy!** Your mining node is recharged. Come back and collect your assets! 🚀"
                    )
                    # On met l'énergie à 100 en DB pour ne pas renvoyer la notification en boucle
                    c.execute("UPDATE users SET energy=%s, last_energy_update=%s WHERE user_id=%s", 
                              (config.MAX_ENERGY, now, uid))
                except:
                    pass # L'utilisateur a peut-être bloqué le bot
        
        conn.commit()
        c.close(); conn.close()

# Dans ta fonction main(), lance la boucle :
async def main():
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    # ... tes handlers ...
    
    # LANCEMENT DE LA BOUCLE DE NOTIFICATION
    asyncio.create_task(notification_loop(bot_app))
    
    # ... reste du main ...
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    await missions.register_user(uid, name, ref_id)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN OWPC HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text("✨ Welcome to OWPC DePIN Hub.", reply_markup=kb)



async def main():
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_cmd))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")).serve()

if __name__ == "__main__":
    asyncio.run(main())
