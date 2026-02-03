import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time
from pypdf import PdfReader, PdfWriter

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Extrator UFES", layout="wide")
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("Erro Crítico: Chave de API não configurada.")
    st.stop()

genai.configure(api_key=api_key)

# --- ENGINE POR PÁGINA ---
def extract_page_data(page_bytes, page_number):
    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.0,
    }
    
    # CORREÇÃO CRÍTICA: O modelo correto é gemini-1.5-flash
    model = genai.GenerativeModel("gemini-2.5-flash", generation_config=generation_config)

    prompt = f"""
    Analise ESTA ÚNICA PÁGINA do relatório de protocolo (Página {page_number}).
    Extraia as linhas da tabela.
    
    ESTRUTURA VISUAL:
    - O 'Rastreio' (ex: AL989685414BR) e 'Processo' (ex: 004094/2025-73) podem estar visualmente misturados. Separe-os.
    - Ignore cabeçalhos repetidos (UFES, Data, Hora no topo da página).
    
    SAÍDA (JSON Array puro):
    [
      {{
        "rastreio": "Código Correios ou null",
        "processo": "Número Processo ou null",
        "data_envio": "DD/MM/AAAA",
        "destino": "Nome do Setor"
      }}
    ]
    """
    
    for attempt in range(3):
        try:
            response = model.generate_content([prompt, {"mime_type": "application/pdf", "data": page_bytes}])
            return json.loads(response.text)
        except Exception as e:
            time.sleep(1)
            continue
            
    return []

# --- INTERFACE ---
st.title("🛡️ Extrator de Protocolo")
st.markdown("**Status:** Processa página por página.")

uploaded_file = st.file_uploader("Arraste o PDF", type=["pdf"])

if uploaded_file:
    file_id = f"{uploaded_file.name}_{uploaded_file.size}"
    
    if "last_processed_file" not in st.session_state or st.session_state["last_processed_file"] != file_id:
        st.session_state["extracted_data"] = None
        st.session_state["last_processed_file"] = file_id

    if st.session_state["extracted_data"] is None:
        pdf_reader = PdfReader(uploaded_file)
        total_pages = len(pdf_reader.pages)
        
        st.info(f"Arquivo identificado com {total_pages} páginas. Iniciando extração...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        all_records = []
        
        for i, page in enumerate(pdf_reader.pages):
            page_num = i + 1
            status_text.text(f"Lendo página {page_num}/{total_pages}...")
            
            writer = PdfWriter()
            writer.add_page(page)
            
            with io.BytesIO() as page_buffer:
                writer.write(page_buffer)
                page_bytes = page_buffer.getvalue()
                
                page_data = extract_page_data(page_bytes, page_num)
                if page_data:
                    all_records.extend(page_data)
            
            progress_bar.progress(page_num / total_pages)
        
        status_text.empty()
        progress_bar.empty()
        
        if all_records:
            st.session_state["extracted_data"] = pd.DataFrame(all_records)
        else:
            st.error("Nenhum dado encontrado.")

    if st.session_state["extracted_data"] is not None:
        df = st.session_state["extracted_data"]
        
        st.success(f"Processamento concluído! {len(df)} registros encontrados.")
        st.dataframe(df, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Completo')
            
        st.download_button(
            label="📥 Baixar Excel Completo",
            data=output.getvalue(),
            file_name="Relatorio_Final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

# --- RODAPÉ AJUSTADO PARA MODO ESCURO ---
st.markdown("<br><br><br><br>", unsafe_allow_html=True)

footer_html = """
<style>
/* Rodapé fixo */
.fixed-footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #0E1117; /* Cor EXATA do fundo dark do Streamlit */
    color: #FAFAFA; /* Texto quase branco */
    border-top: 1px solid #262730;
