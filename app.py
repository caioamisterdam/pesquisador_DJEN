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
st.title("⚖️ Rastreador DJEN")
st.markdown("Baixe múltiplos diários e cruze dados de pautas.")

# --- PASSO 1: GERADOR EM MASSA ---
st.subheader("🔗 1. Obter os arquivos do Diário Oficial (Por Período)")
col_datas, col_botao = st.columns([1, 2])

with col_datas:
    data_inicio = st.date_input("Data Inicial:", value=datetime.now() - timedelta(days=5))
    data_fim = st.date_input("Data Final:", value=datetime.now())

with col_botao:
    st.markdown("**Download em Massa (Pula finais de semana automaticamente):**")
    
    # Monta a lógica de datas para passar para o JavaScript
    # Geramos a lista de datas úteis no Python para facilitar o JS
    lista_datas_js = []
    delta_dias = (data_fim - data_inicio).days + 1
    for i in range(delta_dias):
        dt = data_inicio + timedelta(days=i)
        if dt.weekday() < 5: # 0 a 4 são Segunda a Sexta
            lista_datas_js.append(dt.strftime('%Y-%m-%d'))
            
    datas_json = json.dumps(lista_datas_js)

    # JavaScript que percorre o array de datas e dispara os downloads corrigindo as barras duplas
    js_code = f"""
    <script>
    async function baixarMultiplosDiarios() {{
        let datas = {datas_json};
        if (datas.length === 0) {{
            alert('Nenhum dia útil selecionado no período.');
            return;
        }}
        
        if (datas.length > 10) {{
            if (!confirm('Você selecionou ' + datas.length + ' dias úteis. Isso abrirá muitas janelas de download de uma vez. Deseja continuar?')) {{
                return;
            }}
        }}

        for (let data_formatada of datas) {{
            let url_api = 'https://comunicaapi.pje.jus.br/api/v1/caderno/TJSP/' + data_formatada + '/D';
            try {{
                let response = await fetch(url_api);
                if (response.ok) {{
                    let resData = await response.json();
                    if (resData.url) {{
                        let urlCorrigida = resData.url.replace(/(?<!:|\\/)\\/\\//g, "/");
                        // Abre o download discreto em segundo plano
                        let a = document.createElement('a');
                        a.href = urlCorrigida;
                        a.target = '_blank';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    }}
                }}
            }} catch (err) {{
                console.log('Erro ao buscar data: ' + data_formatada);
            }}
            // Pequena pausa de 300ms entre as requisições para o navegador não travar
            await new Promise(r => setTimeout(r, 300));
        }}
    }}
    </script>
    <button onclick="baixarMultiplosDiarios()" style="background-color: #ff4b4b; color: white; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; width: 100%; font-size: 16px;">
        📥 Gerar e Baixar Diários do Período
    </button>
    """
    components.html(js_code, height=70)

st.divider()

# --- PASSO 2: CRUZAMENTO DE DADOS (SUPORTA MÚLTIPLOS ARQUIVOS) ---
st.subheader("📊 2. Cruzar os Dados")
c1, c2 = st.columns(2)

with c1:
    st.markdown("**Seus Processos Alvo**")
    arquivo_pauta = st.file_uploader("Suba a Pauta (PDF ou TXT)", type=["pdf", "txt"], key="pauta")
    texto_manual = st.text_area("Ou cole os processos aqui (um por linha):", height=150)

with c2:
    st.markdown("**Os Diários Oficiais Baixados**")
    # ATENÇÃO: Mudado para accept_multiple_files=True para o usuário arrastar TODOS os ZIPs baixados de uma vez só!
    arquivos_diarios = st.file_uploader("Suba TODOS os arquivos .zip baixados (pode selecionar vários)", type=["zip"], accept_multiple_files=True, key="diarios")

btn_processar = st.button("🚀 Cruzar Dados e Buscar Pautas", use_container_width=True)

# --- LÓGICA DE PROCESSAMENTO ---
if btn_processar:
    if (not arquivo_pauta and not texto_manual) or not arquivos_diarios:
        st.error("❌ Por favor, informe os processos e suba ao menos um arquivo .zip de Diário.")
    else:
        lista_pauta = extrair_pauta(arquivo_pauta, texto_manual)
        
        if not lista_pauta:
            st.warning("⚠️ Nenhum número de processo válido foi detectado.")
        else:
            alvos = {limpar_estrito(p): p for p in lista_pauta}
            frase_procurada_norm = normalizar_texto(FRASE_ALVO)
            resultados = []
            encontrados_set = set()
            
            st.info(f"📋 {len(lista_pauta)} processos identificados. Analisando os {len(arquivos_diarios)} arquivos enviados...")

            # Loop para ler CADA UM dos arquivos ZIP enviados pelo usuário
            for arquivo_zip_unico in arquivos_diarios:
                try:
                    with zipfile.ZipFile(io.BytesIO(arquivo_zip_unico.getvalue())) as z:
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
                                                'Diário Origem': arquivo_zip_unico.name,
                                                'Processo': num_orig,
                                                'Status': 'Pautado para Julgamento Virtual'
                                            })
                except:
                    st.error(f"⚠️ Alerta: Falha ao ler o arquivo {arquivo_zip_unico.name}. Verifique se o download dele terminou.")

            # --- EXIBIÇÃO ---
            st.divider()
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Localizados nos Diários Anexados", len(encontrados_set))
            col_m2.metric("Não Encontrados", len(lista_pauta) - len(encontrados_set))

            if resultados:
                df = pd.DataFrame(resultados)
                df.index = range(1, len(df) + 1)
                df.index.name = 'Nº'
                st.subheader("📊 Correspondências Encontradas")
                st.table(df)
                
                csv = df.to_csv(index=True, encoding='utf-8-sig', sep=';').encode('utf-8-sig')
                st.download_button("📥 Baixar Planilha Consolidade", data=csv, file_name="resultado_cruzamento_periodo.csv")
            
            faltantes = [p for limpo, p in alvos.items() if limpo not in encontrados_set]
            if faltantes:
                with st.expander("❌ Ver Processos Ausentes no Período Analisado"):
                    df_f = pd.DataFrame(sorted(faltantes), columns=["Processo Ausente"])
                    df_f.index = range(1, len(df_f) + 1)
                    st.table(df_f)
