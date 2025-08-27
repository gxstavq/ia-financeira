# Importa as ferramentas necessárias
from flask import Flask, request
import json
import requests
import datetime
import os
import csv
import re
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
SALDO_FILE_NAME = os.path.join(DATA_DIR, "saldo.csv")
DIVIDAS_FILE_NAME = os.path.join(DATA_DIR, "dividas.csv")
REMINDERS_SENT_FILE = os.path.join(DATA_DIR, "lembretes_enviados.csv")
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# Mensagem de boas-vindas com os comandos disponíveis
COMMANDS_MESSAGE = """
Eu sou a sua IA de controle financeiro.
Você pode me enviar os seguintes comandos:

💰 **Gastos e Saldo:**
- **Adicionar gasto:** `[descrição] [valor]` (Ex: `Almoço 25`)
- **Adicionar pagamento:** `pagamento [valor]` (Ex: `pagamento 1500`)
- **Ver saldo:** `ver saldo`
- **Apagar último gasto:** `apagar último gasto`

📋 **Dívidas:**
- **Adicionar dívida:** `nova dívida [data] [valor] [descrição]` (Ex: `nova dívida 27/08 500 aluguel`)
- **Ver dívidas:** `ver dívidas`
- **Pagar dívida:** `pagar dívida [descrição]`

📊 **Relatórios e Análises:**
- **Resumo financeiro:** `resumo financeiro`
- **Gastos de hoje:** `gastos de hoje`
- **Gastos da semana:** `gastos da semana`
- **Gastos do mês:** `gastos do mês`
- **Análise da semana:** `análise da semana`
- **Análise do mês:** `análise do mês`
- **Listar gastos:** `listar gastos [categoria]`
- **Últimos 5 gastos:** `últimos 5 gastos`

Comece registrando seu primeiro gasto ou pagamento!
"""

# --- Funções da IA ---

def save_debt_to_csv(user_id, date, value, description):
    new_row = f"{user_id};{date};{description};{value:.2f}\n"
    file_exists = os.path.exists(DIVIDAS_FILE_NAME)
    with open(DIVIDAS_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists:
            file.write("UserID;Data de Vencimento;Descricao;Valor\n")
        file.write(new_row)

def get_debts_report(user_id):
    if not os.path.exists(DIVIDAS_FILE_NAME):
        return "Nenhuma dívida registrada ainda."
    report_lines = ["📋 Suas Dívidas Pendentes 📋\n"]
    total_debts = 0.0
    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader)
        except StopIteration: return "Nenhuma dívida registrada ainda."
        for row in reader:
            if row[0] == user_id:
                try:
                    date_due = row[1]; description = row[2]; value = float(row[3])
                    report_lines.append(f"- {description} (Vencimento: {date_due}): R${value:.2f}")
                    total_debts += value
                except (ValueError, IndexError): continue
    if len(report_lines) == 1: return "Nenhuma dívida registrada ainda."
    report_lines.append(f"\n*Total de Dívidas: R${total_debts:.2f}*")
    return "\n".join(report_lines)

def delete_debt_from_csv(user_id, description_to_delete):
    if not os.path.exists(DIVIDAS_FILE_NAME): return "Não há dívidas para apagar."
    lines = []; debt_found = False
    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
    new_lines = []
    for line in lines:
        if not debt_found and user_id in line and description_to_delete in line.lower():
            debt_found = True; continue
        new_lines.append(line)
    if not debt_found: return f"Não encontrei a dívida '{description_to_delete}' para apagar."
    with open(DIVIDAS_FILE_NAME, 'w', encoding='utf-8') as file: file.writelines(new_lines)
    return f"✅ Dívida '{description_to_delete}' paga e removida da sua lista!"

def record_payment_and_update_balance(user_id, value):
    try:
        current_balance = get_current_balance(user_id); new_balance = current_balance + value
        lines = []; user_found = False
        if os.path.exists(SALDO_FILE_NAME):
            with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
        with open(SALDO_FILE_NAME, 'w', encoding='utf-8') as file:
            for line in lines:
                if line.startswith(user_id):
                    file.write(f"{user_id};{new_balance:.2f}\n"); user_found = True
                else: file.write(line)
            if not user_found: file.write(f"{user_id};{new_balance:.2f}\n")
        return f"✅ Pagamento de R${value:.2f} registrado!\n\nSeu saldo atual é de *R${new_balance:.2f}*."
    except Exception as e: return f"Ocorreu um erro ao registrar o pagamento: {e}"

def record_expense_and_update_balance(user_id, value):
    try:
        current_balance = get_current_balance(user_id); new_balance = current_balance - value
        lines = []; user_found = False
        if os.path.exists(SALDO_FILE_NAME):
            with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
        with open(SALDO_FILE_NAME, 'w', encoding='utf-8') as file:
            for line in lines:
                if line.startswith(user_id):
                    file.write(f"{user_id};{new_balance:.2f}\n"); user_found = True
                else: file.write(line)
            if not user_found: file.write(f"{user_id};{new_balance:.2f}\n")
        return True
    except Exception: return False

def get_current_balance(user_id):
    if not os.path.exists(SALDO_FILE_NAME): return 0.0
    with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        for row in reader:
            if row[0] == user_id: return float(row[1])
    return 0.0

def save_expense_to_csv(user_id, description, value):
    now = datetime.datetime.now(TIMEZONE); timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists(CSV_FILE_NAME); expense_id = 1
    if file_exists and os.path.getsize(CSV_FILE_NAME) > 0:
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file: expense_id = sum(1 for line in file)
    new_row = f"{user_id};{expense_id};{timestamp};{description};{value:.2f}\n"
    with open(CSV_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists: file.write("UserID;ID;Data e Hora;Descricao;Valor\n")
        file.write(new_row)

def get_month_total(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    total_month = 0.0; current_month_str = datetime.datetime.now(TIMEZONE).strftime("%Y-%m")
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row[0] == user_id and row[2].startswith(current_month_str): total_month += float(row[4])
    return f"📊 Total do Mês 📊\n\nAté agora, você gastou um total de *R${total_month:.2f}* neste mês."

def get_week_total(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    total_week = 0.0; today = datetime.datetime.now(TIMEZONE).date()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            try:
                expense_date = datetime.datetime.strptime(row[2].split(' ')[0], "%Y-%m-%d").date()
                if row[0] == user_id and expense_date >= start_of_week: total_week += float(row[4])
            except (ValueError, IndexError): continue
    return f"🗓️ Total da Semana 🗓️\n\nAté agora, você gastou um total de *R${total_week:.2f}* nesta semana."

def list_expenses_by_category(user_id, category):
    if not os.path.exists(CSV_FILE_NAME): return f"Não encontrei nenhum gasto para a categoria '{category}'."
    list_lines = [f"🧾 Gastos de '{category.capitalize()}' 🧾\n"]; total_category = 0.0; found_expenses = False
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row[0] == user_id and category in row[3].lower():
                description = row[3].capitalize(); value = float(row[4])
                list_lines.append(f"- {description}: R${value:.2f}"); total_category += value; found_expenses = True
    if not found_expenses: return f"Não encontrei nenhum gasto para a categoria '{category}'."
    list_lines.append(f"\n*Total da Categoria: R${total_category:.2f}*"); return "\n".join(list_lines)

def delete_last_expense(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Não há gastos para apagar."
    lines = []; last_expense_of_user = -1
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().split(';')[0] == user_id:
            last_expense_of_user = i
            break
    if last_expense_of_user == -1: return "Você não tem gastos registrados para apagar."
    deleted_line = lines.pop(last_expense_of_user).strip().split(';')
    deleted_description = deleted_line[3]; deleted_value = float(deleted_line[4])
    with open(CSV_FILE_NAME, 'w', encoding='utf-8') as file: file.writelines(lines)
    record_payment_and_update_balance(user_id, deleted_value)
    return f"🗑️ Último gasto apagado!\n\n- Descrição: {deleted_description}\n- Valor: R${deleted_value:.2f}"

def get_last_5_expenses(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    all_expenses = []
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row[0] == user_id: all_expenses.append(f"ID {row[1]} - {row[3]}: R${float(row[4]):.2f}")
    if not all_expenses: return "Nenhum gasto registrado ainda."
    last_5 = all_expenses[-5:]; last_5.reverse()
    return "🗓️ Seus Últimos 5 Gastos 🗓️\n\n" + "\n".join(last_5)

def get_spending_pattern_analysis(user_id, period):
    if not os.path.exists(CSV_FILE_NAME): return "Não há gastos para analisar ainda."
    
    today = datetime.datetime.now(TIMEZONE).date()
    if period == 'week':
        start_date = today - datetime.timedelta(days=today.weekday())
        period_name = "semana"
    elif period == 'month':
        start_date = today.replace(day=1)
        period_name = "mês"
    else:
        return "Período de análise inválido."

    category_totals = defaultdict(float)
    total_spent = 0.0
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            try:
                expense_date = datetime.datetime.strptime(row[2].split(' ')[0], "%Y-%m-%d").date()
                if row[0] == user_id and expense_date >= start_date:
                    description = row[3].capitalize(); value = float(row[4])
                    # Simplesmente usa a descrição como a "categoria" para esta análise
                    category_totals[description] += value
                    total_spent += value
            except (ValueError, IndexError): continue
    
    if not category_totals: return f"Você não teve gastos neste(a) {period_name} para analisar."

    top_category = max(category_totals, key=category_totals.get)
    top_category_value = category_totals[top_category]
    
    insight = f"Neste(a) {period_name}, seu maior gasto foi com '{top_category}', totalizando R${top_category_value:.2f}. "
    insight += f"Isso representa { (top_category_value / total_spent) * 100:.1f}% do seu total de R${total_spent:.2f} gastos no período."

    return f"📈 Análise da {period_name.capitalize()} 📈\n\n{insight}"

def check_debt_reminders(user_id):
    if not os.path.exists(DIVIDAS_FILE_NAME): return None
    
    reminders = []
    today = datetime.datetime.now(TIMEZONE).date()
    today_str = today.strftime("%Y-%m-%d")
    
    reminders_sent_today = set()
    if os.path.exists(REMINDERS_SENT_FILE):
        with open(REMINDERS_SENT_FILE, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            for row in reader:
                if row[0] == user_id and row[2] == today_str:
                    reminders_sent_today.add(row[1])

    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row[0] == user_id:
                try:
                    due_date_str = row[1]; description = row[2]
                    due_date = datetime.datetime.strptime(f"{due_date_str}/{today.year}", "%d/%m/%Y").date()
                    days_until_due = (due_date - today).days
                    
                    if 0 <= days_until_due <= 3 and description not in reminders_sent_today:
                        reminders.append(f"🔔 *Lembrete:* Sua dívida '{description}' vence em {days_until_due} dia(s)!")
                        with open(REMINDERS_SENT_FILE, 'a', encoding='utf-8') as rem_file:
                            rem_file.write(f"{user_id};{description};{today_str}\n")
                except (ValueError, IndexError): continue
                
    return "\n".join(reminders) if reminders else None

def parse_natural_language_expense(message_text):
    money_pattern = r'(\d+([,.]\d{1,2})?)'
    found_values = re.findall(money_pattern, message_text)
    
    if not found_values: return {"error": "Nenhum valor encontrado."}
    
    value_str = found_values[-1][0].replace(',', '.')
    value = float(value_str)
    
    description = message_text.replace(found_values[-1][0], "").strip()
    
    stopwords = ['gastei', 'reais', 'real', 'no', 'na', 'em', 'com', 'de', 'foi', 'custou', 'anota', 'aí']
    for word in stopwords:
        description = description.replace(word, "").strip()
        
    if not description: return {"error": "Não consegui identificar a descrição do gasto."}
    
    return {"description": description.capitalize(), "value": value}

def parse_debt_message(message_text):
    parts = message_text.replace("nova dívida ", "").strip().split()
    if len(parts) < 3: return {"error": "Formato inválido. Use 'nova dívida [data] [valor] [descrição]'."}
    try:
        date_str = parts[0]; value_str = parts[1].replace(',', '.'); value = float(value_str); description = " ".join(parts[2:])
        datetime.datetime.strptime(date_str, "%d/%m")
        return {"date": date_str, "value": value, "description": description.capitalize()}
    except (ValueError, IndexError):
        return {"error": "Formato de data ou valor inválido. Use 'nova dívida [data] [valor] [descrição]'."}

def send_whatsapp_message(phone_number, message_text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"; headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}; data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}; requests.post(url, headers=headers, json=data)

def get_financial_summary(user_id):
    current_balance = get_current_balance(user_id); total_debts = 0.0
    if os.path.exists(DIVIDAS_FILE_NAME):
        with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row[0] == user_id:
                    try: total_debts += float(row[3])
                    except (ValueError, IndexError): continue
    available_after_debts = current_balance - total_debts; amount_to_save = available_after_debts * 0.20
    safe_to_spend = available_after_debts - amount_to_save
    report = ["💰 Resumo Financeiro Completo 💰\n", f"Seu saldo atual é: *R${current_balance:.2f}*", f"Suas dívidas totais são: *R${total_debts:.2f}*", f"Valor na conta após pagar as dívidas: *R${available_after_debts:.2f}*", f"Você deve guardar (20%): *R${amount_to_save:.2f}*", f"\nSeu saldo para gastar livremente é: *R${safe_to_spend:.2f}*"]
    return "\n".join(report)

# Webhook principal
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode'); token = request.args.get('hub.verify_token'); challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN: return challenge, 200
        else: return 'Failed verification', 403
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            value = data['entry'][0]['changes'][0]['value']
            user_name = "Pessoa"
            if 'contacts' in value and len(value['contacts']) > 0:
                user_name = value['contacts'][0].get('profile', {}).get('name', 'Pessoa')
            message_data = value['messages'][0]; user_id = message_data['from']
            message_text = message_data['text']['body'].strip().lower()
            
            reply_message = ""
            reminders = check_debt_reminders(user_id)

            greetings = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "ajuda", "comandos"]
            if message_text in greetings:
                reply_message = f"Olá, {user_name}! 👋\n\n{COMMANDS_MESSAGE}"
            elif message_text.startswith("nova dívida "):
                parsed_data = parse_debt_message(message_text)
                if "error" in parsed_data: reply_message = parsed_data["error"]
                else:
                    date, val, desc = parsed_data["date"], parsed_data["value"], parsed_data["description"]
                    save_debt_to_csv(user_id, date, val, desc)
                    reply_message = f"✅ Dívida de R${val:.2f} com vencimento em {date} registrada!\n\n- Descrição: {desc}"
            elif message_text == "ver dívidas":
                reply_message = get_debts_report(user_id)
            elif message_text == "ver saldo":
                reply_message = f"💵 Saldo Atual 💵\n\nSeu saldo atual é de *R${get_current_balance(user_id):.2f}*."
            elif message_text == "análise da semana":
                reply_message = get_spending_pattern_analysis(user_id, 'week')
            elif message_text == "análise do mês":
                reply_message = get_spending_pattern_analysis(user_id, 'month')
            elif message_text == "gastos da semana":
                reply_message = get_week_total(user_id)
            elif message_text == "últimos 5 gastos":
                reply_message = get_last_5_expenses(user_id)
            elif message_text == "gastos do mês":
                reply_message = get_month_total(user_id)
            elif message_text == "apagar último gasto":
                reply_message = delete_last_expense(user_id)
            # ... (outros comandos elif)
            else:
                parsed_data = parse_natural_language_expense(message_text)
                if "error" in parsed_data:
                    reply_message = f"Desculpe, {user_name}, não entendi o comando. Envie 'oi' para ver a lista de comandos."
                else:
                    desc, val = parsed_data["description"], parsed_data["value"]
                    save_expense_to_csv(user_id, desc, val)
                    record_expense_and_update_balance(user_id, val)
                    reply_message = f"✅ Gasto Registrado!\n\n- Descrição: {desc}\n- Valor: R${val:.2f}"
            
            final_message = f"{reminders}\n\n---\n\n{reply_message}" if reminders and reply_message else reminders or reply_message
            if final_message:
                send_whatsapp_message(user_id, final_message)
        except (KeyError, IndexError, TypeError): 
            pass
        return 'EVENT_RECEIVED', 200
