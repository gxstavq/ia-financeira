import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import pickle

data = []

# -- Gerador automático de frases para turbinar as intenções --

# Greetings
greetings_frases = [
    "oi", "olá", "ola", "opa", "e aí", "eae", "yo", "fala ai", "fala", "salve", "alô", "alow", "hey", "hi", "hello", "bom dia", "boa tarde", "boa noite", "menu", "comandos", "funcoes", "me ajuda", "ajuda", "ajuda por favor", "socorro", "preciso de ajuda", "me salva", "tudo bem", "tudo certo", "como vai", "tranquilo", "beleza", "blz", "suave", "sup", "fala comigo", "start", "iniciar", "inicio", "vamos la", "começar", "ajudaaa", "ajudaaa!", "me socorre", "alguém aí?", "tem alguém aí?", "tem alguem", "está ai?", "vc está ai?", "vc ta ai?", "você está ai?", "você ta ai?", "olá bot", "ei bot", "oi bot", "fala bot", "olá ia", "assistente financeira", "e aí, beleza?", "fala zap", "fala chat", "oi zap", "opa assistente", "alô bot", "alow bot", "fala zapbot", "olá zapbot", "yo bot", "fala ai bot", "tudo bem bot", "tudo certo bot", "beleza bot", "blz bot", "suave bot", "fala zap", "fala ia", "oi assistente", "olá assistente", "bom dia bot", "boa tarde bot", "boa noite bot"
]
# Multiplica por variações
for frase in greetings_frases:
    data.append((frase, "greetings"))
    data.append((frase + " tudo bem?", "greetings"))
    data.append(("oi " + frase, "greetings"))
    data.append((frase + " 👋", "greetings"))
    data.append((frase + " 😃", "greetings"))
    data.append(("👋 " + frase, "greetings"))
    data.append(("fala " + frase, "greetings"))
    data.append(("menu " + frase, "greetings"))
    data.append(("comandos " + frase, "greetings"))

# Dividas
dividas_frases = [
    "minhas dívidas", "minhas dividas", "ver dívidas", "ver dividas", "quais as minhas dívidas", "quais as minhas dividas", "tenho dívidas?", "tenho dividas?", "contas a pagar", "contas pra pagar", "contas pendentes", "contas atrasadas", "me mostra as dívidas", "me mostra as dividas", "dívidas atuais", "dividas atuais", "quais contas estão abertas?", "quais contas tão abertas?", "meus débitos", "meus debitos", "débitos", "debitos", "lista de dívidas", "lista de dividas", "dívida atrasada", "divida atrasada", "dívida vencida", "divida vencida", "dividas pendentes", "dívidas pendentes", "o que devo?", "o que eu devo?", "tô devendo?", "to devendo?", "tem dívida?", "tem divida?", "tem contas pra eu pagar?", "tem boleto?", "ver boleto", "meus boletos", "ver boletos", "contas vencidas", "contas vencidas já", "alguma dívida", "alguma divida", "dividas por favor", "dívidas por favor", "relatório de dívidas", "relatório de dividas", "relatorio de dívidas", "relatorio de dividas", "relatorio de contas", "relatório de contas", "quais contas estão pendentes", "quais contas faltam", "tem boleto vencido?", "tem algo pra vencer?", "devo algo?", "contas vencendo", "devo pra alguém?", "devo pra alguém", "tenho dívida?", "tenho divida?", "lista de pendências", "lista de pendencias", "pendências financeiras", "pendencias financeiras", "quais pendências", "quais pendencias", "me mostra pendencias", "me mostra pendências", "pendencia", "pendência"
]
for frase in dividas_frases:
    data.append((frase, "dividas"))
    data.append(("quero " + frase, "dividas"))
    data.append(("ver " + frase, "dividas"))
    data.append(("me diz " + frase, "dividas"))
    data.append(("me fala " + frase, "dividas"))
    data.append((frase + " por favor", "dividas"))
    data.append(("tem " + frase + "?", "dividas"))
    data.append(("tenho " + frase + "?", "dividas"))
    data.append(("mostra " + frase, "dividas"))
    data.append((frase + " 👀", "dividas"))
    data.append(("ver minhas " + frase, "dividas"))

# Saldo
saldo_frases = [
    "qual o meu saldo", "meu saldo", "quanto dinheiro eu tenho", "saldo atual", "quanto sobrou", "quanto tenho", "saldo", "ver saldo", "quanto ainda tenho", "quanto tenho de grana", "money atual", "grana atual", "quanto tem na conta", "quantos reais eu tenho", "saldo por favor", "saldo agora", "saldo bancário", "saldo disponível", "quero ver meu saldo", "quanto resta", "quanto resta na conta", "quanto dinheiro resta", "quanto tenho sobrando", "quanto tenho pra gastar", "quanto tenho disponível", "saldo na conta", "quanto tenho de saldo", "saldo da conta", "me diz meu saldo", "mostra o saldo", "saldo total", "saldo final", "saldo zap", "saldo bot", "saldo ai"
]
for frase in saldo_frases:
    data.append((frase, "saldo"))
    data.append((frase + "?", "saldo"))
    data.append(("me mostra " + frase, "saldo"))
    data.append(("quero saber " + frase, "saldo"))
    data.append(("saldo " + frase, "saldo"))
    data.append(("quanto tenho " + frase, "saldo"))
    data.append(("disponível " + frase, "saldo"))
    data.append(("tenho " + frase, "saldo"))

# Dica
dica_frases = [
    "me dá uma dica financeira", "conselho de finanças", "dica para economizar", "dica de grana", "alguma dica de dinheiro", "dica de economia", "me dá uma dica", "quero dica financeira", "me aconselha", "me dá um conselho financeiro", "tem alguma dica de finanças?", "dica do dia", "manda uma dica", "me ensina a economizar", "dica pra guardar dinheiro", "dica pra juntar grana", "dica pra investir", "dica de investimento", "dica", "me ajuda a economizar", "tem alguma dica?", "tip financeiro", "dica de poupar", "me ensina a poupar", "dica de poupança", "me diz uma dica", "conselho pra economizar", "conselho do dia", "me fala uma dica", "me fala uma dica financeira", "alguma dica", "conselho?", "me aconselha ai", "algum conselho", "me da uma dica ai", "dica financeira ai", "tip do dia", "tip zap", "tip bot", "dica bot", "dica ai", "dica zap"
]
for frase in dica_frases:
    data.append((frase, "dica"))
    data.append(("tem " + frase + "?", "dica"))
    data.append(("me manda " + frase, "dica"))
    data.append(("quero " + frase, "dica"))
    data.append(("qual " + frase, "dica"))
    data.append(("dica " + frase, "dica"))
    data.append((frase + " por favor", "dica"))
    data.append((frase + " 🙏", "dica"))
    data.append((frase + " 😁", "dica"))
    data.append(("manda uma " + frase, "dica"))

# Orçamento
orcamento_frases = [
    "meu orçamento", "ver orçamento", "relatório de orçamento", "orcamento mensal", "qual meu budget", "como está meu orçamento", "orcamento", "me mostra o orçamento", "mostra orçamento", "orcamento atual", "quero ver meu orçamento", "meu budget", "como está o budget", "ver meu orçamento", "relatório do orçamento", "budget", "status do orçamento", "me diz o orçamento", "plano financeiro", "meu plano financeiro", "ver plano financeiro", "mostra meu orçamento", "orçamento detalhado", "orçamento resumido", "resumo do orçamento", "meu orçamento atual", "relatorio financeiro", "financeiro", "relatorio mensal", "resumo financeiro", "relatorio do mês", "relatorio de gastos", "resumo do mês"
]
for frase in orcamento_frases:
    data.append((frase, "orcamento"))
    data.append(("ver " + frase, "orcamento"))
    data.append(("me mostra " + frase, "orcamento"))
    data.append(("mostra " + frase, "orcamento"))
    data.append((frase + " por favor", "orcamento"))
    data.append((frase + " do mês", "orcamento"))
    data.append((frase + " desse mês", "orcamento"))
    data.append((frase + " atual", "orcamento"))
    data.append(("quero saber " + frase, "orcamento"))
    data.append(("quero " + frase, "orcamento"))

# Você pode adicionar outros tipos de intenção aqui...

df = pd.DataFrame(data, columns=["frase", "intencao"])

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(df.frase)
y = df.intencao

clf = LogisticRegression(max_iter=1500)
clf.fit(X, y)

# Salva modelo e vetor em disco
pickle.dump(clf, open("intent_clf.pkl", "wb"))
pickle.dump(vectorizer, open("intent_vectorizer.pkl", "wb"))