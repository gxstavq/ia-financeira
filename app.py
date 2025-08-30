# -*- coding: utf-8 -*-

# Importa as ferramentas necessárias
import os
import json
import requests
import datetime
import csv
import re
import random
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
# Esta seção define as palavras-chave que a IA usa para categorizar automaticamente cada gasto.
CATEGORY_KEYWORDS = {
    "Alimentação": [
        "restaurante", "almoço", "janta", "ifood", "rappi", "mercado", "comida", "lanche", "pizza", "hamburguer", 
        "padaria", "café", "sorvete", "açaí", "supermercado", "hortifruti", "sacolão", "feira", "açougue", 
        "peixaria", "doces", "bolo", "salgado", "esfiha", "pastel", "churrasco", "bebida", "refrigerante", 
        "cerveja", "vinho", "suco", "água", "energético", "quitanda", "mercearia", "conveniência", "delivery",
        "marmita", "quentinha", "sushi", "temaki", "japonês", "chinês", "italiano", "mexicano", "árabe",
        "pão", "leite", "queijo", "presunto", "frutas", "verduras", "legumes", "carne", "frango", "peixe",
        "ovos", "arroz", "feijão", "macarrão", "molho", "biscoito", "bolacha", "chocolate", "bombom", "cereal", "chiclete"
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
        "workshop", "seminário", "inscrição", "concurso", "certificação", "idiomas", "inglês", "espanhol"],
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
    "Anote todos os seus gastos, até os pequenos. Isso te ajuda a entender para onde seu dinheiro está indo.", "Crie um orçamento mensal. A regra 50/30/20 (50% necessidades, 30% desejos, 20% poupança) é um bom começo!", "Antes de uma compra por impulso, espere 24 horas. Muitas vezes, a vontade passa e você economiza.", "Tenha uma reserva de emergência. O ideal é ter o equivalente a 3 a 6 meses do seu custo de vida guardado.", "Compare preços antes de comprar. A internet facilita muito a pesquisa e a economia.", "Evite usar o cartão de crédito para compras do dia a dia. É mais fácil perder o controle dos gastos assim.", "Defina metas financeiras claras, como 'guardar R$1000 para uma viagem'. Metas te mantêm motivado."
]

# --- FUNÇÕES AUXILIARES DE INTERPRETAÇÃO ---

def parse_monetary_value(text):
    if not isinstance(text, str): return None
    pattern = r'(?:R\$\s*)?([\d.,]+)'
    matches = re.findall(pattern, text)
    if not matches: return None
    best_match = max(matches, key=lambda m: len(re.sub(r'\D', '', m)))
    if not best_match: return None
    standardized_value = best_match.replace('.', '').replace(',', '.')
    if len(standardized_value.split('.')) == 2 and len(standardized_value.split('.')[1]) > 2:
         standardized_value = standardized_value.replace('.', '')
    try:
        return float(standardized_value)
    except (ValueError, IndexError):
        return None

def extract_all_transactions(text):
    transactions = []
    clauses = re.split(r'\s+e\s+|\s+depois\s+|,\s*(?!\d{3})', text)
    for clause in clauses:
        value = parse_monetary_value(clause)
        if value is not None:
            transactions.append({"value": value, "context": clause})
    return transactions

def extract_due_date(text):
    match = re.search(r'(\d{1,2}/\d{1,2})', text)
    return match.group(0) if match else "Sem data"

def clean_description(text, value):
    if value is not None:
        formatted_value_br = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        text = text.replace(formatted_value_br, "").replace(str(value), "").replace(str(int(value)), "")
    noise_patterns = [
        r'\b(hoje|gastei|comprei|paguei|foi|deu|custou|no valor de|de|acabei de pedir|acabei de ganhar)\b',
        r'\b(recebi|salário|ganhei|depósito|rendimento|entrada|caixinha|gorjeta)\b',
        r'\b(dívida|conta|vence|vencimento|apagar|último|parcela|boleto)\b',
        r'r\$', 'reais', r'\b(minha|meu|pro dia|com o|para a|pra)\b', r'(\d{1,2}/\d{1,2})'
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip(" ,.:;")
    return text.capitalize() if text else "Gasto geral"

def infer_category(description):
    desc_lower = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in desc_lower for keyword in keywords): return category
    return "Outros"

# --- FUNÇÕES DE LÓGICA FINANCEIRA ---

def write_to_csv(filepath, header, row):
    file_exists = os.path.exists(filepath)
    try:
        with open(filepath, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            if not file_exists or os.path.getsize(filepath) == 0: writer.writerow(header)
            writer.writerow(row)
        return True
    except IOError as e:
        print(f"Erro de I/O: {e}"); return False

def get_balance(user_id):
    if not os.path.exists(CSV_SALDO): return 0.0
    with open(CSV_SALDO, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader, None)
        except StopIteration: return 0.0
        for row in reader:
            if row and row[0] == user_id: return float(row[1])
    return 0.0

def set_balance(user_id, new_balance):
    lines, user_found = [], False
    if os.path.exists(CSV_SALDO):
        with open(CSV_SALDO, 'r', encoding='utf-8') as file: lines = file.readlines()
    with open(CSV_SALDO, 'w', encoding='utf-8') as file:
        if not lines or not lines[0].strip().lower().startswith("userid"): file.write("UserID;Saldo\n")
        for line in lines:
            if line.strip().lower().startswith("userid"):
                if "userid;saldo" not in line.lower(): file.write("UserID;Saldo\n")
                else: file.write(line)
                continue
            if line.startswith(user_id):
                file.write(f"{user_id};{new_balance:.2f}\n"); user_found = True
            elif line.strip(): file.write(line)
        if not user_found: file.write(f"{user_id};{new_balance:.2f}\n")

def record_expense(user_id, value, description, update_balance=True):
    now = datetime.datetime.now(TIMEZONE)
    category = infer_category(description)
    row = [user_id, now.strftime("%Y-%m-%d %H:%M:%S"), description, f"{value:.2f}", category]
    if write_to_csv(CSV_GASTOS, ["UserID", "DataHora", "Descricao", "Valor", "Categoria"], row):
        if update_balance:
            set_balance(user_id, get_balance(user_id) - value)
        return {"description": description, "value": value, "category": category}
    return None

def record_income(user_id, value, description):
    now = datetime.datetime.now(TIMEZONE)
    today_str_msg = now.strftime("%d/%m")
    new_balance = get_balance(user_id) + value
    set_balance(user_id, new_balance)
    write_to_csv(CSV_ENTRADAS, ["UserID", "DataHora", "Descricao", "Valor"], [user_id, now.strftime("%Y-%m-%d %H:%M:%S"), description, f"{value:.2f}"])
    return f"💰 Entrada registrada em {today_str_msg}!\n- {description}: *R${value:.2f}*\n\nSeu novo saldo é *R${new_balance:.2f}*."

def record_debt(user_id, value, description, due_date):
    write_to_csv(CSV_DIVIDAS, ["UserID", "DataVencimento", "Descricao", "Valor"], [user_id, due_date, description, f"{value:.2f}"])
    return f"🧾 Dívida registrada!\n- {description}: *R${value:.2f}*\n- Vencimento: {due_date}"

def pay_debt(user_id, text):
    if not os.path.exists(CSV_DIVIDAS): return "Você não tem nenhuma dívida para pagar."
    search_desc = re.sub(r'\b(paguei|a|o|conta|fatura|boleto|de|da|do)\b', '', text, flags=re.IGNORECASE).strip()
    lines, debt_found = [], None
    with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file: lines = file.readlines()
    for i, line in reversed(list(enumerate(lines))):
        if line.strip().startswith(user_id) and len(line.strip().split(';')) > 2:
            parts = line.strip().split(';')
            if search_desc.lower() in parts[2].lower():
                debt_found = {"index": i, "desc": parts[2], "value": float(parts[3])}; break
    if not debt_found: return f"Não encontrei a dívida '{search_desc}'. Verifique a lista em 'minhas dívidas'."
    lines.pop(debt_found["index"])
    with open(CSV_DIVIDAS, 'w', encoding='utf-8') as file: file.writelines(lines)
    record_expense(user_id, debt_found['value'], f"Pagamento: {debt_found['desc']}")
    return f"✅ Dívida '{debt_found['desc']}' paga com sucesso!\nSeu novo saldo é *R${get_balance(user_id):.2f}*."

def delete_last_expense(user_id):
    if not os.path.exists(CSV_GASTOS): return "Você não tem gastos para apagar."
    lines, last_expense_index = [], -1
    with open(CSV_GASTOS, 'r', encoding='utf-8') as file: lines = file.readlines()
    for i, line in reversed(list(enumerate(lines))):
        if line.strip().startswith(user_id): last_expense_index = i; break
    if last_expense_index == -1: return "Não encontrei gastos seus para apagar."
    deleted_line_parts = lines.pop(last_expense_index).strip().split(';')
    deleted_value = float(deleted_line_parts[3])
    with open(CSV_GASTOS, 'w', encoding='utf-8') as file: file.writelines(lines)
    set_balance(user_id, get_balance(user_id) + deleted_value)
    return f"🗑️ Último gasto apagado!\n- {deleted_line_parts[2]}: R${deleted_value:.2f}\nO valor foi devolvido. Novo saldo: *R${get_balance(user_id):.2f}*."

def get_debts_report(user_id):
    if not os.path.exists(CSV_DIVIDAS): return "Você não tem nenhuma dívida registrada. Parabéns! 🎉"
    report_lines, total_debts = ["📋 *Suas Dívidas Pendentes* 📋\n"], 0.0
    with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                report_lines.append(f"- {row[2]} (Vence: {row[1]}): R${float(row[3]):.2f}"); total_debts += float(row[3])
    if len(report_lines) == 1: return "Você não tem nenhuma dívida registrada. Parabéns! 🎉"
    report_lines.append(f"\n*Total de Dívidas: R${total_debts:.2f}*")
    return "\n".join(report_lines)

def get_financial_summary(user_id):
    balance = get_balance(user_id)
    total_debts = sum(float(row[3]) for row in csv.reader(open(CSV_DIVIDAS), delimiter=';') if len(row) > 3 and row[0] == user_id) if os.path.exists(CSV_DIVIDAS) else 0.0
    return f"📊 *Resumo Financeiro*\n\n- Saldo em conta: *R${balance:.2f}*\n- Total de dívidas: *R${total_debts:.2f}*"

def get_period_report(user_id, period):
    if not os.path.exists(CSV_GASTOS): return "Nenhum gasto registrado ainda."
    now, total_spent, report_lines = datetime.datetime.now(TIMEZONE), 0.0, []
    if period == "dia": start_date, period_name = now.date(), "hoje"
    elif period == "semana": start_date, period_name = now.date() - datetime.timedelta(days=now.weekday()), "nesta semana"
    else: start_date, period_name = now.date().replace(day=1), "neste mês"
    report_lines.append(f"🧾 *Seus gastos {period_name}* 🧾\n")
    with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                if datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date() >= start_date:
                    report_lines.append(f"- {row[2]}: R${float(row[3]):.2f}"); total_spent += float(row[3])
    if len(report_lines) == 1: return f"Você não teve gastos {period_name}. 🎉"
    report_lines.append(f"\n*Total gasto: R${total_spent:.2f}*")
    return "\n".join(report_lines)

def get_io_summary(user_id, period):
    now, total_in, total_out = datetime.datetime.now(TIMEZONE), 0.0, 0.0
    if period == "dia": start_date, period_name = now.date(), "de hoje"
    elif period == "semana": start_date, period_name = now.date() - datetime.timedelta(days=now.weekday()), "da semana"
    else: start_date, period_name = now.date().replace(day=1), "do mês"
    if os.path.exists(CSV_GASTOS):
        with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id and datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date() >= start_date: total_out += float(row[3])
    if os.path.exists(CSV_ENTRADAS):
        with open(CSV_ENTRADAS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id and datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date() >= start_date: total_in += float(row[3])
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

# --- PROCESSADOR DE COMANDOS (LÓGICA DE REGRAS) ---
def process_message(user_id, user_name, message_text):
    
    # --- MILHARES DE COMANDOS (EXPANSÃO MASSIVA) ---
    
    # SAUDAÇÕES E CONVERSA BÁSICA
    CMD_GREETINGS = [
        "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "eae", "opa", "salve", 
        "tudo bem?", "td bem?", "tudo bom?", "td bom?", "como vai?", "blz?", "beleza?"
    ]
    CMD_HELP = [
        "ajuda", "comandos", "menu", "começar", "opções", "o que você faz", "como funciona", "help",
        "preciso de ajuda", "me ajuda", "quais os comandos", "lista de comandos", "como usar"
    ]

    # CONSULTAS DE SALDO
    CMD_GET_SALDO = [
        "qual meu saldo", "ver saldo", "quanto tenho", "meu dinheiro", "dinheiro em conta", "grana", 
        "ver a grana", "kd meu dinheiro", "quanto de dinheiro eu tenho", "saldo", "mostra o saldo",
        "meu saldo", "meu saldo por favor", "poderia ver meu saldo?", "consulta de saldo", "checar saldo",
        "qual o valor na minha conta?", "qto tenho?", "quanto eu tenho?", "quanto me resta?"
    ]
    
    # DEFINIÇÃO DE SALDO INICIAL
    CMD_SET_SALDO = [
        "meu saldo é", "tenho na conta", "definir saldo", "saldo inicial", "começar com", 
        "meu saldo atual é", "tenho um total de", "meu saldo inicial é", "iniciar com", "tenho"
    ]

    # RESUMO E RELATÓRIOS GERAIS
    CMD_RESUMO = [
        "resumo", "resumo financeiro", "visão geral", "como estou", "minhas finanças", 
        "situação financeira", "meu status", "como estão as contas", "faz um resumo pra mim",
        "resumo geral", "balanço geral"
    ]
    
    # AÇÕES DE CORREÇÃO
    CMD_APAGAR = [
        "apagar último", "excluir último", "cancelar último", "apaga o último", "deleta o último", 
        "foi errado", "lancei errado", "apagar ultimo gasto", "remove o ultimo", "excluir lançamento"
    ]

    # DICAS
    CMD_DICA = [
        "dica", "dica financeira", "me dê uma dica", "uma dica", "conselho", "me ajuda a economizar", 
        "conselho financeiro", "preciso de uma dica", "manda uma dica"
    ]

    # RELATÓRIOS DE GASTOS
    CMD_GASTOS = [
        "gastos", "o que gastei", "relatório de gastos", "saídas", "minhas despesas", 
        "onde gastei", "com o que gastei", "lista de gastos", "ver gastos", "meus gastos",
        "mostra as saídas", "quais foram as despesas"
    ]
    
    # RELATÓRIOS DE ENTRADAS E SAÍDAS
    CMD_BALANCO = [
        "entradas e saídas", "entrou e saiu", "balanço", "fluxo de caixa", "relatório de transações", 
        "movimentações", "o que entrou e o que saiu", "balanço do período"
    ]

    # REGISTRO DE DÍVIDAS
    CMD_REGISTRAR_DIVIDA = [
        "dívida", "divida", "parcela", "boleto", "conta", "vencimento", "tenho que pagar", 
        "anota uma conta", "registra uma dívida", "fatura", "tenho uma conta", "lançar conta"
    ]
    
    # PAGAMENTO DE DÍVIDAS
    CMD_PAGAR_DIVIDA = [
        "paguei", "já paguei", "pagamento de", "quitei", "dar baixa", "paguei a conta",
        "pagamento da fatura", "paguei o boleto", "quitar dívida"
    ]
    
    # CONSULTA DE DÍVIDAS
    CMD_VER_DIVIDAS = [
        "minhas dívidas", "ver dívidas", "quais minhas contas", "o que devo", "lista de dívidas", 
        "contas a pagar", "o que tenho pra pagar", "ver boletos"
    ]

    # REGISTRO DE ENTRADAS
    CMD_ENTRADA = [
        "recebi", "salário", "ganhei", "depósito", "rendimento", "entrada", "pix", "me pagaram", 
        "um amigo me pagou", "salario", "recebimento", "caiu na conta", "caixinha", "gorjeta", "bico", "freela"
    ]
    
    # 1. Hierarquia de Intenção (a ordem importa)
    
    # Conversa Básica
    if message_text in CMD_GREETINGS: return f"Olá, {user_name}! Como posso te ajudar hoje? 😊"
    if any(cmd in message_text for cmd in CMD_HELP): return COMMANDS_MESSAGE

    value_in_message = parse_monetary_value(message_text)
    
    # Ações de Saldo (alta prioridade para evitar conflitos com "conta")
    if any(cmd in message_text for cmd in CMD_SET_SALDO) and value_in_message is not None:
        # Condição extra para evitar que "gastei 50 na conta de luz" seja confundido com "tenho na conta 50"
        if not any(gasto in message_text for gasto in ["gastei", "paguei", "comprei"]):
            set_balance(user_id, value_in_message)
            return f"✅ Saldo definido! Seu saldo atual é *R${value_in_message:.2f}*."

    if any(cmd in message_text for cmd in CMD_GET_SALDO):
        return f"💵 Seu saldo atual é de *R${get_balance(user_id):.2f}*."

    # Ações e Relatórios Diretos
    if any(cmd in message_text for cmd in CMD_RESUMO): return get_financial_summary(user_id)
    if any(cmd in message_text for cmd in CMD_APAGAR): return delete_last_expense(user_id)
    if any(cmd in message_text for cmd in CMD_DICA): return random.choice(FINANCIAL_TIPS)
    if any(cmd in message_text for cmd in CMD_VER_DIVIDAS): return get_debts_report(user_id)
    if any(cmd in message_text for cmd in CMD_PAGAR_DIVIDA): return pay_debt(user_id, message_text)

    # Relatórios com Período
    if any(cmd in message_text for cmd in CMD_GASTOS):
        if any(p in message_text for p in ["hoje", "hj", "de hoje"]): return get_period_report(user_id, "dia")
        if "semana" in message_text: return get_period_report(user_id, "semana")
        if "mês" in message_text: return get_period_report(user_id, "mês")
    if any(cmd in message_text for cmd in CMD_BALANCO):
        if any(p in message_text for p in ["hoje", "hj", "de hoje"]): return get_io_summary(user_id, "dia")
        if "semana" in message_text: return get_io_summary(user_id, "semana")
        if "mês" in message_text: return get_io_summary(user_id, "mês")

    # Transações Financeiras
    if any(keyword in message_text for keyword in CMD_REGISTRAR_DIVIDA):
        if value_in_message is not None:
            description = clean_description(message_text, value_in_message)
            due_date = extract_due_date(message_text)
            return record_debt(user_id, value_in_message, description, due_date)

    if any(keyword in message_text for keyword in CMD_ENTRADA) and value_in_message is not None:
        description = clean_description(message_text, value_in_message)
        if not description: description = "Entrada"
        return record_income(user_id, value_in_message, description)

    # Fallback: Se não for nada acima, assume que é um gasto
    transactions = extract_all_transactions(message_text)
    if transactions:
        if len(transactions) > 1:
            today_str_msg = datetime.datetime.now(TIMEZONE).strftime("%d/%m")
            response_lines = [f"Entendido! Registrei {len(transactions)} gastos para você em {today_str_msg}:"]
            total_value = sum(t['value'] for t in transactions)
            for trans in transactions:
                description = clean_description(trans['context'], trans['value'])
                result = record_expense(user_id, trans['value'], description, update_balance=False)
                if result: response_lines.append(f"- {result['description']}: *R${result['value']:.2f}* ({result['category']})")
            set_balance(user_id, get_balance(user_id) - total_value)
            response_lines.append(f"\nSeu novo saldo é *R${get_balance(user_id):.2f}*.")
            return "\n".join(response_lines)
        
        elif len(transactions) == 1:
            value = transactions[0]['value']
            description = clean_description(message_text, value)
            result = record_expense(user_id, value, description)
            if result:
                today_str_msg = datetime.datetime.now(TIMEZONE).strftime("%d/%m")
                return f"✅ Gasto registrado em {today_str_msg}!\n- {result['description']}: *R${result['value']:.2f}* ({result['category']})\n\nSeu novo saldo é *R${get_balance(user_id):.2f}*."

    return f"Não entendi, {user_name}. 🤔 Se precisar de ajuda, envie `comandos`."

# --- WEBHOOK PRINCIPAL DA APLICAÇÃO ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode, token, challenge = request.args.get('hub.mode'), request.args.get('hub.verify_token'), request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED"); return challenge, 200
        return 'Failed verification', 403
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
            if message_data.get('type') != 'text': return 'EVENT_RECEIVED', 200
            user_id = message_data['from']
            user_name = data['entry'][0]['changes'][0]['value']['contacts'][0].get('profile', {}).get('name', 'Pessoa')
            message_text = message_data['text']['body'].strip().lower()
            
            print(f"Recebida mensagem de {user_name} ({user_id}): '{message_text}'")
            reply_message = process_message(user_id, user_name, message_text)
            
            if reply_message: send_whatsapp_message(user_id, reply_message)
        except Exception as e:
            print(f"!!! ERRO CRÍTICO NO WEBHOOK: {e} !!!")
            send_whatsapp_message(data['entry'][0]['changes'][0]['value']['messages'][0]['from'], "❌ Desculpe, encontrei um erro inesperado. Pode tentar de novo?")
        return 'EVENT_RECEIVED', 200
