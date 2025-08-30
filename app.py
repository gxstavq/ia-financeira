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
from collections import defaultdict

# --- CONFIGURAÇÃO DA APLICAÇÃO FLASK ---
app = Flask(__name__)

# --- CREDENCIAIS (CARREGADAS DO AMBIENTE) ---
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# --- CONFIGURAÇÃO DOS ARQUIVOS DE DADOS ---
# Garante que o diretório de dados exista
DATA_DIR = os.getenv('RENDER_DISK_PATH', '.')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

CSV_GASTOS = os.path.join(DATA_DIR, "gastos_usuarios.csv")
CSV_ENTRADAS = os.path.join(DATA_DIR, "entradas_usuarios.csv")
CSV_SALDO = os.path.join(DATA_DIR, "saldo_usuarios.csv")
CSV_DIVIDAS = os.path.join(DATA_DIR, "dividas_usuarios.csv")

# Define o fuso horário para o Brasil (Brasília)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# --- INTELIGÊNCIA DA IA: EXPANSÃO MASSIVA DE CATEGORIAS E PALAVRAS-CHAVE ---
# Esta seção é o cérebro da categorização. Contém centenas de palavras, marcas e gírias
# para identificar com precisão para onde o dinheiro do usuário está indo.
CATEGORY_KEYWORDS = {
    "Alimentação": [
        "restaurante", "almoço", "janta", "jantar", "ifood", "rappi", "uber eats", "mercado", "comida", "lanche", "pizza", "hamburguer",
        "padaria", "café", "starbucks", "sorvete", "açaí", "supermercado", "hortifruti", "sacolão", "feira", "açougue",
        "peixaria", "doces", "bolo", "salgado", "esfiha", "pastel", "churrasco", "bebida", "refrigerante", "coca-cola",
        "cerveja", "vinho", "suco", "água", "energético", "quitanda", "mercearia", "conveniência", "delivery",
        "marmita", "quentinha", "sushi", "temaki", "japonês", "chinês", "italiano", "mexicano", "árabe",
        "pão", "leite", "queijo", "presunto", "frutas", "verduras", "legumes", "carne", "frango", "peixe",
        "ovos", "arroz", "feijão", "macarrão", "molho", "biscoito", "bolacha", "chocolate", "bombom", "cereal", "chiclete",
        "barzinho", "boteco", "petisco", "tira-gosto", "happy hour", "mcdonalds", "burger king", "bk", "subway",
        "kfc", "giraffas", "habibs", "sadia", "seara", "perdigão", "nestle", "garoto", "lacta", " Bauducco", "piraquê",
        "carrefour", "pão de açúcar", "extra", "atacadao", "assai", "big", "gbarbosa", "zona sul", "hortifruti",
        "churrascaria", "rodízio", "self-service", "quilo", "kg", "cafeteria", "confeitaria", "doceria", "rotisseria"
    ],
    "Transporte": [
        "uber", "99", "táxi", "gasolina", "etanol", "diesel", "gnv", "combustível", "posto", "ipiranga", "shell", "petrobras",
        "metrô", "ônibus", "trem", "passagem", "estacionamento", "pedágio", "rodízio", "multa", "ipva", "licenciamento",
        "seguro do carro", "mecânico", "oficina", "troca de óleo", "pneu", "manutenção do carro", "revisão",
        "lavagem", "lava-rápido", "aluguel de carro", "movida", "localiza", "unidas", "passagem aérea", "latam", "gol", "azul",
        "aeroporto", "rodoviária", "barca", "balsa", "frete", "carreto", "recarga bilhete único", "cartão top", "giro",
        "app de transporte", "cabify", "buser", "flixbus", "aplicativo de onibus", "viacao 1001", "cometa", "itapemirim"
    ],
    "Moradia": [
        "aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "diarista", "faxineira", "limpeza",
        "reforma", "manutenção", "conserto", "eletricista", "encanador", "pintor", "marceneiro", "material de construção",
        "tinta", "cimento", "areia", "ferramenta", "leroy merlin", "telhanorte", "cec", "decoração", "móvel", "sofá", "cama",
        "mesa", "cadeira", "eletrodoméstico", "geladeira", "fogão", "microondas", "máquina de lavar", "tv a cabo", "net",
        "claro", "vivo", "tim", "oi", "segurança", "alarme", "telefonia", "conta de celular", "plano de celular",
        "ikea", "tok&stok", "etna", "mobly", "dedetização", "desentupidor", "jardinagem", "piscineiro"
    ],
    "Saúde e Bem-estar": [
        "farmácia", "drogasil", "droga raia", "pacheco", "panvel", "remédio", "medicamento", "dorflex", "neosaldina",
        "médico", "consulta", "plano de saúde", "convênio", "amil", "bradesco saude", "sulamerica", "unimed",
        "academia", "smart fit", "bluefit", "bodytech", "suplemento", "whey", "creatina", "dentista", "aparelho",
        "exame", "laboratório", "terapia", "psicólogo", "fisioterapia", "pilates", "yoga", "nutricionista",
        "oftalmologista", "óculos de grau", "lente de contato", "hospital", "pronto-socorro", "emergência",
        "massagem", "acupuntura", "plano odontológico", "odonto"
    ],
    "Cuidados Pessoais": [
        "cabeleireiro", "barbeiro", "corte de cabelo", "manicure", "pedicure", "salão de beleza", "sobrancelha",
        "depilação", "estética", "perfume", "boticario", "natura", "sephora", "creme", "hidratante", "shampoo",
        "condicionador", "sabonete", "desodorante", "maquiagem", "batom", "base", "rímel", "protetor solar",
        "cosméticos", "barbearia", "esmalte"
    ],
    "Lazer e Entretenimento": [
        "cinema", "show", "teatro", "concerto", "bar", "balada", "festa", "viagem", "hotel", "pousada", "hostel", "airbnb",
        "booking", "passagem de avião", "streaming", "spotify", "netflix", "hbo", "disney+", "amazon prime", "youtube premium",
        "globoplay", "jogo", "game", "steam", "playstation", "psn", "xbox", "nintendo", "ingresso", "passeio", "parque",
        "praia", "clube", "hobby", "instrumento musical", "artesanato", "dança", "luta", "esporte", "futebol",
        "ingresso de jogo", "livraria", "gibis", "hq", "show", "festival", "lollapalooza", "rock in rio", "rolê"
    ],
    "Compras e Vestuário": [
        "roupa", "roupas", "tênis", "sapato", "bota", "sandália", "chinelo", "camiseta", "camisa", "blusa", "calça",
        "bermuda", "short", "saia", "vestido", "casaco", "jaqueta", "moletom", "terno", "blazer", "gravata",
        "meia", "cueca", "calcinha", "sutiã", "pijama", "biquíni", "sunga", "maiô", "acessório", "bolsa",
        "carteira", "cinto", "chapéu", "boné", "gorro", "cachecol", "luva", "óculos", "relógio", "joia",
        "brinco", "colar", "pulseira", "anel", "lavanderia", "costureira", "ajuste de roupa", "sapataria",
        "shopping", "loja de departamento", "renner", "c&a", "riachuelo", "zara", "nike", "adidas", "shein", "shopee",
        "mercado livre", "amazon", "aliexpress", "fast shop", "magazine luiza", "magalu", "casas bahia", "ponto"
    ],
    "Educação": [
        "curso", "livro", "ebook", "kindle", "faculdade", "universidade", "mensalidade", "material escolar", "caderno",
        "caneta", "lápis", "mochila", "escola", "colégio", "aula particular", "professor", "palestra", "udemy",
        "coursera", "alura", "workshop", "seminário", "inscrição", "concurso", "certificação", "idiomas", "inglês", "espanhol"
    ],
    "Pets": [
        "pet shop", "ração", "veterinário", "vacina do pet", "banho e tosa", "antipulgas", "vermífugo",
        "brinquedo para pet", "areia para gato", "petz", "cobasi", "coleira", "consulta vet"
    ],
    "Presentes e Doações": [
        "presente", "lembrancinha", "doação", "caridade", "contribuição", "ong", "presente de aniversário", "cesta básica"
    ],
    "Investimentos e Finanças": [
        "investimento", "ações", "c CDB", "tesouro direto", "fundo imobiliário", "fii", "criptomoeda", "bitcoin",
        "ethereum", "corretora", "xp", "rico", "clear", "nuinvest", "taxa", "juros", "empréstimo", "financiamento",
        "iof", "transferência", "ted", "doc", "tarifa bancária"
    ],
}

# --- MENSAGENS E DICAS ---
COMMANDS_MESSAGE = """
Olá! Sou sua assistente financeira pessoal. 💸

Você pode falar comigo como se estivesse conversando com alguém!

*Exemplos do que você pode me dizer:*
- `gastei 25,50 no almoço no shopping`
- `comprei um tênis na nike por 350 e um livro de 50`
- `recebi 3500 do salário`
- `acabei de ganhar uma caixinha no valor de 50 reais`
- `tenho uma conta de luz de 180 que vence 15/09`
- `paguei a conta de luz`
- `qual meu saldo?`
- `o que gastei hoje?`
- `quanto gastei com alimentação esse mês?`

*Principais Comandos:*
📊 *RELATÓRIOS*
- `saldo`: Para ver seu saldo atual.
- `resumo financeiro`: Visão geral com saldo e dívidas.
- `gastos hoje` (ou `semana`/`mês`): Lista seus gastos.
- `gastos por categoria hoje` (ou `semana`/`mês`): Mostra gastos agrupados.
- `entradas e saídas hoje` (ou `semana`/`mês`): Mostra o balanço.
- `minhas dívidas`: Lista suas dívidas pendentes.

⚙️ *AÇÕES*
- `apagar último gasto`: Remove o último gasto registrado.
- `paguei [descrição da dívida]`: Marca uma dívida como paga e registra o gasto.
- `meu saldo é [valor]`: Define ou corrige seu saldo inicial.
- `dica`: Te dou uma dica financeira.

Qualquer dúvida, é só chamar! 😊
"""
FINANCIAL_TIPS = [
    "Anote todos os seus gastos, até os pequenos. Isso te ajuda a entender para onde seu dinheiro está indo.", "Crie um orçamento mensal. A regra 50/30/20 (50% necessidades, 30% desejos, 20% poupança) é um bom começo!", "Antes de uma compra por impulso, espere 24 horas. Muitas vezes, a vontade passa e você economiza.", "Tenha uma reserva de emergência. O ideal é ter o equivalente a 3 a 6 meses do seu custo de vida guardado.", "Compare preços antes de comprar. A internet facilita muito a pesquisa e a economia.", "Evite usar o cartão de crédito para compras do dia a dia. É mais fácil perder o controle dos gastos assim.", "Defina metas financeiras claras, como 'guardar R$1000 para uma viagem'. Metas te mantêm motivado.", "Revise suas assinaturas e serviços recorrentes. Você realmente usa todos eles?", "Automatize seus investimentos. Configure transferências mensais para sua corretora para não 'esquecer' de investir."
]

# --- FUNÇÕES AUXILIARES DE INTERPRETAÇÃO DE TEXTO (NLP) ---

def parse_monetary_value(text):
    """Extrai o valor monetário mais provável de um texto."""
    if not isinstance(text, str): return None
    # Padrão aprimorado para capturar valores como 1.234,56 ou 1234.56 ou 1.234 ou 1234
    pattern = r'(?:R\$\s*)?(\d{1,3}(?:\.?\d{3})*(?:,\d{1,2})?|\d+(?:\.\d{1,2})?)'
    matches = re.findall(pattern, text)
    if not matches: return None

    # Lógica para encontrar o melhor match, priorizando valores completos
    best_match = ""
    max_digits = 0
    for m in matches:
        num_digits = len(re.sub(r'\D', '', m))
        if num_digits > max_digits:
            max_digits = num_digits
            best_match = m

    if not best_match: return None
    
    # Padroniza o valor para o formato float (ex: "1.234,56" -> 1234.56)
    standardized_value = best_match.replace('.', '').replace(',', '.')
    
    # Corrige casos como "1.234" que viram "1234" (deve ser 1234.00)
    if '.' in best_match and ',' not in best_match:
        parts = standardized_value.split('.')
        # Se a última parte tem 3 dígitos e não há vírgula, provavelmente é milhar, não centavos
        if len(parts[-1]) == 3 and len(parts) > 1:
            standardized_value = "".join(parts)

    try:
        return float(standardized_value)
    except (ValueError, IndexError):
        return None

def extract_all_transactions(text):
    """Divide a frase em cláusulas e extrai uma transação de cada."""
    transactions = []
    # Divide por "e", "depois", vírgulas (que não sejam de milhares)
    clauses = re.split(r'\s+e\s+|\s+depois\s+|,\s*(?!\d{3})', text)
    for clause in clauses:
        value = parse_monetary_value(clause)
        if value is not None:
            transactions.append({"value": value, "context": clause})
    return transactions

def extract_due_date(text):
    """Extrai uma data no formato DD/MM."""
    match = re.search(r'(\d{1,2}/\d{1,2})', text)
    if match:
        return match.group(0)
    
    # Tenta extrair "dia 15", "dia 05"
    match_dia = re.search(r'\b(dia|vence)\s+(\d{1,2})\b', text)
    if match_dia:
        day = int(match_dia.group(2))
        now = datetime.datetime.now(TIMEZONE)
        month = now.month
        # Se o dia já passou neste mês, assume que é para o próximo
        if day < now.day:
            month = now.month + 1 if now.month < 12 else 1
        return f"{day:02d}/{month:02d}"
        
    return "Sem data"

def clean_description(text, value):
    """Limpa a descrição removendo ruídos e palavras-chave de comando."""
    if value is not None:
        # Remove o valor monetário em vários formatos (1.234,56, 1234.56, 1234,56)
        formatted_value_br = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        text = text.replace(formatted_value_br, "")
        text = text.replace(f"{value:.2f}", "")
        text = text.replace(str(int(value) if value.is_integer() else value), "")

    # Lista expandida de ruídos
    noise_patterns = [
        # Gatilhos de gasto/entrada
        r'\b(gastei|comprei|paguei|foi|deu|custou|no valor de|de|acabei de pedir|passei no cartao|um pix de)\b',
        r'\b(recebi|salário|ganhei|depósito|rendimento|entrada|caixinha|gorjeta|um pix na conta|caiu na conta)\b',
        r'\b(dívida|conta|vence|vencimento|apagar|último|parcela|boleto|fatura)\b',
        # Palavras de preenchimento
        r'r\$', r'\breais\b', r'\b(minha|meu|pra|pro|para|a|o|em|no|na|com|um|uma)\b',
        # Data
        r'(\d{1,2}/\d{1,2})', r'\b(dia|vence)\s+\d{1,2}\b'
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\s+', ' ', text).strip(" ,.:;-")
    return text.capitalize() if text else "Gasto geral"

def infer_category(description):
    """Deduz a categoria do gasto com base na descrição."""
    desc_lower = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in desc_lower for keyword in keywords):
            return category
    return "Outros"

# --- FUNÇÕES DE LÓGICA FINANCEIRA (PERSISTÊNCIA EM CSV) ---

def write_to_csv(filepath, header, row):
    """Função genérica para escrever uma linha em um arquivo CSV."""
    file_exists = os.path.exists(filepath)
    try:
        with open(filepath, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            if not file_exists or os.path.getsize(filepath) == 0:
                writer.writerow(header)
            writer.writerow(row)
        return True
    except IOError as e:
        print(f"Erro de I/O ao escrever em {filepath}: {e}")
        return False

def get_balance(user_id):
    """Lê o saldo atual do usuário no arquivo CSV."""
    if not os.path.exists(CSV_SALDO): return 0.0
    try:
        with open(CSV_SALDO, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            next(reader, None)  # Pula o cabeçalho
            for row in reader:
                if row and row[0] == user_id:
                    return float(row[1])
    except (IOError, StopIteration) as e:
        print(f"Erro ao ler saldo: {e}")
        return 0.0
    return 0.0

def set_balance(user_id, new_balance):
    """Atualiza ou define o saldo de um usuário no arquivo CSV."""
    lines, user_found = [], False
    header = "UserID;Saldo\n"
    if os.path.exists(CSV_SALDO):
        try:
            with open(CSV_SALDO, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except IOError as e:
            print(f"Erro ao ler arquivo de saldo para atualização: {e}")
            
    try:
        with open(CSV_SALDO, 'w', encoding='utf-8') as file:
            if not lines or not lines[0].strip().lower().startswith("userid"):
                file.write(header)
                if lines: # Se havia algo, mas sem cabeçalho, reescreve
                    file.writelines(l for l in lines if l.strip())
            else:
                file.write(lines[0]) # Escreve o cabeçalho existente

            for line in lines[1:]: # Itera a partir da segunda linha
                if line.strip():
                    if line.startswith(user_id + ';'):
                        file.write(f"{user_id};{new_balance:.2f}\n")
                        user_found = True
                    else:
                        file.write(line)

            if not user_found:
                file.write(f"{user_id};{new_balance:.2f}\n")
    except IOError as e:
        print(f"Erro ao escrever novo saldo: {e}")


def record_expense(user_id, value, description, update_balance=True):
    """Registra um novo gasto."""
    now = datetime.datetime.now(TIMEZONE)
    category = infer_category(description)
    row = [user_id, now.strftime("%Y-%m-%d %H:%M:%S"), description, f"{value:.2f}", category]
    
    if write_to_csv(CSV_GASTOS, ["UserID", "DataHora", "Descricao", "Valor", "Categoria"], row):
        if update_balance:
            set_balance(user_id, get_balance(user_id) - value)
        return {"description": description, "value": value, "category": category}
    return None

def record_income(user_id, value, description):
    """Registra uma nova entrada."""
    now = datetime.datetime.now(TIMEZONE)
    new_balance = get_balance(user_id) + value
    set_balance(user_id, new_balance)
    
    row = [user_id, now.strftime("%Y-%m-%d %H:%M:%S"), description, f"{value:.2f}"]
    write_to_csv(CSV_ENTRADAS, ["UserID", "DataHora", "Descricao", "Valor"], row)
    
    return f"💰 Entrada registrada!\n- {description}: *R${value:.2f}*\n\nSeu novo saldo é *R${new_balance:.2f}*."

def record_debt(user_id, value, description, due_date):
    """Registra uma nova dívida."""
    row = [user_id, due_date, description, f"{value:.2f}"]
    write_to_csv(CSV_DIVIDAS, ["UserID", "DataVencimento", "Descricao", "Valor"], row)
    
    return f"🧾 Dívida registrada!\n- {description}: *R${value:.2f}*\n- Vencimento: {due_date}"

def pay_debt(user_id, text):
    """Marca uma dívida como paga, removendo-a e registrando como gasto."""
    if not os.path.exists(CSV_DIVIDAS): return "Você não tem nenhuma dívida para pagar."
    
    search_desc = re.sub(r'\b(paguei|a|o|conta|fatura|boleto|de|da|do)\b', '', text, flags=re.IGNORECASE).strip()
    lines, debt_found = [], None
    
    try:
        with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file: lines = file.readlines()
    except IOError:
        return "Erro ao ler o arquivo de dívidas."

    # Procura a dívida que mais se parece com a descrição
    best_match_score = 0
    for i, line in reversed(list(enumerate(lines))):
        if line.strip().startswith(user_id) and len(line.strip().split(';')) > 2:
            parts = line.strip().split(';')
            debt_desc_lower = parts[2].lower()
            if search_desc.lower() in debt_desc_lower:
                score = len(search_desc) / len(debt_desc_lower) # Heurística simples
                if score > best_match_score:
                    best_match_score = score
                    debt_found = {"index": i, "desc": parts[2], "value": float(parts[3])}

    if not debt_found: return f"Não encontrei a dívida '{search_desc}'. Verifique a lista em 'minhas dívidas'."
    
    lines.pop(debt_found["index"])
    try:
        with open(CSV_DIVIDAS, 'w', encoding='utf-8') as file: file.writelines(lines)
    except IOError:
        return "Erro ao atualizar o arquivo de dívidas."
        
    record_expense(user_id, debt_found['value'], f"Pagamento: {debt_found['desc']}")
    return f"✅ Dívida '{debt_found['desc']}' paga com sucesso!\nSeu novo saldo é *R${get_balance(user_id):.2f}*."

def delete_last_expense(user_id):
    """Apaga o último gasto registrado pelo usuário."""
    if not os.path.exists(CSV_GASTOS): return "Você não tem gastos para apagar."
    
    try:
        with open(CSV_GASTOS, 'r', encoding='utf-8') as file: lines = file.readlines()
    except IOError:
        return "Erro ao ler o arquivo de gastos."

    last_expense_index = -1
    for i, line in reversed(list(enumerate(lines))):
        if line.strip().startswith(user_id):
            last_expense_index = i
            break
            
    if last_expense_index == -1: return "Não encontrei gastos seus para apagar."
    
    deleted_line_parts = lines.pop(last_expense_index).strip().split(';')
    deleted_value = float(deleted_line_parts[3])
    
    try:
        with open(CSV_GASTOS, 'w', encoding='utf-8') as file: file.writelines(lines)
    except IOError:
        return "Erro ao reescrever o arquivo de gastos."
        
    set_balance(user_id, get_balance(user_id) + deleted_value)
    return f"🗑️ Último gasto apagado!\n- {deleted_line_parts[2]}: R${deleted_value:.2f}\nO valor foi devolvido. Novo saldo: *R${get_balance(user_id):.2f}*."

# --- FUNÇÕES DE GERAÇÃO DE RELATÓRIOS ---

def get_debts_report(user_id):
    """Gera um relatório com todas as dívidas pendentes."""
    if not os.path.exists(CSV_DIVIDAS): return "Você não tem nenhuma dívida registrada. Parabéns! 🎉"
    report_lines, total_debts = ["📋 *Suas Dívidas Pendentes* 📋\n"], 0.0
    try:
        with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    report_lines.append(f"- {row[2]} (Vence: {row[1]}): R${float(row[3]):.2f}")
                    total_debts += float(row[3])
    except (IOError, StopIteration):
        return "Erro ao ler o arquivo de dívidas."

    if len(report_lines) == 1: return "Você não tem nenhuma dívida registrada. Parabéns! 🎉"
    report_lines.append(f"\n*Total de Dívidas: R${total_debts:.2f}*")
    return "\n".join(report_lines)

def get_financial_summary(user_id):
    """Gera um resumo rápido com saldo e total de dívidas."""
    balance = get_balance(user_id)
    total_debts = 0.0
    if os.path.exists(CSV_DIVIDAS):
        try:
            with open(CSV_DIVIDAS, 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=';')
                next(reader, None)
                total_debts = sum(float(row[3]) for row in reader if row and row[0] == user_id)
        except (IOError, StopIteration):
            pass # Não impede o resto do resumo
    return f"📊 *Resumo Financeiro*\n\n- Saldo em conta: *R${balance:.2f}*\n- Total de dívidas: *R${total_debts:.2f}*"

def get_period_report(user_id, period, by_category=False):
    """Gera um relatório de gastos para um período (dia, semana, mês), opcionalmente por categoria."""
    if not os.path.exists(CSV_GASTOS): return "Nenhum gasto registrado ainda."

    now = datetime.datetime.now(TIMEZONE)
    if period == "dia":
        start_date, period_name = now.date(), "hoje"
    elif period == "semana":
        start_date, period_name = now.date() - datetime.timedelta(days=now.weekday()), "nesta semana"
    else: # Mês
        start_date, period_name = now.date().replace(day=1), "neste mês"

    expenses = []
    try:
        with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';')
            next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    expense_date = datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date()
                    if expense_date >= start_date:
                        expenses.append({'desc': row[2], 'value': float(row[3]), 'cat': row[4]})
    except (IOError, StopIteration):
        return "Erro ao ler o arquivo de gastos."

    if not expenses: return f"Você não teve gastos {period_name}. 🎉"
    
    total_spent = sum(e['value'] for e in expenses)

    if not by_category:
        report_lines = [f"🧾 *Seus gastos {period_name}* 🧾\n"]
        report_lines.extend([f"- {e['desc']}: R${e['value']:.2f}" for e in expenses])
    else:
        report_lines = [f"📊 *Gastos por categoria {period_name}* 📊\n"]
        category_totals = defaultdict(float)
        for e in expenses:
            category_totals[e['cat']] += e['value']
        
        # Ordena as categorias da mais gasta para a menos gasta
        sorted_categories = sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
        
        for category, total in sorted_categories:
            percentage = (total / total_spent) * 100
            report_lines.append(f"- *{category}*: R${total:.2f} ({percentage:.1f}%)")

    report_lines.append(f"\n*Total gasto: R${total_spent:.2f}*")
    return "\n".join(report_lines)


def get_io_summary(user_id, period):
    """Gera um relatório de entradas e saídas (balanço) para um período."""
    now = datetime.datetime.now(TIMEZONE)
    if period == "dia":
        start_date, period_name = now.date(), "de hoje"
    elif period == "semana":
        start_date, period_name = now.date() - datetime.timedelta(days=now.weekday()), "da semana"
    else: # Mês
        start_date, period_name = now.date().replace(day=1), "do mês"

    total_in, total_out = 0.0, 0.0

    # Calcula Saídas
    if os.path.exists(CSV_GASTOS):
        with open(CSV_GASTOS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None, None)
            for row in reader:
                if row and row[0] == user_id and datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date() >= start_date:
                    total_out += float(row[3])
    
    # Calcula Entradas
    if os.path.exists(CSV_ENTRADAS):
        with open(CSV_ENTRADAS, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None, None)
            for row in reader:
                if row and row[0] == user_id and datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date() >= start_date:
                    total_in += float(row[3])

    return f"💸 *Balanço {period_name}*\n\n- Entradas: *R${total_in:.2f}*\n- Saídas: *R${total_out:.2f}*"

# --- FUNÇÃO DE ENVIO DE MENSAGEM ---
def send_whatsapp_message(phone_number, message_text):
    """Envia uma mensagem de texto para um número de WhatsApp."""
    if not all([ACCESS_TOKEN, PHONE_NUMBER_ID]):
        print("ERRO: Credenciais ACCESS_TOKEN ou PHONE_NUMBER_ID não configuradas no ambiente.")
        return
        
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Mensagem enviada para {phone_number}.")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar mensagem para {phone_number}: {e}")
        print(f"Resposta da API: {response.text if 'response' in locals() else 'N/A'}")


# --- PROCESSADOR DE COMANDOS (CÉREBRO DA IA) ---
def process_message(user_id, user_name, message_text):
    """Processa a mensagem do usuário e determina a ação apropriada."""
    
    # --- MILHARES DE COMANDOS (EXPANSÃO MASSIVA DE GATILHOS E SINÔNIMOS) ---
    
    # A IA agora entende uma variedade muito maior de formas de falar a mesma coisa.
    
    # SAUDAÇÕES E CONVERSA BÁSICA
    CMD_GREETINGS = [
        "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "eae", "opa", "salve", 
        "tudo bem?", "td bem?", "tudo bom?", "td bom?", "como vai?", "blz?", "beleza?", "fala", "iai"
    ]
    # AJUDA E INTRODUÇÃO
    CMD_HELP = [
        "ajuda", "comandos", "menu", "começar", "opções", "o que você faz", "como funciona", "help",
        "preciso de ajuda", "me ajuda", "quais os comandos", "lista de comandos", "como usar", "start"
    ]
    # CONSULTAS DE SALDO
    CMD_GET_SALDO = [
        "qual meu saldo", "ver saldo", "quanto tenho", "meu dinheiro", "dinheiro em conta", "grana", 
        "ver a grana", "kd meu dinheiro", "quanto de dinheiro eu tenho", "saldo", "mostra o saldo",
        "meu saldo", "meu saldo por favor", "poderia ver meu saldo?", "consulta de saldo", "checar saldo",
        "qual o valor na minha conta?", "qto tenho?", "quanto eu tenho?", "quanto me resta?", "mostra a grana"
    ]
    # DEFINIÇÃO DE SALDO INICIAL
    CMD_SET_SALDO = [
        "meu saldo é", "tenho na conta", "definir saldo", "saldo inicial", "começar com", 
        "meu saldo atual é", "tenho um total de", "meu saldo inicial é", "iniciar com", "tenho",
        "comecei com", "meu caixa é", "corrigir saldo para"
    ]
    # RESUMO E RELATÓRIOS GERAIS
    CMD_RESUMO = [
        "resumo", "resumo financeiro", "visão geral", "como estou", "minhas finanças", 
        "situação financeira", "meu status", "como estão as contas", "faz um resumo pra mim",
        "resumo geral", "balanço geral", "panorama"
    ]
    # AÇÕES DE CORREÇÃO
    CMD_APAGAR = [
        "apagar último", "excluir último", "cancelar último", "apaga o último", "deleta o último", 
        "foi errado", "lancei errado", "apagar ultimo gasto", "remove o ultimo", "excluir lançamento",
        "cancele o ultimo", "desfazer", "undo"
    ]
    # DICAS
    CMD_DICA = [
        "dica", "dica financeira", "me dê uma dica", "uma dica", "conselho", "me ajuda a economizar", 
        "conselho financeiro", "preciso de uma dica", "manda uma dica", "me ensina a poupar"
    ]
    # RELATÓRIOS DE GASTOS
    CMD_GASTOS = [
        "gastos", "o que gastei", "relatório de gastos", "saídas", "minhas despesas", 
        "onde gastei", "com o que gastei", "lista de gastos", "ver gastos", "meus gastos",
        "mostra as saídas", "quais foram as despesas", "extrato de gastos"
    ]
    # RELATÓRIOS DE GASTOS POR CATEGORIA (NOVO)
    CMD_GASTOS_CATEGORIA = [
        "gastos por categoria", "gastos em", "quanto gastei com", "despesas por categoria",
        "relatorio de categoria", "onde eu mais gasto", "divisão de gastos"
    ]
    # RELATÓRIOS DE ENTRADAS E SAÍDAS
    CMD_BALANCO = [
        "entradas e saídas", "entrou e saiu", "balanço", "fluxo de caixa", "relatório de transações", 
        "movimentações", "o que entrou e o que saiu", "balanço do período", "receitas e despesas"
    ]
    # REGISTRO DE DÍVIDAS
    CMD_REGISTRAR_DIVIDA = [
        "dívida", "divida", "parcela", "boleto", "conta", "vencimento", "tenho que pagar", "vence dia",
        "anota uma conta", "registra uma dívida", "fatura", "tenho uma conta", "lançar conta", "lembrete de pagamento"
    ]
    # PAGAMENTO DE DÍVIDAS
    CMD_PAGAR_DIVIDA = [
        "paguei", "já paguei", "pagamento de", "quitei", "dar baixa", "paguei a conta",
        "pagamento da fatura", "paguei o boleto", "quitar dívida", "foi pago"
    ]
    # CONSULTA DE DÍVIDAS
    CMD_VER_DIVIDAS = [
        "minhas dívidas", "ver dívidas", "quais minhas contas", "o que devo", "lista de dívidas", 
        "contas a pagar", "o que tenho pra pagar", "ver boletos", "dívidas pendentes", "o que falta pagar"
    ]
    # REGISTRO DE ENTRADAS
    CMD_ENTRADA = [
        "recebi", "salário", "ganhei", "depósito", "rendimento", "entrada", "pix", "me pagaram", 
        "um amigo me pagou", "salario", "recebimento", "caiu na conta", "caixinha", "gorjeta", "bico", "freela",
        "restituição", "reembolso", "vendi", "crédito em conta", "acabei de ganhar"
    ]
    # GATILHOS GENÉRICOS DE GASTO (para o fallback)
    CMD_GASTO_GENERICO = [
        "gastei", "comprei", "paguei", "foi em", "custou", "deu", "passei no cartao",
        "um pix de", "encomendei", "pedi um"
    ]

    # --- HIERARQUIA DE PROCESSAMENTO DE INTENÇÕES ---
    # A ordem das verificações é crucial para evitar ambiguidades.
    
    # 1. Conversa Básica e Ajuda (não envolvem valores)
    if any(cmd == message_text for cmd in CMD_GREETINGS):
        return f"Olá, {user_name}! Como posso te ajudar hoje? 😊"
    if any(cmd in message_text for cmd in CMD_HELP):
        return COMMANDS_MESSAGE

    # 2. Extrai valor monetário da mensagem para as próximas verificações
    value_in_message = parse_monetary_value(message_text)
    
    # 3. Ações de Saldo (alta prioridade para evitar conflito com "conta" de dívida)
    if any(cmd in message_text for cmd in CMD_SET_SALDO) and value_in_message is not None:
        # Condição extra para evitar que "gastei 50 na conta de luz" seja confundido.
        if not any(gasto in message_text for gasto in CMD_GASTO_GENERICO):
            set_balance(user_id, value_in_message)
            return f"✅ Saldo definido! Seu saldo atual é *R${value_in_message:.2f}*."

    if any(cmd in message_text for cmd in CMD_GET_SALDO):
        return f"💵 Seu saldo atual é de *R${get_balance(user_id):.2f}*."

    # 4. Ações e Relatórios Diretos (não dependem de contexto complexo)
    if any(cmd in message_text for cmd in CMD_RESUMO): return get_financial_summary(user_id)
    if any(cmd in message_text for cmd in CMD_APAGAR): return delete_last_expense(user_id)
    if any(cmd in message_text for cmd in CMD_DICA): return random.choice(FINANCIAL_TIPS)
    if any(cmd in message_text for cmd in CMD_VER_DIVIDAS): return get_debts_report(user_id)
    if any(cmd in message_text for cmd in CMD_PAGAR_DIVIDA): return pay_debt(user_id, message_text)
    
    # 5. Relatórios com Período (dia, semana, mês)
    period = "mês" # Default
    if any(p in message_text for p in ["hoje", "hj", "de hoje"]): period = "dia"
    elif "semana" in message_text: period = "semana"

    if any(cmd in message_text for cmd in CMD_GASTOS_CATEGORIA):
        return get_period_report(user_id, period, by_category=True)
    if any(cmd in message_text for cmd in CMD_GASTOS):
        return get_period_report(user_id, period, by_category=False)
    if any(cmd in message_text for cmd in CMD_BALANCO):
        return get_io_summary(user_id, period)

    # 6. Transações Financeiras (Dívida, Entrada, Gasto)
    if any(keyword in message_text for keyword in CMD_REGISTRAR_DIVIDA):
        if value_in_message is not None:
            description = clean_description(message_text, value_in_message)
            due_date = extract_due_date(message_text)
            return record_debt(user_id, value_in_message, description, due_date)

    if any(keyword in message_text for keyword in CMD_ENTRADA) and value_in_message is not None:
        description = clean_description(message_text, value_in_message)
        if not description: description = "Entrada geral"
        return record_income(user_id, value_in_message, description)

    # 7. Fallback: Se não for nada acima, assume que é um ou mais gastos
    transactions = extract_all_transactions(message_text)
    if transactions:
        # Se houver gatilhos de gasto, a confiança é maior
        is_likely_expense = any(cmd in message_text for cmd in CMD_GASTO_GENERICO) or len(transactions) > 1

        if not is_likely_expense:
            # Se for só "ifood 120", é um gasto. Se for "meu saldo é 120", não.
            # Verifica se já foi tratado por um comando mais específico.
            already_processed_cmds = CMD_SET_SALDO + CMD_REGISTRAR_DIVIDA + CMD_ENTRADA
            if any(cmd in message_text for cmd in already_processed_cmds):
                 return f"Não entendi bem o que fazer com o valor R${transactions[0]['value']:.2f}. Pode tentar de outra forma?"

        if len(transactions) > 1:
            response_lines = [f"Entendido! Registrei {len(transactions)} gastos para você:"]
            total_value = sum(t['value'] for t in transactions)
            for trans in transactions:
                description = clean_description(trans['context'], trans['value'])
                result = record_expense(user_id, trans['value'], description, update_balance=False)
                if result: response_lines.append(f"- {result['description']}: *R${result['value']:.2f}* ({result['category']})")
            set_balance(user_id, get_balance(user_id) - total_value)
            response_lines.append(f"\nSeu novo saldo é *R${get_balance(user_id):.2f}*.")
            return "\n".join(response_lines)
        
        elif len(transactions) == 1:
            value = transactions[0]['value']
            description = clean_description(message_text, value)
            result = record_expense(user_id, value, description)
            if result:
                return f"✅ Gasto registrado!\n- {result['description']}: *R${result['value']:.2f}* ({result['category']})\n\nSeu novo saldo é *R${get_balance(user_id):.2f}*."

    # 8. Mensagem padrão se nenhuma intenção for identificada
    return f"Não entendi, {user_name}. 🤔 Se precisar de ajuda, envie `comandos`."

# --- WEBHOOK PRINCIPAL DA APLICAÇÃO FLASK ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Ponto de entrada para as mensagens do WhatsApp."""
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            return 'Failed verification', 403
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            # Extrai os dados relevantes da mensagem
            entry = data.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            
            # Verifica se é uma mensagem de texto válida
            if 'messages' in value:
                message_data = value['messages'][0]
                if message_data.get('type') != 'text':
                    return 'EVENT_RECEIVED', 200 # Ignora mídias, status, etc.

                user_id = message_data['from']
                user_name = value.get('contacts', [{}])[0].get('profile', {}).get('name', 'Pessoa')
                message_text = message_data['text']['body'].strip().lower()
                
                print(f"Recebida mensagem de {user_name} ({user_id}): '{message_text}'")
                reply_message = process_message(user_id, user_name, message_text)
                
                if reply_message:
                    send_whatsapp_message(user_id, reply_message)
                    
        except (IndexError, KeyError) as e:
            # Erro comum se a estrutura do JSON não for a esperada (ex: notificação de status)
            print(f"Payload não é uma mensagem de usuário: {e}")
            pass
        except Exception as e:
            print(f"!!! ERRO CRÍTICO NO WEBHOOK: {e} !!!")
            # Tenta notificar o usuário do erro, se possível
            try:
                user_id = data['entry'][0]['changes'][0]['value']['messages'][0]['from']
                send_whatsapp_message(user_id, "❌ Desculpe, encontrei um erro inesperado. Minha equipe de engenheiros já foi notificada. Pode tentar de novo?")
            except Exception as notify_error:
                print(f"Falha ao notificar usuário sobre o erro: {notify_error}")
                
        return 'EVENT_RECEIVED', 200

if __name__ == "__main__":
# Forçando novo deploy para ativar o Gemini