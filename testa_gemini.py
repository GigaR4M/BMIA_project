# testa_gemini.py

import os
import google.generativeai as genai
from dotenv import load_dotenv

print("Iniciando teste de conexão com a API do Gemini...")

# Carrega as variáveis de ambiente
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    print("ERRO: Chave da API do Gemini não encontrada no arquivo .env")
else:
    try:
        # Configura a API
        genai.configure(api_key=GEMINI_API_KEY)

        # Usa um modelo qualquer para o teste
        model = genai.GenerativeModel('gemini-2.0-flash-lite')

        print("-> Tentando se comunicar com o Gemini...")

        # Usa a versão SÍNCRONA (não-async) para simplificar o teste
        response = model.generate_content("Isso é apenas um teste de conectividade.")

        print("\n-------------------------------------------")
        print("✅ SUCESSO! Comunicação com o Gemini está funcionando.")
        print("Resposta recebida:", response.text)
        print("-------------------------------------------\n")

    except Exception as e:
        print("\n-------------------------------------------")
        print("❌ FALHA! Ocorreu um erro ao se comunicar com o Gemini.")
        print(f"Tipo de Erro: {type(e).__name__}")
        print(f"Mensagem de Erro: {e}")
        print("-------------------------------------------\n")