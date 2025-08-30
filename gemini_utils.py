import google.generativeai as genai
import os
import json
import re

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash-latest')

def extrair_json(texto):
    """
    Esta função "limpa" a resposta da IA para extrair apenas o JSON.
    """
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            print(f"Erro: A string extraída não é um JSON válido: {json_str}")
            return None
    else:
        print(f"Erro: Nenhum JSON encontrado na resposta da IA: {texto}")
        return None

def interpretar_mensagem_gemini(mensagem_usuario):
    """
    Envia a mensagem do usuário para a IA e interpreta a resposta JSON.
    """
    # PROMPT MELHORADO: Instruções mais claras para a IA.
    prompt = f"""
    Sua tarefa é analisar a mensagem de um usuário para um bot de finanças e retornar SEMPRE uma resposta em formato JSON.

    1.  **Se a mensagem for um registro de gasto ou receita**:
        - Extraia as informações para as seguintes chaves: "intencao" (use "registrar_gasto" ou "registrar_receita"), "valor", "categoria", "data", "descricao", "recorrencia", "data_vencimento", "observacao".
        - Se uma informação não for encontrada, use o valor null.

    2.  **Se a mensagem for uma saudação** (como "oi", "olá", "bom dia"):
        - Retorne o JSON: {{"intencao": "saudacao", "valor": null, "categoria": null, "data": null, "descricao": null, "recorrencia": null, "data_vencimento": null, "observacao": null}}

    3.  **Se a mensagem não for nem um registro financeiro nem uma saudação**:
        - Retorne o JSON: {{"intencao": "desconhecido", "valor": null, "categoria": null, "data": null, "descricao": null, "recorrencia": null, "data_vencimento": null, "observacao": null}}

    NUNCA responda com texto normal ou explicações. Sua resposta deve ser APENAS o JSON.

    A mensagem do usuário é: "{mensagem_usuario}"
    """

    print("Enviando prompt para a IA...")
    response = model.generate_content(prompt)
    print(f"Resposta bruta da IA: {response.text}")

    dados_transacao = extrair_json(response.text)

    if dados_transacao:
        print(f"JSON extraído com sucesso: {dados_transacao}")
        return dados_transacao
    else:
        print("Falha ao extrair ou decodificar o JSON da resposta.")
        return None

