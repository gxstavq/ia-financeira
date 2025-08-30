from flask import Flask, request
from db import get_db, create_tables
import re
from datetime import datetime
import os
import requests

app = Flask(__name__)
create_tables()

# Variáveis de ambiente do Render (mantenha o que já tem configurado!)
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN") or "SEU_ACCESS_TOKEN"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID") or "SEU_PHONE_ID"
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") or "TOKEN123"

def parse_transaction(text):
    """
    Recebe frase tipo 'academia 120', 'recebi salário 2000', 'paguei ifood 37,67'
    e retorna dict com tipo, categoria, valor, data, descricao
    """
    text = text.lower()
    valor_match = re.search(r'([0-9]+(?:[.,][0-9]{1,2})?)', text)
    if not valor_match:
        return None

    valor = float(valor_match.group(1).replace(',', '.'))
    descricao = text

    # Data: se houver, pega; senão usa hoje
    data_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    if data_match:
        data = datetime.strptime(data_match.group(1), "%d/%m/%Y").date()
    else:
        data = datetime.now().date()
    
    # Categoria e tipo (básico, pode evoluir depois)
    palavras_receita = ["recebi", "salario", "depósito", "deposito", "entrou", "ganhei", "receita"]
    palavras_divida = ["divida", "dívida", "pagar", "emprestimo", "empréstimo"]
    palavras_despesa = ["paguei", "gastei", "comprei", "compra", "pago", "gastou"]
    tipo = "despesa"
    for p in palavras_receita:
        if p in text:
            tipo = "receita"
    for p in palavras_divida:
        if p in text:
            tipo = "divida"
    if tipo == "despesa":
        for p in palavras_despesa:
            if p in text:
                tipo = "despesa"

    # Categoria: palavra logo antes do valor
    cat_match = re.search(r'([a-zA-Zãõáéíóúçêôâûü ]+)\s+' + valor_match.group(1), text)
    categoria = cat_match.group(1).strip() if cat_match else ("receita" if tipo=="receita" else "outros")

    return {
        "tipo": tipo,
        "categoria": categoria,
        "valor": valor,
        "data": str(data),
        "descricao": descricao
    }

def registrar_transacao(user_id, transacao):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO transacoes (user_id, tipo, categoria, valor, data, descricao)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, transacao["tipo"], transacao["categoria"], transacao["valor"], transacao["data"], transacao["descricao"]))
    conn.commit()
    conn.close()

def resumo_usuario(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COALESCE(SUM(valor),0) FROM transacoes WHERE user_id=? AND tipo="receita"', (user_id,))
    total_receita = c.fetchone()[0]
    c.execute('SELECT COALESCE(SUM(valor),0) FROM transacoes WHERE user_id=? AND tipo="despesa"', (user_id,))
    total_despesa = c.fetchone()[0]
    saldo = total_receita - total_despesa
    c.execute('SELECT categoria, SUM(valor) FROM transacoes WHERE user_id=? AND tipo="despesa" GROUP BY categoria', (user_id,))
    despesas_cat = c.fetchall()
    conn.close()
    return saldo, total_receita, total_despesa, despesas_cat

def listar_transacoes(user_id, limit=5):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT tipo, categoria, valor, data, descricao FROM transacoes WHERE user_id=? ORDER BY id DESC LIMIT ?', (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def resposta_ajuda():
    return (
        "🤖 Eu sou sua IA financeira!\n\n"
        "Você pode:\n"
        "• Registrar gastos: mercado 120\n"
        "• Registrar receitas: recebi salário 2000\n"
        "• Consultar saldo: saldo\n"
        "• Ver últimas transações: extrato\n"
        "• Consultar orçamento do mês: orçamento\n"
        "• E muito mais! Tente frases livres 😉"
    )

def send_whatsapp_message(phone_number, message_text):
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
        response.raise_for_status()
    except Exception as e:
        print("Erro ao enviar mensagem:", e)

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == 'GET':
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if token == VERIFY_TOKEN:
            return challenge, 200
        return "Verificação falhou", 403

    if request.method == "POST":
        try:
            data = request.get_json()
            value = data['entry'][0]['changes'][0]['value']
            if 'messages' not in value:
                return 'EVENT_RECEIVED', 200

            message_data = value['messages'][0]
            user_id = message_data['from']
            message_text = message_data['text']['body'].strip().lower()

            # Lógica de intenção inteligente
            if re.match(r"^(comando|ajuda|menu|start)", message_text):
                resp = resposta_ajuda()
            elif "saldo" in message_text:
                saldo, total_receita, total_despesa, _ = resumo_usuario(user_id)
                resp = f"💰 Seu saldo: R${saldo:.2f}\nReceitas: R${total_receita:.2f}\nDespesas: R${total_despesa:.2f}"
            elif "extrato" in message_text or "ultimas" in message_text or "últimas" in message_text:
                transacoes = listar_transacoes(user_id)
                if not transacoes:
                    resp = "Você ainda não registrou transações."
                else:
                    linhas = []
                    for t in transacoes:
                        emoji = "🟢" if t["tipo"]=="receita" else "🔴" if t["tipo"]=="despesa" else "🟡"
                        linhas.append(f"{emoji} {t['categoria'].title()}: R${t['valor']} em {t['data']}")
                    resp = "Últimos lançamentos:\n" + "\n".join(linhas)
            elif "orçamento" in message_text or "orcamento" in message_text:
                _, _, _, despesas_cat = resumo_usuario(user_id)
                if not despesas_cat:
                    resp = "Você ainda não tem despesas registradas este mês."
                else:
                    resp = "📝 Orçamento por categoria:\n" + "\n".join([f"• {cat}: R${valor:.2f}" for cat, valor in despesas_cat])
            elif re.match(r".*\d", message_text):
                transacao = parse_transaction(message_text)
                if transacao:
                    registrar_transacao(user_id, transacao)
                    emoji = "🟢" if transacao["tipo"]=="receita" else "🔴" if transacao["tipo"]=="despesa" else "🟡"
                    resp = f"{emoji} {transacao['tipo'].capitalize()} registrada!\n{transacao['categoria'].title()} | R${transacao['valor']:.2f} | {transacao['data']}\n"
                else:
                    resp = "Não consegui entender. Tente: mercado 120 ou recebi salário 2000"
            else:
                resp = resposta_ajuda()

            send_whatsapp_message(user_id, resp)

        except Exception as e:
            print("Erro no webhook:", e)
        return 'EVENT_RECEIVED', 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)