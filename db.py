import sqlite3

DATABASE = 'financeiro.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    return conn

def create_tables():
    # Corrigido de get_di() para get_db()
    conn = get_db()
    c = conn.cursor()
    # Tabela de transações evoluída para incluir status e data de vencimento
    c.execute('''
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            tipo TEXT NOT NULL, -- 'receita', 'despesa', 'divida'
            categoria TEXT,
            valor REAL NOT NULL,
            data TEXT NOT NULL,
            descricao TEXT,
            data_vencimento TEXT, -- Apenas para dívidas
            status TEXT NOT NULL -- 'pago', 'pendente'
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_tables()

