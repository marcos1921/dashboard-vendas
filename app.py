import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from html import escape
import os
import re
import unicodedata
import time

# --- CONFIGURAÇÃO DE PÁGINA ---
st.set_page_config(page_title="Dashboard Vendas", page_icon="⚡", layout="wide")

# --- CSS E RESPONSIVIDADE (MOBILE & DESKTOP) ---
st.markdown("""
    <style>
    /* Variáveis nativas garantem a leitura em qualquer tema (Dark/Light) */
    .main-title { color: #e51e25; font-weight: 900; font-size: 2.8rem; margin-bottom: 0px; text-transform: uppercase; }
    .sub-title { color: #f4ab13; font-size: 1.4rem; font-weight: 700; margin-top: -10px; margin-bottom: 30px; text-transform: uppercase; }
    
    [data-testid="stMetricValue"] { font-size: 2.2rem !important; font-weight: 900 !important; color: var(--text-color) !important; }
    [data-testid="stMetricLabel"] { font-size: 1rem !important; font-weight: 700 !important; color: var(--text-color) !important; opacity: 0.7; text-transform: uppercase; }
    
    /* Cabeçalhos Dinâmicos e Responsivos */
    .header-yellow { background: linear-gradient(90deg, #f4ab13 0%, #ffc547 100%); padding: 10px 20px; border-radius: 8px; color: #000000; font-weight: 900; font-size: 1.2rem; margin-top: 30px; margin-bottom: 20px; text-transform: uppercase; }
    .header-red { background: linear-gradient(90deg, #e51e25 0%, #ff4b4b 100%); padding: 10px 20px; border-radius: 8px; color: #ffffff; font-weight: 900; font-size: 1.2rem; margin-top: 30px; margin-bottom: 20px; text-transform: uppercase; }
    .header-green { background: linear-gradient(90deg, #21c354 0%, #28a745 100%); padding: 10px 20px; border-radius: 8px; color: #ffffff; font-weight: 900; font-size: 1.2rem; margin-top: 30px; margin-bottom: 20px; text-transform: uppercase; }
    
    .cat-destaque { background-color: var(--secondary-background-color); color: #f4ab13; padding: 6px 18px; border-radius: 20px; font-size: 1.1rem; font-weight: 800; display: inline-block; margin-bottom: 10px;}
    .cliente-titulo { color: var(--text-color); font-size: 2.2rem; font-weight: 900; margin-top: 0px; margin-bottom: 20px; text-transform: uppercase; border-bottom: 3px solid #e51e25; padding-bottom: 8px;}
    
    /* Inverte as cores da tabela para contrastar com o tema atual (Light/Dark) */
    [data-testid="stDataFrame"] { filter: invert(1) hue-rotate(180deg); }

    /* REGRAS DE MOBILE: Ajusta os tamanhos para telas menores que 768px (Celulares) */
    @media (max-width: 768px) {
        .main-title { font-size: 1.8rem; }
        .sub-title { font-size: 1.1rem; }
        .cliente-titulo { font-size: 1.5rem; }
        .header-yellow, .header-red, .header-green { font-size: 1rem; padding: 10px 15px; }
        [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

# MATRIZ DE CAMPANHAS OFICIAL
CAMPANHAS_MAP = {
    "1. INFINITO / TNT EXCLUSIVE": {"Rebates": "TNT Exclusive", "Camp1": "Conexão Suvinil", "Camp2": "", "Camp3": "", "Camp4": ""},
    "1.1 INFINITO": {"Rebates": "", "Camp1": "Conexão Suvinil", "Camp2": "Vamos Juntos - 1 vaga", "Camp3": "Stock Car - 1 vaga", "Camp4": "Big Fish"},
    "2. DIAMANTE": {"Rebates": "", "Camp1": "Conexão Suvinil", "Camp2": "Vamos juntos - 2 vaga", "Camp3": "Stock Car - 1 vaga", "Camp4": "Big Fish"},
    "3. PLATINUM": {"Rebates": "", "Camp1": "", "Camp2": "Vamos Juntos - 1 vaga", "Camp3": "Stock Car - 1 vaga", "Camp4": "Big Fish"},
    "4. SAFIRA": {"Rebates": "", "Camp1": "", "Camp2": "Vamos Juntos - 1 vaga", "Camp3": "Stock Car - 1 vaga", "Camp4": "Compre e Ganhe"},
    "5. ESMERALDA": {"Rebates": "", "Camp1": "", "Camp2": "Vamos Juntos - 1 vaga", "Camp3": "Stock Car - 1 vaga", "Camp4": "Compre e Ganhe"},
    "6. QUARTZO": {"Rebates": "", "Camp1": "", "Camp2": "Vamos Juntos - 1 vaga", "Camp3": "", "Camp4": "Compre e Ganhe"},
}

def chave_coluna(nome):
    texto = unicodedata.normalize("NFKD", str(nome))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = texto.replace("", "")
    return re.sub(r"\s+", " ", texto).strip().upper()

def normalizar_colunas(df, aliases):
    colunas_por_chave = {chave_coluna(coluna): coluna for coluna in df.columns}
    renomear = {}
    for nome_padrao, nomes_alternativos in aliases.items():
        for alternativa in [nome_padrao, *nomes_alternativos]:
            coluna_origem = colunas_por_chave.get(chave_coluna(alternativa))
            if coluna_origem:
                renomear[coluna_origem] = nome_padrao
                break
    return df.rename(columns=renomear)

def validar_colunas(df, obrigatorias, nome_base):
    ausentes = sorted(set(obrigatorias) - set(df.columns))
    if ausentes:
        raise ValueError(f"A base de {nome_base} não possui as colunas: {', '.join(ausentes)}.")

import base64
import streamlit.components.v1 as components

import extra_streamlit_components as stx

# Instancia o CookieManager diretamente sem cache para evitar o CachedWidgetWarning no Streamlit novo
cookie_manager = stx.CookieManager(key="cookie_manager")

# --- SISTEMA DE LOGIN DE VENDAS ---
# Usa a API nativa do Streamlit para ler o cookie instantaneamente na primeira execução
cookie_auth = None
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# 1. Tenta ler instantaneamente pela API nativa (Streamlit 1.35+)
if hasattr(st, "context") and hasattr(st.context, "cookies"):
    if st.context.cookies.get("auth_vendas") == "true":
        st.session_state["autenticado"] = True

# 2. Verifica pela URL (st.query_params) - a prova de falhas!
if hasattr(st, "query_params") and st.query_params.get("auth") == "true":
    st.session_state["autenticado"] = True

# 3. Fallback robusto via CookieManager do frontend
cookie_auth_stx = cookie_manager.get(cookie="auth_vendas")
if cookie_auth_stx == "true" and not st.session_state["autenticado"]:
    st.session_state["autenticado"] = True
    if hasattr(st, "query_params"):
        st.query_params["auth"] = "true"
    st.rerun()

# 4. Dispara a criação do cookie de forma segura (fora de containers que serão apagados)
if "set_auth_cookie" in st.session_state:
    cookie_manager.set("auth_vendas", "true", max_age=st.session_state["set_auth_cookie"])
    del st.session_state["set_auth_cookie"]

login_container = st.empty()

if not st.session_state["autenticado"]:
    with login_container.container():
        # Exibe a logo e o título perfeitamente centralizados via HTML/Base64
        img_html = ""
        if os.path.exists("logo.png"):
            with open("logo.png", "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            img_html = f'<img src="data:image/png;base64,{img_b64}" style="max-width: 280px; width: 100%; height: auto; display: block; margin: 0 auto;">'

        st.markdown(f'''
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-top: 5vh;">
                {img_html}
                <div class="main-title" style="text-align: center; margin-top: 25px; margin-bottom: 30px;">PORTAL DE VENDAS</div>
            </div>
        ''', unsafe_allow_html=True)
        
        col_log1, col_log2, col_log3 = st.columns([1, 1.5, 1])
        with col_log2:
            senha_digitada = st.text_input("Senha de acesso da equipe:", type="password")
            if st.button("Entrar", use_container_width=True):
                senha_equipe = st.secrets.get("senha_equipe", "vendas123") # Senha padrão se não configurada no secrets
                if senha_digitada == senha_equipe:
                    # Calcula quantos segundos faltam para a meia-noite no fuso horário do Brasil (UTC-3)
                    agora_br = datetime.utcnow() - timedelta(hours=3)
                    meia_noite_br = (agora_br + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    segundos_restantes = int((meia_noite_br - agora_br).total_seconds())

                    # Salva no session_state para que o cookie seja criado FORA do container no próximo rerun
                    st.session_state["set_auth_cookie"] = segundos_restantes
                    st.session_state["autenticado"] = True
                    if hasattr(st, "query_params"):
                        st.query_params["auth"] = "true"
                    st.rerun()
                else:
                    st.error("Senha incorreta!")
                    
    # Se ainda não estiver autenticado após clicar, para a execução.
    if not st.session_state["autenticado"]:
        st.stop()
    else:
        # Se autenticou, limpa o formulário de login para renderizar o resto do app
        login_container.empty()

# --- MENU LATERAL (SIDEBAR) ---
st.sidebar.image("logo.png", use_container_width=True)
aba_selecionada = st.sidebar.radio("Navegação", ["🔍 Consulta de Clientes", "⚙️ Área do Administrador"])

PASTA_DADOS = "dados_atuais"
if not os.path.exists(PASTA_DADOS): os.makedirs(PASTA_DADOS)
ARQ_VENDAS_SERVIDOR = os.path.join(PASTA_DADOS, "vendas.xlsx")
ARQ_RECEBER_SERVIDOR = os.path.join(PASTA_DADOS, "receber.csv")
ARQ_CAMPANHAS_SERVIDOR = os.path.join(PASTA_DADOS, "campanhas.xlsx")

# ==========================================
# ÁREA DO ADMINISTRADOR
# ==========================================
if aba_selecionada == "⚙️ Área do Administrador":
    st.markdown('<div class="main-title">ÁREA ADMINISTRATIVA</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Atualização Diária de Bases</div>', unsafe_allow_html=True)
    
    senha = st.text_input("Senha de administrador:", type="password")
    senha_admin = st.secrets.get("senha_admin")
    if not senha_admin:
        st.error("A senha administrativa não foi configurada no servidor.")
    elif senha == senha_admin:
        up_vendas = st.file_uploader("1. Substituir Base de Vendas (Excel)", type=["xlsx"])
        up_receber = st.file_uploader("2. Substituir Base de Receber (CSV)", type=["csv"])
        up_campanhas = st.file_uploader("3. Substituir Base de Campanhas (Excel)", type=["xlsx", "xls"])
        if st.button("💾 Salvar Novas Bases"):
            if up_vendas is not None or up_receber is not None or up_campanhas is not None:
                if up_vendas is not None:
                    with open(ARQ_VENDAS_SERVIDOR, "wb") as arquivo:
                        arquivo.write(up_vendas.getbuffer())
                if up_receber is not None:
                    with open(ARQ_RECEBER_SERVIDOR, "wb") as arquivo:
                        arquivo.write(up_receber.getbuffer())
                if up_campanhas is not None:
                    with open(ARQ_CAMPANHAS_SERVIDOR, "wb") as arquivo:
                        arquivo.write(up_campanhas.getbuffer())
                st.cache_data.clear()
                st.success("✅ Bases atualizadas com sucesso! Recarregando...")
                time.sleep(1.5)
                st.rerun()
            else:
                st.warning("⚠️ Faça o upload de pelo menos uma base antes de salvar.")
        
        st.markdown("---")
        with st.expander("🛠️ Modo Desenvolvedor: Ver Colunas Lidas", expanded=False):
            st.write("**Colunas Vendas:**", df_vendas.columns.tolist() if 'df_vendas' in locals() else "Nenhuma")
            st.write("**Colunas Receber:**", df_receber.columns.tolist() if 'df_receber' in locals() else "Nenhuma")
    elif senha:
        st.error("Senha incorreta.")

# ==========================================
# VISÃO DO VENDEDOR (CONSULTA)
# ==========================================
elif aba_selecionada == "🔍 Consulta de Clientes":
    st.markdown('<div class="main-title">DASHBOARD VENDAS</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">INTELIGÊNCIA COMERCIAL EM CAMPO</div>', unsafe_allow_html=True)

    # Tenta usar as bases do servidor (dados_atuais/). Se não existirem, pega qualquer XLSX e CSV na raiz.
    excel_local = [f for f in os.listdir('.') if f.endswith(('.xlsx', '.xls')) and f != 'app.py' and 'campanha' not in f.lower() and 'apuracao' not in f.lower() and 'apuração' not in f.lower()]
    csv_local = [f for f in os.listdir('.') if f.endswith('.csv')]
    campanhas_local = [f for f in os.listdir('.') if f.endswith(('.xlsx', '.xls')) and ('campanha' in f.lower() or 'apuracao' in f.lower() or 'apuração' in f.lower())]
    
    path_vendas = ARQ_VENDAS_SERVIDOR if os.path.exists(ARQ_VENDAS_SERVIDOR) else (excel_local[0] if excel_local else None)
    path_receber = ARQ_RECEBER_SERVIDOR if os.path.exists(ARQ_RECEBER_SERVIDOR) else (csv_local[0] if csv_local else None)
    path_campanhas = ARQ_CAMPANHAS_SERVIDOR if os.path.exists(ARQ_CAMPANHAS_SERVIDOR) else (campanhas_local[0] if campanhas_local else None)

    if not path_vendas or not path_receber:
        st.warning("⏳ **Atenção:** Arquivos não encontrados. Vá à **Área do Administrador** e faça o upload das duas bases.")
        st.stop()

    @st.cache_data(show_spinner="Processando inteligência comercial e corrigindo datas...")
    def carregar_dados_blindado(vendas_file, receber_file, mod_vendas, mod_receber):
        df_v = pd.read_excel(vendas_file, sheet_name=0)
        df_r = pd.read_csv(receber_file, encoding="latin1", sep=None, engine="python")

        df_v = normalizar_colunas(df_v, {
            "DATA EMISSÃO": ["DATA EMISSO", "DATA", "EMISSAO"],
            "CÓDIGO CLIENTE": ["CDIGO CLIENTE", "CODIGO", "COD CLIENTE"],
            "DESCRIÇÃO": ["DESCRIO", "PRODUTO", "DESCRICAO DO PRODUTO"],
            "MIX BASICO": ["MIX\nBASICO", "MIX BÁSICO", "MIX"],
            "QTD": ["QUANTIDADE", "QTDE", "VOLUMES", "QTD."],
            "HIERARQUIA AGRUPADA": ["hierarquia Agrupada", "HIERARQUIA AGRUPADA", "HIERARQUIA"],
            "SELF COLOR": ["SELF\nCOLOR", "SELF COLOR", "SELFCOLOR"],
        })
        df_r = normalizar_colunas(df_r, {
            "EMISSÃO": ["DATAEMISSÃO", "DATAEMISSAO", "EMISSO", "DATA EMISSAO", "DT EMISSAO", "EMISSAO", "DATA DE EMISSAO"],
            "VALOR EMABERTO": ["VALOREM ABERTO", "VALOR EM ABERTO", "VALOR ABERTO", "VLR EM ABERTO", "VLR ABERTO", "SALDO EM ABERTO", "SALDO ABERTO", "SALDO", "VALOR", "VLR", "VALOR A RECEBER", "TITULO ABERTO"],
            "CLIENTE": ["NOME CLIENTE", "RAZAO SOCIAL", "PARCEIRO", "SACADO", "NOME", "CLIENTE NOME"],
            "CÓDIGO CLIENTE": ["CÓDIGOCLIENTE", "CODIGO CLIENTE", "CODIGO", "COD CLIENTE", "CDIGO CLIENTE"],
            "DOCUMENTO": ["NOTA FISCAL", "NF", "NUMERO", "TITULO", "DOC", "N DOCUMENTO", "DOCUMENTO NUMERO"],
            "VENCIMENTO": ["DATAVENCIMENTO", "DATA VENCIMENTO", "DT VENCIMENTO", "VENC", "DATA DE VENCIMENTO", "VENCIMENTO TITULO"],
            "ATRASO": ["DIASATRASO", "DIAS DE ATRASO", "DIAS ATRASO", "DIAS"]
        })
        
        # Caso extremo: Se ainda não tiver a coluna, tenta encontrar qualquer coluna com 'ABERTO' ou 'SALDO' ou assume zero
        if "VALOR EMABERTO" not in df_r.columns:
            possiveis = [c for c in df_r.columns if "ABERTO" in str(c).upper() or "SALDO" in str(c).upper()]
            if possiveis:
                df_r.rename(columns={possiveis[0]: "VALOR EMABERTO"}, inplace=True)
            else:
                df_r["VALOR EMABERTO"] = "0"
                
        if "CLIENTE" not in df_r.columns:
            df_r["CLIENTE"] = "NÃO INFORMADO"
            
        if "VENCIMENTO" not in df_r.columns:
            df_r["VENCIMENTO"] = None
        
        from datetime import datetime
        def convert_date(val):
            if pd.isna(val):
                return pd.NaT
            if isinstance(val, (pd.Timestamp, datetime)):
                return pd.to_datetime(val)
            try:
                num = float(val)
                if 20000 < num < 70000:
                    return pd.to_datetime(num, unit="D", origin="1899-12-30")
            except (ValueError, TypeError):
                pass
            return pd.to_datetime(val, dayfirst=True, errors="coerce")

        df_v["DATA_DT"] = df_v["DATA EMISSÃO"].apply(convert_date)

        df_v["ANO"] = df_v["DATA_DT"].dt.year
        df_v["MES"] = df_v["DATA_DT"].dt.month
        df_v["Grupo de Cliente"] = df_v["Grupo de Cliente"].fillna(df_v["CLIENTE"]).astype(str).str.strip()
        df_v["FABRICANTE_LAVADO"] = df_v["FABRICANTE"].astype(str).str.strip().str.upper()
        
        df_v["VENDALITROS"] = pd.to_numeric(df_v["VENDALITROS"], errors="coerce").fillna(0)
        df_v["VALORTOTAL"] = pd.to_numeric(df_v["VALORTOTAL"], errors="coerce").fillna(0)
        
        valor_aberto = df_r["VALOR EMABERTO"].astype(str).str.strip()
        # Remove letras, R$ e espaços, mantendo apenas números, vírgula, ponto e sinal de menos
        valor_aberto = valor_aberto.str.replace(r"[^\d\,\.\-]", "", regex=True)
        valor_aberto = valor_aberto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        df_r["VALOR_NUM"] = pd.to_numeric(valor_aberto, errors="coerce").fillna(0)
        if "CÓDIGO CLIENTE" in df_r.columns:
            df_r["CODIGO_CLIENTE"] = df_r["CÓDIGO CLIENTE"].astype(str).str.extract(r"(\d+)", expand=False).str.zfill(7)
        else:
            df_r["CODIGO_CLIENTE"] = df_r["CLIENTE"].astype(str).str.extract(r"(\d+)", expand=False).str.zfill(7)
        df_r["VENCIMENTO_DT"] = pd.to_datetime(df_r["VENCIMENTO"], dayfirst=True, errors="coerce")
            
        return df_v, df_r

    @st.cache_data(show_spinner="Processando base de campanhas...")
    def carregar_campanhas(camp_file, mod_camp):
        if not camp_file or not os.path.exists(camp_file):
            return None
        try:
            # Lê sem cabeçalho para não quebrar com células mescladas do Excel
            df = pd.read_excel(camp_file, sheet_name=0, header=None)
            
            col_grupo = None
            col_cat = None
            col_pos = None
            col_pts = None
            col_classif = None
            
            # Varre as primeiras 5 linhas e todas as colunas para encontrar as posições exatas
            for row_idx in range(min(5, len(df))):
                for col_idx in range(len(df.columns)):
                    val = str(df.iloc[row_idx, col_idx]).strip().lower()
                    if val == "grupo de cliente": col_grupo = col_idx
                    elif "categor" in val: col_cat = col_idx
                    elif val in ["posição", "posicao"]: col_pos = col_idx
                    elif val == "total": col_pts = col_idx
                    elif "classifica" in val: col_classif = col_idx
                    
            if col_grupo is not None and col_pos is not None:
                df_clean = pd.DataFrame({
                    "Grupo de Cliente": df.iloc[:, col_grupo].astype(str),
                    "Categoria": df.iloc[:, col_cat].astype(str) if col_cat is not None else "",
                    "Posição": df.iloc[:, col_pos],
                    "Total pts": df.iloc[:, col_pts] if col_pts is not None else "",
                    "Classificação": df.iloc[:, col_classif] if col_classif is not None else ""
                })
                # Filtra valores inválidos da coluna de grupo
                df_clean = df_clean[~df_clean["Grupo de Cliente"].isin(["nan", "Grupo de Cliente", "Soma de VENDALITROS"])]
                return df_clean
            return None
        except Exception as e:
            print("Erro ao ler campanhas:", e)
            return None

    try:
        mod_v = os.path.getmtime(path_vendas)
        mod_r = os.path.getmtime(path_receber)
        df_vendas, df_receber = carregar_dados_blindado(path_vendas, path_receber, mod_v, mod_r)
        
        df_campanhas = None
        if path_campanhas:
            mod_c = os.path.getmtime(path_campanhas)
            df_campanhas = carregar_campanhas(path_campanhas, mod_c)
            
    except (ValueError, KeyError, Exception) as erro:
        print("ERROR IN CARREGAR_DADOS:", erro)
        st.error(f"Não foi possível carregar as bases: {erro}")
        st.stop()

    anos_disponiveis = df_vendas["ANO"].dropna().unique()
    ANO_ATUAL = int(max(anos_disponiveis)) if len(anos_disponiveis) > 0 else 2026
    ANO_ANTERIOR = ANO_ATUAL - 1
    
    max_dt_base = df_vendas["DATA_DT"].max()
    MES_ATUAL = int(max_dt_base.month) if pd.notna(max_dt_base) else datetime.now().month
    # HOJE travado na data real do calendário para análise financeira correta:
    HOJE = datetime.now()
    # --- FILTROS ---
    import streamlit.components.v1 as components
    # Injeta um script minúsculo para transformar o text_input num campo de "search" nativo do navegador, 
    # o que adiciona o botão de "X" automaticamente e fica muito mais profissional.
    components.html("""
        <script>
            const inputs = window.parent.document.querySelectorAll('input[type="text"]');
            inputs.forEach(input => {
                input.setAttribute('type', 'search');
                input.style.outline = 'none';
            });
        </script>
    """, height=0, width=0)

    termo_busca = st.sidebar.text_input("🔎 Nome ou código do cliente", placeholder="Ex.: 141428 ou Express").strip()
    cidades = sorted(df_vendas["CIDADE"].dropna().astype(str).str.strip().unique())
    cidade_sel = st.sidebar.selectbox("Cidade (opcional)", cidades, index=None, placeholder="Todas as cidades...")

    df_filt = df_vendas
    if termo_busca:
        import re
        # Remove caracteres especiais para busca burra (ex: "casa & cor" vira "casa cor")
        termo_clean = re.sub(r'[^a-zA-Z0-9]+', ' ', termo_busca).strip()
        termos = termo_clean.split()
        
        grupos = df_vendas["Grupo de Cliente"].fillna("").astype(str)
        clientes = df_vendas["CLIENTE"].fillna("").astype(str)
        codigos = pd.to_numeric(df_vendas["CÓDIGO CLIENTE"], errors="coerce")
        
        mascara_busca = pd.Series(True, index=df_vendas.index)
        for t in termos:
            # Para cada palavra, verifica se existe no grupo, cliente ou código
            mascara_termo = (
                grupos.str.contains(t, case=False, regex=False) | 
                clientes.str.contains(t, case=False, regex=False)
            )
            if t.isdigit():
                mascara_termo |= codigos.eq(int(t))
            mascara_busca &= mascara_termo

        df_filt = df_filt[mascara_busca]

    if cidade_sel:
        df_filt = df_filt[df_filt["CIDADE"].astype(str).str.strip() == cidade_sel]

    grupos_disponiveis = sorted(df_filt["Grupo de Cliente"].dropna().unique())
    if not grupos_disponiveis:
        st.error("Nenhum cliente encontrado com os filtros informados.")
        st.stop()

    grupo_escolhido = st.sidebar.selectbox("Selecione a Rede (Grupo)", grupos_disponiveis, index=None, placeholder="Selecione uma rede...")
    
    if grupo_escolhido:
        st.session_state["ultimo_grupo"] = grupo_escolhido

    grupo_ativo = st.session_state.get("ultimo_grupo")
    
    # Se o grupo ativo não existe mais nos filtros atuais (ou seja, o usuário pesquisou outra coisa)
    if grupo_ativo not in grupos_disponiveis and (termo_busca or cidade_sel):
        grupo_ativo = grupos_disponiveis[0]
        st.session_state["ultimo_grupo"] = grupo_ativo

    if grupo_ativo and grupo_ativo not in df_vendas["Grupo de Cliente"].values:
        grupo_ativo = None
    
    if not grupo_ativo:
        st.info("👈 Selecione uma rede no menu lateral para visualizar o dashboard.")
        st.stop()
        
    # Filtra as lojas que pertencem a este grupo_ativo (usando df_vendas, não df_filt, para mostrar todas da rede)
    lojas_do_grupo = sorted(df_vendas[df_vendas["Grupo de Cliente"] == grupo_ativo]["CLIENTE"].dropna().unique())
    
    # Auto-selecionar loja se a busca filtrou exatamente UMA loja específica para esse grupo
    lojas_filtradas = sorted(df_filt[df_filt["Grupo de Cliente"] == grupo_ativo]["CLIENTE"].dropna().unique())
    loja_default_idx = None
    if termo_busca and len(lojas_filtradas) == 1:
        unica_loja = lojas_filtradas[0]
        if unica_loja in lojas_do_grupo:
            loja_default_idx = lojas_do_grupo.index(unica_loja)

    loja_escolhida = st.sidebar.selectbox("Filtrar por Loja (opcional)", lojas_do_grupo, index=loja_default_idx, placeholder="Todas as lojas da rede...")
    
    st.sidebar.markdown("---")
    
    if path_vendas and os.path.exists(path_vendas):
        # Lê a data e hora no servidor
        timestamp_upload = os.path.getmtime(path_vendas)
        
        # Converte a data e subtrai 3 horas para ajustar ao fuso do Brasil (UTC-3)
        data_upload = datetime.fromtimestamp(timestamp_upload) - timedelta(hours=3)
        
        # Formata para o padrão brasileiro (Ex: 09/09/2026 às 14:30)
        data_formatada = data_upload.strftime('%d/%m/%Y às %H:%M')
        
        st.sidebar.info(f"⏳ **Último upload da base:** {data_formatada}")
        
    # --- PROCESSAMENTO DO GRUPO ---
    if loja_escolhida:
        df_grupo = df_vendas[df_vendas["CLIENTE"] == loja_escolhida]
    else:
        df_grupo = df_vendas[df_vendas["Grupo de Cliente"] == grupo_ativo]
        
    grupo_da_loja = grupo_ativo
    
    dia_ano_max = max_dt_base.dayofyear if pd.notna(max_dt_base) else 365
    df_atual = df_grupo[(df_grupo["ANO"] == ANO_ATUAL) & (df_grupo["DATA_DT"].dt.dayofyear <= dia_ano_max)]
    df_anterior = df_grupo[(df_grupo["ANO"] == ANO_ANTERIOR) & (df_grupo["DATA_DT"].dt.dayofyear <= dia_ano_max)]

    info_grupo = df_grupo.iloc[0]
    cat_dashboard = str(info_grupo.get("CATEGORIA", "Sem Categoria")).strip()
    
    # --- IDENTIFICAÇÃO DA CATEGORIA CORRETA ---
    # A regra é: A categoria que vale é a da Planilha de Campanhas.
    chave_final = cat_dashboard # Default
    cat_atual = cat_dashboard
    
    if 'df_campanhas' in locals() and df_campanhas is not None and not df_campanhas.empty and "Categoria" in df_campanhas.columns:
        # A campanha sempre é avaliada pelo 'Grupo de Cliente', mesmo se estivermos na visão por Loja
        grupo_da_loja = df_grupo["Grupo de Cliente"].iloc[0] if not df_grupo.empty else grupo_ativo
        nome_busca = str(grupo_da_loja).strip().upper()
        grupos_camp = df_campanhas["Grupo de Cliente"].astype(str).str.strip().str.upper()
        
        # 1. Tenta achar o cliente pelo nome exato
        cliente_na_campanha = df_campanhas[grupos_camp == nome_busca]
        
        # 2. Se falhar, tenta match parcial inteligente (ex: "COMERCIAL TINTAS" contido em "COMERCIAL TINTAS LTDA-ME")
        if cliente_na_campanha.empty:
            mascara_parcial = grupos_camp.apply(lambda x: x in nome_busca or nome_busca in x)
            cliente_na_campanha = df_campanhas[mascara_parcial]
            
        if not cliente_na_campanha.empty:
            cat_atual = str(cliente_na_campanha.iloc[0]["Categoria"]).strip().upper()
            import re
            # Procura a chave correspondente no CAMPANHAS_MAP (ex: "INFINITO" -> "1.1 INFINITO")
            for k in CAMPANHAS_MAP.keys():
                k_clean = re.sub(r'^\d+(\.\d+)?\s*', '', k).strip().upper()
                if cat_atual == k_clean or cat_atual in k.upper():
                    # Evita que "INFINITO" puro puxe "INFINITO / TNT EXCLUSIVE"
                    if cat_atual == "INFINITO" and "TNT" in k.upper():
                        continue
                    chave_final = k
                    break

    titulo_tela = loja_escolhida if loja_escolhida else grupo_ativo
    st.markdown(f'<div class="cat-destaque">🏆 Categoria: {escape(cat_atual)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="cliente-titulo">{escape(titulo_tela)}</div>', unsafe_allow_html=True)

    # ==========================================
    # 1. SUVINIL + SHERWIN
    # ==========================================
    st.markdown(f'<div class="header-yellow">PERFORMANCE PRINCIPAL (SUVINIL + SHERWIN) - ACUMULADO JAN A {MES_ATUAL:02d}/{ANO_ATUAL}</div>', unsafe_allow_html=True)
    
    fab_principais = df_grupo[df_grupo["FABRICANTE_LAVADO"].str.contains("SUVINIL|SHERWIN", na=False)]
    L_atual = df_atual[df_atual["FABRICANTE_LAVADO"].str.contains("SUVINIL|SHERWIN", na=False)]["VENDALITROS"].sum()
    L_ant = df_anterior[df_anterior["FABRICANTE_LAVADO"].str.contains("SUVINIL|SHERWIN", na=False)]["VENDALITROS"].sum()

    ultima_compra = fab_principais["DATA_DT"].max()
    data_ref_inatividade = max_dt_base if pd.notna(max_dt_base) else HOJE
    dias_inativo = (data_ref_inatividade - ultima_compra).days if pd.notna(ultima_compra) else 999
    meses_inativo = dias_inativo // 30
    status_inat = "N/A" if pd.isna(ultima_compra) else (f"⚠️ INATIVO ({meses_inativo} meses)" if meses_inativo >= 3 else f"✅ Ativo")

    if L_ant > 0:
        cresc = ((L_atual - L_ant) / L_ant) * 100
        txt_cresc = f"{cresc:.1f}% (Ano Ant: {L_ant:,.0f} L)"
    else:
        txt_cresc = "Sem base no ano anterior"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Positivação", "🟢 SIM" if L_atual > 0 else "🔴 NÃO")
    c2.metric(f"Venda Litros ({ANO_ATUAL})", f"{L_atual:,.0f} L".replace(',', '.'), txt_cresc)
    
    delta_pulv = "Meta Atingida" if L_atual >= 50 else f"-{50 - L_atual:.1f} L (Abaixo da Meta)"
    c3.metric("Pulverização", "META OK" if L_atual >= 50 else f"Faltam {50 - L_atual:,.0f} L".replace(',', '.'), delta_pulv)
    
    c4.metric("Status Ciclo", status_inat, "Tempo de recompra", delta_color="off")

    # ==========================================
    # 2. MIX BÁSICO & HIERARQUIA DE PRODUTOS
    # ==========================================
    st.markdown('<div class="header-yellow">MIX BÁSICO & HIERARQUIA DE PRODUTOS</div>', unsafe_allow_html=True)
    
    cli_suv_sher = df_atual[df_atual["FABRICANTE_LAVADO"].str.contains("SUVINIL|SHERWIN", na=False)]
    
    vol_alvenaria = cli_suv_sher[cli_suv_sher["MIX BASICO"].astype(str).str.upper().str.contains("ALVENARIA", na=False)]["VENDALITROS"].sum()
    vol_complementos = cli_suv_sher[cli_suv_sher["MIX BASICO"].astype(str).str.upper().str.contains("COMPLEMENTO", na=False)]["VENDALITROS"].sum()
    vol_esmaltes = cli_suv_sher[cli_suv_sher["MIX BASICO"].astype(str).str.upper().str.contains("ESM", na=False)]["VENDALITROS"].sum()
    
    META_MIX = 14.4
    
    if (vol_alvenaria >= META_MIX) and (vol_complementos >= META_MIX) and (vol_esmaltes >= META_MIX):
        st.markdown('<div style="background-color: rgba(33, 195, 84, 0.15); border-left: 5px solid #21c354; padding: 15px; border-radius: 5px; color: var(--text-color); font-weight: 600; margin-bottom: 20px;">🏆 Mix Básico Completo! O cliente positivou todas as categorias.</div>', unsafe_allow_html=True)
    else:
        def format_falta(vol):
            if vol < META_MIX:
                falta = META_MIX - vol
                return f"<span style='color: #ff9999; font-weight: 400; font-size: 0.95rem;'>- Faltam {falta:.1f} L</span>".replace('.', ',')
            return ""

        st_alv = f"<div style='color: {'#e51e25; font-weight: 900;' if vol_alvenaria < META_MIX else 'var(--text-color)'}; margin-bottom: 8px; font-size: 1.05rem;'>{'❌' if vol_alvenaria < META_MIX else '✅'} Alvenaria {format_falta(vol_alvenaria)}</div>"
        st_comp = f"<div style='color: {'#e51e25; font-weight: 900;' if vol_complementos < META_MIX else 'var(--text-color)'}; margin-bottom: 8px; font-size: 1.05rem;'>{'❌' if vol_complementos < META_MIX else '✅'} Complementos {format_falta(vol_complementos)}</div>"
        st_esm = f"<div style='color: {'#e51e25; font-weight: 900;' if vol_esmaltes < META_MIX else 'var(--text-color)'}; margin-bottom: 8px; font-size: 1.05rem;'>{'❌' if vol_esmaltes < META_MIX else '✅'} Esmaltes e Vernizes {format_falta(vol_esmaltes)}</div>"
        
        st.markdown(
            f"""
            <div style="background-color: var(--secondary-background-color); border-left: 5px solid #e51e25; padding: 15px 20px; border-radius: 5px; margin-bottom: 20px;">
                <p style="font-weight: 900; font-size: 1.1rem; color: var(--text-color); margin-top: 0; margin-bottom: 15px;">⚠️ FOCO DE VENDA: POSITIVAR MIX BÁSICO</p>
                {st_alv}
                {st_comp}
                {st_esm}
            </div>
            """, 
            unsafe_allow_html=True
        )

    todas_hierarquias = df_vendas[df_vendas["FABRICANTE_LAVADO"].str.contains("SUVINIL|SHERWIN", na=False)]["HIERARQUIA AGRUPADA"].dropna().astype(str).unique()
    hierarquias_compradas = cli_suv_sher["HIERARQUIA AGRUPADA"].dropna().astype(str).unique()
    hierarquias_faltantes = [h for h in todas_hierarquias if h not in hierarquias_compradas]
    
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.markdown(f"**✅ Linhas Já Compradas ({len(hierarquias_compradas)}):**")
        st.dataframe(pd.DataFrame(hierarquias_compradas, columns=["PRODUTOS COMPRADOS"]), hide_index=True, use_container_width=True, height=200)
            
    with col_h2:
        st.markdown(f"**❌ Oportunidades - Não Compradas ({len(hierarquias_faltantes)}):**")
        st.dataframe(pd.DataFrame(hierarquias_faltantes, columns=["AÇÕES DE VENDA (FALTANTES)"]), hide_index=True, use_container_width=True, height=200)

    # ==========================================
    # 3. OUTROS FORNECEDORES
    # ==========================================
    st.markdown('<div class="header-yellow">PERFORMANCE DE MARCAS COMPLEMENTARES</div>', unsafe_allow_html=True)
    
    col_f0, col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(6)
    
    v_suv_at = df_atual[df_atual["FABRICANTE_LAVADO"].str.contains("SUVINIL", na=False)]["VENDALITROS"].sum()
    v_suv_ant = df_anterior[df_anterior["FABRICANTE_LAVADO"].str.contains("SUVINIL", na=False)]["VENDALITROS"].sum()
    dif_suv = f"{(((v_suv_at - v_suv_ant) / v_suv_ant) * 100):+.1f}%" if v_suv_ant > 0 else "Sem base"
    with col_f0:
        st.metric("Suvinil (Litros)", f"{v_suv_at:,.0f} L".replace(',', '.') if v_suv_at > 0 else "-", dif_suv if v_suv_at > 0 else None)

    v_amais_at = df_atual[df_atual["FABRICANTE_LAVADO"].str.contains("AMAIS", na=False)]["VENDALITROS"].sum()
    v_amais_ant = df_anterior[df_anterior["FABRICANTE_LAVADO"].str.contains("AMAIS", na=False)]["VENDALITROS"].sum()
    dif_amais = f"{(((v_amais_at - v_amais_ant) / v_amais_ant) * 100):+.1f}%" if v_amais_ant > 0 else "Sem base"
    with col_f1:
        st.metric("Amais (Litros)", f"{v_amais_at:,.0f} L".replace(',', '.') if v_amais_at > 0 else "-", dif_amais if v_amais_at > 0 else None)

    v_farb_at = df_atual[df_atual["FABRICANTE_LAVADO"].str.contains("FARBEN", na=False)]["VENDALITROS"].sum()
    v_farb_ant = df_anterior[df_anterior["FABRICANTE_LAVADO"].str.contains("FARBEN", na=False)]["VENDALITROS"].sum()
    dif_farb = f"{(((v_farb_at - v_farb_ant) / v_farb_ant) * 100):+.1f}%" if v_farb_ant > 0 else "Sem base"
    with col_f2:
        st.metric("Farben (Litros)", f"{v_farb_at:,.0f} L".replace(',', '.') if v_farb_at > 0 else "-", dif_farb if v_farb_at > 0 else None)

    v_self_at = 0
    v_self_ant = 0
    if "SELF COLOR" in df_atual.columns:
        # Filtra apenas o mês atual para a Selfcolor (Mensal)
        df_self_atual_mes = df_atual[df_atual["MES"] == MES_ATUAL]
        df_self_ant_mes = df_anterior[df_anterior["MES"] == MES_ATUAL]
        
        # Pega qualquer valor que não seja vazio e não seja "NÃO"
        mask_self_at = df_self_atual_mes["SELF COLOR"].notna() & (df_self_atual_mes["SELF COLOR"].astype(str).str.strip() != "") & ~df_self_atual_mes["SELF COLOR"].astype(str).str.upper().str.contains("NÃO|NAO", na=False)
        v_self_at = df_self_atual_mes[mask_self_at]["VENDALITROS"].sum()
        
        mask_self_ant = df_self_ant_mes["SELF COLOR"].notna() & (df_self_ant_mes["SELF COLOR"].astype(str).str.strip() != "") & ~df_self_ant_mes["SELF COLOR"].astype(str).str.upper().str.contains("NÃO|NAO", na=False)
        v_self_ant = df_self_ant_mes[mask_self_ant]["VENDALITROS"].sum()
    dif_self = f"{(((v_self_at - v_self_ant) / v_self_ant) * 100):+.1f}%" if v_self_ant > 0 else "Sem base"
    with col_f3:
        st.metric(f"Selfcolor (Mês {MES_ATUAL:02d})", f"{v_self_at:,.0f} L".replace(',', '.') if v_self_at > 0 else "-", dif_self if v_self_at > 0 else None)

    v_ad_at = df_atual[df_atual["FABRICANTE_LAVADO"].str.contains("ADERE", na=False)]["VALORTOTAL"].sum()
    v_ad_ant = df_anterior[df_anterior["FABRICANTE_LAVADO"].str.contains("ADERE", na=False)]["VALORTOTAL"].sum()
    dif_ad = f"{(((v_ad_at - v_ad_ant) / v_ad_ant) * 100):+.1f}%" if v_ad_ant > 0 else "Sem base"
    with col_f4:
        st.metric("Adere (Faturamento)", f"R$ {v_ad_at:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if v_ad_at > 0 else "-", dif_ad if v_ad_at > 0 else None)

    v_con_at = df_atual[df_atual["FABRICANTE_LAVADO"].str.contains("CONDOR", na=False)]["VALORTOTAL"].sum()
    v_con_ant = df_anterior[df_anterior["FABRICANTE_LAVADO"].str.contains("CONDOR", na=False)]["VALORTOTAL"].sum()
    dif_con = f"{(((v_con_at - v_con_ant) / v_con_ant) * 100):+.1f}%" if v_con_ant > 0 else "Sem base"
    with col_f5:
        st.metric("Condor (Faturamento)", f"R$ {v_con_at:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if v_con_at > 0 else "-", dif_con if v_con_at > 0 else None)

    # ==========================================
    # 4. COMPRAS DOS ÚLTIMOS 30 DIAS
    # ==========================================
    st.markdown('<div class="header-yellow">📦 COMPRAS DOS ÚLTIMOS 30 DIAS</div>', unsafe_allow_html=True)
    
    data_limite_30d = HOJE - timedelta(days=30)
    compras_30d = df_grupo[df_grupo["DATA_DT"] >= data_limite_30d]

    if compras_30d.empty:
        st.info("ℹ️ O grupo não registrou compras nos últimos 30 dias.")
    else:
        cols_compras = ["DATA_DT", "DOCUMENTO", "FABRICANTE", "DESCRIÇÃO", "VENDALITROS", "VALORTOTAL"]
        cols_disponiveis = [c for c in cols_compras if c in compras_30d.columns]
        tabela_compras = compras_30d[cols_disponiveis].sort_values(by="DATA_DT", ascending=False)
        
        with st.expander("Clique aqui para ver o histórico detalhado de notas fiscais"):
            st.dataframe(tabela_compras.rename(columns={"DATA_DT": "DATA EMISSÃO"}), hide_index=True, use_container_width=True)

    # ==========================================
    # 5. CAMPANHAS A OFERTAR
    # ==========================================
    st.markdown("<div class=\"header-yellow\">🏆 CAMPANHAS DE INCENTIVO</div>", unsafe_allow_html=True)
    tab_vamos_juntos, tab_conexao = st.tabs(["🏎️ Vamos Juntos (Stock Car)", "🤝 Conexão Suvinil"])
    with tab_vamos_juntos:
    
        camp = CAMPANHAS_MAP.get(chave_final, {}).copy()
    
        # --- DADOS DA PLANILHA DE CAMPANHA (Se existir) ---
        df_ranking_local = pd.DataFrame()
        if 'df_campanhas' in locals() and df_campanhas is not None and not df_campanhas.empty and "Categoria" in df_campanhas.columns:
            # 1. Filtra a categoria inteira
            df_ranking_local = df_campanhas[df_campanhas["Categoria"].astype(str).str.strip().str.upper() == cat_atual].copy()
        
            if not df_ranking_local.empty:
                # 2. Descobre quantas vagas existem para essa categoria nas regras base
                import re
                vagas_vj = 0
                vagas_sc = 0
                for k, v in CAMPANHAS_MAP.get(chave_final, {}).items():
                    v_upper = str(v).upper()
                    match = re.search(r"(\d+)\s*VAGA", v_upper)
                    if match:
                        vagas = int(match.group(1))
                        if "VAMOS JUNTOS" in v_upper: vagas_vj += vagas
                        elif "STOCK CAR" in v_upper: vagas_sc += vagas

                # 3. Ordena os clientes da categoria
                df_ranking_local["Posição_num"] = pd.to_numeric(df_ranking_local["Posição"], errors='coerce')
                df_ranking_local = df_ranking_local.sort_values(by="Posição_num", na_position="last")
            
                # 4. Distribui as classificações automaticamente (ignorando o que veio na planilha)
                novas_classificacoes = []
                for idx, row in df_ranking_local.iterrows():
                    pos_num = row["Posição_num"]
                    if pd.isna(pos_num):
                        novas_classificacoes.append("-")
                    elif pos_num <= vagas_vj:
                        novas_classificacoes.append("🏆 Classifica Vamos Juntos")
                    elif pos_num <= (vagas_vj + vagas_sc):
                        novas_classificacoes.append("🏎️ Classifica Stock Car")
                    else:
                        novas_classificacoes.append("-")
            
                df_ranking_local["Classificação"] = novas_classificacoes
            
                # 5. Localiza o cliente atual dentro do ranking recalculado
                cliente_camp = df_ranking_local[df_ranking_local["Grupo de Cliente"].astype(str).str.strip().str.upper() == nome_busca]
                if not cliente_camp.empty:
                    linha_c = cliente_camp.iloc[0]
                    pos = str(linha_c.get("Posição", "")).strip()
                    pts = str(linha_c.get("Total pts", "")).strip()
                    classif = str(linha_c.get("Classificação", "")).strip().upper()
                
                    if pos and pos != "nan" and pos != "-" and "NÃO" not in pos.upper():
                        try: pos_str = str(int(float(pos))) 
                        except: pos_str = pos
                        try: pts_str = str(int(float(pts)))
                        except: pts_str = pts
                    
                        ranking_text = f"<br><span style='color:#e51e25; font-size:1.1rem; font-weight:900;'>🏆 {pos_str}º LUGAR ({pts_str} pts)</span>"
                    
                        for k, v in camp.items():
                            texto_campanha = str(v).upper()
                            if "STOCK CAR" in texto_campanha or "VAMOS JUNTOS" in texto_campanha:
                                camp[k] = str(v) + ranking_text

        cc1, cc2, cc3, cc4, cc5 = st.columns(5)
        def box_campanha(titulo, valor):
            return f"""<div style="background-color: var(--secondary-background-color); padding: 15px; border-radius: 8px; border-top: 4px solid #e51e25; min-height: 110px;">
            <p style="color: var(--text-color); opacity: 0.7; font-size: 0.8rem; font-weight: 700; margin-bottom: 5px; text-transform: uppercase;">{titulo}</p>
            <p style="color: var(--text-color); font-size: 1rem; font-weight: 800; line-height: 1.2;">{valor}</p></div>"""
    
        with cc1: st.markdown(box_campanha("Rebates", camp.get('Rebates', '-') or '-'), unsafe_allow_html=True)
        with cc2: st.markdown(box_campanha("Ação 1", camp.get('Camp1', '-') or '-'), unsafe_allow_html=True)
        with cc3: st.markdown(box_campanha("Ação 2", camp.get('Camp2', '-') or '-'), unsafe_allow_html=True)
        with cc4: st.markdown(box_campanha("Ação 3", camp.get('Camp3', '-') or '-'), unsafe_allow_html=True)
        with cc5: st.markdown(box_campanha("Ação 4", camp.get('Camp4', '-') or '-'), unsafe_allow_html=True)

        # --- TABELA DE RANKING DA CATEGORIA ---
        if not df_ranking_local.empty:
            st.markdown(f'<div class="sub-title" style="margin-top: 25px; font-size: 1.1rem; color: #f4ab13;">🏆 RANKING GERAL - {cat_atual}</div>', unsafe_allow_html=True)
        
            # Remove a coluna temporária usada pra ordenação
            df_ranking_local = df_ranking_local.drop(columns=["Posição_num"])
        
            def limpa_num(x):
                try: return str(int(float(x)))
                except: return str(x)
        
            df_ranking_local["Posição"] = df_ranking_local["Posição"].apply(limpa_num)
            df_ranking_local["Total pts"] = df_ranking_local["Total pts"].apply(limpa_num)
            df_ranking_local = df_ranking_local.fillna("-").replace("nan", "-")

            def highlight_client(row):
                row_grupo = str(row["Grupo de Cliente"]).strip().upper()
                if row_grupo == nome_busca or row_grupo in nome_busca or nome_busca in row_grupo:
                    return ['background-color: rgba(244, 171, 19, 0.4); font-weight: bold'] * len(row)
                return [''] * len(row)
            
            df_view = df_ranking_local[["Posição", "Grupo de Cliente", "Total pts", "Classificação"]]
        
            st.dataframe(
                df_view.style.apply(highlight_client, axis=1),
                use_container_width=True,
                hide_index=True
            )
        else:
            cats_disp = ", ".join(df_campanhas["Categoria"].astype(str).str.strip().str.upper().unique())
            st.info(f"O ranking não foi exibido porque a categoria '{cat_atual}' do dashboard não bate com os nomes das categorias escritas na planilha de campanhas. Categorias lidas da planilha: {cats_disp}")

    with tab_conexao:
        path_conexao = ARQ_CONEXAO_SERVIDOR
        if os.path.exists(path_conexao):
            try:
                df_cx = pd.read_excel(path_conexao)
                grupo_da_loja = df_grupo["Grupo de Cliente"].iloc[0] if not df_grupo.empty else grupo_ativo
                nome_busca_cx = str(grupo_da_loja).strip().upper()
                df_cx["Grupo Upper"] = df_cx["Grupo de lojas"].astype(str).str.strip().str.upper()
                
                cliente_cx = df_cx[df_cx["Grupo Upper"] == nome_busca_cx]
                if cliente_cx.empty:
                    cliente_cx = df_cx[df_cx["Grupo Upper"].apply(lambda x: x in nome_busca_cx or nome_busca_cx in x)]
                
                if not cliente_cx.empty:
                    rank = cliente_cx.iloc[0]["Ranking"]
                    st.markdown(f"<h4 style='color: var(--text-color);'>Posição Atual: {rank}º Lugar</h4>", unsafe_allow_html=True)
                    
                    cx1, cx2, cx3 = st.columns(3)
                    
                    def box_cx(titulo, valor, color="#e51e25"):
                        return f"""<div style="background-color: var(--secondary-background-color); padding: 15px; border-radius: 8px; border-top: 4px solid {color}; min-height: 110px;">\n<p style="color: var(--text-color); opacity: 0.7; font-size: 0.8rem; font-weight: 700; margin-bottom: 5px; text-transform: uppercase;">{titulo}</p>\n<p style="color: var(--text-color); font-size: 1.1rem; font-weight: 800; line-height: 1.2;">{valor}</p></div>"""
                    
                    status_cx = str(cliente_cx.iloc[0]["Status Cliente"]).strip()
                    status_color = "#28a745" if "Não" not in status_cx else "#dc3545"
                    
                    with cx1: st.markdown(box_cx("Status", status_cx, status_color), unsafe_allow_html=True)
                    
                    falta_vol = cliente_cx.iloc[0]["Falta Volume Elegibilidade"]
                    falta_str = f"{falta_vol:,.0f} L".replace(",", ".") if isinstance(falta_vol, (int, float)) else str(falta_vol)
                    with cx2: st.markdown(box_cx("Falta para Elegibilidade", falta_str), unsafe_allow_html=True)
                    
                    pontos = cliente_cx.iloc[0]["Pontos"]
                    pontos_str = f"{pontos:,.2f}".replace(".", ",") if isinstance(pontos, (int, float)) else str(pontos)
                    with cx3: st.markdown(box_cx("Pontuação", pontos_str), unsafe_allow_html=True)
                    
                    with st.expander("Ver Ranking Completo"):
                        df_show = df_cx.drop(columns=["Grupo Upper"]).copy()
                        
                        def highlight_cx(row):
                            if str(row["Grupo de lojas"]).strip().upper() == str(cliente_cx.iloc[0]["Grupo de lojas"]).strip().upper():
                                return ["background-color: #ffeebf; color: #000; font-weight: bold;"] * len(row)
                            return [""] * len(row)
                        
                        st.dataframe(df_show.style.apply(highlight_cx, axis=1), hide_index=True, use_container_width=True)
                else:
                    st.info("Cliente não encontrado no ranking Conexão Suvinil.")
            except Exception as e:
                st.error(f"Erro ao carregar Conexão Suvinil: {e}")
        else:
            st.info("O ranking da Conexão Suvinil não foi carregado pelo administrador.")
        
        st.markdown("<br>", unsafe_allow_html=True)
    # ==========================================
    # 6. FINANCEIRO (TÍTULO DINÂMICO E TABELA LIMPA)
    # ==========================================
    codigos_grupo = (pd.to_numeric(df_grupo["CÓDIGO CLIENTE"], errors="coerce").dropna().astype(int).astype(str).str.zfill(7).unique())
    boletos_grupo = df_receber[df_receber["CODIGO_CLIENTE"].isin(codigos_grupo) & (df_receber["VALOR_NUM"] > 0)]

    if boletos_grupo.empty: 
        # TÍTULO VERDE: Sem boletos
        st.markdown('<div class="header-green">SITUAÇÃO FINANCEIRA (TUDO EM DIA)</div>', unsafe_allow_html=True)
        # ALERTA CUSTOMIZADO
        st.markdown('<div style="background-color: rgba(33, 195, 84, 0.15); border-left: 5px solid #21c354; padding: 15px; border-radius: 5px; color: var(--text-color); font-weight: 600; margin-bottom: 20px;">✅ Tudo limpo! O grupo não possui boletos vencidos ou pendentes.</div>', unsafe_allow_html=True)
    
    else:
        df_boletos_view = boletos_grupo.sort_values(by="VENCIMENTO_DT")
        
        # Filtra e conta
        mask_pedidos = df_boletos_view["DOCUMENTO"].astype(str).str.upper().str.contains("-P")
        qtd_pedidos = mask_pedidos.sum()
        qtd_notas = len(boletos_grupo) - qtd_pedidos
        
        # Conta notas vencidas (ignorando pedidos para essa métrica)
        qtd_notas_vencidas = 0
        for i, row in df_boletos_view.iterrows():
            if not "-P" in str(row.get("DOCUMENTO", "")).upper():
                venc_val = row.get("VENCIMENTO_DT")
                if pd.notna(venc_val) and venc_val < HOJE:
                    qtd_notas_vencidas += 1
        
        if qtd_notas_vencidas > 0:
            st.markdown('<div class="header-red">SITUAÇÃO FINANCEIRA (NOTAS VENCIDAS)</div>', unsafe_allow_html=True)
            texto_alerta = f"O grupo possui <b>{qtd_notas} nota(s)</b> em aberto (sendo <b>{qtd_notas_vencidas} vencida(s)</b>)."
        else:
            st.markdown('<div class="header-yellow">SITUAÇÃO FINANCEIRA (EM DIA)</div>', unsafe_allow_html=True)
            texto_alerta = f"O grupo possui <b>{qtd_notas} nota(s)</b> em aberto (nenhuma vencida)."
            
        if qtd_pedidos > 0:
            texto_alerta += f" Além disso, há <b>{qtd_pedidos} pedido(s)</b> a receber."
            
        # ALERTA CUSTOMIZADO AMARELO (Sem símbolo, cor dinâmica pro modo claro/escuro)
        st.markdown(f'<div style="background-color: rgba(244, 171, 19, 0.15); border-left: 5px solid #f4ab13; padding: 15px; border-radius: 5px; color: var(--text-color); font-weight: 600; margin-bottom: 20px;">{texto_alerta}</div>', unsafe_allow_html=True)
        
        colunas_desejadas = ["CLIENTE", "DOCUMENTO", "EMISSÃO", "VENCIMENTO", "VALOR EMABERTO", "ATRASO"]
        colunas_boletos = [c for c in colunas_desejadas if c in df_boletos_view.columns]
        
        def destacar_vencidos(row):
            doc = str(row.get("DOCUMENTO", "")).upper()
            
            # Pedidos a receber (P) têm prioridade absoluta na cor (Azul)
            if "-P" in doc:
                return ['background-color: rgba(30, 144, 255, 0.3); font-weight: bold'] * len(row)
                
            # Notas (N) vencidas ficam em vermelho
            venc_val = row.get("VENCIMENTO")
            try:
                venc = pd.to_datetime(venc_val, dayfirst=True) if pd.notna(venc_val) else None
                if pd.notna(venc) and venc < HOJE:
                    return ['background-color: rgba(229, 30, 37, 0.4); font-weight: bold'] * len(row)
            except:
                pass
                
            return [''] * len(row)
        
        tabela_estilizada = df_boletos_view[colunas_boletos].style.apply(destacar_vencidos, axis=1)
        st.dataframe(tabela_estilizada, use_container_width=True, hide_index=True)
        
        # Legenda explicativa
        st.markdown('''
            <div style="font-size: 0.9em; margin-top: -10px; margin-bottom: 20px; padding: 10px; background-color: rgba(0,0,0,0.05); border-radius: 5px;">
                <b>📋 Legenda da Tabela:</b><br>
                <span style="display: inline-block; width: 15px; height: 15px; background-color: rgba(30, 144, 255, 0.6); vertical-align: middle; margin-right: 5px;"></span> <b>Pedidos a Receber (P):</b> Valores referentes a pedidos em carteira (não são notas fiscais faturadas).<br>
                <span style="display: inline-block; width: 15px; height: 15px; background-color: rgba(229, 30, 37, 0.6); vertical-align: middle; margin-right: 5px;"></span> <b>Notas Vencidas (N):</b> Notas fiscais faturadas que já passaram da data de vencimento.
            </div>
        ''', unsafe_allow_html=True)