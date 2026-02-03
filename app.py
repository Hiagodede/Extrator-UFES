import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

# --- CONFIGURAÇÃO E SEGURANÇA ---
st.set_page_config(page_title="Extrator UFES", layout="wide")

# Recupera a chave dos Segredos do Streamlit (Ambiente de Produção)
# Ou usa uma variável local se estiver rodando na sua máquina (fallback)
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("Erro Crítico: Chave de API não configurada nos secrets.")
    st.stop()

genai.configure(api_key=api_key)

# --- ENGINE DE EXTRAÇÃO ---
def extract_data_from_pdf(file_bytes):
    # Configuração explícita para maximizar a saída
    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.1,       # Reduz criatividade para evitar alucinação
        "max_output_tokens": 8192 # AUMENTADO: Permite respostas longas para PDFs grandes
    }

    # Tente usar o modelo mais recente e estável
    model = genai.GenerativeModel(
        "gemini-1.5-flash", # Se der erro 404 de novo, use "gemini-1.5-flash-latest"
        generation_config=generation_config
    )

    prompt = """
    Você é um parser de dados especialista em relatórios governamentais (SIPAC).
    Analise o PDF anexo. O layout visual é tabular mas inconsistente.
    
    OBJETIVO: Extrair TODOS os registros da tabela, sem pular nenhum.
    
    SAÍDA OBRIGATÓRIA (JSON Array):
    [
      {
        "rastreio": "Código dos correios (XX123456789BR) ou null",
        "processo": "Número do processo (000000/0000-00) ou null",
        "data_envio": "Data DD/MM/AAAA",
        "destino": "Nome do setor"
      }
    ]
    """

    try:
        response = model.generate_content(
            [prompt, {"mime_type": "application/pdf", "data": file_bytes}]
        )
        
        # Tratamento de erro caso a resposta venha vazia ou cortada
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            # Se o JSON estiver quebrado, mostramos o erro no log do Streamlit mas não quebramos o app
            st.error(f"Erro de Parse JSON: A IA pode ter cortado a resposta. Detalhe: {e}")
            # Retorna lista vazia para não travar a tela
            return []
            
    except Exception as e:
        st.error(f"Falha na inferência da IA: {e}")
        return []

# --- INTERFACE (FRONT-END) ---
st.title("📄 Extrator de Protocolo UFES")
st.markdown("**Instruções:** Faça upload do PDF gerado pelo sistema. A IA vai normalizar a tabela.")

uploaded_file = st.file_uploader("Arraste o PDF aqui", type=["pdf"])

if uploaded_file:
    with st.spinner('Processando documento via Gemini 2.5 Flash...'):
        bytes_data = uploaded_file.getvalue()
        data = extract_data_from_pdf(bytes_data)
        
        if data:
            df = pd.read_json(json.dumps(data))
            
            # Exibição de Métricas
            col1, col2 = st.columns(2)
            col1.metric("Registros Extraídos", len(df))
            col1.info("Verifique se o total bate com o final do PDF.")
            
            # Preview da Tabela
            st.dataframe(df, use_container_width=True)
            
            # Engine de Download (Excel Nativo)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Extracao_IA')
                # Ajuste automático de colunas (perfumaria técnica)
                worksheet = writer.sheets['Extracao_IA']
                for i, col in enumerate(df.columns):
                    width = max(df[col].astype(str).map(len).max(), len(col))
                    worksheet.set_column(i, i, width + 2)
            
            st.download_button(
                label="📥 Baixar Excel Formatado",
                data=output.getvalue(),
                file_name="Relatorio_Processado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.warning("Nenhum dado estruturado foi encontrado.")
