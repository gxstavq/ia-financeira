# -*- coding: utf-8 -*-

# Importa as ferramentas necessárias
import os
import json
import requests
import datetime
import csv
import re
import random
from collections import defaultdict
from flask import Flask, request

# --- CONFIGURAÇÃO DA APLicação FLASK ---
app = Flask(__name__)

# --- CREDENCIAIS (CARREGADAS DO AMBIENTE) ---
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# --- CONFIGURAÇÃO DOS ARQUIVOS DE DADOS ---
DATA_DIR = os.getenv('RENDER_DISK_PATH', '.')
CSV_GASTOS = os.path.join(DATA_DIR, "gastos_usuarios.csv")
CSV_ENTRADAS = os.path.join(DATA_DIR, "entradas_usuarios.csv")
CSV_SALDO = os.path.join(DATA_DIR, "saldo_usuarios.csv")
CSV_DIVIDAS = os.path.join(DATA_DIR, "dividas_usuarios.csv")

# Define o fuso horário para o Brasil (Brasília)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# --- INTELIGÊNCIA DA IA: EXPANSÃO MASSIVA DE CATEGORIAS ---
CATEGORY_KEYWORDS = {
    "Alimentação": [
        "restaurante", "almoço", "janta", "ifood", "rappi", "mercado", "comida", "lanche", "pizza", "hamburguer", 
        "padaria", "café", "sorvete", "açaí", "supermercado", "hortifruti", "sacolão", "feira", "açougue", 
        "peixaria", "doces", "bolo", "salgado", "esfiha", "pastel", "churrasco", "bebida", "refrigerante", 
        "cerveja", "vinho", "suco", "água", "energético", "quitanda", "mercearia", "conveniência", "delivery",
        "marmita", "quentinha", "sushi", "temaki", "japonês", "chinês", "italiano", "mexicano", "árabe",
        "pão", "leite", "queijo", "presunto", "frutas", "verduras", "legumes", "carne", "frango", "peixe",
        "ovos", "arroz", "feijão", "macarrão", "molho", "biscoito", "bolacha", "chocolate", "bombom", "cereal"
    ],
    "Transporte": [
        "uber", "99", "táxi", "gasolina", "etanol", "diesel", "combustível", "metrô", "ônibus", "trem", "passagem", 
        "estacionamento", "pedágio", "rodízio", "multa", "ipva", "licenciamento", "seguro do carro", "mecânico",
        "oficina", "troca de óleo", "pneu", "manutenção do carro", "lavagem", "lava-rápido", "aluguel de carro",
        "passagem aérea", "aeroporto", "rodoviária", "barca", "balsa", "frete", "carreto", "recarga bilhete único"
    ],
    "Moradia": [
        "aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "diarista", "faxineira", "limpeza", 
        "reforma", "manutenção", "conserto", "eletricista", "encanador", "pintor", "marceneiro", "material de construção",
        "tinta", "cimento", "areia", "ferramenta", "decoração", "móvel", "sofá", "cama", "mesa", "cadeira",
        "eletrodoméstico", "geladeira", "fogão", "microondas", "máquina de lavar", "tv a cabo", "segurança", "alarme"
    ],
    "Vestuário e Acessórios": [
        "roupa", "roupas", "tênis", "sapato", "bota", "sandália", "chinelo", "camiseta", "camisa", "blusa", "calça",
        "bermuda", "short", "saia", "vestido", "casaco", "jaqueta", "moletom", "terno", "blazer", "gravata",
        "meia", "cueca", "calcinha", "sutiã", "pijama", "biquíni", "sunga", "maiô", "acessório", "bolsa",
        "carteira", "cinto", "chapéu", "boné", "gorro", "cachecol", "luva", "óculos", "relógio", "joia",
        "brinco", "colar", "pulseira", "anel", "maquiagem", "batom", "base", "rímel", "perfume", "creme",
        "cosméticos", "lavanderia", "costureira", "ajuste de roupa", "sapataria"
    ],
    "Lazer": [
        "cinema", "show", "teatro", "concerto", "bar", "balada", "festa", "viagem", "hotel", "pousada", "hostel",
        "passagem de avião", "streaming", "spotify", "netflix", "hbo", "disney", "amazon prime", "youtube premium",
        "jogo", "game", "steam", "playstation", "xbox", "nintendo", "ingresso", "passeio", "parque", "praia",
        "clube", "hobby", "instrumento musical", "artesanato", "dança", "luta", "esporte", "futebol", "ingresso de jogo"
    ],
    "Saúde": [
        "farmácia", "remédio", "medicamento", "médico", "consulta", "plano de saúde", "convênio", "academia", 
        "suplemento", "whey", "creatina", "dentista", "aparelho", "exame", "laboratório", "terapia", "psicólogo",
        "fisioterapia", "pilates", "yoga", "nutricionista", "oftalmologista", "óculos de grau", "lente de contato",
        "veterinário", "pet shop", "ração", "vacina do pet"
    ],
    "Educação": [
        "curso", "livro", "ebook", "faculdade", "universidade", "mensalidade", "material escolar", "caderno",
        "caneta", "lápis", "mochila", "escola", "colégio", "aula particular", "professor", "palestra",
        "workshop", "seminário", "inscrição", "concurso", "certificação", "idiomas", "inglês", "espanhol"
    ],
    "Outros": []
}

# --- MENSAGENS E DICAS ---
COMMANDS_MESSAGE = """
Olá! Sou sua assistente financeira pessoal. 💸

Você pode falar comigo como se estivesse conversando com alguém!

*Exemplos do que você pode me dizer:*
- `gastei 25,50 no almoço`
- `recebi 3500 do salário`
- `tenho uma conta de luz de 180 que vence 15/09`
- `paguei a conta de luz`
- `qual meu saldo?`
- `o que gastei hoje?`

*Principais Comandos:*
📊 *RELATÓRIOS*
- `saldo`: Para ver seu saldo atual.
- `resumo financeiro`: Visão geral com saldo e dívidas.
- `gastos hoje` (ou `semana`/`mês`): Lista seus gastos.
- `entradas e saídas hoje` (ou `semana`/`mês`): Mostra o balanço.
- `minhas dívidas`: Lista suas dívidas pendentes.

⚙️ *AÇÕES*
- `apagar último gasto`: Remove o último gasto registrado.
- `paguei [descrição da dívida]`: Marca uma dívida como paga e registra o gasto.
- `dica`: Te dou uma dica financeira.

Qualquer dúvida, é só chamar! 😊
"""

FINANCIAL_TIPS = [
    "Anote todos os seus gastos, até os pequenos. Isso te ajuda a entender para onde seu dinheiro está indo.",
    "Crie um orçamento mensal. A regra 50/30/20 (50% necessidades, 30% desejos, 20% poupança) é um bom começo!",
    "Antes de uma compra por impulso, espere 24 horas. Muitas vezes, a vontade passa e você economiza.",
    "Tenha uma reserva de emergência. O ideal é ter o equivalente a 3 a 6 meses do seu custo de vida guardado.",
    "Compare preços antes de comprar. A internet facilita muito a pesquisa e a economia.",
    "Evite usar o cartão de crédito para compras do dia a dia. É mais fácil perder o controle dos gastos assim.",
    "Defina metas financeiras claras, como 'guardar R$1000 para uma viagem'. Metas te mantêm motivado."
]

# --- FUNÇÕES AUXILIARES RECONSTRUÍDAS ---

def parse_monetary_value(text):
    """Extrai o primeiro valor monetário de uma string de forma segura."""
    if not isinstance(text, str): return None
    pattern = r'(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2}|\d+)'
    match = re.search(pattern, text)
    if not match: return None
    try:
        return float(match.group(1).replace('.', '').replace(',', '.'))
    except (ValueError, IndexError):
        return None

def extract_all_transactions_intelligent(text):
    """
    FUNÇÃO RECONSTRUÍDA: Divide a frase em cláusulas e extrai uma transação de cada.
    """
    transactions = []
    # Divide a frase por conectores como 'e', ',', 'depois'
    clauses = re.split(r'\s+e\s+|\s*,\s*|\s+depois\s+', text)
    
    for clause in clauses:
        value = parse_monetary_value(clause)
        if value is not None:
            transactions.append({"value": value, "context": clause})
            
    return transactions

def extract_due_date(text):
    match = re.search(r'(\d{1,2}/\d{1,2})', text)
    return match.group(0) if match else "Sem data"

def clean_description(text, value):
    """
    FUNÇÃO DE LIMPEZA DRÁSTICAMENTE MELHORADA: Isola o sujeito da transação.
    """
    # Remove o valor monetário exato para não ser confundido com a descrição
    if value is not None:
        # Formata o valor com ponto como separador de milhar e vírgula para decimal
        formatted_value_br = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        text = text.replace(formatted_value_br, "")
        # Remove também o valor sem formatação
        text = text.replace(f"{value:.2f}", "")
        text = text.replace(str(int(value)), "")

    # Remove frases e palavras de "ruído"
    noise_patterns = [
        r'\b(hoje|gastei|comprei|paguei|foi|deu|custou|no valor de|de)\b',
        r'\b(recebi|salário|ganhei|depósito|rendimento|entrada)\b',
        r'\b(dívida|conta|vence|vencimento|apagar|último|parcela|boleto)\b',
        r'r\$', 'reais', r'\b(minha|meu|pro dia|com o)\b',
        r'(\d{1,2}/\d{1,2})' # Remove a data
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Limpeza final de espaços e caracteres indesejados
    text = re.sub(r'\s+', ' ', text).strip(" ,.:;")
    return text.capitalize() if text else "Gasto geral"


def infer_category(description):
    desc_lower = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in desc_lower for keyword in keywords): return category
    return "Outros"

def write_to_csv(filepath, header, row):
    file_exists = os.path.exists(filepath)
    try:
        with open(filepath, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            if not file_exists or os.path.getsize(filepath) == 0: writer.writerow(header)
            writer.writerow(row)
        return True
    except IOError as e:
        print(f"Erro de I/O ao escrever no arquivo {filepath}: {e}")
        return False

# --- FUNÇÕES DE LÓGICA FINANCEIRA ---

def get_balance(user_id):
    if not os.path.exists(CSV_SALDO): return 0.0
    with open(CSV_SALDO, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader, None)
        except StopIteration: return 0.0
        for row in reader:
            if row and row[0] == user_id: return float(row[1])
    return 0.0

def update_balance(user_id, new_balance):
    lines = []; user_found = False
    if os.path.exists(CSV_SALDO):
        with open(CSV_SALDO, 'r', encoding='utf-8') as file: lines = file.readlines()
    with open(CSV_SALDO, 'w', encoding='utf-8') as file:
        header_written = False
        if not lines or not lines[0].strip().lower() == "userid;saldo":
            file.write("UserID;Saldo\n"); header_written = True
        for line in lines:
            if line.strip().lower() == "userid;saldo" and not header_written:
                file.write(line); header_written = True; continue
            elif line.strip().lower() == "userid;saldo" and header_written: continue
            if line.startswith(user_id):
                file.write(f"{user_id};{new_balance:.2f}\n"); user_found = True
            elif line.strip(): file.write(line)
        if not user_found: file.write(f"{user_id};{new_balance:.2f}\n")

def record_expense(user_id, value, description, update=True):
    now = datetime.datetime.now(TIMEZONE)
    now_str_db = now.strftime("%Y-%m-%d %H:%M:%S")
    category = infer_category(description)
    header = ["UserID", "DataHora", "Descricao", "Valor", "Categoria"]
    row = [user_id, now_str_db, description, f"{value:.2f}", category]
    if write_to_csv(CSV_GASTOS, header, row):
        if update:
            current_balance = get_balance(user_id)
            update_balance(user_id, current_balance - value)
        return f"- {description}: *R${value:.2f}* ({category})"
    return None

def record_income(user_id, value, description):
    now = datetime.datetime.now(TIMEZONE)
    now_str_db = now.strftime("%Y-%m-%d %H:%M:%S"); today_str_msg = now.strftime("%d/%m")
    header = ["UserID", "DataHora", "Descricao", "Valor"]
    row = [user_id, now_str_db, description, f"{value:.2f}"]
    if write_to_csv(CSV_ENTRADAS, header, row):
        current_balance = get_balance(user_id)
        new_balance = current_balance + value
        update_balance(user_id, new_balance)
        return f"💰 Entrada registrada em {today_str_msg}!\n- {description}: *R${value:.2f}*\n\nSeu novo saldo é *R${new_balance:.2f}*."
    return "❌ Ops, não consegui registrar sua entrada."

def record_debt(user_id, value, description, due_date):
    header = ["UserID", "DataVencimento", "Descricao", "Valor"]
    row = [user_id, due_date, description, f"{value:.2f}"]
    if write_to_csv(CSV_DIVIDAS, header, row):
        return f"🧾 Dívida registrada!\n- {description}: *R${value:.2f}*\n- Vencimento: {due_date}"
    return "❌ Ops, não consegui registrar sua dívida."

def pay_debt(user_id, text):
    if not os.path.exists(CSV_DIVIDAS): return "Você não tem nenhuma dívida para pagar."
    search_desc = re.sub(r'\b(paguei|a|o|conta|fatura|boleto|de|da|do)\b', '', text, flags=re.IGNORECASE).strip()
    lines = []; debt_found = None
    with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file: lines = file.readlines()
    for i in range(len(lines) - 1, 0, -1):
        line = lines[i].strip()
        if line.startswith(user_id):
            parts = line.split(';')
            if search_desc.lower() in parts[2].lower():
                debt_found = {"index": i, "desc": parts[2], "value": float(parts[3])}
                break
    if not debt_found: return f"Não encontrei a dívida '{search_desc}'. Verifique a lista em 'minhas dívidas'."
    lines.pop(debt_found["index"])
    with open(CSV_DIVIDAS, 'w', encoding='utf-8') as file: file.writelines(lines)
    payment_desc = f"Pagamento: {debt_found['desc']}"
    record_expense(user_id, debt_found['value'], payment_desc)
    new_balance = get_balance(user_id)
    return f"✅ Dívida '{debt_found['desc']}' paga com sucesso!\nSeu novo saldo é *R${new_balance:.2f}*."

def delete_last_expense(user_id):
    if not os.path.exists(CSV_GASTOS): return "Você não tem gastos para apagar."
    lines = []; last_expense_index = -1
    with open(CSV_GASTOS, 'r', encoding='utf-8') as file: lines = file.readlines()
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip().startswith(user_id): last_expense_index = i; break
    if last_expense_index == -1: return "Não encontrei gastos seus para apagar."
    deleted_line_parts = lines.pop(last_expense_index).strip().split(';')
    deleted_description = deleted_line_parts[2]; deleted_value = float(deleted_line_parts[3])
    with open(CSV_GASTOS, 'w', encoding='utf-8') as file: file.writelines(lines)
    current_balance = get_balance(user_id)
    new_balance = current_balance + deleted_value
    update_balance(user_id, new_balance)
    return f"🗑️ Último gasto apagado!\n- {deleted_description}: R${deleted_value:.2f}\nO valor foi devolvido ao seu saldo. Novo saldo: *R${new_balance:.2f}*."

# --- FUNÇÕES DE RELATÓRIO ---

def get_debts_report(user_id):
    if not os.path.exists(CSV_DIVIDAS): return "Você não tem nenhuma dívida registrada. Parabéns! 🎉"
    report_lines = ["📋 *Suas Dívidas Pendentes* 📋\n"]
    total_debts = 0.0
    with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                try:
                    due_date, desc, value = row[1], row[2], float(row[3])
                    report_lines.append(f"- {desc} (Vence: {due_date}): R${value:.2f}")
                    total_debts += value
                except (ValueError, IndexError): continue
    if len(report_lines) == 1: return "Você não tem nenhuma dívida registrada. Parabéns! 🎉"
    report_lines.append(f"\n*Total de Dívidas: R${total_debts:.2f}*")
    return "\n".join(report_lines)

def get_total_debts(user_id):
    if not os.path.exists(CSV_DIVIDAS): return 0.0
    total = 0.0
    with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                try: total += float(row[3])
                except (ValueError, IndexError): continue
    return total

def get_financial_summary(user_id):
    balance = get_balance(user_id)
    total_debts = get_total_debts(user_id)
    return f"📊 *Resumo Financeiro*\n\n- Saldo em conta: *R${balance:.2f}*\n- Total de dívidas: *R${total_debts:.2f}*"

def get_period_report(user_id, period):
    if not os.path.exists(CSV_GASTOS): return "Nenhum gasto registrado ainda."
    now = datetime.datetime.now(TIMEZONE); total_spent = 0.0; report_lines = []
    if period == "dia": start_date = now.date(); period_name = "hoje"
    elif period == "semana": start_date = now.date() - datetime.timedelta(days=now.weekday()); period_name = "nesta semana"
    else: start_date = now.date().replace(day=1); period_name = "neste mês"
    report_lines.append(f"🧾 *Seus gastos {period_name}* 🧾\n")
    with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                try:
                    expense_date = datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date()
                    if expense_date >= start_date:
                        report_lines.append(f"- {row[2]}: R${float(row[3]):.2f}"); total_spent += float(row[3])
                except (ValueError, IndexError): continue
    if len(report_lines) == 1: return f"Você não teve gastos {period_name}. 🎉"
    report_lines.append(f"\n*Total gasto: R${total_spent:.2f}*")
    return "\n".join(report_lines)

def get_io_summary(user_id, period):
    now = datetime.datetime.now(TIMEZONE); total_in, total_out = 0.0, 0.0
    if period == "dia": start_date, period_name = now.date(), "de hoje"
    elif period == "semana": start_date, period_name = now.date() - datetime.timedelta(days=now.weekday()), "da semana"
    else: start_date, period_name = now.date().replace(day=1), "do mês"
    if os.path.exists(CSV_GASTOS):
        with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        if datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date() >= start_date: total_out += float(row[3])
                    except (ValueError, IndexError): continue
    if os.path.exists(CSV_ENTRADAS):
        with open(CSV_ENTRADAS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        if datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date() >= start_date: total_in += float(row[3])
                    except (ValueError, IndexError): continue
    return f"💸 *Balanço {period_name}*\n\n- Entradas: *R${total_in:.2f}*\n- Saídas: *R${total_out:.2f}*"

# --- FUNÇÃO DE ENVIO DE MENSAGEM ---

def send_whatsapp_message(phone_number, message_text):
    if not all([ACCESS_TOKEN, PHONE_NUMBER_ID]): print("ERRO: Credenciais não configuradas."); return
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}
    try:
        response = requests.post(url, headers=headers, json=data); response.raise_for_status()
        print(f"Mensagem enviada para {phone_number}.")
    except requests.exceptions.RequestException as e: print(f"Erro ao enviar mensagem: {e}")

# --- PROCESSADOR DE COMANDOS ---

def process_message(user_id, user_name, message_text):
    """Função principal que interpreta a mensagem do usuário e decide qual ação tomar."""
    
    # --- EXPANSÃO MASSIVA DE COMANDOS (FORMAIS E INFORMAIS) ---
    CMD_SALDO = ["saldo", "qual meu saldo", "ver saldo", "quanto tenho", "meu dinheiro", "dinheiro em conta", "grana", "ver a grana", "kd meu dinheiro", "quanto de dinheiro eu tenho"]
    CMD_RESUMO = ["resumo", "resumo financeiro", "visão geral", "como estou", "minhas finanças", "situação financeira", "meu status", "como estão as contas"]
    CMD_APAGAR = ["apagar último", "excluir último", "cancelar último", "apaga o último", "deleta o último", "foi errado", "lancei errado"]
    CMD_DICA = ["dica", "dica financeira", "me dê uma dica", "uma dica", "conselho", "me ajuda a economizar"]
    CMD_GASTOS = ["gastos", "o que gastei", "relatório de gastos", "saídas", "minhas despesas", "onde gastei", "com o que gastei", "lista de gastos"]
    CMD_BALANCO = ["entradas e saídas", "entrou e saiu", "balanço", "fluxo de caixa", "relatório de transações", "movimentações"]
    CMD_REGISTRAR_DIVIDA = ["dívida", "divida", "parcela", "boleto", "conta", "vencimento", "tenho que pagar", "anota uma conta", "registra uma dívida"]
    CMD_PAGAR_DIVIDA = ["paguei", "já paguei", "pagamento de", "quitei", "dar baixa"]
    CMD_VER_DIVIDAS = ["minhas dívidas", "ver dívidas", "quais minhas contas", "o que devo", "lista de dívidas"]
    
    # 1. Comandos diretos e de alta prioridade
    if any(cmd in message_text for cmd in ["ajuda", "comandos", "menu", "começar", "opções"]): return COMMANDS_MESSAGE
    greetings = ["oi", "olá", "bom dia", "boa tarde", "boa noite", "e aí", "opa", "salve"]
    if message_text.strip() in greetings: return f"Olá, {user_name}! Como posso te ajudar hoje? 😊"
    if any(cmd in message_text for cmd in CMD_SALDO): return f"💵 Seu saldo atual é de *R${get_balance(user_id):.2f}*."
    if any(cmd in message_text for cmd in CMD_RESUMO): return get_financial_summary(user_id)
    if any(cmd in message_text for cmd in CMD_APAGAR): return delete_last_expense(user_id)
    if any(cmd in message_text for cmd in CMD_DICA): return random.choice(FINANCIAL_TIPS)
    if any(cmd in message_text for cmd in CMD_VER_DIVIDAS): return get_debts_report(user_id)

    # 2. Comando de Pagar Dívida (prioridade alta)
    if any(cmd in message_text for cmd in CMD_PAGAR_DIVIDA):
        return pay_debt(user_id, message_text)

    # 3. Comandos de Relatório com Período
    if any(cmd in message_text for cmd in CMD_GASTOS):
        if any(p in message_text for p in ["hoje", "hj", "de hoje"]): return get_period_report(user_id, "dia")
        if "semana" in message_text: return get_period_report(user_id, "semana")
        if "mês" in message_text: return get_period_report(user_id, "mês")
    if any(cmd in message_text for cmd in CMD_BALANCO):
        if any(p in message_text for p in ["hoje", "hj", "de hoje"]): return get_io_summary(user_id, "dia")
        if "semana" in message_text: return get_io_summary(user_id, "semana")
        if "mês" in message_text: return get_io_summary(user_id, "mês")

    # --- LÓGICA DE TRANSAÇÃO RECONSTRUÍDA ---
    
    # 4. ANÁLISE DE INTENÇÃO PRIMEIRO
    if any(keyword in message_text for keyword in CMD_REGISTRAR_DIVIDA):
        value = parse_monetary_value(message_text)
        if value is not None:
            description = clean_description(message_text, value)
            due_date = extract_due_date(message_text)
            return record_debt(user_id, value, description, due_date)

    # 5. Se não for dívida, procura por transações (gastos ou entradas)
    transactions = extract_all_transactions_intelligent(message_text)
    
    if len(transactions) > 1:
        today_str_msg = datetime.datetime.now(TIMEZONE).strftime("%d/%m")
        response_lines = [f"Entendido! Registrei {len(transactions)} gastos para você em {today_str_msg}:"]
        total_value = 0
        for trans in transactions:
            value = trans['value']
            description = clean_description(trans['context'], value)
            result_line = record_expense(user_id, value, description, update=False)
            if result_line:
                response_lines.append(result_line)
                total_value += value
        
        current_balance = get_balance(user_id)
        update_balance(user_id, current_balance - total_value)
        response_lines.append(f"\nSeu novo saldo é *R${get_balance(user_id):.2f}*.")
        return "\n".join(response_lines)

    if len(transactions) == 1:
        value = transactions[0]['value']
        description = clean_description(message_text, value)
        
        income_keywords = ["recebi", "salário", "ganhei", "depósito", "rendimento", "entrada", "pix", "me pagaram"]
        if any(keyword in message_text for keyword in income_keywords):
            if not description: description = "Entrada"
            return record_income(user_id, value, description)
            
        return record_expense(user_id, value, description)

    # 6. Se nada correspondeu, retorna mensagem de ajuda
    return f"Não entendi, {user_name}. 🤔\n\n- Para *gastos*, tente: `gastei 20 no lanche`\n- Para *dívidas*, tente: `conta de luz 150 vence 10/09`\n- Para *entradas*, tente: `recebi 500`\n\nPara ver tudo, envie `comandos`."

# --- WEBHOOK PRINCIPAL DA APLICAÇÃO ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode'); token = request.args.get('hub.verify_token'); challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED"); return challenge, 200
        return 'Failed verification', 403
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            if 'entry' in data and data['entry'][0]['changes'][0]['value'].get('messages'):
                message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
                if message_data.get('type') != 'text': return 'EVENT_RECEIVED', 200
                user_id = message_data['from']
                user_name = data['entry'][0]['changes'][0]['value']['contacts'][0].get('profile', {}).get('name', 'Pessoa')
                message_text = message_data['text']['body'].strip().lower()
                print(f"Recebida mensagem de {user_name} ({user_id}): '{message_text}'")
                reply_message = process_message(user_id, user_name, message_text)
                if reply_message: send_whatsapp_message(user_id, reply_message)
        except (KeyError, IndexError, TypeError) as e:
            print(f"Erro ao processar webhook: {e}\nDados: {json.dumps(data, indent=2)}")
        return 'EVENT_RECEIVED', 200