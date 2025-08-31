from flask import Flask, request
from db import get_db, create_tables
import os
import requests
from datetime import date, datetime, timedelta

# Importa a nova função de interpretação
from gemini_utils import interpretar_mensagem_gemini

app = Flask(__name__)
# Garante que as tabelas sejam criadas na inicialização
create_tables()

# Configurações de ambiente para a API do WhatsApp
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# --- Funções do Banco de Dados ---

def registrar_transacao(user_id, transacao):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        '''
        INSERT INTO transacoes (user_id, tipo, categoria, valor, data, descricao, data_vencimento, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            user_id,
            transacao.get("tipo"),
            transacao.get("categoria"),
            transacao.get("valor"),
            transacao.get("data") or str(date.today()),
            transacao.get("descricao"),
            transacao.get("data_vencimento"),
            transacao.get("status")
        )
    )
    conn.commit()
    conn.close()

def marcar_divida_paga(user_id, descricao_divida):
    conn = get_db()
    c = conn.cursor()
    # Procura a dívida pendente mais recente com a descrição fornecida
    c.execute(
        """
        UPDATE transacoes 
        SET status = 'pago', data = ?
        WHERE user_id = ? AND status = 'pendente' AND descricao LIKE ?
        ORDER BY data_vencimento ASC LIMIT 1
        """,
        (str(date.today()), user_id, f'%{descricao_divida}%')
    )
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def consultar_dividas_pendentes(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT descricao, valor, data_vencimento FROM transacoes WHERE user_id = ? AND status = 'pendente' ORDER BY data_vencimento ASC",
        (user_id,)
    )
    dividas = c.fetchall()
    conn.close()
    return dividas

def resumo_usuario(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(valor),0) FROM transacoes WHERE user_id=? AND tipo='receita' AND status='pago'", (user_id,))
    total_receita = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(valor),0) FROM transacoes WHERE user_id=? AND tipo='despesa' AND status='pago'", (user_id,))
    total_despesa = c.fetchone()[0]
    saldo = total_receita - total_despesa
    conn.close()
    return saldo

def verificar_vencimentos_proximos(user_id, dias=7):
    conn = get_db()
    c = conn.cursor()
    data_limite = date.today() + timedelta(days=dias)
    c.execute(
        "SELECT descricao, valor, data_vencimento FROM transacoes WHERE user_id = ? AND status = 'pendente' AND data_vencimento <= ?",
        (user_id, data_limite.strftime('%Y-%m-%d'))
    )
    vencimentos = c.fetchall()
    conn.close()
    return vencimentos

# --- Comunicação com WhatsApp ---

def send_whatsapp_message(phone_number, message_text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message_text}}
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Mensagem enviada para {phone_number}: {message_text}")
    except Exception as e:
        print("Erro ao enviar mensagem:", e)

# --- Rota Principal (Webhook) ---

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == 'GET':
        token, challenge = request.args.get('hub.verify_token'), request.args.get('hub.challenge')
        if token == VERIFY_TOKEN:
            return challenge, 200
        return "Verificação falhou", 403

    if request.method == "POST":
        user_id = ""
        try:
            data = request.get_json()
            value = data['entry'][0]['changes'][0]['value']
            if 'messages' not in value: return 'EVENT_RECEIVED', 200

            message_data = value['messages'][0]
            user_id = message_data['from']
            message_text = message_data['text']['body'].strip()

            dados = interpretar_mensagem_gemini(message_text)
            if not dados:
                send_whatsapp_message(user_id, "Não consegui processar sua mensagem. Pode tentar de outra forma?")
                return 'EVENT_RECEIVED', 200

            resp = ""
            intencao = dados.get("intencao")

            if intencao in ["registrar_gasto", "registrar_receita", "registrar_divida"]:
                # Define o tipo com base na intenção
                dados["tipo"] = "despesa" if intencao == "registrar_gasto" else "receita" if intencao == "registrar_receita" else "divida"
                registrar_transacao(user_id, dados)
                resp = f"✅ {dados['tipo'].capitalize()} registrada: {dados.get('descricao')} - R${dados.get('valor'):.2f}"
            
            elif intencao == "marcar_pago":
                descricao = dados.get("descricao")
                if descricao and marcar_divida_paga(user_id, descricao):
                    resp = f"✅ Baixa de pagamento realizada para: {descricao}."
                else:
                    resp = f"Não encontrei uma dívida pendente com a descrição '{descricao}'. Tente ser mais específico."

            elif intencao == "consultar_dividas":
                dividas = consultar_dividas_pendentes(user_id)
                if not dividas:
                    resp = "Você não tem nenhuma dívida pendente. Ufa! 😅"
                else:
                    resp = "Suas dívidas pendentes:\n"
                    for desc, val, venc in dividas:
                        resp += f"\n• {desc} - R${val:.2f} (vence em {datetime.strptime(venc, '%Y-%m-%d').strftime('%d/%m')})"

            elif intencao == "verificar_vencimentos":
                vencimentos = verificar_vencimentos_proximos(user_id)
                if not vencimentos:
                    resp = "Nenhuma conta vencendo nos próximos 7 dias. 👍"
                else:
                    resp = "Atenção! Contas vencendo em breve:\n"
                    for desc, val, venc in vencimentos:
                         resp += f"\n• {desc} - R${val:.2f} (vence em {datetime.strptime(venc, '%Y-%m-%d').strftime('%d/%m')})"

            elif intencao == "consultar_saldo":
                saldo = resumo_usuario(user_id)
                resp = f"💰 Seu saldo atual (receitas - despesas pagas) é de R${saldo:.2f}"

            elif intencao == "saudacao":
                resp = "Olá! 👋 Sou seu assistente financeiro. Como posso ajudar?"

            else: # ajuda ou desconhecido
                resp = (
                    "Comandos que eu entendo:\n\n"
                    "• *Registrar*: 'gastei 50 no açaí', 'salário de 2000', 'conta de luz 150 vence dia 25'\n"
                    "• *Pagar*: 'paguei a conta de luz'\n"
                    "• *Consultar*: 'saldo', 'minhas dívidas', 'verificar contas'"
                )

            send_whatsapp_message(user_id, resp)

        except Exception as e:
            print(f"Erro geral no webhook: {e}")
            if user_id: send_whatsapp_message(user_id, "😕 Ocorreu um erro. Já estou verificando o que aconteceu.")
        
        return 'EVENT_RECEIVED', 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

