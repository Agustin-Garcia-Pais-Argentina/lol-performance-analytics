import sqlite3

DB_NAME = "lol_stats.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        match_id TEXT PRIMARY KEY,
        puuid TEXT NOT NULL,
        champion TEXT,
        lane TEXT,
        kills INTEGER,
        deaths INTEGER,
        assists INTEGER,
        win BOOLEAN,
        game_mode TEXT,
        total_cs INTEGER,
        cs_per_min REAL,
        dmg_objectives INTEGER,
        dmg_turrets INTEGER,
        total_damage INTEGER,
        game_duration REAL,
        timestamp INTEGER
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS match_timeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT,
        minute INTEGER,
        cs INTEGER,
        cs_min REAL,
        damage INTEGER,
        kills INTEGER,
        deaths INTEGER,
        assists INTEGER,
        FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE,
        UNIQUE(match_id, minute)
    )
    ''')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()