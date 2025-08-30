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
import unicodedata  # Adicionado para normalização de texto (remoção de acentos)

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
PAGAMENTOS_FILE_NAME = os.path.join(DATA_DIR, "pagamentos.csv")
SALDO_FILE_NAME = os.path.join(DATA_DIR, "saldo.csv")
DIVIDAS_FILE_NAME = os.path.join(DATA_DIR, "dividas.csv")
ORCAMENTO_FILE_NAME = os.path.join(DATA_DIR, "orcamento.csv")
METAS_FILE_NAME = os.path.join(DATA_DIR, "metas.csv")
RECORRENTES_FILE_NAME = os.path.join(DATA_DIR, "recorrentes.csv")
TIMEZONE = datetime.timezone(datetime.timedelta(hours=-3))

# --- LISTAS DE FRASES PARA COMANDOS (MOVidas PARA O ESCOPO GLOBAL) ---
GREETINGS = ["oi", "ola", "eai", "hey", "bom dia", "boa tarde", "boa noite", "tudo bem", "ajuda", "comandos", "menu", "help", "o que voce faz", "como usar", "instrucoes", "guia", "tutorial", "start", "inicio", "bem vindo", "saudacoes", "alow", "fala ai", "eae", "yo", "sup", "whats up", "ola assistente", "ei grok", "ola ia", "menu principal", "lista comandos", "ver comandos", "mostra menu", "ajuda por favor", "preciso de ajuda", "como comeco", "primeiros passos", "ola tudo bem", "bom dia assistente", "boa noite ia", "hey ai", "ola financas", "menu de opcoes", "opcoes disponiveis", "o q vc sabe fazer", "funcoes", "capacidades", "habilidades", "comandos disponiveis", "lista de comandos", "ver ajuda", "socorro", "auxilio", "suporte", "guia usuario", "manual", "instrucao", "dicas uso", "como funciona", "explicacao", "demonstracao", "exemplo comandos", "ola bot", "ei bot", "fala bot", "bot ajuda", "assistente financeiro oi", "ia financeira ola", "grok oi", "xai oi"]
DEBTS_PHRASES = ["quais as minhas dividas", "minhas dividas", "ver dividas", "relatorio de dividas", "o q eu devo", "contas a pagar", "dividas pendentes", "lista dividas", "ver contas", "minhas contas", "debito", "o que ta pendente", "divida atual", "relatorio debito", "quais contas", "ver pendencias", "pendentes", "dividas agora", "mostra dividas", "exibe dividas", "lista de dividas", "dividas registradas", "ver minhas dividas", "quais sao minhas dividas", "dividas por favor", "relatorio das dividas", "oq devo", "contas pendentes", "ver debito", "minha divida", "dividas totais", "total dividas", "quanto devo", "quanto ta pendente", "pendencias financeiras", "lista pendentes", "ver lista dividas", "exibir dividas", "mostrar dividas", "dividas atuais", "relatorio pendentes", "quais pendencias", "debts", "my debts", "ver debts", "lista debts", "o que devo pagar", "contas pra pagar", "dividas a vencer", "vencimentos", "proximas dividas", "dividas proximas", "ver vencimentos", "lista vencimentos", "quais vencem", "dividas vencendo", "pendentes a pagar", "ver pendentes pagar", "minhas obrigacoes", "obligacoes financeiras", "ver obrigacoes", "lista obrigacoes", "quais obrigacoes", "debito pendente", "ver debito pendente", "lista debito", "exibe debito", "mostra debito", "debito atual", "debito total", "quanto em debito", "total em debito", "dividas em aberto", "ver dividas aberto", "lista aberto", "pendentes em aberto", "ver pendentes aberto", "quais em aberto", "dividas nao pagas", "ver nao pagas", "lista nao pagas", "quais nao pagas", "contas nao quitadas", "ver nao quitadas", "lista nao quitadas"]
INCOME_PHRASES = ["definir rendimento", "meu rendimento e", "definir salario", "meu salario e", "rendimento mensal", "salario mensal", "definir ganho", "meu ganho e", "setar rendimento", "atualizar rendimento", "mudar rendimento", "rendimento eh", "salario eh", "ganho mensal", "definir income", "meu income e", "set income", "update salario", "meu rendimento atual", "definir meu rendimento", "rendimento [valor]", "salario [valor]", "ganhei mensal [valor]", "meu salario mensal [valor]", "definir rendimento mensal", "atualiza salario", "mudar salario", "salario novo", "rendimento novo", "setar salario", "definir ganhos", "meus ganhos sao", "ganhos mensais", "definir provento", "meu provento e", "proventos [valor]", "definir renda", "minha renda e", "renda mensal", "setar renda", "update renda", "renda eh", "minha renda mensal [valor]", "definir minha renda", "renda [valor]", "ganho [valor]", "meu ganho mensal [valor]", "definir ganho mensal", "atualizar ganho", "mudar ganho", "ganho novo", "setar ganho", "definir pagamento mensal", "meu pagamento e", "pagamento mensal [valor]", "definir mesada", "minha mesada e", "mesada [valor]", "definir faturamento", "meu faturamento e", "faturamento [valor]", "definir lucro", "meu lucro e", "lucro [valor]"]
BUDGET_PHRASES = ["meu orcamento", "ver orcamento", "relatorio orcamento", "como ta meu budget", "budget atual", "ver budget", "orcamento mensal", "meu budget", "exibe orcamento", "mostra orcamento", "orcamento agora", "relatorio budget", "ver meu orcamento", "quais meu orcamento", "orcamento por favor", "meu orcamento atual", "ver orcamento mensal", "budget mensal", "meu plano financeiro", "ver plano", "plano orcamento", "exibe plano", "mostra plano financeiro", "orcamento detalhado", "detalhes orcamento", "ver detalhes budget", "resumo orcamento", "summary budget", "meu summary orcamento", "orcamento resumido", "ver resumido", "budget resumido", "como esta meu orcamento", "status orcamento", "ver status budget", "atualizacao orcamento", "update orcamento ver", "meu orcamento eh", "ver meu plano", "plano mensal", "ver plano mensal"]
TIP_PHRASES = ["dica financeira", "dica pra economizar", "me da uma dica", "dica de grana", "tip financeiro", "conselho financeiro", "dica poupar", "como economizar", "dica investimento", "tip poupanca", "conselho grana", "dica dinheiro", "me ajuda a economizar", "dicas financas", "dica rapida", "tip rapido", "conselho rapido", "dica do dia", "tip do dia", "conselho do dia", "dica financeira por favor", "me da dica financeira", "quero uma dica", "dica ai", "tip ai", "conselho ai", "dica pra poupar", "como poupar", "dica pra investir", "como investir", "dica basica", "tip basico", "conselho basico", "dica avancada", "tip avancado", "conselho avancado", "dica sobre orcamento", "tip budget", "conselho orcamento", "dica sobre dividas", "tip debts", "conselho dividas", "dica sobre metas", "tip metas", "conselho metas"]
COMPARE_PHRASES = ["comparar gastos", "compara mes passado", "comparacao gastos", "ver comparacao", "gastos comparados", "comparar mes atual", "comparar despesas", "ver diferenca gastos", "diferenca mes", "comparar agora vs antes", "comparacao financeira", "ver comparativo", "comparativo gastos", "compara gastos mensais", "comparar mes a mes", "ver mudancas gastos", "mudancas em gastos", "analise comparativa", "comparar periodos", "ver comparacao periodos", "gastos vs mes passado", "despesas vs anterior", "comparar saidas", "ver comparacao saidas", "comparativo despesas", "analisar diferenca", "diferenca gastos", "compara agora", "comparacao rapida", "ver rapida comparacao", "gastos comparativos", "comparar meu gastos"]
SUMMARY_PHRASES = ["resumo financeiro", "visao geral da grana", "resumo grana", "ver resumo", "summary financeiro", "resumo atual", "visao geral", "resumo saldo", "resumo entradas saidas", "resumo total", "ver visao geral", "resumo por favor", "meu resumo", "resumo rapido", "quick summary", "resumo financas", "visao financas", "resumo mensal", "monthly summary", "resumo semanal", "weekly summary", "resumo diario", "daily summary", "resumo completo", "full summary", "resumo detalhado", "detailed summary", "resumo basico", "basic summary", "ver meu resumo", "mostra resumo", "exibe resumo", "resumo agora"]
BALANCE_PHRASES = ["qual o meu saldo", "meu saldo", "ver saldo", "saldo atual", "como esta meu saldo", "quanto sobrou", "quanto eu tenho", "saldo", "ver meu saldo", "quanto ta sobrando", "meu dinheiro", "quanto em conta", "saldo agora", "ver saldo atual", "quanto tenho", "saldo por favor", "me mostra o saldo", "exibe saldo", "quanto sobrou ai", "to com quanto", "meu sld", "sald", "balanco", "ver balanco", "quanto $$", "dinheiro atual", "ver dinheiro", "quanto na conta", "conta atual", "ver conta", "saldo total", "total saldo", "quanto eh meu saldo", "saldo eh", "ver meu dinheiro", "quanto meu dinheiro", "saldo rapido", "quick saldo", "saldo basico", "ver saldo basico", "saldo detalhado", "detailed saldo", "como ta a conta", "conta ta como", "ver status conta", "status saldo", "atualizacao saldo", "update saldo ver"]
DELETE_PHRASES = ["apagar ultimo gasto", "excluir ultimo", "deletar ultimo gasto", "remover ultimo", "apaga o ultimo", "exclui ultimo gasto", "delete last", "remove ultimo", "cancela ultimo gasto", "anula ultimo", "desfazer ultimo", "undo last expense", "apagar recente", "excluir recente", "deletar recente", "remover recente", "apaga recente", "exclui recente", "delete recent", "remove recent", "cancela recente", "anula recente", "desfazer recente", "undo recent", "apagar ultimo registro", "excluir ultimo registro", "deletar ultimo registro", "remover ultimo registro", "apaga ultimo registro", "exclui ultimo registro", "delete last record", "remove last record", "cancela ultimo registro", "anula ultimo registro", "desfazer ultimo registro", "undo last record"]
META_PHRASES_SET = ["definir meta", "adicionar meta", "setar meta", "criar meta", "nova meta", "meta nova", "definir poupanca", "meta poupar", "quero meta", "set meta", "add meta", "create meta", "new meta", "definir objetivo", "adicionar objetivo", "setar objetivo", "criar objetivo", "novo objetivo", "objetivo novo", "definir target", "adicionar target", "set target", "add target", "new target", "meta [descricao] [valor]", "objetivo [descricao] [valor]", "poupar pra [descricao] [valor]", "quero poupar [valor] pra [descricao]", "meta de [valor] pra [descricao]"]
META_PHRASES_GET = ["minhas metas", "ver metas", "lista metas", "relatorio metas", "quais metas", "metas pendentes", "ver objetivos", "lista objetivos", "relatorio objetivos", "quais objetivos", "objetivos pendentes", "ver targets", "lista targets", "my metas", "see metas", "list metas", "metas report", "what metas", "metas status", "progresso metas", "ver progresso metas", "metas atuais", "current metas", "exibe metas", "mostra metas", "metas por favor"]
REC_PHRASES_SET = ["adicionar recorrente", "definir recorrente", "setar recorrente", "criar recorrente", "novo recorrente", "recorrente novo", "adicionar fixo", "definir fixo", "gasto fixo", "add recorrente", "set recorrente", "new recorrente", "todo mes [descricao]", "toda semana [descricao]", "recorrente [descricao] [valor] [frequencia]", "fixo [descricao] [valor] [frequencia]", "adicionar gasto recorrente", "definir gasto fixo", "setar gasto recorrente", "criar fixo"]
REC_PHRASES_GET = ["meus recorrentes", "ver recorrentes", "lista recorrentes", "gastos fixos", "ver fixos", "lista fixos", "relatorio recorrentes", "quais recorrentes", "recorrentes pendentes", "my recorrentes", "see recorrentes", "list recorrentes", "fixos report", "what fixos", "recorrentes status", "ver gastos recorrentes", "lista gastos fixos", "exibe recorrentes", "mostra fixos", "recorrentes por favor"]
EXPENSE_REPORT_PHRASES = ["gastos d", "relatorio d", "gastos do", "relatorio do", "ver gastos", "lista gastos", "despesas d", "ver despesas", "gastos hoje", "gastos dia", "gastos semana", "gastos mes", "relatorio hoje", "relatorio dia", "relatorio semana", "relatorio mes", "o q gastei", "quanto gastei", "gastos atuais", "despesas atuais", "ver meus gastos", "mostra gastos", "exibe despesas", "gastos por favor", "relatorio despesas", "gastos diarios", "daily expenses", "gastos semanais", "weekly expenses", "gastos mensais", "monthly expenses", "ver gastos dia", "ver gastos semana", "ver gastos mes", "lista despesas dia", "lista despesas semana", "lista despesas mes"]
IO_PHRASES = ["entrada e saida", "entrou e saiu", "balanco", "entradas saidas", "io summary", "ver entradas", "ver saidas", "quanto entrou", "quanto saiu", "balanco hoje", "balanco dia", "balanco semana", "balanco mes", "entradas hoje", "saidas dia", "entradas semana", "saidas mes", "ver balanco", "mostra entradas saidas", "exibe balanco", "balanco por favor", "resumo entradas saidas", "io report", "entradas e saidas hoje", "entrou e saiu dia", "entradas e saidas semana", "entrou e saiu mes", "quanto entrou e saiu", "balanco rapido", "quick balanco", "balanco detalhado", "detailed io"]
PAY_DEBT_PHRASES = ["pagamento de divida", "paguei a divida", "paguei a conta", "quitei", "pago divida", "paguei debito", "conta paga", "divida quitada", "paguei [descricao]", "quitei [descricao]", "pago [descricao]", "conta quitada", "debito pago", "paguei a luz", "paguei agua", "paguei internet", "quitei aluguel", "pago condominio", "divida paga", "ver pago", "confirmar pagamento", "registrar pagamento divida", "paguei divida de [valor]", "quitei conta", "pago a divida", "conta foi paga", "divida foi quitada", "paguei sim", "quitei sim", "pago ok", "conta ok", "debito ok"]
DEBT_PHRASES = ["divida", "parcela", "vence", "vencimento", "conta a pagar", "debito novo", "adicionar divida", "nova divida", "registrar divida", "divida [descricao] [valor]", "parcela [valor]", "vence dia [data] [valor]", "vencimento em [data]", "conta luz [valor]", "divida aluguel [valor]", "parcela carro [valor]", "adicionar debito", "novo debito", "registrar parcela", "divida nova", "debito [descricao] [valor]", "add divida", "new debt", "register debt", "divida vence [data]", "parcela vence [data]", "conta vence [data]"]
INCOME_ADD_PHRASES = ["recebi", "salario", "ganhei", "deposito", "entrou", "recebido", "pagamento recebido", "salario entrou", "ganhei [valor]", "deposito [valor]", "recebi salario", "entrou na conta", "recebimento", "add income", "new income", "register income", "recebi [descricao] [valor]", "salario de [valor]", "ganhei bonus [valor]", "deposito bancario [valor]", "recebi pagamento", "entrou grana", "grana entrou", "recebi dinheiro", "dinheiro entrou", "add recebimento", "novo recebimento", "registrar salario", "salario novo", "ganho novo", "recebi sim", "entrou ok", "pagamento ok"]

# Função para normalizar texto (remover acentos e converter para minúsculas)
def normalize_text(text):
    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text

# Dicionário de palavras-chave
CATEGORY_KEYWORDS = {
    "Alimentação": ["restaurante", "almoço", "janta", "ifood", "rappi", "mercado", "comida", "lanche", "pizza", "hamburguer", "padaria", "café", "sorvete", "açaí", "supermercado", "refeicao", "almoco", "jantinha", "lanx", "pizzaria", "burguer", "acai", "doces", "salgados", "frutas", "vegetais", "carnes", "pao", "queijo", "leite", "iogurte", "refri", "cerveja", "vinho", "agua", "suco", "cha", "almocinho", "jantarzinho"],
    "Transporte": ["uber", "99", "táxi", "gasolina", "metrô", "ônibus", "passagem", "estacionamento", "escritorio", "combustível", "pedágio", "rodízio", "moto", "taxi", "onibus", "metro", "carro", "bicicleta", "patinete", "van", "trem", "aviao", "barco", "combustivel", "oleo", "manutencao carro", "ipva", "licenciamento", "seguro carro", "multa", "transporte publico", "cartao transporte", "uber black", "99 pop", "inDriver"],
    "Moradia": ["aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "diarista", "limpeza", "reforma", "manutenção", "conta", "aluguelzinho", "condominio", "energia", "agua", "net", "gas", "faxina", "reforminha", "consertos", "casa", "apto", "imovel", "telefone fixo", "tv a cabo", "netflix casa", "spotify casa", "alarmes", "seguranca", "jardim", "piscina", "elevador", "porteiro"],
    "Lazer": ["cinema", "show", "bar", "festa", "viagem", "streaming", "spotify", "netflix", "jogo", "ingresso", "passeio", "clube", "hobby", "balada", "pub", "rolê", "viagenzinha", "filme", "serie", "musica", "game", "videogame", "futebol", "esporte", "ginastica", "praia", "piscina lazer", "churrasco", "amigos", "familia", "aniversario", "casamento", "ferias", "hotel", "airbnb", "passeios", "turismo"],
    "Saúde": ["farmácia", "remédio", "médico", "consulta", "plano", "academia", "suplemento", "dentista", "exame", "terapia", "farmacia", "remedio", "medico", "plano saude", "gym", "vitamina", "odontologo", "psicologo", "fisioterapia", "nutricionista", "oftalmologista", "hospital", "cirurgia", "vacina", "checkup", "massagem", "yoga", "pilates", "corrida", "saude mental", "remedios naturais", "suplementos alimentares"],
    "Compras": ["roupa", "roupas", "tênis", "sapato", "presente", "shopping", "online", "eletrônicos", "celular", "computador", "acessório", "decoração", "livraria", "tenis", "sapatos", "presentinho", "comprinhas", "eletrodomesticos", "fone", "headphone", "mouse", "teclado", "monitor", "tv", "geladeira", "fogao", "microondas", "maquina lavar", "joias", "bolsa", "mochila", "oculos", "relogio", "perfume", "maquiagem"],
    "Educação": ["curso", "livro", "faculdade", "material", "escola", "aula", "palestra", "cursinho", "livros", "facul", "materiais escolares", "escolinha", "aulas", "workshop", "seminario", "certificacao", "idiomas", "ingles", "espanhol", "online course", "udemy", "coursera", "livraria escola", "caderno", "caneta", "mochila escola", "uniforme", "mensalidade", "matricula", "prova", "exame vestibular"],
    "Essenciais": ["aluguel", "condomínio", "luz", "água", "internet", "gás", "iptu", "mercado", "farmácia", "plano", "metrô", "ônibus", "combustível", "faculdade", "escola", "basico", "necessario", "essencial", "contas basicas", "morar", "viver", "sobrevivencia"],
    "Desejos": ["restaurante", "ifood", "rappi", "lanche", "pizza", "cinema", "show", "bar", "festa", "viagem", "streaming", "jogo", "roupas", "tênis", "presente", "shopping", "uber", "99", "táxi", "hobby", "luxo", "diversao", "prazer", "gostos", "caprichos", "mimos", "extras"],
    "Outros": ["outro", "diversos", "miscelanea", "nao categorizado", "geral"]
}

COMMANDS_MESSAGE = """
Olá! Sou a sua assistente financeira. 😊
Você pode falar comigo de forma natural! Tente coisas como:

- `gastei 25,50 no almoço` ou `almoco 25,5`
- `recebi meu pagamento de 2.500,08` ou `salario entrou 2500`
- `dívida luz 180` ou `conta luz vence dia 15 180`
- `paguei a conta de luz` ou `quitei luz`
- `qual o meu saldo?` ou `quanto sobrou?`
- `quanto entrou e saiu hoje?` ou `balanço do dia`
- `dica financeira` ou `me da uma dica de grana`

Aqui estão alguns dos comandos que eu entendo (tem muuuitos mais, formais e informais!):

💰 **Orçamento e Metas**
- `definir rendimento [valor]` ou `meu salario eh [valor]`
- `meu orçamento` ou `como ta meu budget?`
- `definir meta [descricao] [valor]` ou `quero poupar pra [descricao] [valor]`
- `minhas metas` ou `quais metas eu tenho?`

📊 **Análises e Relatórios**
- `resumo financeiro` ou `visao geral da grana`
- `comparar gastos` ou `compara mes passado`
- `gastos da [semana/mês/dia]` ou `o q gastei nessa semana?`
- `entradas e saídas [hoje/semana/mês]` ou `quanto entrou e saiu no mes?`
- `minhas dívidas` ou `o q eu devo?`

💡 **Outros**
- `dica financeira` ou `dica pra economizar`
- `apagar último gasto` ou `exclui o ultimo`
- `adicionar recorrente [descricao] [valor] [frequencia]` ou `todo mes [descricao] [valor]`
- `meus recorrentes` ou `gastos fixos?`
"""

# --- Funções da IA ---

def parse_value_string(s):
    if not isinstance(s, str): return float(s)
    s = s.replace('R$', '').strip()
    
    if ',' not in s and '.' not in s:
        return float(s)
    
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif '.' in s:
        parts = s.split('.')
        if len(parts[-1]) == 3 and len(parts) > 1:
            s = s.replace('.', '')
    return float(s)

def extract_all_monetary_values(text):
    pattern = r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+)'
    matches = re.findall(pattern, text)
    if not matches: return []
    values = []
    for match in matches:
        try:
            values.append(parse_value_string(match))
        except (ValueError, IndexError): continue
    return values

def extract_date(text):
    match = re.search(r'(\d{1,2}/\d{1,2})', text)
    if match: return match.group(0)
    return None

def infer_category(description):
    normalized_desc = normalize_text(description)
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category in ["Essenciais", "Desejos"]: continue
        for keyword in keywords:
            if normalize_text(keyword) in normalized_desc: return category
    return "Outros"

def save_expense_to_csv(user_id, description, value):
    now = datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    category = infer_category(description)
    file_exists = os.path.exists(CSV_FILE_NAME)
    expense_id = 1
    if file_exists and os.path.getsize(CSV_FILE_NAME) > 0:
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
            expense_id = sum(1 for line in file if line.strip() and not line.startswith("UserID"))
    new_row = f"{user_id};{expense_id};{timestamp};{description};{value:.2f};{category}\n"
    with open(CSV_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(CSV_FILE_NAME) == 0:
            file.write("UserID;ID;Data e Hora;Descricao;Valor;Categoria\n")
        file.write(new_row)
    return category

def save_payment_to_csv(user_id, description, value):
    now = datetime.datetime.now(TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists(PAGAMENTOS_FILE_NAME)
    with open(PAGAMENTOS_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(PAGAMENTOS_FILE_NAME) == 0:
            file.write("UserID;Data e Hora;Descricao;Valor\n")
        file.write(f"{user_id};{timestamp};{description};{value:.2f}\n")

def save_debt_to_csv(user_id, value, description, date="Sem data"):
    new_row = f"{user_id};{date};{description};{value:.2f}\n"
    file_exists = os.path.exists(DIVIDAS_FILE_NAME)
    with open(DIVIDAS_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(DIVIDAS_FILE_NAME) == 0:
            file.write("UserID;Data de Vencimento;Descricao;Valor\n")
        file.write(new_row)
    if date != "Sem data":
        return f"✅ Dívida registrada: {description} no valor de R${value:.2f} com vencimento em {date}."
    else:
        return f"✅ Dívida registrada: {description} no valor de R${value:.2f} (sem data de vencimento)."

def get_debts_report(user_id):
    if not os.path.exists(DIVIDAS_FILE_NAME): return "Nenhuma dívida registrada ainda."
    report_lines = ["📋 *Suas Dívidas Pendentes* 📋\n"]
    total_debts, found_debts = 0.0, False
    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                try:
                    date_due, description, value = row[1], row[2], float(row[3])
                    report_lines.append(f"- {description} (Vence: {date_due}): R${value:.2f}")
                    total_debts += value; found_debts = True
                except (ValueError, IndexError): continue
    if not found_debts: return "Você não tem nenhuma dívida pendente. Parabéns! 🎉"
    report_lines.append(f"\n*Total de Dívidas: R${total_debts:.2f}*")
    return "\n".join(report_lines)

def delete_debt_from_csv(user_id, description_to_delete):
    if not os.path.exists(DIVIDAS_FILE_NAME):
        return "Não há dívidas para apagar."
    lines, debt_found = [], False
    normalized_desc_to_del = normalize_text(description_to_delete)
    with open(DIVIDAS_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
    with open(DIVIDAS_FILE_NAME, 'w', encoding='utf-8') as file:
        if lines:
            file.write(lines[0])
        for line in lines[1:]:
            parts = line.strip().split(';')
            if len(parts) > 2 and parts[0] == user_id and normalized_desc_to_del == normalize_text(parts[2]):
                debt_found = True
            else:
                file.write(line)
    if not debt_found: return f"Não encontrei a dívida '{description_to_delete}' para apagar."
    return f"✅ Dívida '{description_to_delete}' paga e removida da sua lista!"

def set_balance(user_id, value):
    lines, user_found = [], False
    if os.path.exists(SALDO_FILE_NAME):
        with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
    
    with open(SALDO_FILE_NAME, 'w', encoding='utf-8') as file:
        file.write("UserID;Saldo\n")
        for line in lines[1:]:  # Pula cabeçalho antigo
            if line.startswith(user_id):
                file.write(f"{user_id};{value:.2f}\n"); user_found = True
            else:
                file.write(line)
        if not user_found:
            file.write(f"{user_id};{value:.2f}\n")
            
    return f"✅ Saldo atualizado! Seu novo saldo é de *R${value:.2f}*."

def record_payment_and_update_balance(user_id, value, description="Pagamento"):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance + value
        set_balance(user_id, new_balance)
        
        save_payment_to_csv(user_id, description, value)
        today_str = datetime.datetime.now(TIMEZONE).strftime("%d/%m")
        return f"✅ Pagamento de R${value:.2f} registrado em {today_str}!\n\nSeu saldo atual é de *R${new_balance:.2f}*."
    except Exception as e: return f"Ocorreu um erro ao registrar o pagamento: {e}"

def get_io_summary(user_id, period):
    total_in, total_out = 0.0, 0.0
    now = datetime.datetime.now(TIMEZONE)
    start_date = None
    
    if period == "dia":
        start_date_str, period_name = now.strftime("%Y-%m-%d"), "hoje"
    elif period == "semana":
        start_date = now.date() - datetime.timedelta(days=now.weekday())
        period_name = "na semana"
        start_date_str = start_date.strftime("%Y-%m-%d")
    elif period == "mês":
        start_date_str, period_name = now.strftime("%Y-%m"), "no mês"

    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        timestamp_str = row[2]
                        value = float(row[4])
                        
                        if period == "semana":
                            row_date = datetime.datetime.strptime(timestamp_str.split(' ')[0], "%Y-%m-%d").date()
                            if row_date >= start_date:
                                total_out += value
                        elif timestamp_str.startswith(start_date_str):
                            total_out += value
                    except (ValueError, IndexError):
                        continue

    if os.path.exists(PAGAMENTOS_FILE_NAME):
        with open(PAGAMENTOS_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        timestamp_str = row[1]
                        value = float(row[3])

                        if period == "semana":
                             row_date = datetime.datetime.strptime(timestamp_str.split(' ')[0], "%Y-%m-%d").date()
                             if row_date >= start_date:
                                 total_in += value
                        elif timestamp_str.startswith(start_date_str):
                            total_in += value
                    except (ValueError, IndexError):
                        continue
                        
    return f"💸 *Balanço {period_name}*\n\n- Entradas: *R${total_in:.2f}*\n- Saídas: *R${total_out:.2f}*"

def send_whatsapp_message(phone_number, message_text):
    if not all([ACCESS_TOKEN, PHONE_NUMBER_ID]):
        print("Credenciais faltando. Mensagem não enviada.")
        print(f"Para: {phone_number}\nMensagem: {message_text}")
        return

    try:
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
        data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e: print(f"Erro ao enviar mensagem para {phone_number}: {e}")

def get_current_balance(user_id):
    if not os.path.exists(SALDO_FILE_NAME): return 0.0
    with open(SALDO_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        next(reader, None) # Pula o cabeçalho
        for row in reader:
            if row and row[0] == user_id: return float(row[1])
    return 0.0

def record_expense_and_update_balance(user_id, value):
    try:
        current_balance = get_current_balance(user_id)
        new_balance = current_balance - value
        set_balance(user_id, new_balance)
        return True
    except Exception: return False

def delete_last_expense(user_id):
    if not os.path.exists(CSV_FILE_NAME): return "Não há gastos para apagar."
    lines, last_expense_of_user_idx = [], -1
    with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file: lines = file.readlines()
    
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip().split(';')[0] == user_id:
            last_expense_of_user_idx = i
            break
            
    if last_expense_of_user_idx == -1: return "Você não tem gastos registrados para apagar."
    
    deleted_line = lines.pop(last_expense_of_user_idx).strip().split(';')
    deleted_description, deleted_value = deleted_line[3], float(deleted_line[4])
    
    with open(CSV_FILE_NAME, 'w', encoding='utf-8') as file: file.writelines(lines)
    
    current_balance = get_current_balance(user_id)
    new_balance = current_balance + deleted_value
    set_balance(user_id, new_balance)
    
    return f"🗑️ Último gasto apagado com sucesso!\n- Descrição: {deleted_description}\n- Valor: R${deleted_value:.2f}\n\nSeu saldo foi atualizado para *R${new_balance:.2f}*."

def get_financial_summary(user_id):
    balance = get_current_balance(user_id)
    return f"💰 *Resumo Financeiro*\nSeu saldo atual é: *R${balance:.2f}*."

def get_period_report(user_id, period):
    if not os.path.exists(CSV_FILE_NAME): return "Nenhum gasto registrado ainda."
    total, now = 0.0, datetime.datetime.now(TIMEZONE)
    start_date = None

    if period == "dia":
        start_date_str, period_name = now.strftime("%Y-%m-%d"), "de hoje"
    elif period == "semana":
        start_date = now.date() - datetime.timedelta(days=now.weekday())
        period_name = "da semana"
        start_date_str = start_date.strftime("%Y-%m-%d")
    elif period == "mês":
        start_date_str, period_name = now.strftime("%Y-%m"), "do mês"

    report_lines = [f"🧾 Seus gastos {period_name} 🧾\n"]
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

# --- FUNÇÕES EXPANDIDAS E NOVAS ---

def set_income(user_id, value):
    # Agora salva também em um arquivo de orçamento como rendimento mensal (simples)
    file_exists = os.path.exists(ORCAMENTO_FILE_NAME)
    with open(ORCAMENTO_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(ORCAMENTO_FILE_NAME) == 0:
            file.write("UserID;Tipo;Valor\n")
        file.write(f"{user_id};Rendimento;{value:.2f}\n")
    return set_balance(user_id, value) + "\nRendimento definido como base para orçamento!"

def get_budget_report(user_id):
    if not os.path.exists(ORCAMENTO_FILE_NAME): return "Nenhum orçamento definido ainda."
    rendimento = 0.0
    with open(ORCAMENTO_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id and row[1] == "Rendimento":
                rendimento = float(row[2])
    if rendimento == 0.0: return "Defina seu rendimento primeiro com `definir rendimento [valor]`."
    return f"📊 *Seu Orçamento*\nRendimento mensal: R${rendimento:.2f}\nSugestão: 50% essenciais (R${rendimento*0.5:.2f}), 30% desejos (R${rendimento*0.3:.2f}), 20% poupança (R${rendimento*0.2:.2f})."

def get_financial_tip():
    tips = [
        "💡 Dica: Anote todos os seus gastos, até mesmo os pequenos. Isso ajuda a ter uma visão clara de para onde seu dinheiro está indo.",
        "💡 Dica: Tente a regra 50/30/20. Destine 50% da sua renda para necessidades, 30% para desejos e 20% para poupança e investimentos.",
        "💡 Dica: Antes de uma compra por impulso, espere 24 horas. Muitas vezes, a vontade passa e você economiza!",
        "💡 Dica: Crie um fundo de emergência. O ideal é ter o equivalente a 3 a 6 meses de suas despesas guardado para imprevistos.",
        "💡 Dica: Negocie descontos em contas fixas, como internet ou plano de saúde. Muitas empresas oferecem promoções!",
        "💡 Dica: Use apps de cashback para compras online. Pode render uma graninha extra no fim do mês.",
        "💡 Dica: Planeje refeições semanais para evitar pedidos caros de delivery.",
        "💡 Dica: Invista em educação financeira: leia livros como 'Pai Rico, Pai Pobre'.",
        "💡 Dica: Defina metas SMART: Específicas, Mensuráveis, Alcançáveis, Relevantes e Temporais.",
        "💡 Dica: Revise seu orçamento todo mês e ajuste conforme necessário.",
    ]
    return random.choice(tips)

def compare_expenses(user_id):
    # Implementação básica: compara total de gastos do mês atual vs anterior
    now = datetime.datetime.now(TIMEZONE)
    current_month = now.strftime("%Y-%m")
    last_month = (now - datetime.timedelta(days=now.day)).strftime("%Y-%m")
    total_current, total_last = 0.0, 0.0
    
    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=';'); next(reader, None)
            for row in reader:
                if row and row[0] == user_id:
                    try:
                        timestamp = row[2]
                        value = float(row[4])
                        if timestamp.startswith(current_month): total_current += value
                        elif timestamp.startswith(last_month): total_last += value
                    except: continue
    
    diff = total_current - total_last
    if diff > 0:
        msg = f"Gastou R${diff:.2f} a mais que no mês passado."
    elif diff < 0:
        msg = f"Economizou R${-diff:.2f} comparado ao mês passado. Parabéns!"
    else:
        msg = "Gastos iguais ao mês passado."
    return f"📈 *Comparação de Gastos*\nMês atual: R${total_current:.2f}\nMês passado: R${total_last:.2f}\n{msg}"

# Novas funções para metas (implementação básica)
def save_meta_to_csv(user_id, description, value):
    new_row = f"{user_id};{description};{value:.2f};0.00\n"  # Meta;Progresso
    file_exists = os.path.exists(METAS_FILE_NAME)
    with open(METAS_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(METAS_FILE_NAME) == 0:
            file.write("UserID;Descricao;Valor Meta;Progresso\n")
        file.write(new_row)
    return f"✅ Meta registrada: {description} no valor de R${value:.2f}."

def get_metas_report(user_id):
    if not os.path.exists(METAS_FILE_NAME): return "Nenhuma meta registrada ainda."
    report_lines = ["🎯 *Suas Metas* 🎯\n"]
    found_metas = False
    with open(METAS_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                description, meta_value, progress = row[1], float(row[2]), float(row[3])
                report_lines.append(f"- {description}: R${progress:.2f}/{meta_value:.2f}")
                found_metas = True
    if not found_metas: return "Você não tem metas definidas. Defina uma com `definir meta [descricao] [valor]`!"
    return "\n".join(report_lines)

# Novas funções para recorrentes (implementação básica)
def save_recorrente_to_csv(user_id, description, value, frequency):
    new_row = f"{user_id};{description};{value:.2f};{frequency}\n"
    file_exists = os.path.exists(RECORRENTES_FILE_NAME)
    with open(RECORRENTES_FILE_NAME, 'a', encoding='utf-8') as file:
        if not file_exists or os.path.getsize(RECORRENTES_FILE_NAME) == 0:
            file.write("UserID;Descricao;Valor;Frequencia\n")
        file.write(new_row)
    return f"✅ Gasto recorrente adicionado: {description} de R${value:.2f} ({frequency})."

def get_recorrentes_report(user_id):
    if not os.path.exists(RECORRENTES_FILE_NAME): return "Nenhum gasto recorrente registrado."
    report_lines = ["🔄 *Gastos Recorrentes* 🔄\n"]
    found = False
    with open(RECORRENTES_FILE_NAME, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';'); next(reader, None)
        for row in reader:
            if row and row[0] == user_id:
                description, value, frequency = row[1], float(row[2]), row[3]
                report_lines.append(f"- {description}: R${value:.2f} ({frequency})")
                found = True
    if not found: return "Sem gastos recorrentes. Adicione com `adicionar recorrente [descricao] [valor] [frequencia]`!"
    return "\n".join(report_lines)

# --- Webhook Principal ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return 'Failed verification', 403
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            if 'messages' not in value:
                return 'EVENT_RECEIVED', 200

            message_data = value['messages'][0]
            user_id = message_data['from']
            user_name = value['contacts'][0].get('profile', {}).get('name', 'Pessoa')
            original_message_text = message_data['text']['body'].strip()
            message_text = normalize_text(original_message_text)
            
            reply_message = ""
            
            if any(g in message_text for g in GREETINGS):
                reply_message = f"Olá, {user_name}! 👋\n\n{COMMANDS_MESSAGE}"
            elif any(s in message_text for s in DEBTS_PHRASES):
                reply_message = get_debts_report(user_id)
            elif any(s in message_text for s in INCOME_PHRASES):
                values = extract_all_monetary_values(original_message_text)
                if values: reply_message = set_income(user_id, values[0])
                else: reply_message = "Não entendi o valor. Tente `definir rendimento [valor]`."
            elif any(s in message_text for s in BUDGET_PHRASES):
                reply_message = get_budget_report(user_id)
            elif any(s in message_text for s in TIP_PHRASES):
                reply_message = get_financial_tip()
            elif any(s in message_text for s in COMPARE_PHRASES):
                reply_message = compare_expenses(user_id)
            elif any(s in message_text for s in SUMMARY_PHRASES):
                reply_message = get_financial_summary(user_id)
            elif any(s in message_text for s in BALANCE_PHRASES):
                balance = get_current_balance(user_id)
                reply_message = f"💵 Seu saldo atual é de *R${balance:.2f}*."
            elif any(s in message_text for s in DELETE_PHRASES):
                reply_message = delete_last_expense(user_id)
            elif any(s in message_text for s in META_PHRASES_SET):
                values = extract_all_monetary_values(original_message_text)
                if values:
                    description = re.sub(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+|R\$|\s+)', ' ', original_message_text).strip()
                    description = re.sub(r'|'.join(META_PHRASES_SET), '', description, flags=re.IGNORECASE).strip()
                    reply_message = save_meta_to_csv(user_id, description.capitalize(), values[0])
                else:
                    reply_message = "Não entendi o valor. Tente `definir meta [descricao] [valor]`."
            elif any(s in message_text for s in META_PHRASES_GET):
                reply_message = get_metas_report(user_id)
            elif any(s in message_text for s in REC_PHRASES_SET):
                values = extract_all_monetary_values(original_message_text)
                if values:
                    parts = re.split(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+|R\$)', original_message_text)
                    description = ''
                    frequency = 'mensal'  # Default
                    for part in parts:
                        if 'semana' in normalize_text(part): frequency = 'semanal'
                        elif 'mes' in normalize_text(part): frequency = 'mensal'
                        elif 'ano' in normalize_text(part): frequency = 'anual'
                        elif 'dia' in normalize_text(part): frequency = 'diario'
                        else: description += part.strip()
                    description = re.sub(r'|'.join(REC_PHRASES_SET), '', description, flags=re.IGNORECASE).strip()
                    reply_message = save_recorrente_to_csv(user_id, description.capitalize(), values[0], frequency)
                else:
                    reply_message = "Não entendi o valor. Tente `adicionar recorrente [descricao] [valor] [frequencia]`."
            elif any(s in message_text for s in REC_PHRASES_GET):
                reply_message = get_recorrentes_report(user_id)
            elif any(s in message_text for s in EXPENSE_REPORT_PHRASES):
                if "hoje" in message_text or "dia" in message_text: reply_message = get_period_report(user_id, "dia")
                elif "semana" in message_text: reply_message = get_period_report(user_id, "semana")
                elif "mes" in message_text or "mês" in message_text: reply_message = get_period_report(user_id, "mês")
                else: reply_message = "Não entendi o período. Tente `gastos do dia`, `da semana` ou `do mês`."
            elif any(s in message_text for s in IO_PHRASES):
                if "hoje" in message_text or "dia" in message_text: reply_message = get_io_summary(user_id, "dia")
                elif "semana" in message_text: reply_message = get_io_summary(user_id, "semana")
                elif "mes" in message_text or "mês" in message_text: reply_message = get_io_summary(user_id, "mês")
                else: reply_message = "Não entendi o período. Tente `entradas e saídas de hoje`."
            elif any(keyword in message_text for keyword in PAY_DEBT_PHRASES):
                description = re.sub(r'|'.join(PAY_DEBT_PHRASES), '', message_text, flags=re.IGNORECASE).strip()
                values = extract_all_monetary_values(original_message_text)
                if values:
                    description_text_only = re.sub(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{1,2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+|R\$|\s+)', ' ', description).strip()
                    delete_response = delete_debt_from_csv(user_id, description_text_only)
                    save_expense_to_csv(user_id, f"Pagamento: {description_text_only.capitalize()}", values[0])
                    record_expense_and_update_balance(user_id, values[0])
                    current_balance = get_current_balance(user_id)
                    reply_message = f"{delete_response}\n\nSeu saldo agora é de *R${current_balance:.2f}*."
                else:
                    reply_message = "Não consegui identificar o valor pago. Tente: `paguei a conta de luz 150`"
            elif any(keyword in message_text for keyword in DEBT_PHRASES):
                values = extract_all_monetary_values(original_message_text)
                date = extract_date(original_message_text)
                if values:
                    description = re.sub(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{1,2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+|R\$|\s+)', ' ', original_message_text).strip()
                    description = re.sub(r'|'.join(DEBT_PHRASES), '', description, flags=re.IGNORECASE).strip()
                    reply_message = save_debt_to_csv(user_id, values[0], description.capitalize(), date=date if date else "Sem data")
                else:
                    reply_message = "Entendi que é uma dívida, mas não consegui identificar o valor."
            elif any(keyword in message_text for keyword in INCOME_ADD_PHRASES):
                values = extract_all_monetary_values(original_message_text)
                if not values:
                    reply_message = "Entendi que é uma entrada, mas não consegui identificar o valor."
                elif any(s in message_text for s in ["ja tinha", "tinha na conta", "meu saldo e", "saldo inicial", "definir saldo", "set saldo", "atualizar saldo", "mudar saldo", "saldo eh", "conta tem", "iniciar saldo", "start balance", "initial balance"]):
                    total_balance = sum(values)
                    reply_message = set_balance(user_id, total_balance)
                else:
                    payment_value = max(values)
                    description = re.sub(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{1,2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+|R\$|\s+)', ' ', original_message_text).strip()
                    description = re.sub(r'|'.join(INCOME_ADD_PHRASES), '', description, flags=re.IGNORECASE).strip()
                    reply_message = record_payment_and_update_balance(user_id, payment_value, description.capitalize() if description else "Entrada")
            else: # Fallback: Gasto
                values = extract_all_monetary_values(original_message_text)
                if values:
                    value = values[0]
                    description = re.sub(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{1,2}|\d{1,3}(?:\.\d{3})*|\d+\.\d{2}|\d+|R\$|\s+)', ' ', original_message_text).strip()
                    description = re.sub(r'^(de|da|do|no|na|gastei|gasto|despesa|add gasto|new expense|register expense)\s', '', description, flags=re.IGNORECASE)
                    
                    if not description.strip():
                        reply_message = "Parece que você enviou um valor sem descrição. Tente de novo, por favor (ex: `almoço 25,50`)."
                    else:
                        category = save_expense_to_csv(user_id, description.capitalize(), value)
                        record_expense_and_update_balance(user_id, value)
                        today_str = datetime.datetime.now(TIMEZONE).strftime("%d/%m")
                        current_balance = get_current_balance(user_id)
                        reply_message = f"✅ Gasto Registrado em {today_str}! ({category})\n- {description.capitalize()}: R${value:.2f}\n\nSeu saldo atual é *R${current_balance:.2f}*."
                else:
                    reply_message = f"Não entendi, {user_name}. Se for um gasto, tente `[descrição] [valor]`. Se precisar de ajuda, envie `comandos`."

            if reply_message:
                send_whatsapp_message(user_id, reply_message)

        except (KeyError, IndexError, TypeError) as e:
            print(f"Erro ao processar o webhook: {e}\nData: {request.get_data(as_text=True)}")
            pass
        
        return 'EVENT_RECEIVED', 200

if __name__ == "__main__":
    app.run(debug=False, port=os.getenv("PORT", default=5000))

