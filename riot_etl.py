import os
import requests
import sqlite3
from db import get_connection, init_db

def run_extraction():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    RIOT_API_KEY = os.getenv("RIOT_API_KEY")
    if not RIOT_API_KEY:
        raise ValueError("RIOT_API_KEY no detectada en las variables de entorno.")

    headers = {"X-Riot-Token": RIOT_API_KEY}
    REGION_ROOT = "americas"
    
    # Configuración estática del usuario objetivo
    GAME_NAME = "agussgarciaa"
    TAG_LINE = "LAS"
    
    # 1. Obtener PUUID
    url_account = f"https://{REGION_ROOT}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{GAME_NAME}/{TAG_LINE}"
    res_account = requests.get(url_account, headers=headers)
    if res_account.status_code != 200:
        print(f"Error fetching account: {res_account.status_code}")
        return
    puuid = res_account.json()['puuid']

    # 2. Obtener historial de partidas (últimas 10 para barrido diario)
    url_ids = f"https://{REGION_ROOT}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=10"
    resp_ids = requests.get(url_ids, headers=headers)
    match_ids = resp_ids.json()

    # 3. Procesar partidas
    for match_id in match_ids:
        cursor.execute("SELECT game_duration FROM matches WHERE match_id = ?", (match_id,))
        row = cursor.fetchone()
        
        if row:
            if row['game_duration'] is None:
                cursor.execute("DELETE FROM matches WHERE match_id = ?", (match_id,))
                cursor.execute("DELETE FROM match_timeline WHERE match_id = ?", (match_id,))
                conn.commit()
            else:
                continue # Partida existente e íntegra

        # Extracción Match-V5
        url_match = f"https://{REGION_ROOT}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        resp_match = requests.get(url_match, headers=headers)
        
        if resp_match.status_code == 200:
            data = resp_match.json()
            duration_raw = data['info']['gameDuration']
            
            # Filtro Remake
            if duration_raw < 190:
                print(f"Match {match_id} ignorado (Remake/Duración atípica).")
                continue 
            
            game_duration_min = duration_raw / 60
            p = next(p for p in data['info']['participants'] if p['puuid'] == puuid)
            
            total_cs = p.get('totalMinionsKilled', 0) + p.get('neutralMinionsKilled', 0)
            cs_per_min = round(total_cs / game_duration_min, 1) if game_duration_min > 0 else 0
            
            lane = p.get('teamPosition', 'NONE')
            dmg_obj = p.get('damageDealtToObjectives', 0)
            dmg_turrets = p.get('damageDealtToTurrets', 0)
            total_damage = p.get('totalDamageDealtToChampions', 0)
            
            cursor.execute('''
                INSERT INTO matches (match_id, puuid, champion, lane, kills, deaths, assists, win, game_mode, total_cs, cs_per_min, dmg_objectives, dmg_turrets, total_damage, game_duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (match_id, puuid, p['championName'], lane, p['kills'], p['deaths'], p['assists'], p['win'], data['info']['gameMode'], total_cs, cs_per_min, dmg_obj, dmg_turrets, total_damage, game_duration_min, data['info']['gameStartTimestamp']))

            # Extracción Timeline-V5
            url_timeline = f"https://{REGION_ROOT}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
            resp_timeline = requests.get(url_timeline, headers=headers)
            
            if resp_timeline.status_code == 200:
                timeline = resp_timeline.json()
                participant_id = next(part['participantId'] for part in timeline['info']['participants'] if part['puuid'] == puuid)
                target_minutes = [3, 5, 8, 11, 15, 20, 25, 30, 35, 40]
                kills_acc, deaths_acc, assists_acc = 0, 0, 0
                
                for m, frame in enumerate(timeline['info']['frames']):
                    for event in frame['events']:
                        if event['type'] == 'CHAMPION_KILL':
                            if event.get('killerId') == participant_id: kills_acc += 1
                            elif event.get('victimId') == participant_id: deaths_acc += 1
                            elif participant_id in event.get('assistingParticipantIds', []): assists_acc += 1
                    
                    if m in target_minutes:
                        p_frame = frame['participantFrames'][str(participant_id)]
                        cs = p_frame.get('minionsKilled', 0) + p_frame.get('jungleMinionsKilled', 0)
                        cs_min = round(cs / m, 1) if m > 0 else 0
                        damage = p_frame.get('damageStats', {}).get('totalDamageDoneToChampions', 0)
                        
                        cursor.execute('''
                            INSERT OR IGNORE INTO match_timeline (match_id, minute, cs, cs_min, damage, kills, deaths, assists)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (match_id, m, cs, cs_min, damage, kills_acc, deaths_acc, assists_acc))
            
            conn.commit()
            print(f"Match {match_id} procesado exitosamente.")

    conn.close()

if __name__ == "__main__":
    print("Iniciando proceso ETL...")
    run_extraction()
    print("Proceso ETL finalizado.")