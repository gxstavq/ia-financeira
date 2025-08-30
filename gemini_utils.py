import google.generativeai as genai
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Defina essa variável de ambiente no Render

def interpretar_mensagem_gemini(mensagem_usuario):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')

    prompt = (
        "Você é uma IA financeira. Interprete a frase e extraia:\n"
        "- intencao (registrar_gasto, registrar_receita, consultar_saldo, ajuda, etc.)\n"
        "- valor (float), categoria, data (YYYY-MM-DD), descricao, recorrencia, data_vencimento, observacao\n"
        "Responda apenas em JSON, sem texto extra. Por exemplo:\n"
        "{\n"
        "\"intencao\": \"registrar_receita\",\n"
        "\"valor\": 2250.00,\n"
        "\"categoria\": \"salário\",\n"
        "\"data\": \"2025-08-30\",\n"
        "\"descricao\": \"recebi meu salário no valor de 2250\"\n"
        "}\n"
        f"Frase: {mensagem_usuario}"
    )

    response = model.generate_content(prompt)
    return response.text