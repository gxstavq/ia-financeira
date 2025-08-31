import google.generativeai as genai
import os
import re
import json
from datetime import date, timedelta

# Configuração da API Key do Gemini
# Lembre-se de configurar a variável de ambiente GOOGLE_API_KEY no Render
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

def extrair_json(texto):
    """Extrai um objeto JSON de uma string, mesmo que esteja dentro de blocos de código Markdown."""
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            print(f"Erro ao decodificar o JSON extraído: {json_str}")
            return None
    return None

def interpretar_mensagem_gemini(mensagem_usuario):
    """
    Usa a IA Gemini para interpretar a mensagem do usuário e extrair informações financeiras estruturadas.
    Agora entende uma gama muito maior de intenções e entidades.
    """
    hoje = date.today()
    amanha = hoje + timedelta(days=1)

    prompt = f"""
    Você é um assistente financeiro especialista. Sua tarefa é analisar a mensagem do usuário e extrair os dados em um formato JSON.

    O JSON deve ter a seguinte estrutura:
    {{
      "intencao": "...",           // Ação principal do usuário
      "valor": "...",             // Valor numérico da transação
      "categoria": "...",         // Categoria (Alimentação, Salário, Contas, etc.)
      "descricao": "...",         // Descrição do item
      "data": "...",              // Data da transação (formato AAAA-MM-DD)
      "data_vencimento": "...",   // Data de vencimento para dívidas (formato AAAA-MM-DD)
      "status": "..."             // 'pago' para despesas e receitas, 'pendente' para dívidas
    }}

    Possíveis intenções:
    - 'registrar_gasto': O usuário informa uma despesa. Ex: "gastei 50 no mercado". Status deve ser 'pago'.
    - 'registrar_receita': O usuário informa um ganho. Ex: "recebi 2000 de salário". Status deve ser 'pago'.
    - 'registrar_divida': O usuário informa uma conta a pagar. Ex: "conta de luz 150 vence dia 25". Status deve ser 'pendente'.
    - 'marcar_pago': O usuário informa que pagou uma dívida. Ex: "paguei a conta de luz".
    - 'consultar_saldo': O usuário quer saber o balanço. Ex: "qual meu saldo?".
    - 'consultar_dividas': O usuário quer ver as contas pendentes. Ex: "quais contas eu tenho?".
    - 'verificar_vencimentos': O usuário pede para verificar contas próximas do vencimento. Ex: "verificar contas a vencer".
    - 'saudacao': Uma saudação simples. Ex: "oi", "bom dia".
    - 'ajuda': O usuário pede ajuda.
    - 'desconhecido': Se não conseguir identificar a intenção.

    Regras importantes:
    1. Se não houver data explícita, use a data de hoje: {hoje.strftime('%Y-%m-%d')}.
    2. Para "amanhã", use: {amanha.strftime('%Y-%m-%d')}.
    3. Para dívidas, a 'data' é quando foi registrada (hoje) e 'data_vencimento' é a data informada.
    4. Para a intenção 'marcar_pago', a 'descricao' é a chave. Tente extrair o que foi pago (ex: "conta de luz").
    5. Se for uma saudação ou consulta, os outros campos podem ser nulos.

    Analise a mensagem a seguir:
    "{mensagem_usuario}"
    """
    try:
        print("Enviando prompt para a IA...")
        response = model.generate_content(prompt)
        print("Resposta bruta da IA:", response.text)
        
        dados_json = extrair_json(response.text)
        if dados_json:
            print("JSON extraído com sucesso:", dados_json)
            return dados_json
        else:
            print("Não foi possível extrair JSON da resposta.")
            return None
    except Exception as e:
        print(f"Erro ao chamar a API do Gemini: {e}")
        return None

