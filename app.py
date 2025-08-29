# Importa as ferramentas necessárias
from flask import Flask, request
import json
import requests
import datetime
import os
import csv
import re  # Importado para a análise de texto
import random  # Importado para as dicas financeiras
from collections import defaultdict
import unicodedata

# Cria a aplicação
app = Flask(__name__)

# --- SUAS CREDENCIAIS ---
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
# --- FIM DAS CREDENCIAIS ---

# Configuração do disco persistente
DATA_DIR = os.getenv('RENDER_DISK_PATH', '.')
CSV_FILE_NAME = os.path.join(DATA_DIR, "meus_gastos.csv")
PAGAMENTOS_FILE_NAME = os.path.join(DATA_DIR, "pagamentos.csv")  # Novo ficheiro para registar entradas
SALDO_FILE_NAME = os.path.join(DATA_DIR, "saldo.csv")
DIVIDAS_FILE_NAME = os.path.join(DATA_DIR, "dividas.csv")
ORCAMENTO_FILE_NAME = os.path.join(DATA_DIR, "orcamento.csv")
METAS_FILE_NAME = os.path.join(DATA_DIR, "metas.csv")
RECORRENTES_FILE_NAME = os.path.join(DATA_DIR, "recorrentes.csv")
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# Dicionário de palavras-chave expandido para maior inteligência
CATEGORY_KEYWORDS = {
    "Alimentação": ["restaurante", "almoço", "janta", "ifood", "rappi", "mercado", "comida", "lanche", "pizza", "hamburguer", "padaria", "café", "sorvete", "açaí", "supermercado"],
    "Transporte": ["uber", "99", "táxi", "gasolina", "metrô", "ônibus", "passagem", "estacionamento", "escritorio", "combustível", "pedágio", "rodízio", "moto"],
    "Moradia": ["aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "diarista", "limpeza", "reforma", "manutenção", "conta"],
    "Lazer": ["cinema", "show", "bar", "festa", "viagem", "streaming", "spotify", "netflix", "jogo", "ingresso", "passeio", "clube", "hobby"],
    "Saúde": ["farmácia", "remédio", "médico", "consulta", "plano", "academia", "suplemento", "dentista", "exame", "terapia"],
    "Compras": ["roupa", "roupas", "tênis", "sapato", "presente", "shopping", "online", "eletrônicos", "celular", "computador", "acessório", "decoração", "livraria"],
    "Educação": ["curso", "livro", "faculdade", "material", "escola", "aula", "palestra"],
    "Essenciais": ["aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "mercado", "farmácia", "plano", "metrô", "ônibus", "combustível", "faculdade", "escola"],
    "Desejos": ["restaurante", "ifood", "rappi", "lanche", "pizza", "cinema", "show", "bar", "festa", "viagem", "streaming", "jogo", "roupas", "tênis", "presente", "shopping", "uber", "99", "táxi", "hobby"]
}

# Mensagem de ajuda mais humana e com novos comandos
COMMANDS_MESSAGE = """
Olá! Sou a sua assistente financeira. 😊
Você pode falar comigo de forma natural! Tente coisas como:

- `gastei 25,50 no almoço`
- `recebi meu pagamento de 2.500,08`
- `dívida luz 180`
- `paguei a conta de luz`
- `qual o meu saldo?`
- `quanto entrou e saiu hoje?`
- `dica financeira`

Aqui estão alguns dos comandos que eu entendo:

💰 **Orçamento e Metas**
- `definir rendimento [valor]`
- `meu orçamento`

📊 **Análises e Relatórios**
- `resumo financeiro`
- `comparar gastos`
- `gastos da [semana/mês/dia]`
- `entradas e saídas [hoje/semana/mês]`
- `minhas dívidas`

💡 **Outros**
- `dica financeira`
- `apagar último gasto`
"""

# --------------------
# UTILITÁRIAS / NORMALIZAÇÃO
# --------------------
def normalize_text(s: str) -> str:
    """Minúsculas, remove acentos e espaços extras."""
    s = (s or "").lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\s+', ' ', s)
    return s

def contains_any(text: str, patterns) -> bool:
    """Checa se qualquer padrão (string) está presente em text."""
    for p in patterns:
        if isinstance(p, str) and p in text:
            return True
    return False

# --------------------
# PARSERS E EXTRAÇÃO
# --------------------
# >>> CÓDIGO ALTERADO: Função de parsing de valores reconstruída para máxima precisão
def parse_value_string(s):
    """
    Aceita formatos:
      - BR: 1.234,56 ou 123,45 ou 2900
      - EN: 1,234.56 ou 123.45
    Garante que '2900' -> 2900.0 (não 290.0).
    """
    if s is None:
        raise ValueError("Valor inválido")
    if not isinstance(s, str):
        return float(s)

    s = s.strip()
    # remove R$ e espaços
    s = s.replace('R$', '').replace('r$', '').strip()

    # apenas dígitos -> inteiro
    if re.fullmatch(r'\d+', s):
        return float(s)

    # BR: 1.234,56  ou 123,45
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})*,\d{2}', s) or re.fullmatch(r'\d+,\d{2}', s):
        return float(s.replace('.', '').replace(',', '.'))

    # EN: 1,234.56  ou 123.45
    if re.fullmatch(r'\d{1,3}(?:,\d{3})*\.\d{2}', s):
        return float(s.replace(',', ''))

    # milhar com pontos sem decimais: 2.900 -> 2900
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})+', s) and ',' not in s:
        return float(s.replace('.', ''))

    # fallback: tenta converter trocando vírgula por ponto
    s_temp = s.replace('.', '').replace(',', '.')
    return float(s_temp)

def extract_all_monetary_values(text):
    """
    Pega números em formatos BR/EN e inteiros.
    Ex.: "paguei 2.900,00 e 100" -> [2900.0, 100.0]
    """
    if not text:
        return []
    # reconhece: 1.234,56 | 123,45 | 1,234.56 | 123.45 | 2900
    pattern = r'\b(?:\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d{1,3}(?:[.,]\d{3})+|\d+)\b'
    matches = re.findall(pattern, text)
    values = []
    for m in matches:
        try:
            values.append(parse_value_string(m))
        except Exception:
            continue
    return values

def extract_date(text):
    """Extrai dd/mm se houver."""
    if not text: return None
    match = re.search(r'(\d{1,2}/\d{1,2})', text)
    if match:
        return match.group(0)
    return None

# --------------------
# CATEGORIAS E SALVAMENTO
# --------------------
def infer_category(description):
    desc = (description or "").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category in ["Essenciais", "Desejos"]:
            continue
        for keyword in keywords:
            if keyword in desc:
                return category
    return "Outros"

def save_expense_to_csv(user_id, description, value):
    now = datetime.datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    category = infer_category(description)
    file_exists = os.path.exists(CSV_FILE_NAME)
    expense_id = 1
    if file_exists:
        try:
            with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
                # conta apenas linhas de dados
                reader = csv.reader(file, delimiter=';')
                next(reader, None)
                expense_id = sum(1 for _ in reader) + 1
        except Exception:
            expense_id = 1
    new_row = f"{user_id};{expense_id};{timestamp};{description};{value:.2f};{category}\n"
    with open(CSV_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(CSV_FILE_NAME) == 0:
            file.write("UserID;ID;Data e Hora;Descricao;Valor;Categoria\n")
        file.write(new_row)
    return category

def save_payment_to_csv(user_id, description, value):
    now = datetime.datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists(PAGAMENTOS_FILE_NAME)
    with open(PAGAMENTOS_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(PAGAMENTOS_FILE_NAME) == 0:
            file.write("UserID;Data e Hora;Descricao;Valor\n")
        file.write(f"{user_id};{timestamp};{description};{value:.2f}\n")

def save_debt_to_csv(user_id, value, description, date="Sem data"):
    new_row = f"{user_id};{date};{description};{value:.2f}\n"
    file_exists = os.path.exists(DIVIDAS_FILE_NAME)
    with open(DIVIDAS_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(DIVIDAS_FILE_NAME) == 0:
            file.write("UserID;Data de Vencimento;Descricao;Valor\n")
        file.write(new_row)
    if date != "Sem data":
        return f"✅ Dívida registrada: {description} no valor de R${value:.2f} com vencimento em {date}."
    else:
        return f"✅ Dívida registrada: {description} no valor de R${value:.2f} (sem data de vencimento)."

# --------------------
# DÍVIDAS
# --------------------
def get_debts_report(user_id):
    if not os.path.exists(DIVIDAS_FILE_NAME):
        return "Nenhuma dívida registrada ainda."
    report_lines = ["📋 *Suas Dívidas Pendentes* 📋\n"]
    total_debts, found_debts = 0.0, False
    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        next(reader, None)
        for row in reader:
            if row and len(row) >= 4 and row[0] == user_id:
                try:
                    date_due, description, value = row[1], row[2], float(row[3])
                    report_lines.append(f"- {description} (Vence: {date_due}): R${value:.2f}")
                    total_debts += value
                    found_debts = True
                except (ValueError, IndexError):
                    continue
    if not found_debts:
        return "Você não tem nenhuma dívida pendente. Parabéns! 🎉"
    report_lines.append(f"\n*Total de Dívidas: R${total_debts:.2f}*")
    return "\n".join(report_lines)

def delete_debt_from_csv(user_id, description_to_delete):
    if not os.path.exists(DIVIDAS_FILE_NAME):
        return "Não há dívidas para apagar."
    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        header = next(reader, None)
        rows = list(reader)
    new_rows = []
    debt_found = False
    for row in rows:
        if (not debt_found) and len(row) >= 4 and row[0] == user_id and description_to_delete.lower() in row[2].lower():
            debt_found = True
            continue  # pula esta dívida
        new_rows.append(row)
    with open(DIVIDAS_FILE_NAME, 'w', encoding='utf-8') as file:
        if header:
            file.write(";".join(header) + "\n")
        for r in new_rows:
            file.write(";".join(r) + "\n")
    if not debt_found:
        return f"Não encontrei a dívida '{description_to_delete}' para apagar."
    return f"✅ Dívida '{description_to_delete}' paga e removida da sua lista!"

# --------------------
# SALDO (LEITURA / ESCRITA SEGURA)
# --------------------
def get_current_balance(user_id):
    if not os.path.exists(SALDO_FILE_NAME):
        return 0.0
    with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        header = next(reader, None)
        for row in reader:
            if row and len(row) >= 2 and row[0] == user_id:
                try:
                    return float(row[1])
                except Exception:
                    return 0.0
    return 0.0

def set_balance(user_id, value):
    balances = {}
    if os.path.exists(SALDO_FILE_NAME):
        with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            header = next(reader, None)
            for row in reader:
                if not row: continue
                uid = row[0]
                try:
                    balances[uid] = float(row[1])
                except Exception:
                    balances[uid] = 0.0
    # atualiza o usuário
    balances[user_id] = float(value)
    # reescreve o arquivo com cabeçalho
    with open(SALDO_FILE_NAME, 'w', encoding='utf-8') as f:
        f.write("UserID;Saldo\n")
        for uid, bal in balances.items():
            f.write(f"{uid};{bal:.2f}\n")
    return f"✅ Saldo atualizado! Seu novo saldo é de *R${value:.2f}*."

def record_payment_and_update_balance(user_id, value, description="Pagamento"):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance + float(value)
        # Atualiza o saldo
        set_balance(user_id, new_balance)
        # Salva pagamento
        save_payment_to_csv(user_id, description, value)
        today_str = datetime.datetime.datetime.now(TIMEZONE).strftime("%d/%m")
        return f"✅ Pagamento de R${float(value):.2f} registrado em {today_str}!\n\nSeu saldo atual é de *R${new_balance:.2f}*."
    except Exception as e:
        return f"Ocorreu um erro ao registrar o pagamento: {e}"

def record_expense_and_update_balance(user_id, value):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance - float(value)
        set_balance(user_id, new_balance)
        return True
    except Exception:
        return False

# --------------------
# RELATÓRIOS (Entradas / Saídas / Períodos)
# --------------------
def _period_bounds(period: str):
    now = datetime.datetime.datetime.now(TIMEZONE)
    if period == "dia":
        return ("hoje", now.strftime("%Y-%m-%d"), None)  # name, start_str, start_date
    if period == "semana":
        start = (now.date() - datetime.timedelta(days=now.weekday()))
        return ("na semana", None, start)
    if period == "mês" or period == "mes":
        return ("no mês", now.strftime("%Y-%m"), None)
    return ("", None, None)

def get_io_summary(user_id, period):
    nome, start_str, start_date = _period_bounds(period)
    total_in = 0.0
    total_out = 0.0

    # Saídas (meus_gastos.csv)
    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            next(reader, None)
            for row in reader:
                if not row or len(row) < 5: continue
                if row[0] != user_id: continue
                timestamp = row[2]  # yyyy-mm-dd HH:MM:SS
                try:
                    value = float(row[4])
                except Exception:
                    continue
                if start_date:
                    try:
                        row_date = datetime.datetime.strptime(timestamp.split(' ')[0], "%Y-%m-%d").date()
                        if row_date >= start_date:
                            total_out += value
                    except Exception:
                        continue
                elif start_str:
                    if timestamp.startswith(start_str):
                        total_out += value

    # Entradas (pagamentos.csv)
    if os.path.exists(PAGAMENTOS_FILE_NAME):
        with open(PAGAMENTOS_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            next(reader, None)
            for row in reader:
                if not row or len(row) < 4: continue
                if row[0] != user_id: continue
                timestamp = row[1]
                try:
                    value = float(row[3])
                except Exception:
                    continue
                if start_date:
                    try:
                        row_date = datetime.datetime.strptime(timestamp.split(' ')[0], "%Y-%m-%d").date()
                        if row_date >= start_date:
                            total_in += value
                    except Exception:
                        continue
                elif start_str:
                    if timestamp.startswith(start_str):
                        total_in += value

    return f"💸 *Balanço {nome}*\n\n- Entradas: *R${total_in:.2f}*\n- Saídas: *R${total_out:.2f}*"

def get_period_report(user_id, period):
    if not os.path.exists(CSV_FILE_NAME):
        return "Nenhum gasto registrado ainda."
    total = 0.0
    nome, start_str, start_date = _period_bounds(period)
    report_lines = [f"🧾 Seus gastos {nome} 🧾\n"]
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        next(reader, None)
        for row in reader:
            if not row or len(row) < 5: continue
            if row[0] != user_id: continue
            timestamp = row[2]
            description = row[3]
            try:
                value = float(row[4])
            except Exception:
                continue
            match = False
            if start_date:
                try:
                    row_date = datetime.datetime.strptime(timestamp.split(' ')[0], "%Y-%m-%d").date()
                    if row_date >= start_date:
                        match = True
                except Exception:
                    match = False
            elif start_str:
                if timestamp.startswith(start_str):
                    match = True
            if match:
                report_lines.append(f"- {description}: R${value:.2f}")
                total += value
    if len(report_lines) == 1:
        return f"Nenhum gasto registrado {nome}."
    report_lines.append(f"\n*Total gasto: R${total:.2f}*")
    return "\n".join(report_lines)

# --------------------
# DELETA ÚLTIMO GASTO
# --------------------
def delete_last_expense(user_id):
    if not os.path.exists(CSV_FILE_NAME):
        return "Não há gastos para apagar."
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        header = next(reader, None)
        rows = list(reader)
    # procura última linha do usuário
    idx_to_remove = -1
    for i in range(len(rows)-1, -1, -1):
        try:
            if rows[i][0] == user_id:
                idx_to_remove = i
                break
        except Exception:
            continue
    if idx_to_remove == -1:
        return "Você não tem gastos registados para apagar."
    deleted = rows.pop(idx_to_remove)
    # reescreve arquivo
    with open(CSV_FILE_NAME, 'w', encoding='utf-8') as file:
        if header:
            file.write(";".join(header) + "\n")
        for r in rows:
            file.write(";".join(r) + "\n")
    try:
        deleted_description = deleted[3]
        deleted_value = float(deleted[4])
    except Exception:
        deleted_description = deleted[3] if len(deleted) > 3 else "Descrição desconhecida"
        deleted_value = 0.0
    # devolve o valor ao saldo
    record_payment_and_update_balance(user_id, deleted_value, description=f"Reembolso (apagar gasto): {deleted_description}")
    return f"🗑️ Último gasto apagado!\n- Descrição: {deleted_description}\n- Valor: R${deleted_value:.2f}"

# --------------------
# RESUMOS E UTILIDADES
# --------------------
def get_financial_summary(user_id):
    balance = get_current_balance(user_id)
    return f"💰 *Resumo Financeiro*\nSeu saldo atual é: *R${balance:.2f}*."

# --------------------
# FUNÇÕES AUXILIARES (stubs / helpers implementados para evitar erros em produção)
# --------------------
def set_income(user_id, value):
    """Grava rendimento (simples) no ORÇAMENTO."""
    incomes = {}
    if os.path.exists(ORCAMENTO_FILE_NAME):
        with open(ORCAMENTO_FILE_NAME, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader, None)
            for row in reader:
                if not row: continue
                incomes[row[0]] = row[1]
    incomes[user_id] = f"{float(value):.2f}"
    with open(ORCAMENTO_FILE_NAME, 'w', encoding='utf-8') as f:
        f.write("UserID;Rendimento\n")
        for uid, val in incomes.items():
            f.write(f"{uid};{val}\n")
    return f"✅ Rendimento definido como R${float(value):.2f}."

def get_budget_report(user_id):
    """Relatório básico de orçamento comparando renda vs gastos do mês atual."""
    rendimento = 0.0
    if os.path.exists(ORCAMENTO_FILE_NAME):
        with open(ORCAMENTO_FILE_NAME, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        rendimento = float(row[1])
                    except Exception:
                        rendimento = 0.0
    # soma gastos do mês
    now = datetime.datetime.datetime.now(TIMEZONE)
    month_prefix = now.strftime("%Y-%m")
    gastos_mes = 0.0
    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    if row[2].startswith(month_prefix):
                        try:
                            gastos_mes += float(row[4])
                        except Exception:
                            continue
    return f"📊 Orçamento:\nRendimento: R${rendimento:.2f}\nGastos este mês: R${gastos_mes:.2f}\nSaldo estimado: R${(rendimento - gastos_mes):.2f}"

def get_financial_tip():
    tips = [
        "Anote todos os seus gastos diários: conhecimento é controle.",
        "Separe uma reserva de emergência com 3-6 meses de despesas.",
        "Revise assinaturas e serviços que você não usa todo mês.",
        "Defina metas pequenas e alcançáveis — consistência vence velocidade.",
        "Priorize pagar dívidas com juros altos primeiro."
    ]
    return random.choice(tips)

def compare_expenses(user_id):
    """
    Compara gastos entre o mês atual e o anterior (resumo simples).
    """
    now = datetime.datetime.datetime.now(TIMEZONE)
    this_month = now.strftime("%Y-%m")
    last_month_date = (now.replace(day=1) - datetime.timedelta(days=1))
    last_month = last_month_date.strftime("%Y-%m")
    sums = {this_month: 0.0, last_month: 0.0}
    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        ts = row[2]
                        val = float(row[4])
                        if ts.startswith(this_month):
                            sums[this_month] += val
                        elif ts.startswith(last_month):
                            sums[last_month] += val
                    except Exception:
                        continue
    diff = sums[this_month] - sums[last_month]
    sign = "+" if diff >= 0 else "-"
    return f"📈 Comparação de gastos:\nMês atual ({this_month}): R${sums[this_month]:.2f}\nMês anterior ({last_month}): R${sums[last_month]:.2f}\nDiferença: {sign}R${abs(diff):.2f}"

# --------------------
# ENVIO DE MENSAGEM (WhatsApp API)
# --------------------
def send_whatsapp_message(phone_number, message_text):
    try:
        if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
            # apenas log local quando variáveis não configuradas
            print(f"[DEBUG] não foi possível enviar (credenciais ausentes). Dest: {phone_number}\nMsg: {message_text}")
            return
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
        data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar mensagem para {phone_number}: {e}")

# --------------------
# ROTA DE WEBHOOK (PRINCIPAL) - MELHORIAS AQUI
# --------------------
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return 'Failed verification', 403

    if request.method == 'POST':
        data = request.get_json()
        try:
            value = data['entry'][0]['changes'][0]['value']
            if 'messages' not in value:
                return 'EVENT_RECEIVED', 200

            message_data = value['messages'][0]
            user_id = message_data['from']
            user_name = value['contacts'][0].get('profile', {}).get('name', 'Pessoa')
            raw_text = message_data['text']['body'].strip()
            message_text = raw_text.lower()
            norm_text = normalize_text(raw_text)

            reply_message = ""

            # --- LÓGICA DE COMANDOS REESTRUTURADA (usando norm_text para reconhecer variações) ---

            # 1. Saudações / Ajuda
            if contains_any(norm_text, ["oi", "ola", "olá", "ajuda", "comandos", "menu"]):
                reply_message = f"Olá, {user_name}! 👋\n\n{COMMANDS_MESSAGE}"

            # 2. Dívidas
            elif contains_any(norm_text, ["quais as minhas dividas", "minhas dividas", "ver dividas", "relatorio de dividas", "relatório de dividas"]):
                reply_message = get_debts_report(user_id)

            # 3. Definir rendimento
            elif "definir rendimento" in norm_text or "meu rendimento" in norm_text:
                values = extract_all_monetary_values(raw_text)
                if values:
                    reply_message = set_income(user_id, values[0])
                else:
                    reply_message = "Não entendi o valor. Tente `definir rendimento [valor]`."

            # 4. Meu orçamento
            elif "meu orcamento" in norm_text or "meu orçamento" in norm_text:
                reply_message = get_budget_report(user_id)

            # 5. Dica financeira
            elif "dica" in norm_text:
                reply_message = get_financial_tip()

            # 6. Comparar gastos
            elif "comparar gastos" in norm_text or "comparar despesas" in norm_text:
                reply_message = compare_expenses(user_id)

            # 7. Resumo financeiro
            elif "resumo financeiro" in norm_text or "resumo" in norm_text:
                reply_message = get_financial_summary(user_id)

            # 8. Ver saldo
            elif contains_any(norm_text, ["qual o meu saldo", "meu saldo", "ver saldo", "saldo atual", "como esta meu saldo"]):
                balance = get_current_balance(user_id)
                reply_message = f"💵 Seu saldo atual é de *R${balance:.2f}*."

            # 9. Apagar último
            elif contains_any(norm_text, ["apagar ultimo", "apagar último", "excluir ultimo", "excluir último"]):
                reply_message = delete_last_expense(user_id)

            # 10. Metas/Recorrentes (placeholder)
            elif "meta" in norm_text or "recorrente" in norm_text:
                reply_message = "Esta funcionalidade ainda está em desenvolvimento, mas fico feliz que você se interessou! 😉"

            # 11. Relatórios de gastos (aceita 'relatorio' sem acento)
            elif ("gastos" in norm_text and ("dia" in norm_text or "hoje" in norm_text)) or "relatorio do dia" in norm_text or "relatório do dia" in norm_text:
                reply_message = get_period_report(user_id, "dia")
            elif ("gastos" in norm_text and "semana" in norm_text) or ("relatorio" in norm_text and "semana" in norm_text):
                reply_message = get_period_report(user_id, "semana")
            elif ("gastos" in norm_text and ("mes" in norm_text or "mês" in norm_text)) or ("relatorio" in norm_text and ("mes" in norm_text or "mês" in norm_text)):
                reply_message = get_period_report(user_id, "mês")

            # 12. Entradas e saídas (variações)
            elif any(k in norm_text for k in ["entrada e saida", "entrada e saída", "entrou e saiu", "quanto entrou", "entradas e saidas"]):
                if "hoje" in norm_text or "dia" in norm_text:
                    reply_message = get_io_summary(user_id, "dia")
                elif "semana" in norm_text:
                    reply_message = get_io_summary(user_id, "semana")
                elif "mes" in norm_text or "mês" in norm_text:
                    reply_message = get_io_summary(user_id, "mês")
                else:
                    reply_message = get_io_summary(user_id, "dia")

            # 13. Pagamento de dívida (pagar uma dívida registrada)
            elif any(keyword in norm_text for keyword in ["pagamento de divida", "paguei a divida", "paguei a conta", "paguei a dívida"]):
                description = re.sub(r'(pagamento de divida|paguei a divida|paguei a conta|paguei a dívida)', '', norm_text).strip()
                reply_message = delete_debt_from_csv(user_id, description)
                values = extract_all_monetary_values(raw_text)
                if values:
                    save_expense_to_csv(user_id, f"Pagamento de Dívida: {description.capitalize()}", values[0])
                    record_expense_and_update_balance(user_id, values[0])

            # 14. Registrar dívida
            elif any(keyword in norm_text for keyword in ["divida", "parcela", "vence", "vencimento", "venc"]):
                values = extract_all_monetary_values(raw_text)
                date = extract_date(raw_text)
                if values:
                    description = re.sub(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+)', ' ', raw_text).strip()
                    description = re.sub(r'(vence dia.*|divida|parcela)', '', description, flags=re.I).strip()
                    reply_message = save_debt_to_csv(user_id, values[0], description.capitalize() or "Dívida", date=date or "Sem data")
                else:
                    reply_message = "Entendi que é uma dívida, mas não consegui identificar o valor."

            # 15. Pagamentos / Receitas
            elif any(keyword in norm_text for keyword in ["pagamento", "recebi", "salario", "ganhei", "deposito", "recebido", "entrada"]):
                values = extract_all_monetary_values(raw_text)
                if not values:
                    reply_message = "Entendi que é um pagamento, mas não consegui identificar o valor."
                elif any(keyword in norm_text for keyword in ["ja tinha", "ja tinha na conta", "tinha na conta", "já tinha"]):
                    total_balance = sum(values)
                    reply_message = set_balance(user_id, total_balance)
                else:
                    payment_value = max(values)
                    description = re.sub(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+)', ' ', raw_text).strip()
                    reply_message = record_payment_and_update_balance(user_id, payment_value, description.capitalize() or "Pagamento")

            # 16. Fallback -> assume gasto
            else:
                values = extract_all_monetary_values(raw_text)
                if values:
                    value = values[0]
                    description = re.sub(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+)', ' ', raw_text).strip()
                    # remove preposições no início
                    description = re.sub(r'^(de|da|do|no|na)\s', '', description, flags=re.I)
                    if not description:
                        if "perdi" in norm_text:
                            description = "Perda"
                        else:
                            reply_message = "Parece que você enviou um valor sem descrição. Tente de novo, por favor."
                    if description:
                        category = save_expense_to_csv(user_id, description.capitalize(), value)
                        record_expense_and_update_balance(user_id, value)
                        today_str = datetime.datetime.datetime.now(TIMEZONE).strftime("%d/%m")
                        reply_message = f"✅ Gasto Registrado em {today_str}! ({category})\n- {description.capitalize()}: R${float(value):.2f}"
                else:
                    reply_message = f"Não entendi, {user_name}. Se for um gasto, tente `[descrição] [valor]`. Se precisar de ajuda, envie `comandos`."

            # Envia resposta (se houver)
            if reply_message:
                send_whatsapp_message(user_id, reply_message)

        except (KeyError, IndexError, TypeError) as e:
            print(f"Erro ao processar o webhook: {e}")
            # não quebrar: retornamos sucesso para o provedor de webhook
            pass

        return 'EVENT_RECEIVED', 200

# Healthcheck simples
@app.route('/health', methods=['GET'])
def health():
    return 'OK', 200

# Rodar localmente (apenas para testes; em produção o servidor do host/provedor cuida disso)
if __name__ == "__main__":
    # Porta padrão 5000; ajuste conforme necessário
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
