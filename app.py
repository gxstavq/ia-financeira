# Importa as ferramentas necessárias
from flask import Flask, request
import json
import requests
import datetime
import os
import csv
import re  # Importado para a análise de texto
import random  # Importado para as dicas financeiras
import unicodedata  # Para normalizar texto (tirar acentos)
from collections import defaultdict

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
# Utilitários
# --------------------

def normalize_text(s: str) -> str:
    """Remove acentos, transforma em minúsculas e limpa espaços extras."""
    if not isinstance(s, str): return ""
    s = s.strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\s+', ' ', s)
    return s

def contains_any(s: str, patterns) -> bool:
    """Verifica se alguma string ou regex na lista aparece em s (s já deve ser normalizado)."""
    for p in patterns:
        if isinstance(p, str):
            if p in s:
                return True
        else:
            # assume regex
            try:
                if p.search(s):
                    return True
            except Exception:
                pass
    return False

# Função centralizada para atualizar o arquivo de saldo
def _write_balance_file(balance_map: dict):
    """Escreve o mapa de saldos no arquivo SALDO_FILE_NAME com cabeçalho."""
    os.makedirs(os.path.dirname(SALDO_FILE_NAME) or '.', exist_ok=True)
    with open(SALDO_FILE_NAME, 'w', encoding='utf-8') as f:
        f.write("UserID;Saldo\n")
        for uid, bal in balance_map.items():
            f.write(f"{uid};{float(bal):.2f}\n")

def _read_balance_file() -> dict:
    """Lê o arquivo de saldos e retorna um dict {user_id: saldo}."""
    balances = {}
    if not os.path.exists(SALDO_FILE_NAME):
        return balances
    with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader, None)  # pula cabeçalho se existir
        for row in reader:
            if not row: continue
            try:
                uid = row[0]
                bal = float(row[1]) if len(row) > 1 and row[1] != '' else 0.0
                balances[uid] = bal
            except Exception:
                continue
    return balances

# --------------------
# Parsing de valores (robusto)
# --------------------
def parse_value_string(s):
    """
    Converte strings numéricas em float com suporte a formatos BR/EN:
      - 2900 -> 2900.0
      - 2.900 -> 2900.0
      - 2.900,00 -> 2900.0
      - 1,234.56 -> 1234.56
      - 1234,56 -> 1234.56
    """
    if not isinstance(s, str):
        return float(s)
    s = s.strip()
    # remove moedas e espaços
    s = s.replace('R$', '').replace('$', '').strip()

    # se tem letras, tira tudo exceto dígitos e separadores
    s = re.sub(r'[^\d,.-]', '', s)

    # casos com ambos separadores
    if ',' in s and '.' in s:
        # decide pelo último separador (virgula ou ponto)
        if s.rfind(',') > s.rfind('.'):
            # formato BR: 1.234,56 -> remove pontos, troca vírgula por ponto
            s = s.replace('.', '').replace(',', '.')
        else:
            # formato EN: 1,234.56 -> remove vírgulas
            s = s.replace(',', '')
    elif ',' in s:
        # apenas vírgula: geralmente decimal no BR
        s = s.replace('.', '').replace(',', '.')
    elif '.' in s:
        # apenas ponto: pode ser decimal (ex 123.45) ou milhar (ex 2.900)
        parts = s.split('.')
        if len(parts) > 1 and len(parts[-1]) == 3:
            # provavelmente milhar
            s = s.replace('.', '')
        # caso contrário mantém o ponto como decimal

    # fallback final
    try:
        return float(s)
    except Exception:
        # extrai números e junta (fallback)
        nums = re.findall(r'\d+', s)
        if nums:
            return float(''.join(nums))
        raise

def extract_all_monetary_values(text):
    """
    Extrai valores monetários do texto aceitando múltiplos formatos.
    Retorna lista de floats.
    """
    if not isinstance(text, str):
        return []
    # procura formatos com separadores ou números simples
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
    """Extrai data no formato dd/mm ou dd/mm/aaaa se houver."""
    if not isinstance(text, str): return None
    match = re.search(r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)', text)
    if match:
        return match.group(0)
    return None

# --------------------
# Categorias e gravação
# --------------------
def infer_category(description):
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category in ["Essenciais", "Desejos"]:
            continue
        for keyword in keywords:
            if keyword in description.lower():
                return category
    return "Outros"

def save_expense_to_csv(user_id, description, value):
    now = datetime.datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    category = infer_category(description)
    os.makedirs(os.path.dirname(CSV_FILE_NAME) or '.', exist_ok=True)
    file_exists = os.path.exists(CSV_FILE_NAME)
    expense_id = 1
    if file_exists and os.path.getsize(CSV_FILE_NAME) > 0:
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
            expense_id = sum(1 for line in file)
    new_row = f"{user_id};{expense_id};{timestamp};{description};{value:.2f};{category}\n"
    with open(CSV_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(CSV_FILE_NAME) == 0:
            file.write("UserID;ID;Data e Hora;Descricao;Valor;Categoria\n")
        file.write(new_row)
    return category

def save_payment_to_csv(user_id, description, value):
    now = datetime.datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(PAGAMENTOS_FILE_NAME) or '.', exist_ok=True)
    file_exists = os.path.exists(PAGAMENTOS_FILE_NAME)
    with open(PAGAMENTOS_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(PAGAMENTOS_FILE_NAME) == 0:
            file.write("UserID;Data e Hora;Descricao;Valor\n")
        file.write(f"{user_id};{timestamp};{description};{value:.2f}\n")

def save_debt_to_csv(user_id, value, description, date="Sem data"):
    new_row = f"{user_id};{date};{description};{value:.2f}\n"
    os.makedirs(os.path.dirname(DIVIDAS_FILE_NAME) or '.', exist_ok=True)
    file_exists = os.path.exists(DIVIDAS_FILE_NAME)
    with open(DIVIDAS_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(DIVIDAS_FILE_NAME) == 0:
            file.write("UserID;Data de Vencimento;Descricao;Valor\n")
        file.write(new_row)
    if date != "Sem data":
        return f"✅ Dívida registrada: {description} no valor de R${value:.2f} com vencimento em {date}."
    else:
        return f"✅ Dívida registrada: {description} no valor de R${value:.2f} (sem data de vencimento)."

def get_debts_report(user_id):
    if not os.path.exists(DIVIDAS_FILE_NAME):
        return "Nenhuma dívida registrada ainda."
    report_lines = ["📋 *Suas Dívidas Pendentes* 📋\n"]
    total_debts, found_debts = 0.0, False
    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
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
    lines, debt_found = [], False
    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    with open(DIVIDAS_FILE_NAME, 'w', encoding='utf-8') as file:
        for line in lines:
            parts = line.strip().split(';')
            if not debt_found and len(parts) > 2 and parts[0] == user_id and description_to_delete.lower() in parts[2].lower():
                debt_found = True
                # pula esta linha (apagar)
            else:
                file.write(line)
    if not debt_found:
        return f"Não encontrei a dívida '{description_to_delete}' para apagar."
    return f"✅ Dívida '{description_to_delete}' paga e removida da sua lista!"

# --------------------
# Saldo (centralizado)
# --------------------
def get_current_balance(user_id):
    balances = _read_balance_file()
    return float(balances.get(user_id, 0.0))

def update_balance(user_id, new_balance):
    balances = _read_balance_file()
    balances[user_id] = float(new_balance)
    _write_balance_file(balances)

def set_balance(user_id, value):
    update_balance(user_id, value)
    return f"✅ Saldo atualizado! Seu novo saldo é de *R${float(value):.2f}*."

def record_payment_and_update_balance(user_id, value, description="Pagamento"):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance + float(value)
        update_balance(user_id, new_balance)
        save_payment_to_csv(user_id, description, value)
        today_str = datetime.datetime.datetime.now(TIMEZONE).strftime("%d/%m")
        return f"✅ Pagamento de R${float(value):.2f} registrado em {today_str}!\n\nSeu saldo atual é de *R${new_balance:.2f}*."
    except Exception as e:
        return f"Ocorreu um erro ao registrar o pagamento: {e}"

def record_expense_and_update_balance(user_id, value):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance - float(value)
        update_balance(user_id, new_balance)
        return True
    except Exception:
        return False

# --------------------
# Relatórios (entradas/saídas, períodos)
# --------------------
def _period_bounds(period: str):
    now = datetime.datetime.datetime.now(TIMEZONE)
    period = normalize_text(period or "")
    if period in ["dia", "hoje"]:
        return ("hoje", now.strftime("%Y-%m-%d"), None)
    if period in ["semana", "semana atual", "na semana"]:
        start = (now.date() - datetime.timedelta(days=now.weekday()))
        return ("na semana", None, start)
    if period in ["mês", "mes", "no mes", "no mês"]:
        return ("no mês", now.strftime("%Y-%m"), None)
    # padrão: dia
    return ("hoje", now.strftime("%Y-%m-%d"), None)

def get_io_summary(user_id, period):
    period_name, start_str, start_date = _period_bounds(period)
    total_in, total_out = 0.0, 0.0

    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        timestamp = row[2]  # yyyy-mm-dd HH:MM:SS
                        value = float(row[4])
                    except Exception:
                        continue
                    if start_date:
                        if datetime.datetime.datetime.strptime(timestamp[:10], "%Y-%m-%d").date() >= start_date:
                            total_out += value
                    else:
                        if timestamp.startswith(start_str):
                            total_out += value

    if os.path.exists(PAGAMENTOS_FILE_NAME):
        with open(PAGAMENTOS_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        timestamp = row[1]
                        value = float(row[3])
                    except Exception:
                        continue
                    if start_date:
                        if datetime.datetime.datetime.strptime(timestamp[:10], "%Y-%m-%d").date() >= start_date:
                            total_in += value
                    else:
                        if timestamp.startswith(start_str):
                            total_in += value

    return f"💸 *Balanço {period_name}*\n\n- Entradas: *R${total_in:.2f}*\n- Saídas: *R${total_out:.2f}*"

def get_period_report(user_id, period):
    if not os.path.exists(CSV_FILE_NAME):
        return "Nenhum gasto registrado ainda."
    total = 0.0
    period_name, start_str, start_date = _period_bounds(period)
    report_lines = [f"🧾 Seus gastos {period_name} 🧾\n"]
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                try:
                    timestamp = row[2]
                    value = float(row[4])
                    description = row[3]
                except Exception:
                    continue
                match = False
                if start_date:
                    if datetime.datetime.datetime.strptime(timestamp[:10], "%Y-%m-%d").date() >= start_date:
                        match = True
                else:
                    if timestamp.startswith(start_str):
                        match = True
                if match:
                    report_lines.append(f"- {description}: R${value:.2f}")
                    total += value
    if len(report_lines) == 1:
        return f"Nenhum gasto registrado {period_name}."
    report_lines.append(f"\n*Total gasto: R${total:.2f}*")
    return "\n".join(report_lines)

# --------------------
# Ações de edição/remoção
# --------------------
def delete_last_expense(user_id):
    if not os.path.exists(CSV_FILE_NAME):
        return "Não há gastos para apagar."
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    last_expense_of_user = -1
    # percorre do final, pula cabeçalho (index 0)
    for i in range(len(lines) - 1, 0, -1):
        parts = lines[i].strip().split(';')
        if parts and parts[0] == user_id:
            last_expense_of_user = i
            break
    if last_expense_of_user == -1:
        return "Você não tem gastos registados para apagar."
    deleted_line = lines.pop(last_expense_of_user).strip().split(';')
    try:
        deleted_description, deleted_value = deleted_line[3], float(deleted_line[4])
    except Exception:
        deleted_description, deleted_value = deleted_line[3] if len(deleted_line) > 3 else "Despesa", 0.0
    with open(CSV_FILE_NAME, 'w', encoding='utf-8') as file:
        file.writelines(lines)
    # devolve o valor ao saldo (registrando como pagamento)
    record_payment_and_update_balance(user_id, deleted_value, f"Reembolso: {deleted_description}")
    return f"🗑️ Último gasto apagado!\n- Descrição: {deleted_description}\n- Valor: R${deleted_value:.2f}"

# --------------------
# Resumo financeiro e outros utilitários
# --------------------
def get_financial_summary(user_id):
    balance = get_current_balance(user_id)
    return f"💰 *Resumo Financeiro*\nSeu saldo atual é: *R${balance:.2f}*."

# --------------------
# Funções adicionais (placeholders implementadas)
# --------------------
def set_income(user_id, value):
    """Define rendimento do usuário (salva em ORCAMENTO_FILE_NAME)."""
    os.makedirs(os.path.dirname(ORCAMENTO_FILE_NAME) or '.', exist_ok=True)
    rows = {}
    if os.path.exists(ORCAMENTO_FILE_NAME):
        with open(ORCAMENTO_FILE_NAME, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader, None)
            for row in reader:
                if row:
                    rows[row[0]] = float(row[1]) if len(row) > 1 and row[1] != '' else 0.0
    rows[user_id] = float(value)
    with open(ORCAMENTO_FILE_NAME, 'w', encoding='utf-8') as f:
        f.write("UserID;Rendimento\n")
        for uid, val in rows.items():
            f.write(f"{uid};{float(val):.2f}\n")
    return f"✅ Rendimento definido para R${float(value):.2f}."

def get_budget_report(user_id):
    """Relatório simples do orçamento (placeholder)."""
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
    return f"📋 *Orçamento*\nRendimento mensal: R${rendimento:.2f}\n(Função de orçamento completa em desenvolvimento.)"

def compare_expenses(user_id):
    """Comparar gastos (placeholder simplório)."""
    return "📊 Comparação de gastos (ainda simples) — essa funcionalidade pode ser expandida para comparar meses/semana."

def get_financial_tip():
    tips = [
        "Guarde pelo menos 10% da sua renda todo mês.",
        "Crie um fundo de emergência equivalente a 3-6 meses de despesas.",
        "Revise assinaturas mensais que você não usa.",
        "Use a regra 50/30/20 para distribuir seus ganhos: necessidades/desejos/poupança.",
        "Anote todos os gastos por 30 dias para entender para onde vai seu dinheiro."
    ]
    return random.choice(tips)

# --------------------
# Webhook principal (com normalização e reconhecimento flexível)
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
            message_text = raw_text  # manter original para extração
            norm_text = normalize_text(raw_text)

            reply_message = ""

            # --- LÓGICA DE COMANDOS REESTRUTURADA (usando norm_text para matching) ---

            # 1. Saudações / ajuda
            if contains_any(norm_text, ["oi", "ola", "olá", "ajuda", "comandos", "menu"]):
                reply_message = f"Olá, {user_name}! 👋\n\n{COMMANDS_MESSAGE}"

            # 2. Dívidas
            elif contains_any(norm_text, ["quais as minhas dividas", "minhas dividas", "ver dividas", "relatorio de dividas", "relatório de dívidas", "minhas dívidas"]):
                reply_message = get_debts_report(user_id)

            # 3. Definir rendimento
            elif "definir rendimento" in norm_text or "meu rendimento e" in norm_text or "meu rendimento é" in norm_text:
                values = extract_all_monetary_values(message_text)
                if values:
                    reply_message = set_income(user_id, values[0])
                else:
                    reply_message = "Não entendi o valor. Tente `definir rendimento [valor]`."

            # 4. Orçamento
            elif "meu orcamento" in norm_text or "meu orçamento" in norm_text:
                reply_message = get_budget_report(user_id)

            # 5. Dica financeira
            elif "dica" in norm_text:
                reply_message = get_financial_tip()

            # 6. Comparar gastos
            elif "comparar gastos" in norm_text:
                reply_message = compare_expenses(user_id)

            # 7. Resumo financeiro
            elif "resumo financeiro" in norm_text:
                reply_message = get_financial_summary(user_id)

            # 8. Saldo
            elif contains_any(norm_text, ["qual o meu saldo", "meu saldo", "ver saldo", "saldo atual", "como esta meu saldo", "como está meu saldo"]):
                balance = get_current_balance(user_id)
                reply_message = f"💵 Seu saldo atual é de *R${balance:.2f}*."

            # 9. Apagar último gasto
            elif contains_any(norm_text, ["apagar ultimo", "apagar último", "excluir ultimo", "excluir último"]):
                reply_message = delete_last_expense(user_id)

            # 10. Meta/recorrente (placeholder)
            elif "meta" in norm_text or "recorrente" in norm_text:
                reply_message = "Esta funcionalidade ainda está em desenvolvimento, mas fico feliz que você se interessou! 😉"

            # 11. Relatórios de gastos (dia/semana/mês)
            elif contains_any(norm_text, ["gastos do dia", "gastos da semana", "gastos do mes", "gastos do mês", "relatorio do dia", "relatório do dia", "gastos hoje", "gastos da semana", "meus gastos"]):
                if "hoje" in norm_text or "dia" in norm_text:
                    reply_message = get_period_report(user_id, "dia")
                elif "semana" in norm_text:
                    reply_message = get_period_report(user_id, "semana")
                elif "mes" in norm_text or "mês" in norm_text:
                    reply_message = get_period_report(user_id, "mês")
                else:
                    reply_message = "Não entendi o período. Tente `gastos do dia`, `gastos da semana` ou `gastos do mês`."

            # 12. Entradas e saídas / balanço do período
            elif contains_any(norm_text, ["entrada e saida", "entrada e saida", "entrada e saída", "entrou e saiu", "quanto entrou", "quanto entrou e saiu", "entradas e saidas", "entradas e saídas", "resumo do dia", "relatorio do dia", "relatório do dia"]):
                if "hoje" in norm_text or "dia" in norm_text:
                    reply_message = get_io_summary(user_id, "dia")
                elif "semana" in norm_text:
                    reply_message = get_io_summary(user_id, "semana")
                elif "mes" in norm_text or "mês" in norm_text:
                    reply_message = get_io_summary(user_id, "mês")
                else:
                    reply_message = get_io_summary(user_id, "dia")

            # 13. Pagamento de dívida / quitar dívida
            elif contains_any(norm_text, ["pagamento de divida", "paguei a divida", "paguei a conta", "paguei a dívida", "pagamento de dívida", "paguei a dívida"]):
                # extrai descrição do texto normalizado; valores do texto original
                desc = re.sub(r'(pagamento de divida|paguei a divida|paguei a conta|paguei a dívida|pagamento de dívida)', '', norm_text).strip()
                reply_message = delete_debt_from_csv(user_id, desc)
                values = extract_all_monetary_values(message_text)
                if values:
                    save_expense_to_csv(user_id, f"Pagamento de Dívida: {desc.capitalize() or 'Dívida'}", values[0])
                    record_expense_and_update_balance(user_id, values[0])

            # 14. Registrar dívida
            elif contains_any(norm_text, ["divida", "parcela", "vence", "vencimento", "vencimentos"]):
                values = extract_all_monetary_values(message_text)
                date = extract_date(message_text)
                if values:
                    description = re.sub(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+|r\$)', ' ', message_text, flags=re.I).strip()
                    description = re.sub(r'vence dia.*|vencimento.*|dívida|divida|parcela', '', description, flags=re.I).strip()
                    reply_message = save_debt_to_csv(user_id, values[0], description.capitalize() or "Dívida", date=date if date else "Sem data")
                else:
                    reply_message = "Entendi que é uma dívida, mas não consegui identificar o valor."

            # 15. Pagamentos / Receitas
            elif contains_any(norm_text, ["pagamento", "recebi", "salario", "salário", "ganhei", "deposito", "depósito"]):
                values = extract_all_monetary_values(message_text)
                if not values:
                    reply_message = "Entendi que é um pagamento, mas não consegui identificar o valor."
                elif contains_any(norm_text, ["ja tinha", "já tinha", "tinha na conta", "ja tinha na conta"]):
                    total_balance = sum(values)
                    reply_message = set_balance(user_id, total_balance)
                else:
                    payment_value = max(values)
                    description = re.sub(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+|r\$)', ' ', message_text, flags=re.I).strip()
                    reply_message = record_payment_and_update_balance(user_id, payment_value, description.capitalize() or "Pagamento")

            # 16. Fallback: assume gasto
            else:
                values = extract_all_monetary_values(message_text)
                if values:
                    value = values[0]
                    description = re.sub(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+|r\$)', ' ', message_text, flags=re.I).strip()
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
                        reply_message = f"✅ Gasto Registrado em {today_str}! ({category})\n- {description.capitalize()}: R${value:.2f}"
                else:
                    reply_message = f"Não entendi, {user_name}. Se for um gasto, tente `[descrição] [valor]`. Se precisar de ajuda, envie `comandos`."

            if reply_message:
                send_whatsapp_message(user_id, reply_message)

        except (KeyError, IndexError, TypeError) as e:
            print(f"Erro ao processar o webhook: {e}")
            # não explodir o endpoint em produção
            pass

        return 'EVENT_RECEIVED', 200

# --------------------
# Envio de mensagem via WhatsApp (Facebook Graph)
# --------------------
def send_whatsapp_message(phone_number, message_text):
    try:
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
        data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar mensagem para {phone_number}: {e}")

# --------------------
# Se quiser rodar em local (apenas para debug)
# --------------------
if __name__ == "__main__":
    # roda em 0.0.0.0 para que possa ser exposto pelo servidor (ajuste conforme necessário)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
