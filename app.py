import os
from flask import Flask, render_template, jsonify, request
import requests
import sqlite3
from db import get_connection, init_db

app = Flask(__name__)
init_db()

# --- CONFIGURACIÓN ---
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
REGION_ROOT = "americas"
PLATFORM_ID = "la2"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    return jsonify({"status": "online", "message": "Servidor de Agustín listo (Modo Read-Only)"})

@app.route('/api/summoner')
def get_summoner():
    # Mantenemos esta única llamada ligera para obtener el PUUID y el Nivel dinámicamente
    game_name = "agussgarciaa"
    tag_line = "LAS"
    url = f"https://{REGION_ROOT}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    res = requests.get(url, headers=headers)
    if res.status_code != 200: return jsonify({"error": "Riot Error"}), res.status_code
    
    user_data = res.json()
    url_sum = f"https://{PLATFORM_ID}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{user_data['puuid']}"
    res_sum = requests.get(url_sum, headers=headers)
    
    return jsonify({
        "riot_id": f"{user_data['gameName']}#{user_data['tagLine']}",
        "puuid": user_data['puuid'],
        "summoner_level": res_sum.json().get("summonerLevel")
    })

@app.route('/api/matches/<puuid>')
def get_matches(puuid):
    """
    MODO READ-ONLY: Ya no consulta a Riot API.
    Solo extrae las partidas que el script ETL (riot_etl.py) guardó en SQLite.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Extraemos las últimas 10 partidas guardadas en la base de datos
    cursor.execute("SELECT * FROM matches WHERE puuid = ? ORDER BY timestamp DESC LIMIT 10", (puuid,))
    rows = cursor.fetchall()
    conn.close()
    
    matches_data = [dict(row) for row in rows]
    return jsonify(matches_data)

@app.route('/api/timeline/<match_id>/<puuid>')
def get_match_timeline(match_id, puuid):
    """
    MODO READ-ONLY: Ya no consulta a Riot API.
    Solo extrae el timeline que el script ETL (riot_etl.py) guardó en SQLite.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM match_timeline WHERE match_id = ? ORDER BY minute ASC", (match_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])

@app.route('/api/analytics')
def get_champion_analytics():
    """
    MODO READ-ONLY: Calcula los promedios y DPM puramente desde la base de datos local.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. DATA PARA CS: Promedios minuto a minuto
    query_intra = '''
        SELECT m.champion, m.lane, mt.minute, 
               ROUND(AVG(mt.cs), 1) as avg_cs
        FROM match_timeline mt
        JOIN matches m ON mt.match_id = m.match_id
        GROUP BY m.champion, m.lane, mt.minute 
        ORDER BY m.champion, m.lane, mt.minute ASC
    '''
    cursor.execute(query_intra)
    rows_intra = cursor.fetchall()

    # 2. DATA PARA DAÑO: Historial por partida 
    query_macro = '''
        SELECT match_id, champion, lane, timestamp,
               game_duration,
               total_damage
        FROM matches
        ORDER BY timestamp ASC
    '''
    cursor.execute(query_macro)
    rows_macro = cursor.fetchall()
    conn.close()
    
    if not rows_intra or not rows_macro:
        return jsonify({"error": "No hay datos suficientes en ambas tablas"}), 404
        
    champions_data = {}

    # Procesamos CS
    for row in rows_intra:
        key = f"{row['champion']}-{row['lane']}"
        if key not in champions_data:
            champions_data[key] = {"intra_match": [], "macro_history": []}
        champions_data[key]["intra_match"].append(dict(row))

    # Procesamos Daño
    for row in rows_macro:
        key = f"{row['champion']}-{row['lane']}"
        if key in champions_data:
            raw_duration = row['game_duration']
            duration = raw_duration if raw_duration is not None and raw_duration > 0 else 1
            
            raw_damage = row['total_damage']
            total_dmg = raw_damage if raw_damage is not None else 0

            champions_data[key]["macro_history"].append({
                "match_id": row['match_id'],
                "dpm": round(total_dmg / duration, 0)
            })
        
    return jsonify(champions_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)