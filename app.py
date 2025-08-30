from flask import Flask, request
from db import get_db, create_tables
import re
from datetime import datetime, date, timedelta
import os
import requests
import csv

app = Flask(__name__)
create_tables()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN") or "SEU_ACCESS_TOKEN"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID") or "SEU_PHONE_ID"
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") or "TOKEN123"

def parse_transaction(text):
    text = text.lower()
    valor_match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:[.,]\d{1,2})?)', text)
    if not valor_match:
        return None

    valor_str = valor_match.group(1)
    valor_str = valor_str.replace('.', '').replace(',', '.')
    valor = float(valor_str)
    descricao = text

    # Data de lançamento
    data = datetime.now().date()

    # Recorrência
    recorrencia = None
    if "todo mês" in text or "mensal" in text:
        recorrencia = "mensal"
    elif "anual" in text or "por ano" in text:
        recorrencia = "anual"
    elif "semanal" in text or "toda semana" in text:
        recorrencia = "semanal"

    # Data de vencimento
    data_vencimento = None
    vencimento_match = re.search(r'vence(em)? (\d{1,2}/\d{1,2}/\d{4})', text)
    if vencimento_match:
        data_vencimento = datetime.strptime(vencimento_match.group(2), "%d/%m/%Y").date()

    # Tipo
    receita_palavras = ["recebi", "salario", "depósito", "deposito", "entrou", "ganhei", "receita"]
    despesa_palavras = ["paguei", "gastei", "comprei", "compra", "pago", "gastou", "gasto"]
    divida_palavras = ["divida", "dívida", "dívidas", "pagar", "emprestimo", "empréstimo", "boleto"]
    tipo = "despesa"
    for p in receita_palavras:
        if p in text:
            tipo = "receita"
    for p in despesa_palavras:
        if p in text:
            tipo = "despesa"
    for p in divida_palavras:
        if p in text:
            tipo = "divida"

    # Categoria
    cat_match = re.search(r'([a-zA-Zãõáéíóúçêôâûü ]+)\s+' + re.escape(valor_match.group(1)), text)
    categoria = cat_match.group(1).strip() if cat_match else ("receita" if tipo == "receita" else "outros")

    # Observação
    observacao = ""
    if recorrencia:
        observacao += f"Recorrente: {recorrencia}. "
    if data_vencimento:
        observacao += f"Vence em: {data_vencimento}. "

    return {
        "tipo": tipo,
        "categoria": categoria,
        "valor": valor,
        "data": str(data),
        "descricao": descricao,
        "recorrencia": recorrencia,
        "data_vencimento": str(data_vencimento) if data_vencimento else None,
        "status": "aberto" if tipo == "divida" else "pago",
        "observacao": observacao
    }

def consultar_dividas_a_vencer(user_id, dias=7):
    conn = get_db()
    c = conn.cursor()
    hoje = datetime.now().date()
    limite = hoje + timedelta(days=dias)
    c.execute(
        '''
        SELECT categoria, valor, data_vencimento FROM transacoes
        WHERE user_id=? AND tipo="divida" AND status="aberto" AND data_vencimento IS NOT NULL
        AND date(data_vencimento) BETWEEN ? AND ?
        ORDER BY data_vencimento ASC
        ''',
        (user_id, str(hoje), str(limite))
    )
    rows = c.fetchall()
    conn.close()
    return rows

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
            transacao["tipo"],
            transacao["categoria"],
            transacao["valor"],
            transacao["data"],
            transacao["descricao"],
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
    c.execute('SELECT categoria, SUM(valor) FROM transacoes WHERE user_id=? AND tipo="despesa" GROUP BY categoria', (user_id,))
    despesas_cat = c.fetchall()
    conn.close()
    return saldo, total_receita, total_despesa, despesas_cat

def listar_transacoes(user_id, limit=5, filtro_tipo=None, filtro_data=None):
    conn = get_db()
    c = conn.cursor()
    query = 'SELECT tipo, categoria, valor, data, descricao FROM transacoes WHERE user_id=?'
    params = [user_id]

    if filtro_tipo:
        query += ' AND tipo=?'
        params.append(filtro_tipo)
    if filtro_data:
        query += ' AND data=?'
        params.append(filtro_data)
    query += ' ORDER BY id DESC LIMIT ?'
    params.append(limit)
    c.execute(query, params)
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
        "• Consultar gastos do dia: gastos de hoje\n"
        "• E muito mais! Tente frases livres 😉"
    )

def consultar_orcamentos(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        '''
        SELECT categoria, valor_limite FROM orcamentos
        WHERE user_id=?
        ''',
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def registrar_orcamento(user_id, categoria, valor_limite):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        '''
        INSERT INTO orcamentos (user_id, categoria, valor_limite)
        VALUES (?, ?, ?)
        ''',
        (user_id, categoria, valor_limite)
    )
    conn.commit()
    conn.close()

def exportar_gastos_csv(user_id, periodo="mes"):
    hoje = datetime.now()
    mes = hoje.month
    ano = hoje.year
    conn = get_db()
    c = conn.cursor()
    if periodo == "mes":
        c.execute(
            '''
            SELECT data, categoria, valor, tipo, descricao FROM transacoes
            WHERE user_id=? AND strftime('%m', data)=? AND strftime('%Y', data)=?
            ''',
            (user_id, str(mes).zfill(2), str(ano))
        )
    else:
        c.execute(
            '''
            SELECT data, categoria, valor, tipo, descricao FROM transacoes
            WHERE user_id=?
            ''',
            (user_id,)
        )
    rows = c.fetchall()
    filename = f"extrato_{user_id}_{periodo}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Data", "Categoria", "Valor", "Tipo", "Descricao"])
        for row in rows:
            writer.writerow([row["data"], row["categoria"], row["valor"], row["tipo"], row["descricao"]])
    conn.close()
    return filename

def gerar_grafico_url(user_id, periodo="mes"):
    hoje = datetime.now()
    mes = hoje.month
    ano = hoje.year
    conn = get_db()
    c = conn.cursor()
    c.execute(
        '''
        SELECT categoria, SUM(valor) as total FROM transacoes
        WHERE user_id=? AND tipo="despesa" AND strftime('%m', data)=? AND strftime('%Y', data)=?
        GROUP BY categoria
        ''',
        (user_id, str(mes).zfill(2), str(ano))
    )
    rows = c.fetchall()
    conn.close()
    labels = [row["categoria"].title() for row in rows]
    values = [row["total"] for row in rows]
    chart_url = (
        "https://quickchart.io/chart?c={type:'pie',data:{labels:"
        f"{labels},datasets:[{{data:{values}}}]}}"
    )
    return chart_url

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

            today_str = str(date.today())
            resp = ""

            # Comandos inteligentes
            if re.match(r"^(comando|ajuda|menu|start)", message_text):
                resp = resposta_ajuda()

            elif "saldo" in message_text:
                saldo, total_receita, total_despesa, _ = resumo_usuario(user_id)
                resp = f"💰 Seu saldo: R${saldo:.2f}\nReceitas: R${total_receita:.2f}\nDespesas: R${total_despesa:.2f}"

            elif "extrato" in message_text or "ultimas" in message_text or "últimas" in message_text:
                transacoes = listar_transacoes(user_id, limit=10)
                if not transacoes:
                    resp = "Você ainda não registrou transações."
                else:
                    linhas = []
                    for t in transacoes:
                        emoji = "🟢" if t["tipo"]=="receita" else "🔴" if t["tipo"]=="despesa" else "🟡"
                        linhas.append(f"{emoji} {t['categoria'].title()}: R${t['valor']:.2f} em {t['data']}")
                    resp = "Últimos lançamentos:\n" + "\n".join(linhas)

            elif "orçamento" in message_text or "orcamento" in message_text:
                _, _, _, despesas_cat = resumo_usuario(user_id)
                if not despesas_cat:
                    resp = "Você ainda não tem despesas registradas este mês."
                else:
                    resp = "📝 Orçamento por categoria:\n" + "\n".join([f"• {cat}: R${valor:.2f}" for cat, valor in despesas_cat])

            elif "gastos de hoje" in message_text or "meus gastos de hoje" in message_text:
                transacoes = listar_transacoes(user_id, limit=20, filtro_tipo="despesa", filtro_data=today_str)
                if not transacoes:
                    resp = "Você não registrou nenhum gasto hoje."
                else:
                    linhas = []
                    total = 0
                    for t in transacoes:
                        total += t["valor"]
                        linhas.append(f"🔴 {t['categoria'].title()}: R${t['valor']:.2f}")
                    resp = "Seus gastos de hoje:\n" + "\n".join(linhas) + f"\nTotal: R${total:.2f}"

            elif "gastos" in message_text and ("ontem" in message_text or "de ontem" in message_text):
                yesterday = date.today() - timedelta(days=1)
                transacoes = listar_transacoes(user_id, limit=20, filtro_tipo="despesa", filtro_data=str(yesterday))
                if not transacoes:
                    resp = "Você não registrou nenhum gasto ontem."
                else:
                    linhas = []
                    total = 0
                    for t in transacoes:
                        total += t["valor"]
                        linhas.append(f"🔴 {t['categoria'].title()}: R${t['valor']:.2f}")
                    resp = "Seus gastos de ontem:\n" + "\n".join(linhas) + f"\nTotal: R${total:.2f}"

            elif "dívida" in message_text or "divida" in message_text or "vencem" in message_text:
                dividas = consultar_dividas_a_vencer(user_id)
                if not dividas:
                    resp = "✅ Nenhuma dívida a vencer nos próximos dias!"
                else:
                    linhas = []
                    for d in dividas:
                        linhas.append(f"⚠️ {d['categoria'].title()} | R${d['valor']:.2f} | Vence em {d['data_vencimento']}")
                    resp = "Suas dívidas a vencer:\n" + "\n".join(linhas)

            elif re.match(r".*\d", message_text):
                transacao = parse_transaction(message_text)
                if transacao:
                    registrar_transacao(user_id, transacao)
                    if transacao["tipo"] == "receita":
                        emoji = "🟢"
                        tipo_resp = "Receita registrada!"
                    elif transacao["tipo"] == "despesa":
                        emoji = "🔴"
                        tipo_resp = "Despesa registrada!"
                    elif transacao["tipo"] == "divida":
                        emoji = "⚠️"
                        tipo_resp = "Dívida registrada!"
                    else:
                        emoji = "🟡"
                        tipo_resp = "Lançamento registrado!"
                    resp = f"{emoji} {tipo_resp}\n{message_text.title()} | R${transacao['valor']:.2f} | {transacao['data']}"
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