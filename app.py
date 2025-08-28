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
# >>> NOVOS FICHEIROS PARA AS NOVAS FUNCIONALIDADES
ORCAMENTO_FILE_NAME = os.path.join(DATA_DIR, "orcamento.csv")
METAS_FILE_NAME = os.path.join(DATA_DIR, "metas.csv")
RECORRENTES_FILE_NAME = os.path.join(DATA_DIR, "recorrentes.csv")
# FIM DA ALTERAÇÃO <<<
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# Dicionário de palavras-chave para categorização automática
CATEGORY_KEYWORDS = {
    "Alimentação": ["restaurante", "almoço", "janta", "ifood", "rappi", "mercado", "comida", "lanche", "pizza", "hamburguer"],
    "Transporte": ["uber", "99", "táxi", "gasolina", "metrô", "ônibus", "passagem", "estacionamento", "escritorio"],
    "Moradia": ["aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu"],
    "Lazer": ["cinema", "show", "bar", "festa", "viagem", "streaming", "spotify", "netflix", "jogo"],
    "Saúde": ["farmácia", "remédio", "médico", "consulta", "plano", "academia", "suplemento"],
    "Compras": ["roupas", "presente", "shopping", "online", "eletrônicos"],
    "Educação": ["curso", "livro", "faculdade", "material"],
    # Categorias para o Orçamento 50/30/20
    "Essenciais": ["aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "mercado", "farmácia", "plano", "metrô", "ônibus"],
    "Desejos": ["restaurante", "ifood", "rappi", "lanche", "pizza", "cinema", "show", "bar", "festa", "viagem", "streaming", "jogo", "roupas", "presente", "shopping", "uber", "99", "táxi"]
}

# Mensagem de ajuda mais humana e com novos comandos
COMMANDS_MESSAGE = """
Olá! Sou a sua assistente financeira. 😊
Você pode falar comigo de forma natural! Tente coisas como:

- `gastei 25,50 no almoço`
- `qual o meu saldo?`
- `define meu rendimento em 3000`
- `meu orçamento`
- `criar meta viagem 5000`
- `gasto recorrente internet 100 dia 10`
- `comparar gastos`
- `dica financeira`

Aqui estão alguns dos comandos que eu entendo:

💰 **Orçamento e Metas**
- `definir rendimento [valor]`
- `meu orçamento`
- `criar meta [nome] [valor]`
- `adicionar à meta [nome] [valor]`
- `minhas metas`

🗓️ **Lançamentos Recorrentes**
- `gasto recorrente [descrição] [valor] dia [dia]`
- `receita recorrente [descrição] [valor] dia [dia]`

📊 **Análises e Relatórios**
- `resumo financeiro`
- `comparar gastos`
- `gastos da [semana/mês]`
- `análise da [semana/mês]`

💡 **Outros**
- `dica financeira`
- `apagar último gasto`
"""

# --- Funções da IA ---

def parse_value_string(s):
    if not isinstance(s, str): return float(s)
    s = s.replace('R$', '').strip()
    if ',' in s and s.rfind(',') > s.rfind('.'):
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '')
    return float(s)

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

# --- NOVAS FUNÇÕES PARA AS NOVAS FUNCIONALIDADES ---

def set_income(user_id, income):
    user_found = False
    lines = []
    if os.path.exists(ORCAMENTO_FILE_NAME):
        with open(ORCAMENTO_FILE_NAME, 'r', encoding='utf-8') as file:
            lines = file.readlines()
    
    with open(ORCAMENTO_FILE_NAME, 'w', encoding='utf-8') as file:
        if not any(line.startswith("UserID;Rendimento") for line in lines):
            file.write("UserID;Rendimento\n")
        for line in lines:
            if line.startswith("UserID;Rendimento"): continue # Pula o cabeçalho antigo se houver
            if line.startswith(user_id):
                file.write(f"{user_id};{income:.2f}\n")
                user_found = True
            else:
                file.write(line)
        if not user_found:
            file.write(f"{user_id};{income:.2f}\n")
    return f"✅ Ótimo! O seu rendimento mensal foi definido como R${income:.2f}.\n\nPara ver o seu orçamento, envie `meu orçamento`."

def get_budget_report(user_id):
    income = 0.0
    if not os.path.exists(ORCAMENTO_FILE_NAME):
        return "Você ainda não definiu o seu rendimento. Use `definir rendimento [valor]` para começar."
    with open(ORCAMENTO_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                income = float(row[1])
                break
    if income == 0.0:
        return "Você ainda não definiu o seu rendimento. Use `definir rendimento [valor]` para começar."

    essentials_limit = income * 0.5
    wants_limit = income * 0.3
    savings_limit = income * 0.2

    essentials_spent, wants_spent = 0.0, 0.0
    current_month_str = datetime.datetime.now(TIMEZONE).strftime("%Y-%m")
    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            next(reader, None)
            for row in reader:
                if row and row[0] == user_id and row[2].startswith(current_month_str):
                    description = row[3].lower()
                    value = float(row[4])
                    if any(keyword in description for keyword in CATEGORY_KEYWORDS["Essenciais"]):
                        essentials_spent += value
                    elif any(keyword in description for keyword in CATEGORY_KEYWORDS["Desejos"]):
                        wants_spent += value
    
    report = [
        "📊 *Seu Orçamento Mensal (50/30/20)* 📊",
        f"\n*Gastos Essenciais (Limite: R${essentials_limit:.2f})*",
        f"Você gastou: R${essentials_spent:.2f}",
        f"\n*Desejos Pessoais (Limite: R${wants_limit:.2f})*",
        f"Você gastou: R${wants_spent:.2f}",
        f"\n*Poupança e Metas (Sugestão: R${savings_limit:.2f})*"
    ]
    return "\n".join(report)

def get_financial_tip():
    tips = [
        "Dica: Anote todos os seus gastos, até os pequenos. Isso cria consciência de para onde o seu dinheiro está a ir.",
        "Dica: Antes de uma compra por impulso, espere 24 horas. Muitas vezes, a vontade passa e você economiza.",
        "Dica: Crie metas com nomes específicos, como 'Viagem'. É mais motivador do que apenas 'guardar dinheiro'.",
        "Dica: Reveja as suas subscrições mensais. Será que você realmente usa todos esses serviços de streaming?",
        "Dica: Tente a regra dos 30 dias: se quiser algo caro, espere 30 dias antes de comprar. Se ainda o quiser, vá em frente."
    ]
    return random.choice(tips)

def compare_expenses(user_id):
    now = datetime.datetime.now(TIMEZONE)
    current_month_str = now.strftime("%Y-%m")
    last_month_date = now.replace(day=1) - datetime.timedelta(days=1)
    last_month_str = last_month_date.strftime("%Y-%m")
    
    current_month_total = 0.0
    last_month_total = 0.0

    if not os.path.exists(CSV_FILE_NAME):
        return "Não há dados suficientes para comparar os seus gastos."

    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                try:
                    timestamp, value = row[2], float(row[4])
                    if timestamp.startswith(current_month_str):
                        current_month_total += value
                    elif timestamp.startswith(last_month_str):
                        last_month_total += value
                except (ValueError, IndexError):
                    continue

    if last_month_total == 0:
        return f"Você não tem gastos registados no mês passado para comparar. Total deste mês: R${current_month_total:.2f}"

    difference = current_month_total - last_month_total
    percentage_change = (difference / last_month_total) * 100
    
    comparison_text = "aumentaram" if difference > 0 else "diminuíram"
    
    report = [
        "📈 *Comparativo de Gastos Mensais* 📉",
        f"\n- Mês Passado: R${last_month_total:.2f}",
        f"- Mês Atual: R${current_month_total:.2f}",
        f"\nOs seus gastos *{comparison_text} {abs(percentage_change):.1f}%* em relação ao mês anterior."
    ]
    return "\n".join(report)

# --- FUNÇÕES ANTIGAS QUE CONTINUAM A SER ÚTEIS ---

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
        return f"✅ Pagamento de R${value:.2f} registrado!\n\nSeu saldo atual é de *R${new_balance:.2f}*."
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
    for i in range(len(lines) - 1, 0, -1): # Começa do fim, ignora o cabeçalho
        if lines[i].strip().split(';')[0] == user_id:
            last_expense_of_user = i
            break
    if last_expense_of_user == -1: return "Você não tem gastos registados para apagar."
    deleted_line = lines.pop(last_expense_of_user).strip().split(';')
    deleted_description, deleted_value = deleted_line[3], float(deleted_line[4])
    with open(CSV_FILE_NAME, 'w', encoding='utf-8') as file: file.writelines(lines)
    # Devolve o dinheiro ao saldo
    record_payment_and_update_balance(user_id, deleted_value)
    return f"🗑️ Último gasto apagado!\n- Descrição: {deleted_description}\n- Valor: R${deleted_value:.2f}"

def get_financial_summary(user_id):
    # Esta função pode ser melhorada para usar os dados do orçamento no futuro
    balance = get_current_balance(user_id)
    return f"💰 *Resumo Financeiro*\nSeu saldo atual é: *R${balance:.2f}*."

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
            
            # Comandos de ajuda e saudação
            if any(greeting in message_text for greeting in ["oi", "olá", "ajuda", "comandos", "menu"]):
                reply_message = f"Olá, {user_name}! 👋\n\n{COMMANDS_MESSAGE}"
            
            # Comandos de Orçamento
            elif "definir rendimento" in message_text or "meu rendimento é" in message_text:
                try:
                    income_str = re.search(r'(\d+([,.]\d{1,2})?)', message_text).group(0)
                    income = parse_value_string(income_str)
                    reply_message = set_income(user_id, income)
                except:
                    reply_message = "Não entendi o valor. Tente `definir rendimento [valor]`."
            elif "meu orçamento" in message_text:
                reply_message = get_budget_report(user_id)

            # Comandos de Análise e Dicas
            elif "dica" in message_text:
                reply_message = get_financial_tip()
            elif "comparar gastos" in message_text:
                reply_message = compare_expenses(user_id)
            elif "resumo financeiro" in message_text:
                reply_message = get_financial_summary(user_id)

            # Comandos de Saldo
            elif any(s in message_text for s in ["qual o meu saldo", "meu saldo", "ver saldo"]):
                 balance = get_current_balance(user_id)
                 reply_message = f"💵 Seu saldo atual é de *R${balance:.2f}*."

            # Comando para apagar último gasto
            elif "apagar último" in message_text or "excluir último" in message_text:
                reply_message = delete_last_expense(user_id)

            # Comando de Pagamento
            elif message_text.startswith("pagamento"):
                try:
                    value_str = message_text.split(" ", 1)[1].strip()
                    value = parse_value_string(value_str)
                    reply_message = record_payment_and_update_balance(user_id, value)
                except (ValueError, IndexError):
                    reply_message = "Comando inválido. Use: `pagamento [valor]`."

            # Se não for nenhum comando, assume que é um registo de gasto
            else:
                try:
                    # Tenta extrair valor e descrição de uma frase natural
                    value_str = re.search(r'(\d+([,.]\d{1,2})?)$', message_text).group(0)
                    value = parse_value_string(value_str)
                    description = message_text.replace(value_str, '').strip()
                    
                    if not description:
                         reply_message = "Parece que você enviou um valor sem descrição. Tente de novo, por favor."
                    else:
                        category = save_expense_to_csv(user_id, description.capitalize(), value)
                        record_expense_and_update_balance(user_id, value)
                        reply_message = f"✅ Gasto Registrado! ({category})\n- {description.capitalize()}: R${value:.2f}"
                except:
                    reply_message = f"Não entendi, {user_name}. Se for um gasto, tente `[descrição] [valor]`. Se precisar de ajuda, envie `comandos`."

            if reply_message:
                send_whatsapp_message(user_id, reply_message)

        except (KeyError, IndexError, TypeError) as e:
            print(f"Erro ao processar o webhook: {e}")
            pass
        
        return 'EVENT_RECEIVED', 200
