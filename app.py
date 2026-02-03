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
    # Configuração determinística
    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.0, # Zero criatividade, foco total em precisão
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
    
    # Retry logic simples (Tenta até 3 vezes se falhar)
    for attempt in range(3):
        try:
            response = model.generate_content([prompt, {"mime_type": "application/pdf", "data": page_bytes}])
            return json.loads(response.text)
        except Exception as e:
            time.sleep(1) # Espera 1seg antes de tentar de novo
            continue
            
    return [] # Retorna vazio se falhar 3 vezes

# --- INTERFACE ---
st.title("🛡️ Extrator de Protocolo ")
st.markdown("**Status:** Processa página por página.")

uploaded_file = st.file_uploader("Arraste o PDF", type=["pdf"])

# ... (todo o código anterior de imports e funções permanece igual) ...

if uploaded_file:
    # 1. Cria um ID único para o arquivo atual
    file_id = f"{uploaded_file.name}_{uploaded_file.size}"
    
    # 2. Verifica se mudou de arquivo (se o usuário subiu um novo)
    if "last_processed_file" not in st.session_state or st.session_state["last_processed_file"] != file_id:
        st.session_state["extracted_data"] = None
        st.session_state["last_processed_file"] = file_id

    # 3. Lógica de Processamento (Só roda se ainda não tiver dados na memória)
    if st.session_state["extracted_data"] is None:
        # Ler o PDF original
        pdf_reader = PdfReader(uploaded_file)
        total_pages = len(pdf_reader.pages)
        
        st.info(f"Arquivo identificado com {total_pages} páginas. Iniciando extração...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        all_records = []
        
        # Loop de Extração
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
        
        status_text.empty() # Limpa o texto de status
        progress_bar.empty() # Limpa a barra quando termina
        
        # SALVA NA MEMÓRIA (Aqui é o pulo do gato)
        if all_records:
            st.session_state["extracted_data"] = pd.DataFrame(all_records)
        else:
            st.error("Nenhum dado encontrado.")

    # 4. Exibição (Pega direto da memória, sem reprocessar)
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


st.markdown("<br><br><br><br>", unsafe_allow_html=True)

# --- RODAPÉ PERSONALIZADO (HTML/CSS) ---
footer_html = """
<style>
/* Estilo do container fixo no rodapé */
.fixed-footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #f1f3f6; /* Cor de fundo cinza suave */
    color: #31333F;
    border-top: 1px solid #d1d5db;
    padding: 10px 0;
    z-index: 999;
}

/* Centraliza o conteúdo dentro do rodapé */
.footer-content {
    display: flex;
    align-items: center;
    justify-content: center;
    max-width: 800px;
    margin: 0 auto;
    font-family: 'Source Sans Pro', sans-serif;
}

/* Estilo da Foto Circular */
.profile-img {
    width: 60px;
    height: 60px;
    border-radius: 50%; /* Faz o círculo */
    object-fit: cover;
    margin-right: 15px;
    border: 2px solid #0066cc; /* Borda azul sutil (opcional) */
}

/* Estilo do Texto */
.text-area {
    font-size: 14px;
    line-height: 1.4;
}

.text-area strong {
    font-size: 16px;
    color: #0e1117;
}

.social-links a {
    text-decoration: none;
    color: #0066cc;
    margin-right: 10px;
    font-weight: 600;
}
</style>

<div class="fixed-footer">
    <div class="footer-content">
        <img src="https://avatars.githubusercontent.com/u/SEU_ID_GITHUB?v=4" class="profile-img" alt="Foto de Perfil">
        
        <div class="text-area">
            <strong>Hiago do Carmo Lopes</strong><br>
            Diretor de Projetos de TI | Cinética Jr. (UFES)<br>
            <span class="social-links">
                <a href="mailto:hiago.lopes@edu.ufes.br" target="_blank">📧 Email</a>
                <a href="https://www.linkedin.com/in/hiago-lopes-201294341" target="_blank">🔗 LinkedIn</a>
            </span>
        </div>
    </div>
</div>
"""

st.markdown(footer_html, unsafe_allow_html=True)
