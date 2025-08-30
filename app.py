from flask import Flask, request
from db import get_db, create_tables
import os
import requests
import json
from datetime import date
from gemini_utils import interpretar_mensagem_gemini

app = Flask(__name__)
create_tables()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN") or "SEU_ACCESS_TOKEN"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID") or "SEU_PHONE_ID"
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") or "TOKEN123"

def registrar_transacao(user_id, transacao):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        '''
        INSERT INTO transacoes (user_id, tipo, categoria, valor, data, descricao, recorrencia, data_vencimento, status, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            user_id,
            transacao.get("tipo"),
            transacao.get("categoria"),
            transacao.get("valor"),
            transacao.get("data"),
            transacao.get("descricao"),
            transacao.get("recorrencia"),
            transacao.get("data_vencimento"),
            transacao.get("status", "pago"),
            transacao.get("observacao", "")
        )
    )
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
    conn.close()
    return saldo, total_receita, total_despesa

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
            message_text = message_data['text']['body'].strip()

            # Chama Gemini para interpretar a mensagem do usuário
            interpretacao = interpretar_mensagem_gemini(message_text)
            try:
                dados = json.loads(interpretacao)
            except Exception as e:
                print("Resposta do Gemini não é JSON válido:", interpretacao)
                send_whatsapp_message(user_id, "❌ Desculpe, não entendi sua mensagem. Tente reformular.")
                return 'EVENT_RECEIVED', 200

            resp = ""
            if dados.get("intencao") == "registrar_receita":
                transacao = {
                    "tipo": "receita",
                    "categoria": dados.get("categoria", "receita"),
                    "valor": dados.get("valor", 0),
                    "data": dados.get("data") or str(date.today()),
                    "descricao": dados.get("descricao") or message_text,
                    "recorrencia": dados.get("recorrencia"),
                    "data_vencimento": dados.get("data_vencimento"),
                    "status": "pago",
                    "observacao": dados.get("observacao", "")
                }
                registrar_transacao(user_id, transacao)
                resp = f"🟢 Receita registrada: {transacao['categoria']} | R${transacao['valor']:.2f} | {transacao['data']}"

            elif dados.get("intencao") == "registrar_gasto":
                transacao = {
                    "tipo": "despesa",
                    "categoria": dados.get("categoria", "despesa"),
                    "valor": dados.get("valor", 0),
                    "data": dados.get("data") or str(date.today()),
                    "descricao": dados.get("descricao") or message_text,
                    "recorrencia": dados.get("recorrencia"),
                    "data_vencimento": dados.get("data_vencimento"),
                    "status": "pago",
                    "observacao": dados.get("observacao", "")
                }
                registrar_transacao(user_id, transacao)
                resp = f"🔴 Despesa registrada: {transacao['categoria']} | R${transacao['valor']:.2f} | {transacao['data']}"

            elif dados.get("intencao") == "consultar_saldo":
                saldo, total_receita, total_despesa = resumo_usuario(user_id)
                resp = f"💰 Seu saldo: R${saldo:.2f}\nReceitas: R${total_receita:.2f}\nDespesas: R${total_despesa:.2f}"

            elif dados.get("intencao") == "ajuda":
                resp = (
                    "🤖 Eu sou sua IA financeira!\n\n"
                    "Você pode:\n"
                    "• Registrar gastos: mercado 120\n"
                    "• Registrar receitas: recebi salário 2000\n"
                    "• Consultar saldo: saldo\n"
                    "• Ver últimas transações: extrato\n"
                    "• Consultar orçamento do mês: orçamento\n"
                    "• Consultar gastos do dia: gastos de hoje\n"
                    "• E muito mais! Tente frases livres 😉"
                )
            else:
                resp = "❓ Não entendi sua mensagem. Tente novamente ou peça ajuda."

            send_whatsapp_message(user_id, resp)

        except Exception as e:
            print("Erro no webhook:", e)
        return 'EVENT_RECEIVED', 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)