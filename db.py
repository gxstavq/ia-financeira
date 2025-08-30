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
        c.execute('''
    CREATE TABLE IF NOT EXISTS orcamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        categoria TEXT,
        valor_limite REAL
    )
''')
c.execute('''
    CREATE TABLE IF NOT EXISTS metas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        descricao TEXT,
        valor_meta REAL,
        valor_atual REAL DEFAULT 0
    )
''')
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            tipo TEXT,
            categoria TEXT,
            valor REAL,
            data TEXT,
            descricao TEXT,
            recorrencia TEXT,
            data_vencimento TEXT,
            status TEXT DEFAULT 'pago',
            observacao TEXT
        )
    ''')
    conn.commit()
    conn.close()