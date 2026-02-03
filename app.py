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
    
    # Modelo Flash (Rápido e barato para loops)
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

# --- RODAPÉ ---
st.markdown("<br><br><br><br>", unsafe_allow_html=True)

footer_html = """
<style>
.fixed-footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #0E1117;
    color: #FAFAFA;
    border-top: 1px solid #262730;
    padding: 15px 0;
    z-index: 999;
}

.footer-content {
    display: flex;
    align-items: center;
    justify-content: center;
    max-width: 800px;
    margin: 0 auto;
    font-family: 'Source Sans Pro', sans-serif;
}

.profile-img {
    width: 75px;
    height: 75px;
    border-radius: 50%;
    object-fit: cover;
    margin-right: 20px;
    border: 2px solid #4da6ff;
}

.text-area {
    font-size: 15px;
    line-height: 1.5;
}

.text-area strong {
    font-size: 17px;
    color: #FFFFFF;
}

.social-links a {
    text-decoration: none;
    color: #4da6ff;
    margin-right: 15px;
    font-weight: 600;
}
</style>

<div class="fixed-footer">
    <div class="footer-content">
        <img src="https://media.licdn.com/dms/image/v2/D4D03AQGWQjoEnvH1Hw/profile-displayphoto-scale_200_200/B4DZwkLUOUJIAY-/0/1770133474521?e=1771459200&v=beta&t=GfeIu9hnn4ZlEd3ZevUOVdy0NnHz6lxp09wGbmaI9Vk" class="profile-img" alt="Foto de Perfil">
        
        <div class="text-area">
            <strong>Hiago do Carmo Lopes</strong><br>
            Diretor de Projetos de TI | Cinética Jr. (UFES)<br>
            <span class="social-links">
                <a href="mailto:hiago.lopes@edu.ufes.br" target="_blank">✉️ Email</a>
                <a href="https://www.linkedin.com/in/hiago-lopes-201294341" target="_blank">🔗 LinkedIn</a>
            </span>
        </div>
    </div>
</div>
"""

st.markdown(footer_html, unsafe_allow_html=True)
