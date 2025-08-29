# -*- coding: utf-8 -*-

# Importa as ferramentas necessárias
import os
import json
import requests
import datetime
import csv
import re
import random
from collections import defaultdict
from flask import Flask, request # <-- CORREÇÃO AQUI

# --- CONFIGURAÇÃO DA APLICAÇÃO FLASK ---
app = Flask(__name__)

# --- CREDENCIAIS (CARREGADAS DO AMBIENTE) ---
# É uma boa prática carregar informações sensíveis das variáveis de ambiente
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# --- CONFIGURAÇÃO DOS ARQUIVOS DE DADOS ---
# Define o diretório de dados para persistência no Render ou localmente
DATA_DIR = os.getenv('RENDER_DISK_PATH', '.')
CSV_GASTOS = os.path.join(DATA_DIR, "gastos_usuarios.csv")
CSV_ENTRADAS = os.path.join(DATA_DIR, "entradas_usuarios.csv")
CSV_SALDO = os.path.join(DATA_DIR, "saldo_usuarios.csv")
CSV_DIVIDAS = os.path.join(DATA_DIR, "dividas_usuarios.csv")
CSV_ORCAMENTO = os.path.join(DATA_DIR, "orcamento_usuarios.csv")

# Define o fuso horário para o Brasil (Brasília)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# --- INTELIGÊNCIA DA IA: PALAVRAS-CHAVE E CATEGORIAS ---
CATEGORY_KEYWORDS = {
    "Alimentação": ["restaurante", "almoço", "janta", "ifood", "rappi", "mercado", "comida", "lanche", "pizza", "hamburguer", "padaria", "café", "sorvete", "açaí", "supermercado"],
    "Transporte": ["uber", "99", "táxi", "gasolina", "metrô", "ônibus", "passagem", "estacionamento", "combustível", "pedágio"],
    "Moradia": ["aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "diarista", "limpeza", "reforma", "manutenção", "conta"],
    "Lazer": ["cinema", "show", "bar", "festa", "viagem", "streaming", "spotify", "netflix", "jogo", "ingresso", "passeio", "clube", "hobby"],
    "Saúde": ["farmácia", "remédio", "médico", "consulta", "plano", "academia", "suplemento", "dentista", "exame", "terapia"],
    "Compras": ["roupa", "roupas", "tênis", "sapato", "presente", "shopping", "online", "eletrônicos", "celular", "livro"],
    "Educação": ["curso", "livro", "faculdade", "material", "escola", "aula"],
    "Outros": [] # Categoria padrão
}

# --- MENSAGENS E DICAS ---
COMMANDS_MESSAGE = """
Olá! Sou sua assistente financeira pessoal. 💸

Posso te ajudar a organizar suas finanças de forma simples e conversada.

Você pode me dizer coisas como:
- `Gastei 25,50 no almoço`
- `Recebi meu salário de 3500`
- `Tenho uma dívida de 180 da conta de luz que vence dia 15/09`
- `Paguei a conta de luz`

Aqui estão alguns comandos que você pode usar:

📊 *RELATÓRIOS*
- `saldo` - Para ver seu saldo atual.
- `resumo financeiro` - Visão geral das suas finanças.
- `gastos hoje` (ou `semana`/`mês`) - Lista seus gastos no período.
- `entradas e saídas hoje` (ou `semana`/`mês`) - Mostra o que entrou e saiu.
- `minhas dívidas` - Lista suas dívidas pendentes.

⚙️ *AÇÕES*
- `definir rendimento [valor]` - Para registrar sua renda mensal.
- `apagar último gasto` - Remove o último gasto que você registrou.
- `dica` - Te dou uma dica financeira rápida.

Se tiver qualquer dúvida, é só me chamar! 😊
"""

FINANCIAL_TIPS = [
    "Anote todos os seus gastos, até mesmo os pequenos. Isso te ajuda a entender para onde seu dinheiro está indo.",
    "Crie um orçamento mensal e tente segui-lo. A regra 50/30/20 (50% para necessidades, 30% para desejos e 20% para poupança) é um bom começo!",
    "Antes de fazer uma compra por impulso, espere 24 horas. Muitas vezes, a vontade passa e você economiza.",
    "Tenha uma reserva de emergência. O ideal é ter o equivalente a 3 a 6 meses do seu custo de vida guardado para imprevistos.",
    "Compare preços antes de comprar. A internet facilita muito a pesquisa e a economia.",
    "Evite usar o cartão de crédito para compras do dia a dia. É mais fácil perder o controle dos gastos assim.",
    "Defina metas financeiras claras, como 'guardar R$1000 para uma viagem'. Metas te mantêm motivado a economizar."
]

# --- FUNÇÕES AUXILIARES ---

def parse_monetary_value(text):
    """
    Função robusta para extrair o primeiro valor monetário de uma string.
    Trata formatos como '2.900,50', '2900,50', '2900.50', e '2900'.
    """
    if not isinstance(text, str):
        return None

    # Remove R$ e espaços extras para facilitar a análise
    text = text.replace('r$', '').strip()

    # Regex para encontrar números nos formatos mais comuns no Brasil
    # Prioriza números com vírgula como decimal
    pattern = r'(\d{1,3}(?:\.\d{3})*,\d{2})|(\d+,\d{2})|(\d{1,3}(?:\.\d{3})*\.\d{2})|(\d+\.\d{2})|(\d+)'
    matches = re.findall(pattern, text)

    if not matches:
        return None

    # O regex captura grupos, então precisamos achar o valor que não está vazio
    for match_tuple in matches:
        for match_str in match_tuple:
            if match_str:
                try:
                    # Limpa e converte para o formato padrão (ponto como decimal)
                    value_str = match_str.replace('.', '').replace(',', '.')
                    return float(value_str)
                except (ValueError, IndexError):
                    continue
    return None


def clean_description(text, value):
    """Remove o valor e palavras-chave da mensagem para obter a descrição limpa."""
    if value is None:
        return text
    # Remove o valor monetário (e variações de formato) da string
    value_str = f"{value:.2f}".replace('.', ',') # 2900.50 -> "2900,50"
    text = text.replace(value_str, '')
    text = text.replace(str(int(value)), '') # Remove a parte inteira também
    
    # Remove palavras comuns de comando
    keywords_to_remove = [
        'gastei', 'gasto', 'custou', 'foi', 'em', 'no', 'na', 'com', 'de', 'da', 'do',
        'recebi', 'pagamento', 'salário', 'ganhei', 'rendimento',
        'dívida', 'conta', 'vence', 'vencimento', 'paguei', 'apagar', 'último',
        'r$'
    ]
    for keyword in keywords_to_remove:
        text = text.replace(keyword, '')

    return text.strip().capitalize()


def infer_category(description):
    """Tenta adivinhar a categoria do gasto com base na descrição."""
    desc_lower = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in desc_lower for keyword in keywords):
            return category
    return "Outros"

def write_to_csv(filepath, header, row):
    """Função centralizada para escrever em arquivos CSV de forma segura."""
    file_exists = os.path.exists(filepath)
    try:
        with open(filepath, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            if not file_exists or os.path.getsize(filepath) == 0:
                writer.writerow(header)
            writer.writerow(row)
        return True
    except IOError as e:
        print(f"Erro de I/O ao escrever no arquivo {filepath}: {e}")
        return False

# --- FUNÇÕES DE LÓGICA FINANCEIRA ---

def get_balance(user_id):
    """Lê o saldo atual do usuário. Retorna 0.0 se não existir."""
    if not os.path.exists(CSV_SALDO):
        return 0.0
    with open(CSV_SALDO, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        for row in reader:
            if row and row[0] == user_id:
                return float(row[1])
    return 0.0

def update_balance(user_id, new_balance):
    """Atualiza ou cria o saldo do usuário no arquivo."""
    lines = []
    user_found = False
    if os.path.exists(CSV_SALDO):
        with open(CSV_SALDO, 'r', encoding='utf-8') as file:
            lines = file.readlines()

    with open(CSV_SALDO, 'w', encoding='utf-8') as file:
        header_written = False
        for line in lines:
            # Garante que o cabeçalho seja mantido se já existir
            if line.strip().lower() == "userid;saldo":
                if not header_written:
                    file.write("UserID;Saldo\n")
                    header_written = True
                continue
            
            if line.startswith(user_id):
                file.write(f"{user_id};{new_balance:.2f}\n")
                user_found = True
            else:
                file.write(line)
        
        if not header_written:
             file.write("UserID;Saldo\n")

        if not user_found:
            file.write(f"{user_id};{new_balance:.2f}\n")

def record_expense(user_id, value, description):
    """Registra um novo gasto e atualiza o saldo."""
    now_str = datetime.datetime.now(TIMEZONE).strftime("%Y-m-%d %H:%M:%S")
    category = infer_category(description)
    
    header = ["UserID", "DataHora", "Descricao", "Valor", "Categoria"]
    row = [user_id, now_str, description, f"{value:.2f}", category]
    
    if write_to_csv(CSV_GASTOS, header, row):
        current_balance = get_balance(user_id)
        update_balance(user_id, current_balance - value)
        return f"✅ Gasto registrado!\n- {description}: *R${value:.2f}* ({category})"
    else:
        return "❌ Ops, não consegui registrar seu gasto agora. Tente novamente."

def record_income(user_id, value, description):
    """Registra uma nova entrada e atualiza o saldo."""
    now_str = datetime.datetime.now(TIMEZONE).strftime("%Y-m-%d %H:%M:%S")
    
    header = ["UserID", "DataHora", "Descricao", "Valor"]
    row = [user_id, now_str, description, f"{value:.2f}"]

    if write_to_csv(CSV_ENTRADAS, header, row):
        current_balance = get_balance(user_id)
        new_balance = current_balance + value
        update_balance(user_id, new_balance)
        return f"💰 Entrada registrada!\n- {description}: *R${value:.2f}*\n\nSeu novo saldo é *R${new_balance:.2f}*."
    else:
        return "❌ Ops, não consegui registrar sua entrada agora. Tente novamente."

def delete_last_expense(user_id):
    """Apaga o último gasto registrado pelo usuário e devolve o valor ao saldo."""
    if not os.path.exists(CSV_GASTOS):
        return "Você ainda não tem gastos para apagar."

    lines = []
    with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    last_expense_index = -1
    for i in range(len(lines) - 1, 0, -1): # Começa do fim, ignora o cabeçalho
        if lines[i].strip().startswith(user_id):
            last_expense_index = i
            break
    
    if last_expense_index == -1:
        return "Não encontrei gastos seus para apagar."

    deleted_line_parts = lines.pop(last_expense_index).strip().split(';')
    deleted_description = deleted_line_parts[2]
    deleted_value = float(deleted_line_parts[3])

    with open(CSV_GASTOS, 'w', encoding='utf-8') as file:
        file.writelines(lines)
    
    # Devolve o valor ao saldo
    current_balance = get_balance(user_id)
    new_balance = current_balance + deleted_value
    update_balance(user_id, new_balance)
    
    return f"🗑️ Último gasto apagado com sucesso!\n- Descrição: {deleted_description}\n- Valor: R${deleted_value:.2f}\n\nO valor foi devolvido ao seu saldo. Seu novo saldo é *R${new_balance:.2f}*."


# --- FUNÇÕES DE RELATÓRIO ---

def get_period_report(user_id, period):
    """Gera um relatório de gastos para um período (dia, semana, mês)."""
    if not os.path.exists(CSV_GASTOS):
        return "Nenhum gasto registrado ainda."

    now = datetime.datetime.now(TIMEZONE)
    total_spent = 0.0
    report_lines = []
    
    if period == "dia":
        start_date = now.date()
        period_name = "hoje"
        report_lines.append(f"🧾 *Seus gastos de {period_name}* 🧾\n")
    elif period == "semana":
        start_date = now.date() - datetime.timedelta(days=now.weekday())
        period_name = "nesta semana"
        report_lines.append(f"🧾 *Seus gastos {period_name}* 🧾\n")
    elif period == "mês":
        start_date = now.date().replace(day=1)
        period_name = "neste mês"
        report_lines.append(f"🧾 *Seus gastos {period_name}* 🧾\n")

    with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        next(reader, None) # Pula o cabeçalho
        for row in reader:
            if row and row[0] == user_id:
                try:
                    expense_date = datetime.datetime.strptime(row[1], "%Y-m-%d %H:%M:%S").date()
                    if expense_date >= start_date:
                        description, value = row[2], float(row[3])
                        report_lines.append(f"- {description}: R${value:.2f}")
                        total_spent += value
                except (ValueError, IndexError):
                    continue
    
    if len(report_lines) == 1: # Apenas o cabeçalho foi adicionado
        return f"Você não teve gastos {period_name}. 🎉"
    
    report_lines.append(f"\n*Total gasto: R${total_spent:.2f}*")
    return "\n".join(report_lines)


def get_io_summary(user_id, period):
    """Gera um resumo de entradas e saídas para um período."""
    now = datetime.datetime.now(TIMEZONE)
    total_in, total_out = 0.0, 0.0

    if period == "dia":
        start_date, period_name = now.date(), "hoje"
    elif period == "semana":
        start_date, period_name = now.date() - datetime.timedelta(days=now.weekday()), "na semana"
    elif period == "mês":
        start_date, period_name = now.date().replace(day=1), "no mês"

    # Calcula saídas
    if os.path.exists(CSV_GASTOS):
        with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        if datetime.datetime.strptime(row[1], "%Y-m-%d %H:%M:%S").date() >= start_date:
                            total_out += float(row[3])
                    except (ValueError, IndexError): continue
    
    # Calcula entradas
    if os.path.exists(CSV_ENTRADAS):
        with open(CSV_ENTRADAS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        if datetime.datetime.strptime(row[1], "%Y-m-%d %H:%M:%S").date() >= start_date:
                            total_in += float(row[3])
                    except (ValueError, IndexError): continue
    
    return f"💸 *Balanço de {period_name}*\n\n- Entradas: *R${total_in:.2f}*\n- Saídas: *R${total_out:.2f}*"


# --- FUNÇÃO DE ENVIO DE MENSAGEM ---

def send_whatsapp_message(phone_number, message_text):
    """Envia uma mensagem de texto para o usuário via WhatsApp API."""
    if not all([ACCESS_TOKEN, PHONE_NUMBER_ID]):
        print("ERRO: As credenciais ACCESS_TOKEN e PHONE_NUMBER_ID não estão configuradas.")
        return

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "text": {"body": message_text}
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status() # Lança um erro para respostas HTTP 4xx/5xx
        print(f"Mensagem enviada para {phone_number}. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar mensagem para {phone_number}: {e}")
        print(f"Resposta do servidor: {e.response.text if e.response else 'N/A'}")


# --- PROCESSADOR DE COMANDOS ---

def process_message(user_id, user_name, message_text):
    """
    Função principal que interpreta a mensagem do usuário e decide qual ação tomar.
    Essa estrutura é mais organizada e fácil de expandir do que um grande bloco if/elif.
    """
    
    # 1. Comandos diretos e de alta prioridade
    if any(word in message_text for word in ["ajuda", "comandos", "menu", "começar"]):
        return COMMANDS_MESSAGE
    
    if any(word in message_text for word in ["oi", "olá", "bom dia", "boa tarde", "boa noite"]):
        return f"Olá, {user_name}! Como posso te ajudar a controlar suas finanças hoje? Se precisar, digite 'comandos' para ver as opções. 😊"

    if "saldo" in message_text:
        balance = get_balance(user_id)
        return f"💵 Seu saldo atual é de *R${balance:.2f}*."

    if "apagar último" in message_text or "excluir último" in message_text:
        return delete_last_expense(user_id)
        
    if "dica" in message_text:
        return random.choice(FINANCIAL_TIPS)

    # 2. Comandos de Relatório com Período
    if any(word in message_text for word in ["gastos", "gastei", "relatório"]):
        if "hoje" in message_text or "dia" in message_text:
            return get_period_report(user_id, "dia")
        if "semana" in message_text:
            return get_period_report(user_id, "semana")
        if "mês" in message_text:
            return get_period_report(user_id, "mês")

    if any(word in message_text for word in ["entradas e saídas", "entrou e saiu", "balanço"]):
        if "hoje" in message_text or "dia" in message_text:
            return get_io_summary(user_id, "dia")
        if "semana" in message_text:
            return get_io_summary(user_id, "semana")
        if "mês" in message_text:
            return get_io_summary(user_id, "mês")

    # 3. Comandos de Transação (com valor monetário)
    value = parse_monetary_value(message_text)
    if value is not None:
        # Se tem valor, pode ser uma entrada ou uma saída
        description = clean_description(message_text, value)
        
        # Palavras-chave que indicam ENTRADA
        income_keywords = ["recebi", "salário", "ganhei", "depósito", "rendimento", "entrada"]
        if any(keyword in message_text for keyword in income_keywords):
            if not description: description = "Entrada"
            return record_income(user_id, value, description)
            
        # Se não for entrada, assume-se que é um GASTO (lógica padrão)
        if not description: description = "Gasto geral"
        return record_expense(user_id, value, description)

    # 4. Se nada correspondeu, retorna mensagem de ajuda
    return f"Não entendi, {user_name}. 🤔\nSe for um gasto ou entrada, tente algo como `gastei 15 com lanche` ou `recebi 100 de um trabalho`.\n\nPara ver tudo que eu faço, envie a palavra `comandos`."


# --- WEBHOOK PRINCIPAL DA APLICAÇÃO ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # Verificação do Webhook (necessário para a API do WhatsApp)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            return 'Failed verification', 403
    
    # Processamento das mensagens recebidas
    if request.method == 'POST':
        data = request.get_json()
        try:
            # Estrutura de dados da notificação do WhatsApp
            if 'entry' in data and data['entry'][0]['changes'][0]['value'].get('messages'):
                message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
                
                # Ignora mensagens que não são de texto
                if message_data.get('type') != 'text':
                    return 'EVENT_RECEIVED', 200

                user_id = message_data['from']
                user_name = data['entry'][0]['changes'][0]['value']['contacts'][0].get('profile', {}).get('name', 'Pessoa')
                message_text = message_data['text']['body'].strip().lower()
                
                print(f"Recebida mensagem de {user_name} ({user_id}): '{message_text}'")

                # Processa a mensagem e obtém a resposta
                reply_message = process_message(user_id, user_name, message_text)
                
                # Envia a resposta de volta para o usuário
                if reply_message:
                    send_whatsapp_message(user_id, reply_message)

        except (KeyError, IndexError, TypeError) as e:
            print(f"Erro ao processar a estrutura do webhook: {e}")
            print(f"Dados recebidos: {json.dumps(data, indent=2)}")
            pass # Ignora eventos que não são mensagens de texto
            
        return 'EVENT_RECEIVED', 200
