from flask import Flask, request
import os
import unicodedata
import re
import requests
import pickle

app = Flask(__name__)

# ==== CONFIGURAÇÕES DO META (TROQUE PELOS SEUS DADOS!) ====
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN") or "SEU_ACCESS_TOKEN_AQUI"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID") or "SEU_PHONE_NUMBER_ID_AQUI"
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") or "SEU_VERIFY_TOKEN_AQUI"
# ==========================================================

# ==== FUNÇÃO DE NORMALIZAÇÃO ====
def normalize_text(text):
    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

# ==== CARREGA O MODELO DE INTENÇÃO ====
intent_clf = pickle.load(open("intent_clf.pkl", "rb"))
intent_vectorizer = pickle.load(open("intent_vectorizer.pkl", "rb"))

def predict_intent(frase):
    X_teste = intent_vectorizer.transform([frase])
    return intent_clf.predict(X_teste)[0]

# ==== RESPOSTAS PADRÃO ====
RESPOSTA_GREETINGS = "Olá! Eu sou sua assistente financeira. Digite 'comandos' para ver o que eu faço! 😄"
RESPOSTA_DIVIDAS = "Aqui está o seu relatório de dívidas! (Exemplo: você pode implementar a lógica real depois)"
RESPOSTA_SALDO = "Seu saldo atual é: R$1234,56 (Exemplo: implemente a lógica real depois)"
RESPOSTA_DICA = "💡 Dica: Anote todos os seus gastos, até os pequenos! Isso ajuda muito na organização!"
RESPOSTA_ORCAMENTO = "Seu orçamento mensal está assim: ... (Exemplo)"

# ==== ENVIO DE MENSAGEM NO WHATSAPP ====
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

# ==== WEBHOOK ====
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return 'Erro de verificação', 403

    if request.method == 'POST':
        try:
            data = request.get_json()
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            if 'messages' not in value:
                return 'EVENT_RECEIVED', 200

            message_data = value['messages'][0]
            user_id = message_data['from']
            original_message_text = message_data['text']['body'].strip()
            message_text = normalize_text(original_message_text)

            # IA: previsão de intenção
            intent = predict_intent(message_text)

            if intent == "greetings":
                reply_message = RESPOSTA_GREETINGS
            elif intent == "dividas":
                reply_message = RESPOSTA_DIVIDAS
            elif intent == "saldo":
                reply_message = RESPOSTA_SALDO
            elif intent == "dica":
                reply_message = RESPOSTA_DICA
            elif intent == "orcamento":
                reply_message = RESPOSTA_ORCAMENTO
            else:
                reply_message = "Desculpe, não entendi! Digite 'comandos' para ver o que eu sei fazer. 😅"

            if reply_message:
                send_whatsapp_message(user_id, reply_message)
        except Exception as e:
            print("Erro no webhook:", e)

        return 'EVENT_RECEIVED', 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)