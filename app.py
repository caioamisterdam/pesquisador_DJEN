import streamlit as st
import pdfplumber
import re
import zipfile
import json
import pandas as pd
import io
import unicodedata
import streamlit.components.v1 as components
from datetime import datetime, timedelta

st.set_page_config(page_title="Rastreador DJEN Público", page_icon="⚖️", layout="wide")

FRASE_ALVO = "PROCESSO PAUTADO PARA A SESSÃO DE JULGAMENTO VIRTUAL"

# --- FUNÇÕES DE LIMPEZA E NORMALIZAÇÃO ---
def remover_acentos(texto):
    if not texto: return ""
    return "".join([c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c)])

def normalizar_texto(texto):
    if not texto: return ""
    return " ".join(remover_acentos(texto).split()).upper()

def limpar_estrito(texto):
    return re.sub(r'\D', '', str(texto))

def extrair_pauta(uploaded_file, manual_input):
    processos = set()
    padrao_cnj = r'\d{7}\s*-\s*\d{2}\s*\.\s*\d{4}\s*\.\s*\d\s*\.\s*\d{2}\s*\.\s*\d{4}(?:[\/\-]\d+)?'
    
    if uploaded_file is not None:
        if uploaded_file.name.lower().endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                for pagina in pdf.pages:
                    texto = pagina.extract_text()
                    if texto:
                        for m in re.findall(padrao_cnj, texto): processos.add(re.sub(r'\s+', '', m))
        else:
            txt_content = uploaded_file.getvalue().decode("utf-8", errors='ignore')
            for m in re.findall(padrao_cnj, txt_content): processos.add(re.sub(r'\s+', '', m))
    
    if manual_input:
        for m in re.findall(padrao_cnj, manual_input): processos.add(re.sub(r'\s+', '', m))
            
    return sorted(list(processos))

# --- INTERFACE ---
st.title("⚖️ Rastreador DJEN - Versão Web Sem Bloqueios")
st.markdown("Cruze dados de pautas e diários de forma simples e sem erros de assinatura.")

# --- PASSO 1: GERADOR INTELIGENTE (RESOLVE O SIGNATURE DOES NOT MATCH) ---
st.subheader("🔗 1. Obter o arquivo do Diário Oficial")
col_data, col_botao = st.columns([1, 2])

with col_data:
    data_selecionada = st.date_input("Escolha a data do Diário:", value=datetime.now())
    data_formatada = data_selecionada.strftime('%Y-%m-%d')
    url_api_tribunal = f"https://comunicaapi.pje.jus.br/api/v1/caderno/TJSP/{data_formatada}/D"

with col_botao:
    st.markdown("**Baixar usando sua internet (Evita bloqueios e corrige erros do Tribunal):**")
    
    # Script em JavaScript que roda no navegador do usuário, busca o link e limpa as barras duplas
    js_code = f"""
    <script>
    async function baixarDiario() {{
        try {{
            let response = await fetch('{url_api_tribunal}');
            if (response.ok) {{
                let data = await response.json();
                if (data.url) {{
                    // O PULO DO GATO: Corrige as barras duplas que quebram a assinatura da Amazon
                    let urlCorrigida = data.url.replace(/(?<!:|\\/)\\/\\//g, "/");
                    window.open(urlCorrigida, '_blank');
                }} else {{
                    alert('Nenhum diário disponível para esta data.');
                }}
            }} else {{
                alert('Erro ao consultar o Tribunal. Código: ' + response.status);
            }}
        }} catch (err) {{
            // Se o fetch direto der bloqueio de CORS no navegador, criamos o link de contingência
            alert('Por segurança do navegador, abra o link da API manualmente e limpe as barras duplas do link gerado.');
            window.open('{url_api_tribunal}', '_blank');
        }}
    }}
    </script>
    <button onclick="baixarDiario()" style="background-color: #ff4b4b; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; width: 100%;">
        📥 Gerar e Baixar Diário (.zip) Oficial
    </button>
    """
    components.html(js_code, height=60)

st.divider()

# --- PASSO 2: CRUZAMENTO DE DADOS ---
st.subheader("📊 2. Cruzar os Dados")
c1, c2 = st.columns(2)

with c1:
    st.markdown("**Seus Processos Alvo**")
    arquivo_pauta = st.file_uploader("Suba a Pauta (PDF ou TXT)", type=["pdf", "txt"], key="pauta")
    texto_manual = st.text_area("Ou cole os processos aqui (um por linha):", height=150)

with c2:
    st.markdown("**O Diário Oficial Baixado**")
    arquivo_diario = st.file_uploader("Suba o arquivo .zip do Diário baixado no Passo 1", type=["zip"], key="diario")

btn_processar = st.button("🚀 Cruzar Dados e Buscar Pautas", use_container_width=True)

# --- LÓGICA DE PROCESSAMENTO ---
if btn_processar:
    if (not arquivo_pauta and not texto_manual) or not arquivo_diario:
        st.error("❌ Por favor, informe os processos e também suba o arquivo .zip do Diário.")
    else:
        lista_pauta = extrair_pauta(arquivo_pauta, texto_manual)
        
        if not lista_pauta:
            st.warning("⚠️ Nenhum número de processo válido foi detectado.")
        else:
            alvos = {limpar_estrito(p): p for p in lista_pauta}
            frase_procurada_norm = normalizar_texto(FRASE_ALVO)
            resultados = []
            encontrados_set = set()
            
            st.info(f"📋 {len(lista_pauta)} processos identificados. Analisando o arquivo enviado...")

            try:
                with zipfile.ZipFile(io.BytesIO(arquivo_diario.getvalue())) as z:
                    for nome_json in z.namelist():
                        corpo_raw = z.read(nome_json).decode('utf-8', errors='ignore')
                        corpo_limpo_num = limpar_estrito(corpo_raw)
                        
                        for num_limpo, num_orig in alvos.items():
                            if num_limpo in corpo_limpo_num:
                                texto_diario_norm = normalizar_texto(corpo_raw)
                                if frase_procurada_norm in texto_diario_norm:
                                    if num_limpo not in encontrados_set:
                                        encontrados_set.add(num_limpo)
                                        resultados.append({
                                            'Processo': num_orig,
                                            'Status': 'Pautado para Julgamento Virtual'
                                        })
            except Exception as e:
                st.error(f"❌ Erro ao ler o arquivo ZIP do Diário. Certifique-se de que o arquivo baixado não está corrompido.")

            # --- EXIBIÇÃO ---
            st.divider()
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Localizados no Diário Anexado", len(encontrados_set))
            col_m2.metric("Não Encontrados", len(lista_pauta) - len(encontrados_set))

            if resultados:
                df = pd.DataFrame(resultados)
                df.index = range(1, len(df) + 1)
                df.index.name = 'Nº'
                st.subheader("📊 Correspondências Encontradas")
                st.table(df)
                
                csv = df.to_csv(index=True, encoding='utf-8-sig', sep=';').encode('utf-8-sig')
                st.download_button("📥 Baixar Planilha", data=csv, file_name="resultado_cruzamento.csv")
            
            faltantes = [p for limpo, p in alvos.items() if limpo not in encontrados_set]
            if faltantes:
                with st.expander("❌ Ver Processos Ausentes neste Diário"):
                    df_f = pd.DataFrame(sorted(faltantes), columns=["Processo Ausente"])
                    df_f.index = range(1, len(df_f) + 1)
                    st.table(df_f)
