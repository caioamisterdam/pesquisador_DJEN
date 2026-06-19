import streamlit as st
import requests
from datetime import datetime, timedelta

# Configurações da página
st.set_page_config(page_title="Gerador de Links DJEN", page_icon="🔗", layout="centered")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

st.title("🔗 Gerador de Links Diretos - DJEN (TJSP)")
st.markdown("Selecione a data para obter o link oficial de download do Diário diretamente da API do PJe.")

# Interface de seleção de data
data_selecionada = st.date_input("Escolha a data do Diário:", value=datetime.now())

st.divider()

if st.button("🔍 Obter Link de Download", use_container_width=True):
    # Formata as datas para a API
    d_api = data_selecionada.strftime('%Y-%m-%d')
    d_br = data_selecionada.strftime('%d/%m/%Y')
    
    # URL da API do PJe para o caderno do TJSP
    url_api = f"https://comunicaapi.pje.jus.br/api/v1/caderno/TJSP/{d_api}/D"
    
    with st.spinner(f"Consultando API para o dia {d_br}..."):
        try:
            res = requests.get(url_api, headers=HEADERS, timeout=15)
            
            if res.status_code == 200:
                dados = res.json()
                url_zip = dados.get('url')
                
                if url_zip:
                    st.success(f"🎉 Link encontrado para o Diário de {d_br}!")
                    
                    # Caixa de destaque com o link clicável
                    st.markdown(f"""
                    <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #ff4b4b; margin-top: 10px;">
                        <h4 style="margin-top: 0;">📦 Arquivo do Diário (.zip)</h4>
                        <p>Clique no link abaixo para baixar direto do Tribunal:</p>
                        <a href="{url_zip}" target="_blank" style="font-weight: bold; color: #ff4b4b; word-break: break-all;">{url_zip}</a>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.caption("💡 Após baixar o arquivo acima, você pode jogá-lo na versão web do seu rastreador para cruzar com a lista de processos!")
                else:
                    st.warning(f"⚠️ A API respondeu, mas não encontrou nenhum link de Diário disponível para {d_br}. (Pode ser um final de semana, feriado ou o diário ainda não foi gerado).")
            
            elif res.status_code == 404: 
                st.error(f"❌ Diário de {d_br} não encontrado na API. Verifique se a data está correta ou se é um dia útil.")
            else:
                st.error(f"❌ Erro na API do Tribunal (Código {res.status_code}). Tente novamente mais tarde.")
                
        except requests.exceptions.Timeout:
            st.error("⏳ O servidor do Tribunal demorou muito para responder. Tente novamente.")
        except Exception as e:
            st.error(f"❌ Ocorreu um erro inesperado: {e}")
