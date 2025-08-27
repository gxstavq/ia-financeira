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

DATA_DIR = os.getenv('RENDER_DISK_PATH', '.')
CSV_FILE_NAME = os.path.join(DATA_DIR, "meus_gastos.csv")
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# --- Funções da IA (Agora recebem o user_id) ---

def save_expense_to_csv(user_id, description, value):
    now = datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    new_row = f"{user_id};{timestamp};{description};{value:.2f}\n"
    file_exists = os.path.exists(CSV_FILE_NAME)
    with open(CSV_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists:
            file.write("UserID;Data e Hora;Descricao;Valor\n")
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
            if row[0] == user_id and row[1].startswith(current_month_str):
                total_month += float(row[3])
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
                expense_date_str = row[1].split(' ')[0]
                expense_date = datetime.datetime.strptime(expense_date_str, "%Y-%m-%d").date()
                if row[0] == user_id and expense_date >= start_of_week:
                    total_week += float(row[3])
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
            if row[0] == user_id and category in row[2].lower():
                total_category += float(row[3])
    return f"📈 Total da Categoria '{category.capitalize()}' 📈\n\nVocê gastou *R${total_category:.2f}* com esta categoria."

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
    deleted_description = deleted_line[2]
    deleted_value = float(deleted_line[3])

    with open(CSV_FILE_NAME, 'w', encoding='utf-8') as file:
        file.writelines(lines)
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
                all_expenses.append(f"- {row[2]}: R${float(row[3]):.2f}")
    if not all_expenses: return "Nenhum gasto registrado ainda."
    last_5 = all_expenses[-5:]; last_5.reverse()
    return "🗓️ Seus Últimos 5 Gastos 🗓️\n\n" + "\n".join(last_5)

def parse_expense_message(message_text):
    parts = message_text.strip().split()
    if len(parts) < 2: return {"error": "Formato inválido."}
    try: value_str = parts[-1].replace(',', '.'); value = float(value_str); description = " ".join(parts[:-1]); return {"description": description.capitalize(), "value": value}
    except ValueError: return {"error": f"Não entendi o valor '{parts[-1]}'."}

def send_whatsapp_message(phone_number, message_text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"; headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}; data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}; requests.post(url, headers=headers, json=data)

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
            message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
            user_id = message_data['from']
            message_text = message_data['text']['body'].strip().lower()
            
            reply_message = ""

            # >>> NOVO CÓDIGO: Lógica para o novo comando
            if message_text == "relatório hoje":
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
                            if row[0] == user_id and row[1].startswith(today_str):
                                description = row[2].capitalize()
                                value = float(row[3])
                                # Lógica para encontrar a categoria no texto do gasto
                                category_found = False
                                # Categorias comuns (pode ser ajustado)
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
            # FIM DO NOVO CÓDIGO <<<
            elif message_text.startswith("total "):
                category = message_text.split("total ")[1].strip()
                reply_message = get_category_total(user_id, category)
            elif message_text == "total da semana":
                reply_message = get_week_total(user_id)
            elif message_text == "últimos 5":
                reply_message = get_last_5_expenses(user_id)
            elif message_text == "total do mês":
                reply_message = get_month_total(user_id)
            elif message_text == "apagar último":
                reply_message = delete_last_expense(user_id)
            else:
                parsed_data = parse_expense_message(message_text)
                if "error" in parsed_data:
                    reply_message = "Comando não reconhecido..."
                else:
                    desc = parsed_data["description"]; val = parsed_data["value"]
                    save_expense_to_csv(user_id, desc, val)
                    reply_message = f"✅ Gasto Registrado!\n\n- Descrição: {desc}\n- Valor: R${val:.2f}"
            
            send_whatsapp_message(user_id, reply_message)
        except (KeyError, IndexError, TypeError): pass
        return 'EVENT_RECEIVED', 200