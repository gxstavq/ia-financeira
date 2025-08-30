import google.generativeai as genai
import os
import json
import re  # Adicionado para "limpar" a resposta da IA

# Configuração da API Key (seu código já deve ter isso)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Seleção do modelo (recomendo usar um dos mais recentes)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

def extrair_json(texto):
    """
    Esta função "limpa" a resposta da IA.
    Ela remove os caracteres extras (```json) e extrai apenas o JSON.
    """
    # Procura por um texto que comece com '{' e termine com '}'
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            # Tenta converter o texto limpo para JSON
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
    # Este é o seu "cérebro", as instruções para a IA.
    prompt = f"""
    Analise a mensagem do usuário e extraia as informações em formato JSON.
    As chaves possíveis são: "intencao", "valor", "categoria", "data", "descricao", "recorrencia", "data_vencimento", "observacao".
    Se uma informação não for encontrada, use o valor null.
    A mensagem é: "{mensagem_usuario}"
    """

    print("Enviando prompt para a IA...")
    response = model.generate_content(prompt)
    print(f"Resposta bruta da IA: {response.text}")

    # AQUI ESTÁ A CORREÇÃO PRINCIPAL:
    # Usamos a função extrair_json para limpar a resposta antes de usar.
    dados_transacao = extrair_json(response.text)

    if dados_transacao:
        print(f"JSON extraído com sucesso: {dados_transacao}")
        return dados_transacao
    else:
        print("Falha ao extrair ou decodificar o JSON da resposta.")
        return None
