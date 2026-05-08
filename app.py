import os

from flask import Flask, render_template, jsonify, request
import requests
import sqlite3
from db import get_connection, init_db # Importamos tu conector


app = Flask(__name__)
init_db()  # Inicializamos la base de datos
# --- CONFIGURACIÓN ---
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
REGION_ROOT = "americas"
PLATFORM_ID = "la2"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    return jsonify({"status": "online", "message": "Servidor de Agustín listo"})

@app.route('/api/summoner')
def get_summoner():
    # ... (Mantenemos la lógica de búsqueda de PUUID igual)
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
    headers = {"X-Riot-Token": RIOT_API_KEY}
    url_ids = f"https://{REGION_ROOT}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=5"
    resp_ids = requests.get(url_ids, headers=headers)
    
    match_ids = resp_ids.json()
    matches_data = []
    
    conn = get_connection()
    cursor = conn.cursor()

    for match_id in match_ids:
        # 1. Intentar leer de la base de datos local
        cursor.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,))
        row = cursor.fetchone()
        
        if row:
            # Si existe en DB, lo añadimos a la lista y saltamos a la siguiente
            matches_data.append(dict(row))
            continue

        # 2. Si no existe, pedir a Riot
        url_match = f"https://{REGION_ROOT}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        resp_match = requests.get(url_match, headers=headers)
        
        if resp_match.status_code == 200:
            data = resp_match.json()
            
            # --- FILTRO DE REMAKE ---
            # Según tu documentación, gameDuration suele estar en segundos. 
            # Si es menor a 190 segundos (aprox 3 min), es un remake o partida cancelada.
            duration_raw = data['info']['gameDuration']
            if duration_raw < 190:
                print(f"Partida {match_id} ignorada por ser Remake/Corta.")
                continue 
            
            game_duration_min = duration_raw / 60
            
            p = next(p for p in data['info']['participants'] if p['puuid'] == puuid)
            
            total_cs = p.get('totalMinionsKilled', 0) + p.get('neutralMinionsKilled', 0)
            cs_per_min = round(total_cs / game_duration_min, 1) if game_duration_min > 0 else 0
            
            # Datos extraídos
            lane = p.get('teamPosition', 'NONE')
            dmg_obj = p.get('damageDealtToObjectives', 0)
            dmg_turrets = p.get('damageDealtToTurrets', 0)
            total_damage = p.get('totalDamageDealtToChampions', 0)
            
            match_entry = {
                "match_id": match_id, "puuid": puuid, "champion": p['championName'], "lane": lane,
                "kills": p['kills'], "deaths": p['deaths'], "assists": p['assists'], "win": p['win'],
                "game_mode": data['info']['gameMode'], "total_cs": total_cs, "cs_per_min": cs_per_min,
                "dmg_objectives": dmg_obj, "dmg_turrets": dmg_turrets, "total_damage": total_damage,
                "game_duration": game_duration_min,
                "timestamp": data['info']['gameStartTimestamp']
            }
            
            # --- CORRECCIÓN SQL: Agregamos game_duration (ahora son 16 columnas) ---
            cursor.execute('''
                INSERT INTO matches (
                    match_id, puuid, champion, lane, kills, deaths, assists, win, 
                    game_mode, total_cs, cs_per_min, dmg_objectives, dmg_turrets, 
                    total_damage, game_duration, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                match_id, puuid, p['championName'], lane, p['kills'], p['deaths'], p['assists'], p['win'], 
                data['info']['gameMode'], total_cs, cs_per_min, dmg_obj, dmg_turrets, 
                total_damage, game_duration_min, data['info']['gameStartTimestamp']
            ))
            
            matches_data.append(match_entry)

    conn.commit()
    conn.close()
    return jsonify(matches_data)

@app.route('/api/timeline/<match_id>/<puuid>')
def get_match_timeline(match_id, puuid):
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Intentar leer timeline de la DB
    cursor.execute("SELECT * FROM match_timeline WHERE match_id = ? ORDER BY minute ASC", (match_id,))
    rows = cursor.fetchall()
    
    if rows:
        conn.close()
        return jsonify([dict(row) for row in rows])

    # 2. Si no existe, pedir a Riot
    headers = {"X-Riot-Token": RIOT_API_KEY}
    url_timeline = f"https://{REGION_ROOT}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{match_id}/timeline" # Nota: corregir URL a match-v5
    url_timeline = f"https://{REGION_ROOT}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
    
    resp = requests.get(url_timeline, headers=headers)
    timeline = resp.json()
    
    participant_id = next(p['participantId'] for p in timeline['info']['participants'] if p['puuid'] == puuid)
    target_minutes = [3, 5, 8, 11, 15, 20, 25, 30, 35, 40]
    results = []
    kills, deaths, assists = 0, 0, 0
    
    for m, frame in enumerate(timeline['info']['frames']):
        for event in frame['events']:
            if event['type'] == 'CHAMPION_KILL':
                if event.get('killerId') == participant_id: kills += 1
                elif event.get('victimId') == participant_id: deaths += 1
                elif participant_id in event.get('assistingParticipantIds', []): assists += 1
        
        if m in target_minutes:
            p_frame = frame['participantFrames'][str(participant_id)]
            cs = p_frame.get('minionsKilled', 0) + p_frame.get('jungleMinionsKilled', 0)
            cs_min = round(cs / m, 1) if m > 0 else 0
            damage = p_frame.get('damageStats', {}).get('totalDamageDoneToChampions', 0)
            
            # Guardar en DB
            cursor.execute('''
                INSERT OR IGNORE INTO match_timeline (match_id, minute, cs, cs_min, damage, kills, deaths, assists)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (match_id, m, cs, cs_min, damage, kills, deaths, assists))
            
            results.append({"minute": m, "cs": cs, "cs_min": cs_min, "damage": damage, "kills": kills, "deaths": deaths, "assists": assists})
            
    conn.commit()
    conn.close()
    return jsonify(results)


@app.route('/api/analytics')
def get_champion_analytics():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. DATA PARA CS: Promedios minuto a minuto (Mantenemos la estructura)
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

    # 2. DATA PARA DAÑO: Historial por partida (Usando las NUEVAS columnas exactas)
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

    # Procesamos CS (Evolución intra-partida)
    for row in rows_intra:
        key = f"{row['champion']}-{row['lane']}"
        if key not in champions_data:
            champions_data[key] = {"intra_match": [], "macro_history": []}
        champions_data[key]["intra_match"].append(dict(row))

    # Procesamos Daño (Historial macro de partidas)
    for row in rows_macro:
        key = f"{row['champion']}-{row['lane']}"
        if key in champions_data:
            # Validación defensiva contra valores NULL (None)
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