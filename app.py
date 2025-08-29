# Importa as ferramentas necessárias
from flask import Flask, request
import json
import requests
import datetime
import os
import csv
import re # Importado para a análise de texto
import random # Importado para as dicas financeiras
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
ORCAMENTO_FILE_NAME = os.path.join(DATA_DIR, "orcamento.csv")
METAS_FILE_NAME = os.path.join(DATA_DIR, "metas.csv")
RECORRENTES_FILE_NAME = os.path.join(DATA_DIR, "recorrentes.csv")
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# Dicionário de palavras-chave expandido para maior inteligência
CATEGORY_KEYWORDS = {
    "Alimentação": [
        "restaurante", "almoço", "janta", "ifood", "rappi", "mercado", "comida", "lanche", 
        "pizza", "hamburguer", "padaria", "café", "sorvete", "açaí", "supermercado"
    ],
    "Transporte": [
        "uber", "99", "táxi", "gasolina", "metrô", "ônibus", "passagem", "estacionamento", 
        "escritorio", "combustível", "pedágio", "rodízio", "moto"
    ],
    "Moradia": [
        "aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "diarista", 
        "limpeza", "reforma", "manutenção", "conta"
    ],
    "Lazer": [
        "cinema", "show", "bar", "festa", "viagem", "streaming", "spotify", "netflix", 
        "jogo", "ingresso", "passeio", "clube", "hobby"
    ],
    "Saúde": [
        "farmácia", "remédio", "médico", "consulta", "plano", "academia", "suplemento", 
        "dentista", "exame", "terapia"
    ],
    "Compras": [
        "roupa", "roupas", "tênis", "sapato", "presente", "shopping", "online", "eletrônicos", 
        "celular", "computador", "acessório", "decoração", "livraria"
    ],
    "Educação": [
        "curso", "livro", "faculdade", "material", "escola", "aula", "palestra"
    ],
    "Essenciais": [
        "aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "mercado", 
        "farmácia", "plano", "metrô", "ônibus", "combustível", "faculdade", "escola"
    ],
    "Desejos": [
        "restaurante", "ifood", "rappi", "lanche", "pizza", "cinema", "show", "bar", 
        "festa", "viagem", "streaming", "jogo", "roupas", "tênis", "presente", "shopping", 
        "uber", "99", "táxi", "hobby"
    ]
}

# Mensagem de ajuda mais humana e com novos comandos
COMMANDS_MESSAGE = """
Olá! Sou a sua assistente financeira. 😊
Você pode falar comigo de forma natural! Tente coisas como:

- `gastei 25,50 no almoço`
- `recebi meu pagamento de 2.500,08`
- `a parcela da moto de 450,30 vence dia 10/09`
- `qual o meu saldo?`
- `define meu rendimento em 3000`
- `meu orçamento`
- `dica financeira`

Aqui estão alguns dos comandos que eu entendo:

💰 **Orçamento e Metas**
- `definir rendimento [valor]`
- `meu orçamento`

📊 **Análises e Relatórios**
- `resumo financeiro`
- `comparar gastos`
- `gastos da [semana/mês/dia]`
- `análise da [semana/mês]`
- `minhas dívidas`

💡 **Outros**
- `dica financeira`
- `apagar último gasto`
"""

# --- Funções da IA ---

def parse_value_string(s):
    if not isinstance(s, str): return float(s)
    s = s.replace('R$', '').strip()
    s = s.replace('.', '')
    if ',' in s:
        s = s.replace(',', '.')
    return float(s)

def extract_all_monetary_values(text):
    pattern = r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+)'
    matches = re.findall(pattern, text)
    if not matches:
        return []
    
    values = []
    for match in matches:
        try:
            values.append(parse_value_string(match))
        except (ValueError, IndexError):
            continue
    return values

def extract_date(text):
    match = re.search(r'(\d{1,2}/\d{1,2})', text)
    if match:
        return match.group(0)
    return None

def infer_category(description):
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category in ["Essenciais", "Desejos"]: continue
        for keyword in keywords:
            if keyword in description.lower():
                return category
    return "Outros"

def save_expense_to_csv(user_id, description, value):
    now = datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    category = infer_category(description)
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

def save_debt_to_csv(user_id, date, value, description):
    new_row = f"{user_id};{date};{description};{value:.2f}\n"
    file_exists = os.path.exists(DIVIDAS_FILE_NAME)
    with open(DIVIDAS_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(DIVIDAS_FILE_NAME) == 0:
            file.write("UserID;Data de Vencimento;Descricao;Valor\n")
        file.write(new_row)
    return f"✅ Dívida registrada: {description} no valor de R${value:.2f} com vencimento em {date}."

# >>> NOVO CÓDIGO: Função para obter o relatório de dívidas
def get_debts_report(user_id):
    if not os.path.exists(DIVIDAS_FILE_NAME):
        return "Nenhuma dívida registrada ainda."
    
    report_lines = ["📋 *Suas Dívidas Pendentes* 📋\n"]
    total_debts = 0.0
    found_debts = False
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
# FIM DO NOVO CÓDIGO <<<

def set_balance(user_id, value):
    lines, user_found = [], False
    if os.path.exists(SALDO_FILE_NAME):
        with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()

    with open(SALDO_FILE_NAME, 'w', encoding='utf-8') as file:
        if not any(line.startswith("UserID;Saldo") for line in lines): file.write("UserID;Saldo\n")
        for line in lines:
            if line.startswith("UserID;Saldo"): continue
            if line.startswith(user_id):
                file.write(f"{user_id};{value:.2f}\n"); user_found = True
            else: file.write(line)
        if not user_found: file.write(f"{user_id};{value:.2f}\n")
    return f"✅ Saldo atualizado! Seu novo saldo é de *R${value:.2f}*."

def set_income(user_id, income):
    user_found, lines = False, []
    if os.path.exists(ORCAMENTO_FILE_NAME):
        with open(ORCAMENTO_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
    
    with open(ORCAMENTO_FILE_NAME, 'w', encoding='utf-8') as file:
        if not any(line.startswith("UserID;Rendimento") for line in lines): file.write("UserID;Rendimento\n")
        for line in lines:
            if line.startswith("UserID;Rendimento"): continue
            if line.startswith(user_id):
                file.write(f"{user_id};{income:.2f}\n"); user_found = True
            else: file.write(line)
        if not user_found: file.write(f"{user_id};{income:.2f}\n")
    return f"✅ Ótimo! O seu rendimento mensal foi definido como R${income:.2f}.\n\nPara ver o seu orçamento, envie `meu orçamento`."

def get_budget_report(user_id):
    income = 0.0
    if not os.path.exists(ORCAMENTO_FILE_NAME):
        return "Você ainda não definiu o seu rendimento. Use `definir rendimento [valor]` para começar."
    with open(ORCAMENTO_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id: income = float(row[1]); break
    if income == 0.0:
        return "Você ainda não definiu o seu rendimento. Use `definir rendimento [valor]` para começar."

    essentials_limit, wants_limit, savings_limit = income * 0.5, income * 0.3, income * 0.2
    essentials_spent, wants_spent = 0.0, 0.0
    current_month_str = datetime.datetime.now(TIMEZONE).strftime("%Y-%m")
    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id and row[2].startswith(current_month_str):
                    description, value = row[3].lower(), float(row[4])
                    if any(keyword in description for keyword in CATEGORY_KEYWORDS["Essenciais"]): essentials_spent += value
                    elif any(keyword in description for keyword in CATEGORY_KEYWORDS["Desejos"]): wants_spent += value
    
    report = ["📊 *Seu Orçamento Mensal (50/30/20)* 📊", f"\n*Gastos Essenciais (Limite: R${essentials_limit:.2f})*", f"Você gastou: R${essentials_spent:.2f}", f"\n*Desejos Pessoais (Limite: R${wants_limit:.2f})*", f"Você gastou: R${wants_spent:.2f}", f"\n*Poupança e Metas (Sugestão: R${savings_limit:.2f})*"]
    return "\n".join(report)

def get_financial_tip():
    tips = ["Dica: Anote todos os seus gastos, até os pequenos. Isso cria consciência de para onde o seu dinheiro está a ir.", "Dica: Antes de uma compra por impulso, espere 24 horas. Muitas vezes, a vontade passa e você economiza.", "Dica: Crie metas com nomes específicos, como 'Viagem'. É mais motivador do que apenas 'guardar dinheiro'.", "Dica: Reveja as suas subscrições mensais. Será que você realmente usa todos esses serviços de streaming?", "Dica: Tente a regra dos 30 dias: se quiser algo caro, espere 30 dias antes de comprar. Se ainda o quiser, vá em frente."]
    return random.choice(tips)

def compare_expenses(user_id):
    now = datetime.datetime.now(TIMEZONE)
    current_month_str = now.strftime("%Y-%m")
    last_month_date = now.replace(day=1) - datetime.timedelta(days=1)
    last_month_str = last_month_date.strftime("%Y-%m")
    current_month_total, last_month_total = 0.0, 0.0
    if not os.path.exists(CSV_FILE_NAME): return "Não há dados suficientes para comparar os seus gastos."
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                try:
                    timestamp, value = row[2], float(row[4])
                    if timestamp.startswith(current_month_str): current_month_total += value
                    elif timestamp.startswith(last_month_str): last_month_total += value
                except (ValueError, IndexError): continue
    if last_month_total == 0: return f"Você não tem gastos registados no mês passado para comparar. Total deste mês: R${current_month_total:.2f}"
    difference = current_month_total - last_month_total
    percentage_change = (difference / last_month_total) * 100
    comparison_text = "aumentaram" if difference > 0 else "diminuíram"
    report = ["📈 *Comparativo de Gastos Mensais* 📉", f"\n- Mês Passado: R${last_month_total:.2f}", f"- Mês Atual: R${current_month_total:.2f}", f"\nOs seus gastos *{comparison_text} {abs(percentage_change):.1f}%* em relação ao mês anterior."]
    return "\n".join(report)

def get_current_balance(user_id):
    if not os.path.exists(SALDO_FILE_NAME): return 0.0
    with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        for row in reader:
            if row and row[0] == user_id: return float(row[1])
    return 0.0

def record_payment_and_update_balance(user_id, value):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance + value
        lines, user_found = [], False
        if os.path.exists(SALDO_FILE_NAME):
            with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
        with open(SALDO_FILE_NAME, 'w', encoding='utf-8') as file:
            for line in lines:
                if line.startswith(user_id):
                    file.write(f"{user_id};{new_balance:.2f}\n"); user_found = True
                else: file.write(line)
            if not user_found: file.write(f"{user_id};{new_balance:.2f}\n")
        today_str = datetime.datetime.now(TIMEZONE).strftime("%d/%m")
        return f"✅ Pagamento de R${value:.2f} registrado em {today_str}!\n\nSeu saldo atual é de *R${new_balance:.2f}*."
    except Exception as e: return f"Ocorreu um erro ao registrar o pagamento: {e}"

def record_expense_and_update_balance(user_id, value):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance - value
        lines, user_found = [], False
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

def delete_last_expense(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Não há gastos para apagar."
    lines, last_expense_of_user = [], -1
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip().split(';')[0] == user_id:
            last_expense_of_user = i
            break
    if last_expense_of_user == -1: return "Você não tem gastos registados para apagar."
    deleted_line = lines.pop(last_expense_of_user).strip().split(';')
    deleted_description, deleted_value = deleted_line[3], float(deleted_line[4])
    with open(CSV_FILE_NAME, 'w', encoding='utf-8') as file: file.writelines(lines)
    record_payment_and_update_balance(user_id, deleted_value)
    return f"🗑️ Último gasto apagado!\n- Descrição: {deleted_description}\n- Valor: R${deleted_value:.2f}"

def get_financial_summary(user_id):
    balance = get_current_balance(user_id)
    return f"💰 *Resumo Financeiro*\nSeu saldo atual é: *R${balance:.2f}*."

def get_period_report(user_id, period):
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    total, now = 0.0, datetime.datetime.now(TIMEZONE)
    if period == "dia": start_date_str, period_name = now.strftime("%Y-%m-%d"), "hoje"
    elif period == "semana": start_date, period_name = now.date() - datetime.timedelta(days=now.weekday()), "na semana"
    elif period == "mês": start_date_str, period_name = now.strftime("%Y-%m"), "no mês"
    report_lines = [f"🧾 Seus gastos de {period_name} 🧾\n"]
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                try:
                    timestamp, value, description = row[2], float(row[4]), row[3]
                    match = False
                    if period == "semana":
                        if datetime.datetime.strptime(timestamp.split(' ')[0], "%Y-%m-%d").date() >= start_date: match = True
                    elif timestamp.startswith(start_date_str): match = True
                    if match:
                        report_lines.append(f"- {description}: R${value:.2f}"); total += value
                except (ValueError, IndexError): continue
    if len(report_lines) == 1: return f"Nenhum gasto registrado {period_name}."
    report_lines.append(f"\n*Total gasto: R${total:.2f}*")
    return "\n".join(report_lines)

def send_whatsapp_message(phone_number, message_text):
    try:
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
        data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e: print(f"Erro ao enviar mensagem para {phone_number}: {e}")

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
            if 'messages' not in value: return 'EVENT_RECEIVED', 200

            message_data = value['messages'][0]
            user_id = message_data['from']
            user_name = value['contacts'][0].get('profile', {}).get('name', 'Pessoa')
            message_text = message_data['text']['body'].strip().lower()
            
            reply_message = ""
            
            # --- LÓGICA DE COMANDOS MAIS HUMANA E ABRANGENTE ---
            
            # >>> CÓDIGO ALTERADO: Lógica de comando reestruturada para maior precisão
            
            # 1. Comandos de alta prioridade (perguntas e comandos específicos)
            if any(greeting in message_text for greeting in ["oi", "olá", "ajuda", "comandos", "menu"]):
                reply_message = f"Olá, {user_name}! 👋\n\n{COMMANDS_MESSAGE}"
            elif any(s in message_text for s in ["quais as minhas dívidas", "minhas dívidas", "ver dívidas", "relatório de dívidas"]):
                reply_message = get_debts_report(user_id)
            elif "definir rendimento" in message_text or "meu rendimento é" in message_text:
                values = extract_all_monetary_values(message_text)
                if values: reply_message = set_income(user_id, values[0])
                else: reply_message = "Não entendi o valor. Tente `definir rendimento [valor]`."
            elif "meu orçamento" in message_text:
                reply_message = get_budget_report(user_id)
            elif "dica" in message_text:
                reply_message = get_financial_tip()
            elif "comparar gastos" in message_text:
                reply_message = compare_expenses(user_id)
            elif "resumo financeiro" in message_text:
                reply_message = get_financial_summary(user_id)
            elif any(s in message_text for s in ["qual o meu saldo", "meu saldo", "ver saldo", "saldo atual", "como está meu saldo"]):
                 balance = get_current_balance(user_id)
                 reply_message = f"💵 Seu saldo atual é de *R${balance:.2f}*."
            elif "apagar último" in message_text or "excluir último" in message_text:
                reply_message = delete_last_expense(user_id)
            elif "meta" in message_text or "recorrente" in message_text:
                reply_message = "Esta funcionalidade ainda está em desenvolvimento, mas fico feliz que você se interessou! Em breve, você poderá criar metas e agendar lançamentos. 😉"
            elif "gastos d" in message_text or "relatório d" in message_text:
                if "hoje" in message_text or "dia" in message_text: reply_message = get_period_report(user_id, "dia")
                elif "semana" in message_text: reply_message = get_period_report(user_id, "semana")
                elif "mês" in message_text: reply_message = get_period_report(user_id, "mês")
                else: reply_message = "Não entendi o período. Tente `gastos do dia`, `da semana` ou `do mês`."
            
            # 2. Comandos de transação (dívidas, pagamentos, gastos)
            elif any(keyword in message_text for keyword in ["dívida", "parcela", "vence", "vencimento"]):
                values = extract_all_monetary_values(message_text)
                date = extract_date(message_text)
                if values and date:
                    description = re.sub(r'(\d{1,3}(?:\.\d{3})*,\d{1,2}|\d+,\d{1,2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+|R\$|\s+)', ' ', message_text).strip()
                    description = re.sub(r'vence dia.*', '', description).strip()
                    reply_message = save_debt_to_csv(user_id, date, values[0], description.capitalize())
                else:
                    reply_message = "Entendi que é uma dívida, mas não consegui identificar o valor e/ou a data de vencimento (dd/mm)."

            elif any(keyword in message_text for keyword in ["pagamento", "recebi", "salário"]):
                values = extract_all_monetary_values(message_text)
                if not values:
                    reply_message = "Entendi que é um pagamento, mas não consegui identificar o valor."
                elif any(keyword in message_text for keyword in ["já tinha", "tinha na conta"]):
                    total_balance = sum(values)
                    reply_message = set_balance(user_id, total_balance)
                else:
                    payment_value = max(values)
                    reply_message = record_payment_and_update_balance(user_id, payment_value)

            # 3. Fallback: Se não for nada acima, assume que é um gasto
            else:
                values = extract_all_monetary_values(message_text)
                if values:
                    value = values[0]
                    description = re.sub(r'(\d{1,3}(?:\.\d{3})*,\d{1,2}|\d+,\d{1,2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+|R\$|\s+)', ' ', message_text).strip()
                    description = re.sub(r'^(de|da|do|no|na)\s', '', description)
                    if not description:
                        reply_message = "Parece que você enviou um valor sem descrição. Tente de novo, por favor."
                    else:
                        category = save_expense_to_csv(user_id, description.capitalize(), value)
                        record_expense_and_update_balance(user_id, value)
                        today_str = datetime.datetime.now(TIMEZONE).strftime("%d/%m")
                        reply_message = f"✅ Gasto Registrado em {today_str}! ({category})\n- {description.capitalize()}: R${value:.2f}"
                else:
                    reply_message = f"Não entendi, {user_name}. Se for um gasto, tente `[descrição] [valor]`. Se precisar de ajuda, envie `comandos`."
            # FIM DA ALTERAÇÃO <<<

            if reply_message:
                send_whatsapp_message(user_id, reply_message)

        except (KeyError, IndexError, TypeError) as e:
            print(f"Erro ao processar o webhook: {e}")
            pass
        
        return 'EVENT_RECEIVED', 200
