# -*- coding: utf-8 -*-
"""
Dashboard Promocoes - Report
=============================
Acompanhamento de promocoes dos shoppings Almeida Junior.
"""
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Promocoes - Report",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS customizado
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    [data-testid="stMetric"] {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetric"] label {font-size: 0.8rem !important;}
    .promo-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        padding: 20px 30px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    .promo-header h1 {color: white; margin: 0; font-size: 1.8rem;}
    .promo-header p {color: #a0a0c0; margin: 5px 0 0 0; font-size: 0.95rem;}
    .kpi-table th {background: #1a1a2e !important; color: white !important; text-align: center !important;}
    .kpi-table td {text-align: right !important; padding: 6px 12px !important;}
    .kpi-table td:first-child {text-align: left !important; font-weight: bold;}
    div[data-testid="stExpander"] details summary span {font-weight: 600;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def carregar_dados():
    """Carrega todos os CSVs e o JSON de info da promo."""
    dados = {}
    try:
        with open("dados/promocao_info.json", "r", encoding="utf-8") as f:
            dados["info"] = json.load(f)
    except FileNotFoundError:
        st.error("Dados nao encontrados. Execute o script de extracao primeiro.")
        st.stop()

    dados["kpis"] = pd.read_csv("dados/kpis_promocao.csv", encoding="utf-8-sig")
    dados["serie"] = pd.read_csv("dados/serie_temporal.csv", encoding="utf-8-sig", parse_dates=["data"])
    dados["serie_total"] = pd.read_csv("dados/serie_temporal_total.csv", encoding="utf-8-sig", parse_dates=["data"])

    try:
        dados["resgates"] = pd.read_csv("dados/resgates_pontos.csv", encoding="utf-8-sig")
        dados["resgates_dia"] = pd.read_csv("dados/resgates_por_dia.csv", encoding="utf-8-sig", parse_dates=["data"])
    except FileNotFoundError:
        dados["resgates"] = pd.DataFrame()
        dados["resgates_dia"] = pd.DataFrame()

    return dados


def formatar_brl(valor):
    """Formata valor em reais."""
    if valor >= 1_000_000:
        return f"R$ {valor/1_000_000:,.1f}M"
    if valor >= 1_000:
        return f"R$ {valor:,.0f}"
    return f"R$ {valor:,.2f}"


def render_tabela_kpis(df_kpis, info):
    """Renderiza a tabela principal de KPIs estilo report."""
    # Separar shoppings e total
    shoppings = df_kpis[df_kpis["shopping_sigla"] != "TOTAL"].sort_values("shopping_sigla")
    total = df_kpis[df_kpis["shopping_sigla"] == "TOTAL"].iloc[0]

    # Ordem das colunas como na imagem: NK, BS, GS, NR, CS, NS, TOTAL
    ordem = ["NK", "BS", "GS", "NR", "CS", "NS"]
    colunas = [s for s in ordem if s in shoppings["shopping_sigla"].values]

    # Montar dados
    metricas = [
        ("Clientes Novos", "clientes_novos", "int"),
        ("Clientes Recorrentes", "clientes_recorrentes", "int"),
        ("Clientes Totais", "clientes_totais", "int"),
        ("Cupons Lancados", "cupons_lancados", "int"),
        ("R$", "valor_total", "brl"),
        ("TM Cliente", "tm_cliente", "brl_sm"),
        ("TM Cupom", "tm_cupom", "brl_sm"),
        ("", "", "sep"),
        ("Lojas na Promocao", "lojas_na_promocao", "int"),
        ("Lojas c/ Cupons Lancados", "lojas_com_cupons", "int"),
        ("Taxa de Conversao", "taxa_conversao_lojas", "pct"),
        ("", "", "sep"),
        ("Pontos Utilizados", "pontos_utilizados", "int"),
        ("Numeros da Sorte", "numeros_sorte", "int"),
        ("Clientes que Resgataram", "clientes_resgataram", "int"),
    ]

    def fmt(val, tipo):
        if tipo == "sep":
            return ""
        if tipo == "int":
            return f"{int(val):,}".replace(",", ".")
        if tipo == "brl":
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if tipo == "brl_sm":
            return f"R$ {val:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if tipo == "pct":
            return f"{val:.0f}%"
        return str(val)

    # Header
    header = "| Metrica |"
    sep_line = "|:---|"
    for s in colunas:
        header += f" **{s}** |"
        sep_line += "---:|"
    header += " **AJ (totais)** |"
    sep_line += "---:|"

    # Rows
    rows = []
    for label, col, tipo in metricas:
        if tipo == "sep":
            rows.append("|" + " |" * (len(colunas) + 2))
            continue
        row = f"| **{label}** |"
        for s in colunas:
            sub = shoppings[shoppings["shopping_sigla"] == s]
            val = sub[col].iloc[0] if len(sub) > 0 and col else 0
            row += f" {fmt(val, tipo)} |"
        row += f" {fmt(total[col], tipo)} |"
        rows.append(row)

    tabela = header + "\n" + sep_line + "\n" + "\n".join(rows)
    st.markdown(tabela)


def render_serie_temporal(dados, info):
    """Renderiza graficos de serie temporal."""
    df = dados["serie_total"].copy()
    promo_inicio = pd.Timestamp(info["data_inicio"])

    # Grafico de cupons por dia
    fig_cupons = go.Figure()
    df_pre = df[~df["na_promocao"]]
    df_promo = df[df["na_promocao"]]

    fig_cupons.add_trace(go.Bar(
        x=df_pre["data"], y=df_pre["cupons"],
        name="Pre-Promocao", marker_color="#94a3b8",
    ))
    fig_cupons.add_trace(go.Bar(
        x=df_promo["data"], y=df_promo["cupons"],
        name="Promocao", marker_color="#3b82f6",
    ))
    fig_cupons.add_vline(x=promo_inicio, line_dash="dash", line_color="red", line_width=2)
    fig_cupons.add_annotation(
        x=promo_inicio, y=1, yref="paper",
        text="Inicio Promo", showarrow=False,
        font=dict(color="red", size=11), yshift=10,
    )
    media_pre = df_pre["cupons"].mean() if len(df_pre) > 0 else 0
    fig_cupons.add_hline(y=media_pre, line_dash="dot", line_color="#64748b",
                         annotation_text=f"Media pre-promo: {media_pre:,.0f}", annotation_position="top left")
    fig_cupons.update_layout(
        title="Cupons Lancados por Dia (60 dias)",
        xaxis_title="", yaxis_title="Cupons",
        template="plotly_white", height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=40, r=20, t=60, b=40),
    )

    # Grafico de valor por dia
    fig_valor = go.Figure()
    fig_valor.add_trace(go.Bar(
        x=df_pre["data"], y=df_pre["valor_total"],
        name="Pre-Promocao", marker_color="#94a3b8",
    ))
    fig_valor.add_trace(go.Bar(
        x=df_promo["data"], y=df_promo["valor_total"],
        name="Promocao", marker_color="#22c55e",
    ))
    fig_valor.add_vline(x=promo_inicio, line_dash="dash", line_color="red", line_width=2)
    media_valor_pre = df_pre["valor_total"].mean() if len(df_pre) > 0 else 0
    fig_valor.add_hline(y=media_valor_pre, line_dash="dot", line_color="#64748b",
                        annotation_text=f"Media: R$ {media_valor_pre:,.0f}", annotation_position="top left")
    fig_valor.update_layout(
        title="Valor Total por Dia (R$)",
        xaxis_title="", yaxis_title="R$",
        template="plotly_white", height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=40, r=20, t=60, b=40),
    )

    return fig_cupons, fig_valor


def render_resgates(dados, info):
    """Renderiza metricas de resgate de pontos."""
    df_kpis = dados["kpis"]
    total = df_kpis[df_kpis["shopping_sigla"] == "TOTAL"].iloc[0]
    df_dia = dados["resgates_dia"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clientes que Resgataram", f"{int(total['clientes_resgataram']):,}")
    c2.metric("Pontos Utilizados", f"{int(total['pontos_utilizados']):,}")
    c3.metric("Numeros da Sorte", f"{int(total['numeros_sorte']):,}")
    media_pts = total["pontos_utilizados"] / total["clientes_resgataram"] if total["clientes_resgataram"] > 0 else 0
    c4.metric("Media Pontos/Cliente", f"{media_pts:,.0f}")

    if len(df_dia) > 0:
        fig = px.bar(
            df_dia, x="data", y="numeros_totais",
            text="numeros_totais",
            labels={"data": "", "numeros_totais": "Numeros da Sorte"},
            title="Numeros da Sorte Gerados por Dia",
            color_discrete_sequence=["#8b5cf6"],
        )
        fig.update_layout(template="plotly_white", height=350, margin=dict(l=40, r=20, t=60, b=40))
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    # Tabela por shopping
    df_resg_shop = df_kpis[df_kpis["shopping_sigla"] != "TOTAL"][
        ["shopping_sigla", "clientes_resgataram", "pontos_utilizados", "numeros_sorte"]
    ].copy()
    df_resg_shop.columns = ["Shopping", "Clientes", "Pontos", "Numeros"]
    df_resg_shop = df_resg_shop.sort_values("Numeros", ascending=False)
    st.dataframe(df_resg_shop, use_container_width=True, hide_index=True)


# ==============================================================
# MAIN
# ==============================================================
def main():
    dados = carregar_dados()
    info = dados["info"]
    df_kpis = dados["kpis"]

    # Header
    st.markdown(f"""
    <div class="promo-header">
        <h1>🎯 Promocoes - Report</h1>
        <p>{info['titulo']} | Periodo: {info['data_inicio']} a {info['data_fim']} | Sorteio: {info['data_sorteio']}</p>
        <p style="color: #70a0ff; font-size: 0.85rem;">
            Atualizado em: {info['atualizado_em']} &nbsp;&nbsp;|&nbsp;&nbsp; Dados ate: {info['dados_ate']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ============================================================
    # TAB PRINCIPAL
    # ============================================================
    tab1, tab2, tab3 = st.tabs(["📊 Report Geral", "📈 Serie Temporal", "🎰 Resgates de Pontos"])

    with tab1:
        # KPIs destaque
        total = df_kpis[df_kpis["shopping_sigla"] == "TOTAL"].iloc[0]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Clientes Totais", f"{int(total['clientes_totais']):,}")
        c2.metric("Cupons Lancados", f"{int(total['cupons_lancados']):,}")
        c3.metric("Valor Total", formatar_brl(total["valor_total"]))
        c4.metric("TM Cliente", f"R$ {total['tm_cliente']:,.0f}")
        c5.metric("Numeros da Sorte", f"{int(total['numeros_sorte']):,}")

        st.markdown("---")

        # Tabela completa
        st.subheader("Detalhamento por Shopping")
        render_tabela_kpis(df_kpis, info)

        # Graficos comparativos por shopping
        st.markdown("---")
        shoppings = df_kpis[df_kpis["shopping_sigla"] != "TOTAL"].copy()

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                shoppings.sort_values("valor_total", ascending=True),
                x="valor_total", y="shopping_sigla",
                orientation="h", text_auto=",.0f",
                labels={"valor_total": "R$", "shopping_sigla": ""},
                title="Valor Total por Shopping",
                color_discrete_sequence=["#3b82f6"],
            )
            fig.update_layout(template="plotly_white", height=350, margin=dict(l=40, r=20, t=60, b=40))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(
                shoppings.sort_values("clientes_totais", ascending=True),
                x="clientes_totais", y="shopping_sigla",
                orientation="h", text_auto=",",
                labels={"clientes_totais": "Clientes", "shopping_sigla": ""},
                title="Clientes Totais por Shopping",
                color_discrete_sequence=["#22c55e"],
            )
            fig.update_layout(template="plotly_white", height=350, margin=dict(l=40, r=20, t=60, b=40))
            st.plotly_chart(fig, use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            fig = px.bar(
                shoppings.sort_values("taxa_conversao_lojas", ascending=True),
                x="taxa_conversao_lojas", y="shopping_sigla",
                orientation="h", text_auto=".0f",
                labels={"taxa_conversao_lojas": "% Conversao", "shopping_sigla": ""},
                title="Taxa de Conversao de Lojas (%)",
                color_discrete_sequence=["#f59e0b"],
            )
            fig.update_layout(template="plotly_white", height=350, margin=dict(l=40, r=20, t=60, b=40))
            fig.update_traces(texttemplate="%{x:.0f}%")
            st.plotly_chart(fig, use_container_width=True)

        with col4:
            fig = px.pie(
                shoppings, values="cupons_lancados", names="shopping_sigla",
                title="Distribuicao de Cupons por Shopping",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=60, b=40))
            fig.update_traces(textinfo="percent+value", textposition="inside")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Serie Temporal - Impacto da Promocao")
        st.info(
            f"Comparativo dos ultimos 60 dias. A linha vermelha marca o inicio da promocao "
            f"**{info['titulo']}** em **{info['data_inicio']}**."
        )

        fig_cupons, fig_valor = render_serie_temporal(dados, info)

        st.plotly_chart(fig_cupons, use_container_width=True)
        st.plotly_chart(fig_valor, use_container_width=True)

        # Serie por shopping
        with st.expander("Serie por Shopping"):
            shopping_sel = st.selectbox("Shopping", ["Todos"] + sorted(dados["serie"]["shopping_sigla"].dropna().unique()))
            df_s = dados["serie"].copy()
            if shopping_sel != "Todos":
                df_s = df_s[df_s["shopping_sigla"] == shopping_sel]
                df_s = df_s.groupby("data").agg(cupons=("cupons","sum"), valor_total=("valor_total","sum")).reset_index()
            else:
                df_s = dados["serie_total"].copy()

            fig = px.line(df_s, x="data", y="cupons", markers=True,
                         labels={"data":"","cupons":"Cupons"}, title=f"Cupons/dia - {shopping_sel}")
            fig.add_vline(x=pd.Timestamp(info["data_inicio"]), line_dash="dash", line_color="red")
            fig.update_layout(template="plotly_white", height=350)
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Resgates de Pontos - Numeros da Sorte")
        st.info(
            f"Cada **{info.get('pontos_por_numero', 100)} pontos** utilizados geram "
            f"**1 numero da sorte** para o sorteio de **{info['data_sorteio']}**."
        )

        if len(dados["resgates"]) > 0:
            render_resgates(dados, info)
        else:
            st.warning("Nenhum resgate de pontos registrado ainda.")


if __name__ == "__main__":
    main()
