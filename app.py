# Importa as ferramentas necessárias
from flask import Flask, request
import json
import requests
import datetime
import os
import csv

# Cria a aplicação
app = Flask(__name__)

# --- SUAS CREDENCIAIS ---
ACCESS_TOKEN = "EAAPUxZCZAn4v8BPSa8iRQuyKevv6kXj4PqX5pTEaoYD4v0fw4kjdXflK3WDRgVPoXVCheLJ6qEdr8Y9ax6Rs8nUqxAZCxjy1YZCjWklvgZAZBOW0WTg6MuaPs8GsRqOVGtzGXSjVQ01kCUZBpSJZAZA9JAraV0LIuJvTCr30F1WDLIW5d30p8F9PAAZAwQjsI6KtdRd1TjulwQeWpw3ZCKFJmGdDvXyo901ZCBVexar7W8yLXTwZD"
PHONE_NUMBER_ID = "758102004052937"
VERIFY_TOKEN = "mude-para-um-token-seu-1245"
# --- FIM DAS CREDENCIAIS ---

DATA_DIR = os.getenv('RENDER_DISK_PATH', '.')
CSV_FILE_NAME = os.path.join(DATA_DIR, "meus_gastos.csv")
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# --- Funções da IA (Agora recebem o user_id) ---

def save_expense_to_csv(user_id, description, value): # MUDANÇA AQUI
    now = datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    # MUDANÇA AQUI: Adicionamos o user_id na linha a ser salva
    new_row = f"{user_id};{timestamp};{description};{value:.2f}\n"
    file_exists = os.path.exists(CSV_FILE_NAME)
    with open(CSV_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists:
            # MUDANÇA AQUI: Adicionamos o cabeçalho da nova coluna
            file.write("UserID;Data e Hora;Descricao;Valor\n")
        file.write(new_row)

def get_month_total(user_id): # MUDANÇA AQUI
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    total_month = 0.0
    current_month_str = datetime.datetime.now(TIMEZONE).strftime("%Y-%m")
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader)
        except StopIteration: return "Nenhum gasto neste mês ainda."
        for row in reader:
            # MUDANÇA AQUI: Verifica se a linha pertence ao usuário certo (row[0]) E ao mês certo (row[1])
            if row[0] == user_id and row[1].startswith(current_month_str):
                total_month += float(row[3]) # O valor agora está na coluna 3
    return f"📊 Total do Mês 📊\n\nAté agora, você gastou um total de *R${total_month:.2f}* neste mês."

def delete_last_expense(user_id): # MUDANÇA AQUI
    if not os.path.exists(CSV_FILE_NAME): return "Não há gastos para apagar."
    lines = []
    last_expense_of_user = -1
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # MUDANÇA AQUI: Procura de baixo para cima pela última linha que pertence ao usuário
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


def get_today_expenses(user_id): # MUDANÇA AQUI
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    total_today = 0.0
    today_str = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader)
        except StopIteration: return "Nenhum gasto registrado hoje."
        for row in reader:
            # MUDANÇA AQUI: Verifica se a linha pertence ao usuário certo (row[0]) E ao dia certo (row[1])
            if row[0] == user_id and row[1].startswith(today_str):
                total_today += float(row[3]) # O valor agora está na coluna 3
    return f"🧾 Relatório de Hoje 🧾\n\nVocê gastou um total de *R${total_today:.2f}* hoje."

def get_last_5_expenses(user_id): # MUDANÇA AQUI
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    all_expenses = []
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        try: next(reader)
        except StopIteration: return "Nenhum gasto registrado ainda."
        for row in reader:
            # MUDANÇA AQUI: Adiciona à lista apenas os gastos do usuário certo
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
            # MUDANÇA AQUI: O número de telefone agora é nosso user_id
            user_id = message_data['from']
            message_text = message_data['text']['body'].strip().lower()
            
            reply_message = ""

            # MUDANÇA AQUI: Passamos o user_id para todas as funções
            if message_text == "relatório hoje":
                reply_message = get_today_expenses(user_id)
            elif message_text == "últimos 5":
                reply_message = get_last_5_expenses(user_id)
            elif message_text == "total do mês":
                reply_message = get_month_total(user_id)
            elif message_text == "apagar último":
                reply_message = delete_last_expense(user_id)
            else:
                parsed_data = parse_expense_message(message_text)
                if "error" in parsed_data:
                    reply_message = "Comando não reconhecido..." # Mensagem de ajuda omitida para brevidade
                else:
                    desc = parsed_data["description"]; val = parsed_data["value"]
                    save_expense_to_csv(user_id, desc, val)
                    reply_message = f"✅ Gasto Registrado!\n\n- Descrição: {desc}\n- Valor: R${val:.2f}"
            
            send_whatsapp_message(user_id, reply_message)
        except (KeyError, IndexError, TypeError): pass
        return 'EVENT_RECEIVED', 200

