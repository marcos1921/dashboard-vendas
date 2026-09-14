import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from html import escape
import os
import re
import unicodedata

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
    "1.1 INFINITO": {"Rebates": "", "Camp1": "Conexão Suvinil", "Camp2": "Vamos Juntos - 1 vaga", "Camp3": "", "Camp4": "Big Fish"},
    "2. DIAMANTE": {"Rebates": "", "Camp1": "Conexão Suvinil", "Camp2": "Vamos juntos - 2 vaga", "Camp3": "Stock Car - 1 vaga", "Camp4": "Big Fish"},
    "3. PLATINUM": {"Rebates": "", "Camp1": "", "Camp2": "Vamos Juntos - 1 vaga", "Camp3": "Stock Car - 2 vaga", "Camp4": "Big Fish"},
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
if hasattr(st, "context") and hasattr(st.context, "cookies"):
    cookie_auth = st.context.cookies.get("auth_vendas")
else:
    cookie_auth = cookie_manager.get(cookie="auth_vendas")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = (cookie_auth == "true")

if not st.session_state["autenticado"]:
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

                # Grava o cookie real no navegador, expirando exatamente à meia-noite
                cookie_manager.set("auth_vendas", "true", max_age=segundos_restantes)
                st.session_state["autenticado"] = True
                
                import time
                time.sleep(0.5) # Dá tempo para o navegador processar o cookie antes de recarregar
                st.rerun()
            else:
                st.error("Senha incorreta!")
    st.stop()

# --- MENU LATERAL (SIDEBAR) ---
st.sidebar.image("logo.png", use_container_width=True)
st.sidebar.divider()

st.sidebar.title("Navegação")
aba_selecionada = st.sidebar.radio("Ir para:", ["🔍 Consulta de Clientes", "⚙️ Área do Administrador"])

PASTA_DADOS = "dados_atuais"
if not os.path.exists(PASTA_DADOS): os.makedirs(PASTA_DADOS)
ARQ_VENDAS_SERVIDOR = os.path.join(PASTA_DADOS, "vendas.xlsx")
ARQ_RECEBER_SERVIDOR = os.path.join(PASTA_DADOS, "receber.csv")

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
        if st.button("💾 Salvar Novas Bases"):
            if up_vendas is not None and up_receber is not None:
                with open(ARQ_VENDAS_SERVIDOR, "wb") as arquivo:
                    arquivo.write(up_vendas.getbuffer())
                with open(ARQ_RECEBER_SERVIDOR, "wb") as arquivo:
                    arquivo.write(up_receber.getbuffer())
                st.cache_data.clear()
                st.success("✅ Bases atualizadas com sucesso!")
            else:
                st.error("Faça o upload de ambos os arquivos antes de salvar.")
    elif senha:
        st.error("Senha incorreta.")

# ==========================================
# VISÃO DO VENDEDOR (CONSULTA)
# ==========================================
elif aba_selecionada == "🔍 Consulta de Clientes":
    st.markdown('<div class="main-title">DASHBOARD VENDAS</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">INTELIGÊNCIA COMERCIAL EM CAMPO</div>', unsafe_allow_html=True)

    path_vendas = ARQ_VENDAS_SERVIDOR if os.path.exists(ARQ_VENDAS_SERVIDOR) else ("Base de vendas.xlsx" if os.path.exists("Base de vendas.xlsx") else None)
    csv_local = [f for f in os.listdir('.') if f.endswith('.csv') and 'receber' in f.lower()]
    path_receber = ARQ_RECEBER_SERVIDOR if os.path.exists(ARQ_RECEBER_SERVIDOR) else (csv_local[0] if csv_local else None)

    if not path_vendas or not path_receber:
        st.warning("⏳ **Atenção:** Arquivos não encontrados. Vá à **Área do Administrador** e faça o upload das duas bases.")
        st.stop()

    @st.cache_data(show_spinner="Processando inteligência comercial e corrigindo datas...")
    def carregar_dados_blindado(vendas_file, receber_file):
        df_v = pd.read_excel(vendas_file, sheet_name=0)
        df_r = pd.read_csv(receber_file, encoding="latin1", sep=None, engine="python")

        df_v = normalizar_colunas(df_v, {
            "DATA EMISSÃO": ["DATA EMISSO"],
            "CÓDIGO CLIENTE": ["CDIGO CLIENTE"],
            "DESCRIÇÃO": ["DESCRIO"],
            "MIX BASICO": ["MIX\nBASICO", "MIX BÁSICO"],
            "HIERARQUIA AGRUPADA": ["hierarquia Agrupada", "HIERARQUIA AGRUPADA"],
            "SELF COLOR": ["SELF\nCOLOR", "SELF COLOR"],
        })
        df_r = normalizar_colunas(df_r, {
            "EMISSÃO": ["EMISSO"],
        })
        
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
        valor_aberto = valor_aberto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        df_r["VALOR_NUM"] = pd.to_numeric(valor_aberto, errors="coerce").fillna(0)
        df_r["CODIGO_CLIENTE"] = (
            df_r["CLIENTE"].astype(str).str.extract(r"^\s*(\d+)", expand=False).str.zfill(7)
        )
        df_r["VENCIMENTO_DT"] = pd.to_datetime(df_r["VENCIMENTO"], dayfirst=True, errors="coerce")
            
        return df_v, df_r

    try:
        df_vendas, df_receber = carregar_dados_blindado(path_vendas, path_receber)
    except (ValueError, KeyError) as erro:
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
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Buscar Cliente")

    termo_busca = st.sidebar.text_input("Nome ou código do cliente", placeholder="Ex.: 141428 ou Express").strip()
    cidades = sorted(df_vendas["CIDADE"].dropna().astype(str).str.strip().unique())
    cidade_sel = st.sidebar.selectbox("Cidade (opcional)", ["Todas"] + cidades)

    df_filt = df_vendas
    if termo_busca:
        grupos = df_vendas["Grupo de Cliente"].fillna("").astype(str)
        clientes = df_vendas["CLIENTE"].fillna("").astype(str)
        mascara_busca = grupos.str.contains(termo_busca, case=False, regex=False) | clientes.str.contains(termo_busca, case=False, regex=False)

        if termo_busca.isdigit():
            codigo_buscado = str(int(termo_busca))
            codigos = pd.to_numeric(df_vendas["CÓDIGO CLIENTE"], errors="coerce")
            mascara_busca |= codigos.eq(int(codigo_buscado))

        df_filt = df_filt[mascara_busca]

    if cidade_sel != "Todas":
        df_filt = df_filt[df_filt["CIDADE"].astype(str).str.strip() == cidade_sel]

    grupos_disponiveis = sorted(df_filt["Grupo de Cliente"].dropna().unique())
    if not grupos_disponiveis:
        st.error("Nenhum cliente encontrado com os filtros informados.")
        st.stop()

    grupo_escolhido = st.sidebar.selectbox("Selecione a rede ou cliente", grupos_disponiveis)

    # Mostra a data e hora do ÚLTIMO UPLOAD da base no menu lateral
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
    df_grupo = df_vendas[df_vendas["Grupo de Cliente"] == grupo_escolhido]
    
    dia_ano_max = max_dt_base.dayofyear if pd.notna(max_dt_base) else 365
    df_atual = df_grupo[(df_grupo["ANO"] == ANO_ATUAL) & (df_grupo["DATA_DT"].dt.dayofyear <= dia_ano_max)]
    df_anterior = df_grupo[(df_grupo["ANO"] == ANO_ANTERIOR) & (df_grupo["DATA_DT"].dt.dayofyear <= dia_ano_max)]

    info_grupo = df_grupo.iloc[0]
    categoria_grupo = str(info_grupo.get("CATEGORIA", "Sem Categoria")).strip()

    st.markdown(f'<div class="cat-destaque">🏆 Categoria: {escape(categoria_grupo)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="cliente-titulo">{escape(grupo_escolhido)}</div>', unsafe_allow_html=True)

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

    todas_hierarquias = df_vendas[df_vendas["FABRICANTE_LAVADO"].str.contains("SUVINIL|SHERWIN", na=False)]["HIERARQUIA AGRUPADA"].dropna().unique()
    hierarquias_compradas = cli_suv_sher["HIERARQUIA AGRUPADA"].dropna().unique()
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
        # Pega qualquer valor que remeta a "BASE/ COLORANTE", "SIM", etc. Evita "Não SelfColor".
        v_self_at = df_atual[df_atual["SELF COLOR"].astype(str).str.upper().str.contains("BASE|COLORANTE|SIM|SELFCOLOR", na=False) & ~df_atual["SELF COLOR"].astype(str).str.upper().str.contains("NÃO|NAO", na=False)]["VENDALITROS"].sum()
        v_self_ant = df_anterior[df_anterior["SELF COLOR"].astype(str).str.upper().str.contains("BASE|COLORANTE|SIM|SELFCOLOR", na=False) & ~df_anterior["SELF COLOR"].astype(str).str.upper().str.contains("NÃO|NAO", na=False)]["VENDALITROS"].sum()
    dif_self = f"{(((v_self_at - v_self_ant) / v_self_ant) * 100):+.1f}%" if v_self_ant > 0 else "Sem base"
    with col_f3:
        st.metric("Selfcolor (Litros)", f"{v_self_at:,.0f} L".replace(',', '.') if v_self_at > 0 else "-", dif_self if v_self_at > 0 else None)

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
    st.markdown('<div class="header-yellow">BENEFÍCIOS E CAMPANHAS (OFERTE NO BALCÃO)</div>', unsafe_allow_html=True)
    camp = CAMPANHAS_MAP.get(categoria_grupo, {})
    
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
        
        # Filtra e conta os boletos vencidos matematicamente
        qtd_vencidos = sum((pd.notna(v) and v < HOJE) for v in df_boletos_view["VENCIMENTO_DT"])
        
        if qtd_vencidos > 0:
            # TÍTULO VERMELHO: Pelo menos um vencido (DATA REMOVIDA)
            st.markdown('<div class="header-red">SITUAÇÃO FINANCEIRA (BOLETOS VENCIDOS)</div>', unsafe_allow_html=True)
            texto_alerta = f"O grupo possui {len(boletos_grupo)} boleto(s) em aberto, sendo {qtd_vencidos} vencido(s)."
        else:
            # TÍTULO AMARELO: Boletos existem, mas todos no prazo (DATA REMOVIDA)
            st.markdown('<div class="header-yellow">SITUAÇÃO FINANCEIRA (BOLETOS A VENCER)</div>', unsafe_allow_html=True)
            texto_alerta = f"O grupo possui {len(boletos_grupo)} boleto(s) em aberto."
            
        # ALERTA CUSTOMIZADO AMARELO (Sem símbolo, cor dinâmica pro modo claro/escuro)
        st.markdown(f'<div style="background-color: rgba(244, 171, 19, 0.15); border-left: 5px solid #f4ab13; padding: 15px; border-radius: 5px; color: var(--text-color); font-weight: 600; margin-bottom: 20px;">{texto_alerta}</div>', unsafe_allow_html=True)
        
        colunas_boletos = ["CLIENTE", "DOCUMENTO", "EMISSÃO", "VENCIMENTO", "VALOR EMABERTO", "ATRASO"]
        
        # Pinta a linha SÓ se estiver vencido, ou de azul se for pedido não faturado
        def destacar_vencidos(row):
            doc = str(row.get("DOCUMENTO", "")).upper()
            if "-P/" in doc:
                return ['background-color: rgba(30, 144, 255, 0.3); font-weight: bold'] * len(row)
            if pd.notna(row["VENCIMENTO_DT"]) and row["VENCIMENTO_DT"] < HOJE:
                return ['background-color: rgba(229, 30, 37, 0.4); font-weight: bold'] * len(row)
            return [''] * len(row)
        
        tabela_estilizada = df_boletos_view.style.apply(destacar_vencidos, axis=1)
        st.dataframe(tabela_estilizada, column_order=colunas_boletos, hide_index=True, use_container_width=True)