import sqlite3

def get_db():
    conn = sqlite3.connect("financas.db")
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            tipo TEXT,
            categoria TEXT,
            valor REAL,
            data TEXT,
            descricao TEXT
        )
    ''')
    conn.commit()
    conn.close()