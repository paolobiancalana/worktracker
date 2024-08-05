import sqlite3

def create_database():
    # Connessione al database (viene creato se non esiste)
    conn = sqlite3.connect('work_tracker.db')
    cursor = conn.cursor()

    # Creazione delle tabelle
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        jira_id TEXT,
        discord_id TEXT,
        full_name TEXT,
        name TEXT,
        surname TEXT,
        email TEXT,
        remote BOOLEAN,
        role TEXT,
        dept TEXT,
        admin BOOLEAN
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS work_logs (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        total_hours REAL,
        effective_hours REAL,
        is_overtime BOOLEAN DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')


    cursor.execute('''
    CREATE TABLE IF NOT EXISTS break_logs (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        type TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS device_usage_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        work_log_id INTEGER NOT NULL,
        mobile_time INTEGER DEFAULT 0,  -- Tempo totale in secondi su mobile
        pc_time INTEGER DEFAULT 0,      -- Tempo totale in secondi su PC
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (work_log_id) REFERENCES work_logs(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS leave_types (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS leave_records (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        leave_type_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        notes TEXT,
        hours INTEGER, -- Ore di permesso (se applicabile)
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
    )
    ''')

    # Inserimento delle tipologie di permessi
    cursor.execute('''
    INSERT OR IGNORE INTO leave_types (id, name) VALUES
    (1, 'malattia'),
    (2, 'permesso'),
    (3, 'ferie')
    ''')

    # Committa le modifiche e chiudi la connessione
    conn.commit()
    conn.close()
    print("Database e tabelle create con successo.")

if __name__ == "__main__":
    create_database()
