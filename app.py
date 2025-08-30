# -*- coding: utf-8 -*-

# Importa as ferramentas necessárias
import os
import json
import requests
import datetime
import csv
import re
import random
from flask import Flask, request
import google.generativeai as genai # Nova importação para o Gemini

# --- CONFIGURAÇÃO DA APLicação FLASK ---
app = Flask(__name__)

# --- CREDENCIAIS (CARREGADAS DO AMBIENTE) ---
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Nova credencial para a API do Gemini

# --- CONFIGURAÇÃO DA API DO GEMINI ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("API do Gemini configurada com sucesso.")
except Exception as e:
    print(f"!!! ERRO AO CONFIGURAR A API DO GEMINI: {e} !!!")
    model = None

# --- CONFIGURAÇÃO DOS ARQUIVOS DE DADOS ---
DATA_DIR = os.getenv('RENDER_DISK_PATH', '.')
CSV_GASTOS = os.path.join(DATA_DIR, "gastos_usuarios.csv")
CSV_ENTRADAS = os.path.join(DATA_DIR, "entradas_usuarios.csv")
CSV_SALDO = os.path.join(DATA_DIR, "saldo_usuarios.csv")
CSV_DIVIDAS = os.path.join(DATA_DIR, "dividas_usuarios.csv")

# Define o fuso horário para o Brasil (Brasília)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# --- CATEGORIAS (USADAS PELAS FUNÇÕES, NÃO MAIS PELO PROCESSADOR PRINCIPAL) ---
CATEGORY_KEYWORDS = {
    "Alimentação": ["restaurante", "almoço", "janta", "ifood", "rappi", "mercado", "comida", "lanche", "pizza", "hamburguer", "padaria", "café", "sorvete", "açaí", "supermercado", "hortifruti", "sacolão", "feira", "açougue", "peixaria", "doces", "bolo", "salgado", "esfiha", "pastel", "churrasco", "bebida", "refrigerante", "cerveja", "vinho", "suco", "água", "energético", "quitanda", "mercearia", "conveniência", "delivery", "marmita", "quentinha", "sushi", "temaki", "japonês", "chinês", "italiano", "mexicano", "árabe", "pão", "leite", "queijo", "presunto", "frutas", "verduras", "legumes", "carne", "frango", "peixe", "ovos", "arroz", "feijão", "macarrão", "molho", "biscoito", "bolacha", "chocolate", "bombom", "cereal", "chiclete"],
    "Transporte": ["uber", "99", "táxi", "gasolina", "etanol", "diesel", "combustível", "metrô", "ônibus", "trem", "passagem", "estacionamento", "pedágio", "rodízio", "multa", "ipva", "licenciamento", "seguro do carro", "mecânico", "oficina", "troca de óleo", "pneu", "manutenção do carro", "lavagem", "lava-rápido", "aluguel de carro", "passagem aérea", "aeroporto", "rodoviária", "barca", "balsa", "frete", "carreto", "recarga bilhete único"],
    "Moradia": ["aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "diarista", "faxineira", "limpeza", "reforma", "manutenção", "conserto", "eletricista", "encanador", "pintor", "marceneiro", "material de construção", "tinta", "cimento", "areia", "ferramenta", "decoração", "móvel", "sofá", "cama", "mesa", "cadeira", "eletrodoméstico", "geladeira", "fogão", "microondas", "máquina de lavar", "tv a cabo", "segurança", "alarme"],
    "Vestuário e Acessórios": ["roupa", "roupas", "tênis", "sapato", "bota", "sandália", "chinelo", "camiseta", "camisa", "blusa", "calça", "bermuda", "short", "saia", "vestido", "casaco", "jaqueta", "moletom", "terno", "blazer", "gravata", "meia", "cueca", "calcinha", "sutiã", "pijama", "biquíni", "sunga", "maiô", "acessório", "bolsa", "carteira", "cinto", "chapéu", "boné", "gorro", "cachecol", "luva", "óculos", "relógio", "joia", "brinco", "colar", "pulseira", "anel", "maquilhagem", "batom", "base", "rímel", "perfume", "creme", "cosméticos", "lavanderia", "costureira", "ajuste de roupa", "sapataria"],
    "Lazer": ["cinema", "show", "teatro", "concerto", "bar", "balada", "festa", "viagem", "hotel", "pousada", "hostel", "passagem de avião", "streaming", "spotify", "netflix", "hbo", "disney", "amazon prime", "youtube premium", "jogo", "game", "steam", "playstation", "xbox", "nintendo", "ingresso", "passeio", "parque", "praia", "clube", "hobby", "instrumento musical", "artesanato", "dança", "luta", "esporte", "futebol", "ingresso de jogo"],
    "Saúde": ["farmácia", "remédio", "medicamento", "médico", "consulta", "plano de saúde", "convênio", "academia", "suplemento", "whey", "creatina", "dentista", "aparelho", "exame", "laboratório", "terapia", "psicólogo", "fisioterapia", "pilates", "yoga", "nutricionista", "oftalmologista", "óculos de grau", "lente de contato", "veterinário", "pet shop", "ração", "vacina do pet"],
    "Educação": ["curso", "livro", "ebook", "faculdade", "universidade", "mensalidade", "material escolar", "caderno", "caneta", "lápis", "mochila", "escola", "colégio", "aula particular", "professor", "palestra", "workshop", "seminário", "inscrição", "concurso", "certificação", "idiomas", "inglês", "espanhol"],
}

# --- DICAS FINANCEIRAS ---
FINANCIAL_TIPS = [
    "Anote todos os seus gastos, até os pequenos. Isso te ajuda a entender para onde seu dinheiro está indo.", "Crie um orçamento mensal. A regra 50/30/20 (50% necessidades, 30% desejos, 20% poupança) é um bom começo!", "Antes de uma compra por impulso, espere 24 horas. Muitas vezes, a vontade passa e você economiza.", "Tenha uma reserva de emergência. O ideal é ter o equivalente a 3 a 6 meses do seu custo de vida guardado.", "Compare preços antes de comprar. A internet facilita muito a pesquisa e a economia.", "Evite usar o cartão de crédito para compras do dia a dia. É mais fácil perder o controle dos gastos assim.", "Defina metas financeiras claras, como 'guardar R$1000 para uma viagem'. Metas te mantêm motivado."
]

# --- O NOVO CÉREBRO: O PROMPT DE SISTEMA PARA O GEMINI ---
SYSTEM_PROMPT = """
Você é um assistente financeiro especialista em interpretar mensagens de WhatsApp em português do Brasil. Sua única função é analisar a mensagem do usuário e extrair os dados financeiros, retornando APENAS um objeto JSON.

**Regras Estritas:**
1.  **NUNCA** responda com texto conversacional. Sua saída deve ser **EXCLUSIVAMENTE** um JSON válido.
2.  Se a mensagem for um cumprimento, pedido de ajuda ou algo não financeiro, retorne `{"action": "chat", "response": "ajuda"}`.
3.  Analise a **intenção principal** antes de extrair os dados.
4.  Para valores monetários, sempre converta para um número (float), independentemente do formato de entrada (ex: "2.250,50" -> 2250.50, "2.250" -> 2250.0).

**Estrutura do JSON de Saída:**

-   **Para registrar gastos:**
    `{"action": "record_expense", "transactions": [{"value": 50.50, "description": "Almoço"}, {"value": 15.00, "description": "Uber"}]}`
    (A lista `transactions` pode conter um ou mais objetos).

-   **Para registrar uma entrada/salário:**
    `{"action": "record_income", "value": 3500.00, "description": "Salário"}`

-   **Para registrar uma dívida:**
    `{"action": "record_debt", "value": 180.75, "description": "Conta de luz", "due_date": "15/09"}`
    (Se não houver data, use "Sem data").

-   **Para PAGAR uma dívida:**
    `{"action": "pay_debt", "description": "conta de luz"}`

-   **Para DEFINIR o saldo inicial:**
    `{"action": "set_balance", "value": 2250.00}`

-   **Para CONSULTAR o saldo:**
    `{"action": "get_balance"}`

-   **Para pedir o RESUMO FINANCEIRO:**
    `{"action": "get_summary"}`

-   **Para pedir um RELATÓRIO DE GASTOS:**
    `{"action": "get_period_report", "period": "dia"}` (period pode ser "dia", "semana", ou "mês").

-   **Para pedir o BALANÇO (entradas/saídas):**
    `{"action": "get_io_summary", "period": "dia"}`

-   **Para APAGAR o último gasto:**
    `{"action": "delete_last"}`
    
-   **Para pedir uma DICA:**
    `{"action": "get_tip"}`

-   **Para ver a LISTA DE DÍVIDAS:**
    `{"action": "get_debts"}`
    
-   **Se não entender ou for uma conversa normal:**
    `{"action": "chat", "response": "ajuda"}`

**Exemplos de Interpretação:**
- "meu saldo atual na conta é 2.250" -> `{"action": "set_balance", "value": 2250.00}`
- "gastei 50 no mercado e 25,50 na farmácia" -> `{"action": "record_expense", "transactions": [{"value": 50.00, "description": "Mercado"}, {"value": 25.50, "description": "Farmácia"}]}`
- "tenho uma conta de 150 para pagar dia 10/12" -> `{"action": "record_debt", "value": 150.00, "description": "Conta", "due_date": "10/12"}`
- "qual meu saldo?" -> `{"action": "get_balance"}`
- "oi tudo bem" -> `{"action": "chat", "response": "saudacao"}`
"""

# --- FUNÇÕES DE LÓGICA FINANCEIRA (A MAIORIA PERMANECE IGUAL) ---
# Estas funções agora apenas EXECUTAM as ordens recebidas do Gemini.

def infer_category(description):
    desc_lower = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in desc_lower for keyword in keywords): return category
    return "Outros"

def write_to_csv(filepath, header, row):
    file_exists = os.path.exists(filepath)
    try:
        with open(filepath, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            if not file_exists or os.path.getsize(filepath) == 0: writer.writerow(header)
            writer.writerow(row)
        return True
    except IOError as e:
        print(f"Erro de I/O ao escrever no arquivo {filepath}: {e}")
        return False

def get_balance(user_id):
    if not os.path.exists(CSV_SALDO): return 0.0
    with open(CSV_SALDO, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id: return float(row[1])
    return 0.0

def set_balance(user_id, new_balance):
    lines = []; user_found = False
    if os.path.exists(CSV_SALDO):
        with open(CSV_SALDO, 'r', encoding='utf-8') as file: lines = file.readlines()
    with open(CSV_SALDO, 'w', encoding='utf-8') as file:
        header_written = False
        if not lines or not lines[0].strip().lower() == "userid;saldo":
            file.write("UserID;Saldo\n"); header_written = True
        for line in lines:
            if line.strip().lower() == "userid;saldo" and not header_written:
                file.write(line); header_written = True; continue
            elif line.strip().lower() == "userid;saldo" and header_written: continue
            if line.startswith(user_id):
                file.write(f"{user_id};{new_balance:.2f}\n"); user_found = True
            elif line.strip(): file.write(line)
        if not user_found: file.write(f"{user_id};{new_balance:.2f}\n")

def record_expense(user_id, value, description, update_balance=True):
    now = datetime.datetime.now(TIMEZONE)
    now_str_db = now.strftime("%Y-%m-%d %H:%M:%S")
    category = infer_category(description)
    header = ["UserID", "DataHora", "Descricao", "Valor", "Categoria"]
    row = [user_id, now_str_db, description, f"{value:.2f}", category]
    if write_to_csv(CSV_GASTOS, header, row):
        if update_balance:
            current_balance = get_balance(user_id)
            set_balance(user_id, current_balance - value)
        return {"description": description, "value": value, "category": category}
    return None

def record_income(user_id, value, description):
    now = datetime.datetime.now(TIMEZONE)
    today_str_msg = now.strftime("%d/%m")
    header = ["UserID", "DataHora", "Descricao", "Valor"]
    row = [user_id, now.strftime("%Y-%m-%d %H:%M:%S"), description, f"{value:.2f}"]
    if write_to_csv(CSV_ENTRADAS, header, row):
        current_balance = get_balance(user_id)
        new_balance = current_balance + value
        set_balance(user_id, new_balance)
        return f"💰 Entrada registrada em {today_str_msg}!\n- {description}: *R${value:.2f}*\n\nSeu novo saldo é *R${new_balance:.2f}*."
    return "❌ Ops, não consegui registrar sua entrada."

def record_debt(user_id, value, description, due_date):
    header = ["UserID", "DataVencimento", "Descricao", "Valor"]
    row = [user_id, due_date, description, f"{value:.2f}"]
    if write_to_csv(CSV_DIVIDAS, header, row):
        return f"🧾 Dívida registrada!\n- {description}: *R${value:.2f}*\n- Vencimento: {due_date}"
    return "❌ Ops, não consegui registrar sua dívida."

def pay_debt(user_id, search_desc):
    if not os.path.exists(CSV_DIVIDAS): return "Você não tem nenhuma dívida para pagar."
    lines = []; debt_found = None
    with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file: lines = file.readlines()
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip().startswith(user_id):
            parts = lines[i].strip().split(';')
            if search_desc.lower() in parts[2].lower():
                debt_found = {"index": i, "desc": parts[2], "value": float(parts[3])}
                break
    if not debt_found: return f"Não encontrei a dívida '{search_desc}'. Verifique a lista em 'minhas dívidas'."
    lines.pop(debt_found["index"])
    with open(CSV_DIVIDAS, 'w', encoding='utf-8') as file: file.writelines(lines)
    payment_desc = f"Pagamento: {debt_found['desc']}"
    record_expense(user_id, debt_found['value'], payment_desc)
    new_balance = get_balance(user_id)
    return f"✅ Dívida '{debt_found['desc']}' paga com sucesso!\nSeu novo saldo é *R${new_balance:.2f}*."

def delete_last_expense(user_id):
    if not os.path.exists(CSV_GASTOS): return "Você não tem gastos para apagar."
    lines = []; last_expense_index = -1
    with open(CSV_GASTOS, 'r', encoding='utf-8') as file: lines = file.readlines()
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip().startswith(user_id): last_expense_index = i; break
    if last_expense_index == -1: return "Não encontrei gastos seus para apagar."
    deleted_line_parts = lines.pop(last_expense_index).strip().split(';')
    deleted_description = deleted_line_parts[2]; deleted_value = float(deleted_line_parts[3])
    with open(CSV_GASTOS, 'w', encoding='utf-8') as file: file.writelines(lines)
    new_balance = get_balance(user_id) + deleted_value
    set_balance(user_id, new_balance)
    return f"🗑️ Último gasto apagado!\n- {deleted_description}: R${deleted_value:.2f}\nO valor foi devolvido. Novo saldo: *R${new_balance:.2f}*."

def get_debts_report(user_id):
    if not os.path.exists(CSV_DIVIDAS): return "Você não tem nenhuma dívida registrada. Parabéns! 🎉"
    report_lines = ["📋 *Suas Dívidas Pendentes* 📋\n"]; total_debts = 0.0
    with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                due_date, desc, value = row[1], row[2], float(row[3])
                report_lines.append(f"- {desc} (Vence: {due_date}): R${value:.2f}"); total_debts += value
    if len(report_lines) == 1: return "Você não tem nenhuma dívida registrada. Parabéns! 🎉"
    report_lines.append(f"\n*Total de Dívidas: R${total_debts:.2f}*")
    return "\n".join(report_lines)

def get_financial_summary(user_id):
    balance = get_balance(user_id)
    total_debts = sum(float(row[3]) for row in csv.reader(open(CSV_DIVIDAS), delimiter=';') if row and row[0] == user_id) if os.path.exists(CSV_DIVIDAS) else 0.0
    return f"📊 *Resumo Financeiro*\n\n- Saldo em conta: *R${balance:.2f}*\n- Total de dívidas: *R${total_debts:.2f}*"

# --- FUNÇÕES DE RELATÓRIO (CONTINUAM IGUAIS) ---
# ... (get_period_report, get_io_summary) ...

def get_period_report(user_id, period):
    if not os.path.exists(CSV_GASTOS): return "Nenhum gasto registrado ainda."
    now = datetime.datetime.now(TIMEZONE); total_spent = 0.0; report_lines = []
    if period == "dia": start_date = now.date(); period_name = "hoje"
    elif period == "semana": start_date = now.date() - datetime.timedelta(days=now.weekday()); period_name = "nesta semana"
    else: start_date = now.date().replace(day=1); period_name = "neste mês"
    report_lines.append(f"🧾 *Seus gastos {period_name}* 🧾\n")
    with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                expense_date = datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date()
                if expense_date >= start_date:
                    report_lines.append(f"- {row[2]}: R${float(row[3]):.2f}"); total_spent += float(row[3])
    if len(report_lines) == 1: return f"Você não teve gastos {period_name}. 🎉"
    report_lines.append(f"\n*Total gasto: R${total_spent:.2f}*")
    return "\n".join(report_lines)

def get_io_summary(user_id, period):
    now = datetime.datetime.now(TIMEZONE); total_in, total_out = 0.0, 0.0
    if period == "dia": start_date, period_name = now.date(), "de hoje"
    elif period == "semana": start_date, period_name = now.date() - datetime.timedelta(days=now.weekday()), "da semana"
    else: start_date, period_name = now.date().replace(day=1), "do mês"
    if os.path.exists(CSV_GASTOS):
        with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    if datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date() >= start_date: total_out += float(row[3])
    if os.path.exists(CSV_ENTRADAS):
        with open(CSV_ENTRADAS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    if datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date() >= start_date: total_in += float(row[3])
    return f"💸 *Balanço {period_name}*\n\n- Entradas: *R${total_in:.2f}*\n- Saídas: *R${total_out:.2f}*"

# --- FUNÇÃO DE ENVIO DE MENSAGEM ---
def send_whatsapp_message(phone_number, message_text):
    if not all([ACCESS_TOKEN, PHONE_NUMBER_ID]): print("ERRO: Credenciais não configuradas."); return
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}
    try:
        response = requests.post(url, headers=headers, json=data); response.raise_for_status()
        print(f"Mensagem enviada para {phone_number}.")
    except requests.exceptions.RequestException as e: print(f"Erro ao enviar mensagem: {e}")

# --- PROCESSADOR DE COMANDOS COM GEMINI ---
def process_message_with_llm(user_id, user_name, message_text):
    if not model:
        return "❌ Desculpe, meu cérebro de IA não está conectado agora. Por favor, verifique a configuração da API Key."

    try:
        # Combina o prompt do sistema com a mensagem do usuário
        full_prompt = f"{SYSTEM_PROMPT}\n\nMensagem do Usuário: \"{message_text}\""
        
        # Chama a API do Gemini
        response = model.generate_content(full_prompt)
        
        # Limpa e converte a resposta para JSON
        json_response_text = response.text.strip().replace("```json", "").replace("```", "")
        action_data = json.loads(json_response_text)
        action = action_data.get("action")
        
        print(f"Ação interpretada pelo Gemini: {action}")

        # Executa a ação correspondente
        if action == "record_expense":
            transactions = action_data.get("transactions", [])
            if not transactions: return "Não consegui identificar os gastos. Pode tentar de novo?"
            
            today_str_msg = datetime.datetime.now(TIMEZONE).strftime("%d/%m")
            response_lines = [f"Entendido! Registrei {len(transactions)} transação(ões) para você em {today_str_msg}:"]
            total_value = 0
            
            for trans in transactions:
                result = record_expense(user_id, trans['value'], trans['description'], update_balance=False)
                if result:
                    response_lines.append(f"- {result['description']}: *R${result['value']:.2f}* ({result['category']})")
                    total_value += result['value']
            
            current_balance = get_balance(user_id)
            set_balance(user_id, current_balance - total_value)
            response_lines.append(f"\nSeu novo saldo é *R${get_balance(user_id):.2f}*.")
            return "\n".join(response_lines)

        elif action == "record_income":
            return record_income(user_id, action_data['value'], action_data['description'])
        
        elif action == "record_debt":
            return record_debt(user_id, action_data['value'], action_data['description'], action_data['due_date'])

        elif action == "pay_debt":
            return pay_debt(user_id, action_data['description'])

        elif action == "set_balance":
            set_balance(user_id, action_data['value'])
            return f"✅ Saldo definido! Seu saldo atual é *R${action_data['value']:.2f}*."

        elif action == "get_balance":
            return f"💵 Seu saldo atual é de *R${get_balance(user_id):.2f}*."

        elif action == "get_summary":
            return get_financial_summary(user_id)
            
        elif action == "get_period_report":
            return get_period_report(user_id, action_data['period'])

        elif action == "get_io_summary":
            return get_io_summary(user_id, action_data['period'])

        elif action == "delete_last":
            return delete_last_expense(user_id)
            
        elif action == "get_tip":
            return random.choice(FINANCIAL_TIPS)

        elif action == "get_debts":
            return get_debts_report(user_id)
            
        elif action == "chat":
            response_type = action_data.get("response")
            if response_type == "saudacao":
                return f"Olá, {user_name}! Como posso te ajudar hoje? 😊"
            else: # "ajuda" ou qualquer outro chat
                return f"Não entendi. Se precisar de ajuda, envie `comandos`."

        else:
            return "Não consegui entender o seu pedido. Pode tentar de outra forma?"

    except Exception as e:
        print(f"!!! ERRO AO PROCESSAR COM O GEMINI: {e} !!!")
        return "❌ Desculpe, tive um problema para entender o seu pedido. Tente ser mais específico, por favor."

# --- WEBHOOK PRINCIPAL (AGORA CHAMA A FUNÇÃO DO LLM) ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode, token, challenge = request.args.get('hub.mode'), request.args.get('hub.verify_token'), request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED"); return challenge, 200
        return 'Failed verification', 403
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            if 'entry' in data and data['entry'][0]['changes'][0]['value'].get('messages'):
                message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
                if message_data.get('type') != 'text': return 'EVENT_RECEIVED', 200
                user_id = message_data['from']
                user_name = data['entry'][0]['changes'][0]['value']['contacts'][0].get('profile', {}).get('name', 'Pessoa')
                message_text = message_data['text']['body'].strip()
                
                print(f"Recebida mensagem de {user_name} ({user_id}): '{message_text}'")
                
                # A grande mudança: chamamos o processador com LLM
                reply_message = process_message_with_llm(user_id, user_name, message_text)
                
                if reply_message: send_whatsapp_message(user_id, reply_message)
        except Exception as e:
            print(f"!!! ERRO CRÍTICO NO WEBHOOK: {e} !!!")
        return 'EVENT_RECEIVED', 200