import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time
from pypdf import PdfReader, PdfWriter

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Extrator UFES (Modo Robusto)", layout="wide")
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
st.title("🛡️ Extrator de Protocolo (Modo Paginado)")
st.markdown("**Status:** Blindado contra erros de limite. Processa página por página.")

uploaded_file = st.file_uploader("Arraste o PDF", type=["pdf"])

if uploaded_file:
    # Ler o PDF original
    pdf_reader = PdfReader(uploaded_file)
    total_pages = len(pdf_reader.pages)
    
    st.info(f"Arquivo identificado com {total_pages} páginas. Iniciando extração sequencial...")
    
    # Barra de Progresso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    all_records = []
    
    # Loop de Processamento (A Mágica da Robustez)
    for i, page in enumerate(pdf_reader.pages):
        page_num = i + 1
        status_text.text(f"Processando página {page_num} de {total_pages}...")
        
        # Cria um mini-pdf apenas com essa página na memória
        writer = PdfWriter()
        writer.add_page(page)
        
        with io.BytesIO() as page_buffer:
            writer.write(page_buffer)
            page_bytes = page_buffer.getvalue()
            
            # Chama a IA para esta página específica
            page_data = extract_page_data(page_bytes, page_num)
            
            if page_data:
                all_records.extend(page_data)
        
        # Atualiza barra
        progress_bar.progress(page_num / total_pages)
    
    status_text.text("Processamento concluído!")
    
    if all_records:
        df = pd.DataFrame(all_records)
        
        st.success(f"Sucesso! {len(df)} registros extraídos de {total_pages} páginas.")
        st.dataframe(df, use_container_width=True)
        
        # Download
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
    else:
        st.error("Falha: Nenhum dado foi extraído. O PDF pode ser imagem (scanned) ou a API está instável.")
