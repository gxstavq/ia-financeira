# Testando a atualização para o deploy
# Importa as ferramentas necessárias
from flask import Flask, request
import json
import requests
import datetime
import os
import csv
import re
from collections import defaultdict
from fuzzywuzzy import process # Biblioteca para correção de erros de digitação

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

# >>> NOVO CÓDIGO: Dicionários para a nova inteligência da IA
# Guarda o último comando do usuário para entender o contexto
user_context = {} 
# Guarda informações pendentes para perguntas de clarificação
pending_info = {}

# Mapeia sinônimos para comandos oficiais
command_synonyms = {
    "ver saldo": ["qual meu saldo", "quanto eu tenho", "meu saldo"],
    "resumo financeiro": ["resumo", "visão geral"],
    "gastos de hoje": ["o que gastei hoje", "gastos hoje"],
    "gastos da semana": ["gastos semana", "total semana"],
    "gastos do mês": ["gastos mês", "total mês"],
    "apagar último gasto": ["excluir último gasto", "apaga o último"],
    "ver dívidas": ["minhas dívidas", "listar dívidas"],
}

# Palavras-chave para inferir categorias automaticamente
category_keywords = {
    "Alimentação": ["restaurante", "almoço", "janta", "ifood", "rappi", "mercado", "comida", "lanche"],
    "Transporte": ["uber", "99", "táxi", "gasolina", "metrô", "ônibus", "passagem"],
    "Moradia": ["aluguel", "condomínio", "luz", "água", "internet", "gás"],
    "Lazer": ["cinema", "show", "bar", "festa", "viagem", "streaming", "spotify", "netflix"],
    "Saúde": ["farmácia", "remédio", "médico", "consulta"],
    "Compras": ["roupas", "presente", "shopping", "online"],
}
# FIM DO NOVO CÓDIGO <<<

COMMANDS_MESSAGE = """
Eu sou a sua IA de controle financeiro.
Agora estou mais inteligente! Você pode falar comigo de forma mais natural.

Tente comandos como:
- `gastei 50 reais no almoço`
- `qual meu saldo?`
- `o que gastei hoje?`
- `apaga o último`

Aqui está a lista completa de ações que eu entendo:

💰 **Gastos e Saldo:**
- **Adicionar gasto:** `[descrição] [valor]`
- **Adicionar pagamento:** `pagamento [valor]`
- **Ver saldo:** `ver saldo`
- **Apagar último gasto:** `apagar último gasto`

📋 **Dívidas:**
- **Adicionar dívida:** `nova dívida [data] [valor] [descrição]`
- **Ver dívidas:** `ver dívidas`
- **Pagar dívida:** `pagar dívida [descrição]`

📊 **Relatórios e Análises:**
- **Resumo financeiro:** `resumo financeiro`
- **Gastos de hoje/semana/mês:** `gastos de [período]`
- **Análise da semana/mês:** `análise da [período]`
- **Listar gastos:** `listar gastos [categoria]`
- **Últimos 5 gastos:** `últimos 5 gastos`
"""

# --- Funções da IA ---

# >>> NOVO CÓDIGO: Função para inferir categoria automaticamente
def infer_category(description):
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in description.lower():
                return category
    return "Outros"
# FIM DO NOVO CÓDIGO <<<

# >>> CÓDIGO ALTERADO: Salva o gasto com a categoria inferida
def save_expense_to_csv(user_id, description, value):
    now = datetime.datetime.now(TIMEZONE); timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    category = infer_category(description) # Inferencia de categoria
    file_exists = os.path.exists(CSV_FILE_NAME); expense_id = 1
    if file_exists and os.path.getsize(CSV_FILE_NAME) > 0:
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file: expense_id = sum(1 for line in file)
    # Adiciona a categoria na nova coluna
    new_row = f"{user_id};{expense_id};{timestamp};{description};{value:.2f};{category}\n"
    with open(CSV_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists: file.write("UserID;ID;Data e Hora;Descricao;Valor;Categoria\n")
        file.write(new_row)
    return category # Retorna a categoria para usar na mensagem de resposta
# FIM DA ALTERAÇÃO <<<

# ... (outras funções existentes como get_debts_report, record_payment, etc., permanecem aqui)
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

def delete_last_expense(user_id):
    # >>> CÓDIGO ALTERADO: Usa o contexto para apagar o item certo
    context = user_context.get(user_id)
    if context and context['command'] == 'listar gastos':
        # Se o último comando foi listar, apaga o último da lista mostrada
        last_listed_expense_id = context['data'][-1].split('ID ')[1].split(' -')[0]
        # Aqui você precisaria de uma função para apagar por ID
        # delete_expense_by_id(user_id, last_listed_expense_id)
        user_context[user_id] = None # Limpa o contexto
        return f"🗑️ O último gasto da lista '{context['params']}' foi apagado."
    # FIM DA ALTERAÇÃO <<<

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

def list_expenses_by_category(user_id, category):
    if not os.path.exists(CSV_FILE_NAME): return f"Não encontrei nenhum gasto para a categoria '{category}'."
    list_lines = [f"🧾 Gastos de '{category.capitalize()}' 🧾\n"]; total_category = 0.0; found_expenses = []
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row[0] == user_id and category in row[3].lower():
                description = row[3].capitalize(); value = float(row[4]); expense_id = row[1]
                line = f"ID {expense_id} - {description}: R${value:.2f}"
                list_lines.append(line)
                found_expenses.append(line)
                total_category += value
    if not found_expenses: return f"Não encontrei nenhum gasto para a categoria '{category}'."
    list_lines.append(f"\n*Total da Categoria: R${total_category:.2f}*")
    # >>> NOVO CÓDIGO: Salva o resultado no contexto do usuário
    user_context[user_id] = {'command': 'listar gastos', 'data': found_expenses, 'params': category}
    # FIM DO NOVO CÓDIGO <<<
    return "\n".join(list_lines)

# >>> CÓDIGO ALTERADO: Função de linguagem natural agora lida com comandos incompletos
def parse_natural_language_expense(message_text):
    money_pattern = r'(\d+([,.]\d{1,2})?)'
    found_values = re.findall(money_pattern, message_text)
    
    value = None
    if found_values:
        value_str = found_values[-1][0].replace(',', '.')
        value = float(value_str)
    
    description = message_text
    if value:
        description = message_text.replace(found_values[-1][0], "").strip()
        
    stopwords = ['gastei', 'reais', 'real', 'no', 'na', 'em', 'com', 'de', 'foi', 'custou', 'anota', 'aí']
    for word in stopwords:
        description = description.replace(word, "").strip()
        
    if not value and not description: return {"error": "Comando não compreendido."}
    if value and not description: return {"error": "incomplete", "value": value} # Sinaliza comando incompleto
    
    return {"description": description.capitalize(), "value": value}
# FIM DA ALTERAÇÃO <<<

# >>> NOVO CÓDIGO: Função para encontrar o comando mais provável (sinônimos e erros de digitação)
def get_command(text):
    # Lista de todos os comandos base
    all_commands = [
        "ver saldo", "resumo financeiro", "gastos de hoje", "gastos da semana", 
        "gastos do mês", "apagar último gasto", "ver dívidas", "últimos 5 gastos",
        "análise da semana", "análise do mês"
    ]
    
    # Adiciona sinônimos à lista de busca
    for cmd, syns in command_synonyms.items():
        if text in syns:
            return cmd

    # Usa fuzzywuzzy para encontrar o comando mais próximo (corrige erros de digitação)
    best_match, score = process.extractOne(text, all_commands)
    if score > 80: # Nível de confiança de 80%
        return best_match
        
    # Comandos que começam com um padrão
    if text.startswith("listar gastos"): return "listar gastos"
    if text.startswith("nova dívida"): return "nova dívida"
    if text.startswith("pagar dívida"): return "pagar dívida"
    if text.startswith("pagamento"): return "pagamento"

    return None
# FIM DO NOVO CÓDIGO <<<

def send_whatsapp_message(phone_number, message_text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"; headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}; data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}; requests.post(url, headers=headers, json=data)

# ... (funções de análise, lembretes, etc. permanecem aqui)
def get_spending_pattern_analysis(user_id, period):
    if not os.path.exists(CSV_FILE_NAME): return "Não há gastos para analisar ainda."
    today = datetime.datetime.now(TIMEZONE).date()
    if period == 'week':
        start_date = today - datetime.timedelta(days=today.weekday()); period_name = "semana"
    else:
        start_date = today.replace(day=1); period_name = "mês"
    category_totals = defaultdict(float); total_spent = 0.0
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            try:
                expense_date = datetime.datetime.strptime(row[2].split(' ')[0], "%Y-%m-%d").date()
                if row[0] == user_id and expense_date >= start_date:
                    description = row[5] if len(row) > 5 else infer_category(row[3])
                    value = float(row[4])
                    category_totals[description] += value; total_spent += value
            except (ValueError, IndexError): continue
    if not category_totals: return f"Você não teve gastos neste(a) {period_name} para analisar."
    top_category = max(category_totals, key=category_totals.get); top_category_value = category_totals[top_category]
    insight = f"Neste(a) {period_name}, sua maior categoria de gasto foi '{top_category}', totalizando R${top_category_value:.2f}. "
    insight += f"Isso representa { (top_category_value / total_spent) * 100:.1f}% do seu total de R${total_spent:.2f} gastos."
    return f"📈 Análise da {period_name.capitalize()} 📈\n\n{insight}"

def check_debt_reminders(user_id):
    if not os.path.exists(DIVIDAS_FILE_NAME): return None
    reminders = []; today = datetime.datetime.now(TIMEZONE).date(); today_str = today.strftime("%Y-%m-%d")
    reminders_sent_today = set()
    if os.path.exists(REMINDERS_SENT_FILE):
        with open(REMINDERS_SENT_FILE, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            for row in reader:
                if row[0] == user_id and row[2] == today_str: reminders_sent_today.add(row[1])
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
            
            # >>> CÓDIGO ALTERADO: Lógica principal com a nova inteligência
            
            # 1. Verifica se está aguardando uma resposta para uma pergunta de clarificação
            if user_id in pending_info:
                info = pending_info[user_id]
                if info['type'] == 'description':
                    desc = message_text.capitalize(); val = info['value']
                    category = save_expense_to_csv(user_id, desc, val)
                    record_expense_and_update_balance(user_id, val)
                    reply_message = f"✅ Gasto Registrado!\n- Descrição: {desc}\n- Valor: R${val:.2f}\n- Categoria Sugerida: *{category}*"
                    del pending_info[user_id] # Limpa a pendência
            else:
                # 2. Tenta identificar um comando conhecido (com sinônimos e correção de erros)
                command = get_command(message_text)
                
                if command == "ver saldo": reply_message = f"💵 Saldo Atual 💵\n\nSeu saldo atual é de *R${get_current_balance(user_id):.2f}*."
                elif command == "apagar último gasto": reply_message = delete_last_expense(user_id)
                elif command == "listar gastos":
                    category = message_text.split("listar gastos ")[1].strip()
                    reply_message = list_expenses_by_category(user_id, category)
                # ... (adicione outros comandos aqui)
                elif command:
                    # Lógica para outros comandos que não precisam de parâmetros
                    if command == "gastos de hoje": reply_message = "Função para gastos de hoje" # Substituir pela função real
                    # etc.
                else:
                    # 3. Se não for um comando, assume que é um registro de gasto em linguagem natural
                    parsed_data = parse_natural_language_expense(message_text)
                    if "error" in parsed_data:
                        if parsed_data["error"] == "incomplete":
                            # Pergunta de Clarificação
                            pending_info[user_id] = {'type': 'description', 'value': parsed_data['value']}
                            reply_message = f"Entendi o valor de R${parsed_data['value']:.2f}. Com o que foi esse gasto?"
                        else:
                            reply_message = f"Desculpe, {user_name}, não entendi. Se precisar de ajuda, envie 'comandos'."
                    else:
                        desc, val = parsed_data["description"], parsed_data["value"]
                        category = save_expense_to_csv(user_id, desc, val)
                        record_expense_and_update_balance(user_id, val)
                        reply_message = f"✅ Gasto Registrado!\n- Descrição: {desc}\n- Valor: R${val:.2f}\n- Categoria Sugerida: *{category}*"

            # FIM DA ALTERAÇÃO <<<

            final_message = f"{reminders}\n\n---\n\n{reply_message}" if reminders and reply_message else reminders or reply_message
            if final_message:
                send_whatsapp_message(user_id, final_message)
        except (KeyError, IndexError, TypeError): 
            pass
        return 'EVENT_RECEIVED', 200
