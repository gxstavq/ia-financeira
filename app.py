# Importa as ferramentas necessárias
from flask import Flask, request
import json
import requests
import datetime
import os
import csv
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
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# >>> CÓDIGO ALTERADO: Mensagem de boas-vindas com comandos simplificados
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

📊 **Relatórios:**
- **Resumo financeiro:** `resumo financeiro`
- **Gastos de hoje:** `gastos de hoje`
- **Gastos da semana:** `gastos da semana`
- **Gastos do mês:** `gastos do mês`
- **Total por categoria:** `total [categoria]` (Ex: `total almoço`)
- **Listar gastos:** `listar gastos [categoria]` (Ex: `listar gastos mercado`)
- **Últimos 5 gastos:** `últimos 5 gastos`

Comece registrando seu primeiro gasto ou pagamento!
"""
# FIM DA ALTERAÇÃO <<<

# --- Funções da IA (permanecem as mesmas) ---

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
                    date_due = row[1]
                    description = row[2]
                    value = float(row[3])
                    report_lines.append(f"- {description} (Vencimento: {date_due}): R${value:.2f}")
                    total_debts += value
                except (ValueError, IndexError):
                    continue
    
    if len(report_lines) == 1:
        return "Nenhuma dívida registrada ainda."
    
    report_lines.append(f"\n*Total de Dívidas: R${total_debts:.2f}*")
    return "\n".join(report_lines)

def delete_debt_from_csv(user_id, description_to_delete):
    if not os.path.exists(DIVIDAS_FILE_NAME):
        return "Não há dívidas para apagar."
    
    lines = []
    debt_found = False
    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    new_lines = []
    for line in lines:
        if not debt_found and line.strip().split(';')[0] == user_id and description_to_delete in line.lower():
            debt_found = True
            continue
        new_lines.append(line)
        
    if not debt_found:
        return f"Não encontrei a dívida '{description_to_delete}' para apagar."
    
    with open(DIVIDAS_FILE_NAME, 'w', encoding='utf-8') as file:
        file.writelines(new_lines)
        
    return f"✅ Dívida '{description_to_delete}' paga e removida da sua lista!"

def record_payment_and_update_balance(user_id, value):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance + value
        
        lines = []
        user_found = False
        if os.path.exists(SALDO_FILE_NAME):
            with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        
        with open(SALDO_FILE_NAME, 'w', encoding='utf-8') as file:
            for line in lines:
                if line.startswith(user_id):
                    file.write(f"{user_id};{new_balance:.2f}\n")
                    user_found = True
                else:
                    file.write(line)
            if not user_found:
                file.write(f"{user_id};{new_balance:.2f}\n")
                
        return f"✅ Pagamento de R${value:.2f} registrado!\n\nSeu saldo atual é de *R${new_balance:.2f}*."
    except Exception as e:
        return f"Ocorreu um erro ao registrar o pagamento: {e}"

def record_expense_and_update_balance(user_id, value):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance - value
        
        lines = []
        user_found = False
        if os.path.exists(SALDO_FILE_NAME):
            with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        
        with open(SALDO_FILE_NAME, 'w', encoding='utf-8') as file:
            for line in lines:
                if line.startswith(user_id):
                    file.write(f"{user_id};{new_balance:.2f}\n")
                    user_found = True
                else:
                    file.write(line)
            if not user_found:
                file.write(f"{user_id};{new_balance:.2f}\n")
                
        return True
    except Exception:
        return False
        
def get_current_balance(user_id):
    if not os.path.exists(SALDO_FILE_NAME):
        return 0.0
    with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        for row in reader:
            if row[0] == user_id:
                return float(row[1])
    return 0.0

def save_expense_to_csv(user_id, description, value):
    now = datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    
    file_exists = os.path.exists(CSV_FILE_NAME)
    expense_id = 1
    if file_exists and os.path.getsize(CSV_FILE_NAME) > 0:
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
            num_lines = sum(1 for line in file)
            expense_id = num_lines
    
    new_row = f"{user_id};{expense_id};{timestamp};{description};{value:.2f}\n"
    with open(CSV_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists:
            file.write("UserID;ID;Data e Hora;Descricao;Valor\n")
        file.write(new_row)

def get_month_total(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    total_month = 0.0
    current_month_str = datetime.datetime.now(TIMEZONE).strftime("%Y-%m")
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader)
        except StopIteration: return "Nenhum gasto neste mês ainda."
        for row in reader:
            if row[0] == user_id and row[2].startswith(current_month_str):
                total_month += float(row[4])
    return f"📊 Total do Mês 📊\n\nAté agora, você gastou um total de *R${total_month:.2f}* neste mês."

def get_week_total(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    total_week = 0.0
    today = datetime.datetime.now(TIMEZONE).date()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader)
        except StopIteration: return "Nenhum gasto nesta semana ainda."
        
        for row in reader:
            try:
                expense_date_str = row[2].split(' ')[0]
                expense_date = datetime.datetime.strptime(expense_date_str, "%Y-%m-%d").date()
                if row[0] == user_id and expense_date >= start_of_week:
                    total_week += float(row[4])
            except (ValueError, IndexError):
                continue
    return f"🗓️ Total da Semana 🗓️\n\nAté agora, você gastou um total de *R${total_week:.2f}* nesta semana."

def get_category_total(user_id, category):
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    total_category = 0.0
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader)
        except StopIteration: return f"Nenhum gasto encontrado na categoria '{category}'."
        for row in reader:
            if row[0] == user_id and category in row[3].lower():
                total_category += float(row[4])
    return f"📈 Total da Categoria '{category.capitalize()}' 📈\n\nVocê gastou *R${total_category:.2f}* com esta categoria."

def list_expenses_by_category(user_id, category):
    if not os.path.exists(CSV_FILE_NAME):
        return f"Não encontrei nenhum gasto para a categoria '{category}'."

    list_lines = [f"🧾 Gastos de '{category.capitalize()}' 🧾\n"]
    total_category = 0.0
    found_expenses = False
    
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try:
            next(reader)
        except StopIteration:
            return f"Não encontrei nenhum gasto para a categoria '{category}'."

        for row in reader:
            if row[0] == user_id and category in row[3].lower():
                description = row[3].capitalize()
                value = float(row[4])
                list_lines.append(f"- {description}: R${value:.2f}")
                total_category += value
                found_expenses = True
    
    if not found_expenses:
        return f"Não encontrei nenhum gasto para a categoria '{category}'."
        
    list_lines.append(f"\n*Total da Categoria: R${total_category:.2f}*")
    return "\n".join(list_lines)

def delete_expense_by_id(user_id, expense_id):
    if not os.path.exists(CSV_FILE_NAME):
        return "Não há gastos para apagar."
    lines = []
    expense_found = False
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    new_lines = []
    deleted_info = None
    for line in lines:
        parts = line.strip().split(';')
        if len(parts) > 1 and parts[0] == user_id and parts[1] == str(expense_id):
            deleted_info = parts
            expense_found = True
        else:
            new_lines.append(line)
            
    if not expense_found:
        return f"Não encontrei o gasto com ID '{expense_id}' para apagar."
    
    with open(CSV_FILE_NAME, 'w', encoding='utf-8') as file:
        file.writelines(new_lines)
        
    deleted_description = deleted_info[3]
    deleted_value = float(deleted_info[4])
    
    record_payment_and_update_balance(user_id, deleted_value)
    
    return f"🗑️ Gasto com ID '{expense_id}' apagado!\n\n- Descrição: {deleted_description}\n- Valor: R${deleted_value:.2f}"

def delete_last_expense(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Não há gastos para apagar."
    lines = []
    last_expense_of_user = -1
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip().split(';')[0] == user_id:
            last_expense_of_user = i
            break
            
    if last_expense_of_user == -1:
        return "Você não tem gastos registrados para apagar."
    
    deleted_line = lines.pop(last_expense_of_user).strip().split(';')
    deleted_description = deleted_line[3]
    deleted_value = float(deleted_line[4])

    with open(CSV_FILE_NAME, 'w', encoding='utf-8') as file:
        file.writelines(lines)
    
    record_payment_and_update_balance(user_id, deleted_value)

    return f"🗑️ Último gasto apagado!\n\n- Descrição: {deleted_description}\n- Valor: R${deleted_value:.2f}"

def get_last_5_expenses(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    all_expenses = []
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader)
        except StopIteration: return "Nenhum gasto registrado ainda."
        for row in reader:
            if row[0] == user_id:
                all_expenses.append(f"ID {row[1]} - {row[3]}: R${float(row[4]):.2f}")
    if not all_expenses: return "Nenhum gasto registrado ainda."
    last_5 = all_expenses[-5:]; last_5.reverse()
    return "🗓️ Seus Últimos 5 Gastos 🗓️\n\n" + "\n".join(last_5)

def parse_expense_message(message_text):
    parts = message_text.strip().split()
    if len(parts) < 2: return {"error": "Formato inválido."}
    try: value_str = parts[-1].replace(',', '.'); value = float(value_str); description = " ".join(parts[:-1]); return {"description": description.capitalize(), "value": value}
    except ValueError: return {"error": f"Não entendi o valor '{parts[-1]}'."}
    
def parse_debt_message(message_text):
    # >>> CÓDIGO ALTERADO: Ajuste para o novo comando "nova dívida"
    parts = message_text.replace("nova dívida ", "").strip().split()
    if len(parts) < 3: return {"error": "Formato inválido. Use 'nova dívida [data] [valor] [descrição]'."}
    # FIM DA ALTERAÇÃO <<<
    try:
        date_str = parts[0]
        value_str = parts[1].replace(',', '.')
        value = float(value_str)
        description = " ".join(parts[2:])
        # Valida o formato da data
        datetime.datetime.strptime(date_str, "%d/%m")
        return {"date": date_str, "value": value, "description": description.capitalize()}
    except (ValueError, IndexError):
        return {"error": "Formato de data ou valor inválido. Use 'nova dívida [data] [valor] [descrição]'."}

def send_whatsapp_message(phone_number, message_text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"; headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}; data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}; requests.post(url, headers=headers, json=data)

def get_financial_summary(user_id):
    current_balance = get_current_balance(user_id)
    total_debts = 0.0
    if os.path.exists(DIVIDAS_FILE_NAME):
        with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            try: next(reader)
            except StopIteration: pass
            for row in reader:
                if row[0] == user_id:
                    try:
                        total_debts += float(row[3])
                    except (ValueError, IndexError):
                        continue
    
    available_after_debts = current_balance - total_debts
    amount_to_save = available_after_debts * 0.20
    safe_to_spend = available_after_debts - amount_to_save
    
    report = []
    report.append("💰 Resumo Financeiro Completo 💰\n")
    report.append(f"Seu saldo atual é: *R${current_balance:.2f}*")
    report.append(f"Suas dívidas totais são: *R${total_debts:.2f}*")
    report.append(f"Valor na conta após pagar as dívidas: *R${available_after_debts:.2f}*")
    report.append(f"Você deve guardar (20%): *R${amount_to_save:.2f}*")
    report.append(f"\nSeu saldo para gastar livremente é: *R${safe_to_spend:.2f}*")

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

            message_data = value['messages'][0]
            user_id = message_data['from']
            message_text = message_data['text']['body'].strip().lower()
            
            reply_message = ""

            greetings = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "ajuda", "comandos"]
            if message_text in greetings:
                reply_message = f"Olá, {user_name}! 👋\n\n{COMMANDS_MESSAGE}"
            
            # >>> CÓDIGO ALTERADO: Lógica com os novos comandos
            elif message_text.startswith("nova dívida "):
                parsed_data = parse_debt_message(message_text)
                if "error" in parsed_data:
                    reply_message = parsed_data["error"]
                else:
                    date = parsed_data["date"]
                    value = parsed_data["value"]
                    description = parsed_data["description"]
                    save_debt_to_csv(user_id, date, value, description)
                    reply_message = f"✅ Dívida de R${value:.2f} com vencimento em {date} registrada!\n\n- Descrição: {description}"
            elif message_text.startswith("pagar dívida "):
                description_to_delete = message_text.split("pagar dívida ")[1].strip()
                reply_message = delete_debt_from_csv(user_id, description_to_delete)
            elif message_text == "ver dívidas":
                reply_message = get_debts_report(user_id)
            elif message_text.startswith("pagamento "):
                try:
                    value_str = message_text.split(" ")[1].replace(',', '.')
                    value = float(value_str)
                    reply_message = record_payment_and_update_balance(user_id, value)
                except (ValueError, IndexError):
                    reply_message = "Comando inválido. Por favor, use 'pagamento [valor]'."
            elif message_text == "resumo financeiro":
                reply_message = get_financial_summary(user_id)
            elif message_text == "ver saldo":
                balance = get_current_balance(user_id)
                reply_message = f"💵 Saldo Atual 💵\n\nSeu saldo atual é de *R${balance:.2f}*."
            elif message_text == "gastos de hoje":
                # A lógica para o relatório diário continua a mesma, apenas o comando mudou
                if not os.path.exists(CSV_FILE_NAME): 
                    reply_message = "Nenhum gasto registrado ainda."
                else:
                    today_str = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d")
                    category_totals = defaultdict(float)
                    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
                        reader = csv.reader(file, delimiter=';')
                        try: next(reader)
                        except StopIteration:
                            reply_message = "Nenhum gasto registrado hoje."
                            send_whatsapp_message(user_id, reply_message)
                            return 'EVENT_RECEIVED', 200
                        
                        for row in reader:
                            if row[0] == user_id and row[2].startswith(today_str):
                                description = row[3].capitalize()
                                value = float(row[4])
                                category_found = False
                                common_categories = ['almoço', 'janta', 'transporte', 'compras', 'lazer', 'mercado']
                                for cat in common_categories:
                                    if cat in description.lower():
                                        category_totals[cat.capitalize()] += value
                                        category_found = True
                                        break
                                if not category_found:
                                    category_totals['Outros'] += value

                    if not category_totals:
                        reply_message = "Nenhum gasto registrado hoje."
                    else:
                        reply_lines = ["🧾 Relatório de Hoje 🧾\n"]
                        total_geral = 0.0
                        for category, total in category_totals.items():
                            reply_lines.append(f"- {category}: R${total:.2f}")
                            total_geral += total
                        reply_lines.append(f"\n*Total Geral: R${total_geral:.2f}*")
                        reply_message = "\n".join(reply_lines)
            elif message_text.startswith("total "):
                category = message_text.split("total ")[1].strip()
                reply_message = get_category_total(user_id, category)
            elif message_text.startswith("listar gastos "):
                category = message_text.split("listar gastos ")[1].strip()
                reply_message = list_expenses_by_category(user_id, category)
            elif message_text.startswith("apagar gasto "):
                try:
                    expense_id = int(message_text.split("apagar gasto ")[1].strip())
                    reply_message = delete_expense_by_id(user_id, expense_id)
                except (ValueError, IndexError):
                    reply_message = "Comando inválido. Por favor, use 'apagar gasto [ID]'."
            elif message_text == "gastos da semana":
                reply_message = get_week_total(user_id)
            elif message_text == "últimos 5 gastos":
                reply_message = get_last_5_expenses(user_id)
            elif message_text == "gastos do mês":
                reply_message = get_month_total(user_id)
            elif message_text == "apagar último gasto":
                reply_message = delete_last_expense(user_id)
            # FIM DA ALTERAÇÃO <<<
            else:
                parsed_data = parse_expense_message(message_text)
                if "error" in parsed_data:
                    reply_message = f"Desculpe, {user_name}, não entendi o comando. Envie 'oi' para ver a lista de comandos."
                else:
                    desc = parsed_data["description"]; val = parsed_data["value"]
                    save_expense_to_csv(user_id, desc, val)
                    record_expense_and_update_balance(user_id, val)
                    reply_message = f"✅ Gasto Registrado!\n\n- Descrição: {desc}\n- Valor: R${val:.2f}"
            
            if reply_message:
                send_whatsapp_message(user_id, reply_message)
        except (KeyError, IndexError, TypeError): 
            pass
        return 'EVENT_RECEIVED', 200
