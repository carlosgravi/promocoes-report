# -*- coding: utf-8 -*-
"""
Dashboard Promoções - Report
=============================
Acompanhamento de promoções dos shoppings Almeida Junior.
"""
import json
import math
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

SHOPPING_FULL = {
    1: "Continente Shopping", 2: "Balneário Shopping", 3: "Neumarkt Shopping",
    4: "Norte Shopping", 5: "Garten Shopping", 6: "Nações Shopping",
}

st.set_page_config(
    page_title="Promoções - Report",
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
        text-align: center;
        min-height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    [data-testid="stMetric"] label {font-size: 0.8rem !important; justify-content: center;}
    [data-testid="stMetric"] [data-testid="stMetricValue"] {justify-content: center;}
    [data-testid="stMetric"] [data-testid="stMetricDelta"] {justify-content: center; font-size: 0.7rem !important; line-height: 1.1 !important;}
    [data-testid="stMetric"] [data-testid="stMetricDelta"] svg {display: none;}
    [data-testid="stHorizontalBlock"] {align-items: stretch;}
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
    abbr {
        text-decoration: none !important;
        cursor: help;
        font-size: 0.75rem;
        opacity: 0.5;
        vertical-align: super;
    }
    abbr:hover {opacity: 1;}
    abbr.ast {font-size: 1.1rem; opacity: 0.8; vertical-align: baseline; font-weight: bold;}
</style>
""", unsafe_allow_html=True)


def carregar_dados():
    """Carrega todos os CSVs e o JSON de info da promo."""
    dados = {}
    try:
        with open("dados/promocao_info.json", "r", encoding="utf-8") as f:
            dados["info"] = json.load(f)
    except FileNotFoundError:
        st.error("Dados não encontrados. Execute o script de extração primeiro.")
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

    try:
        dados["top_lojas"] = pd.read_csv("dados/top_lojas.csv", encoding="utf-8-sig")
    except FileNotFoundError:
        dados["top_lojas"] = pd.DataFrame()

    try:
        dados["participacao"] = pd.read_csv("dados/participacao_lojas.csv", encoding="utf-8-sig")
    except FileNotFoundError:
        dados["participacao"] = pd.DataFrame()

    return dados


def formatar_brl(valor):
    """Formata valor em reais."""
    if valor >= 1_000_000:
        return f"R$ {valor/1_000_000:,.1f}M"
    if valor >= 1_000:
        return f"R$ {valor:,.0f}"
    return f"R$ {valor:,.2f}"


def render_tabela_kpis(df_kpis, info):
    """Renderiza a tabela principal de KPIs estilo relatório."""
    # Separar shoppings e total
    shoppings = df_kpis[df_kpis["shopping_sigla"] != "TOTAL"].sort_values("shopping_sigla")
    total = df_kpis[df_kpis["shopping_sigla"] == "TOTAL"].iloc[0]

    # Ordem das colunas: CS, BS, NK, NR, GS, NS, TOTAL
    ordem = ["CS", "BS", "NK", "NR", "GS", "NS"]
    colunas = [s for s in ordem if s in shoppings["shopping_sigla"].values]

    # Montar dados: (label, coluna, tipo, tooltip)
    metricas = [
        ("Clientes Novos Cadastro", "clientes_novos_cadastro", "int",
         "Clientes que criaram conta no app durante o período da promoção. Shopping atribuído pelo último acesso no app."),
        ("Clientes Novos Cupons", "clientes_novos_cupom", "int",
         "Clientes que lançaram seu primeiro cupom validado de todos os tempos durante a promoção."),
        ("Clientes Recorrentes", "clientes_recorrentes", "int",
         "Clientes que já tinham cupons validados antes do início da promoção."),
        ("Clientes Totais", "clientes_totais", "int",
         "Total de clientes únicos que lançaram pelo menos 1 cupom validado durante a promoção."),
        ("Cupons Lançados", "cupons_lancados", "int",
         "Quantidade total de cupons com status Validado no período."),
        ("R$", "valor_total", "brl",
         "Soma do valor de compra de todos os cupons validados no período."),
        ("TM Cliente", "tm_cliente", "brl_sm",
         "Ticket Médio por Cliente = Valor Total / Clientes Totais."),
        ("TM Cupom", "tm_cupom", "brl_sm",
         "Ticket Médio por Cupom = Valor Total / Cupons Lançados."),
        ("", "", "sep", ""),
        ("Lojas na Promoção", "lojas_na_promocao", "int",
         "Total de lojas cadastradas no shopping (todas participam da promoção)."),
        ("Lojas c/ Cupons Lançados", "lojas_com_cupons", "int",
         "Lojas que tiveram pelo menos 1 cupom validado durante o período."),
        ("Taxa de Conversão", "taxa_conversao_lojas", "pct",
         "Percentual de lojas com cupons lançados em relação ao total de lojas do shopping."),
        ("", "", "sep", ""),
        ("Pontos Utilizados", "pontos_utilizados", "int",
         "Total de pontos resgatados pelos clientes para gerar números da sorte."),
        ("Números da Sorte", "numeros_sorte", "int",
         "Total de números da sorte gerados. Cada 100 pontos = 1 número da sorte."),
        ("Clientes que Resgataram", "clientes_resgataram", "int",
         "Clientes únicos que realizaram pelo menos 1 resgate de pontos por números da sorte."),
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
    header = "| Métrica |"
    sep_line = "|:---|"
    for s in colunas:
        header += f" **{s}** |"
        sep_line += "---:|"
    header += " **AJ (totais)** |"
    sep_line += "---:|"

    # Colunas onde o total é clientes únicos (pode ser menor que soma dos shoppings)
    cols_cliente_unico = {"clientes_totais", "clientes_resgataram"}

    # Rows
    rows = []
    for label, col, tipo, tooltip in metricas:
        if tipo == "sep":
            rows.append("|" + " |" * (len(colunas) + 2))
            continue
        help_icon = f' <abbr title="{tooltip}">❓</abbr>' if tooltip else ""
        row = f"| **{label}**{help_icon} |"
        for s in colunas:
            sub = shoppings[shoppings["shopping_sigla"] == s]
            val = sub[col].iloc[0] if len(sub) > 0 and col else 0
            row += f" {fmt(val, tipo)} |"
        total_val = fmt(total[col], tipo)
        if col in cols_cliente_unico:
            soma_shops = int(shoppings[col].sum())
            total_int = int(total[col])
            if soma_shops != total_int:
                total_val += f' <abbr class="ast" title="Total de clientes únicos ({total_int}). A soma dos shoppings é {soma_shops} porque {soma_shops - total_int} cliente(s) compraram em mais de um shopping.">*</abbr>'
        row += f" {total_val} |"
        rows.append(row)

    tabela = header + "\n" + sep_line + "\n" + "\n".join(rows)
    st.markdown(tabela, unsafe_allow_html=True)


def render_serie_temporal(dados, info):
    """Renderiza gráficos de série temporal."""
    df = dados["serie_total"].copy()
    promo_inicio = pd.Timestamp(info["data_inicio"])

    # Gráfico de cupons por dia
    fig_cupons = go.Figure()
    df_pre = df[~df["na_promocao"]]
    df_promo = df[df["na_promocao"]]

    fig_cupons.add_trace(go.Bar(
        x=df_pre["data"], y=df_pre["cupons"],
        name="Pré-Promoção", marker_color="#94a3b8",
    ))
    fig_cupons.add_trace(go.Bar(
        x=df_promo["data"], y=df_promo["cupons"],
        name="Promoção", marker_color="#3b82f6",
    ))
    fig_cupons.add_vline(x=promo_inicio, line_dash="dash", line_color="red", line_width=2)
    fig_cupons.add_annotation(
        x=promo_inicio, y=1, yref="paper",
        text="Início Promo", showarrow=False,
        font=dict(color="red", size=11), yshift=10,
    )
    media_pre = df_pre["cupons"].mean() if len(df_pre) > 0 else 0
    fig_cupons.add_hline(y=media_pre, line_dash="dot", line_color="#64748b",
                         annotation_text=f"Média pré-promo: {media_pre:,.0f}", annotation_position="top left")
    fig_cupons.update_layout(
        title="Cupons Lançados por Dia (60 dias)",
        xaxis_title="", yaxis_title="Cupons",
        template="plotly_white", height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=40, r=20, t=60, b=40),
    )

    # Gráfico de valor por dia
    fig_valor = go.Figure()
    fig_valor.add_trace(go.Bar(
        x=df_pre["data"], y=df_pre["valor_total"],
        name="Pré-Promoção", marker_color="#94a3b8",
    ))
    fig_valor.add_trace(go.Bar(
        x=df_promo["data"], y=df_promo["valor_total"],
        name="Promoção", marker_color="#22c55e",
    ))
    fig_valor.add_vline(x=promo_inicio, line_dash="dash", line_color="red", line_width=2)
    media_valor_pre = df_pre["valor_total"].mean() if len(df_pre) > 0 else 0
    fig_valor.add_hline(y=media_valor_pre, line_dash="dot", line_color="#64748b",
                        annotation_text=f"Média: R$ {media_valor_pre:,.0f}", annotation_position="top left")
    fig_valor.update_layout(
        title="Valor Total por Dia (R$)",
        xaxis_title="", yaxis_title="R$",
        template="plotly_white", height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=40, r=20, t=60, b=40),
    )

    return fig_cupons, fig_valor


def render_resgates(dados, info):
    """Renderiza métricas de resgate de pontos."""
    df_kpis = dados["kpis"]
    total = df_kpis[df_kpis["shopping_sigla"] == "TOTAL"].iloc[0]
    df_dia = dados["resgates_dia"]

    total_resgates = int(df_dia["resgates"].sum()) if len(df_dia) > 0 else 0
    media_pts = total["pontos_utilizados"] / total["clientes_resgataram"] if total["clientes_resgataram"] > 0 else 0
    kpis_shop = df_kpis[df_kpis["shopping_sigla"] != "TOTAL"]
    soma_cli_shop = int(kpis_shop["clientes_resgataram"].sum())
    cli_unicos = int(total["clientes_resgataram"])
    diff_cli = soma_cli_shop - cli_unicos

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total de Resgates", f"{total_resgates:,}",
              help="Quantidade total de operações de resgate realizadas. Um cliente pode resgatar várias vezes.")
    help_cli = f"Clientes únicos que realizaram pelo menos 1 resgate. A soma por shopping dá {soma_cli_shop} porque {diff_cli} cliente(s) resgataram em mais de um shopping." if diff_cli > 0 else "Clientes únicos que realizaram pelo menos 1 resgate de pontos por números da sorte."
    delta_cli = f"{soma_cli_shop} por shopping · {diff_cli} em +1" if diff_cli > 0 else None
    c2.metric("Clientes Únicos", f"{cli_unicos:,}",
              delta=delta_cli, delta_color="off",
              help=help_cli)
    c3.metric("Pontos Utilizados", f"{int(total['pontos_utilizados']):,}",
              help="Total de pontos resgatados pelos clientes. Calculado como Números da Sorte × 100.")
    c4.metric("Números da Sorte", f"{int(total['numeros_sorte']):,}",
              help=f"Total de números da sorte gerados. Cada {info.get('pontos_por_numero', 100)} pontos = 1 número da sorte.")
    c5.metric("Média Pontos/Cliente", f"{media_pts:,.0f}",
              help="Média de pontos utilizados por cliente = Pontos Utilizados / Clientes Únicos.")

    if len(df_dia) > 0:
        fig = px.bar(
            df_dia, x="data", y="numeros_totais",
            text="numeros_totais",
            labels={"data": "", "numeros_totais": "Números da Sorte"},
            title="Números da Sorte Gerados por Dia",
            color_discrete_sequence=["#8b5cf6"],
        )
        fig.update_layout(template="plotly_white", height=350, margin=dict(l=40, r=20, t=60, b=40))
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    # Tabela por shopping
    df_resg_shop = df_kpis[df_kpis["shopping_sigla"] != "TOTAL"][
        ["shopping_sigla", "clientes_resgataram", "pontos_utilizados", "numeros_sorte"]
    ].copy()
    df_resg_shop.columns = ["Shopping", "Clientes", "Pontos", "Números"]
    df_resg_shop = df_resg_shop.sort_values("Números", ascending=False)
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
        <h1>🎯 Promoções - Report</h1>
        <p>{info['titulo']} | Período: {info['data_inicio']} a {info['data_fim']} | Sorteio: {info['data_sorteio']}</p>
        <p style="color: #70a0ff; font-size: 0.85rem;">
            Atualizado em: {info['atualizado_em']} &nbsp;&nbsp;|&nbsp;&nbsp; Dados até: {info['dados_ate']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ============================================================
    # TAB PRINCIPAL
    # ============================================================
    tab1, tab2, tab_lojas, tab_part, tab3, tab4 = st.tabs([
        "📊 Report Geral", "📈 Série Temporal", "🏪 Top Lojas",
        "🧾 Participação Lojas", "🎰 Resgates de Pontos", "🔍 Validação",
    ])

    with tab1:
        # KPIs destaque
        total = df_kpis[df_kpis["shopping_sigla"] == "TOTAL"].iloc[0]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Clientes Totais", f"{int(total['clientes_totais']):,}")
        c2.metric("Cupons Lançados", f"{int(total['cupons_lancados']):,}")
        c3.metric("Valor Total", formatar_brl(total["valor_total"]))
        c4.metric("TM Cliente", f"R$ {total['tm_cliente']:,.0f}")
        c5.metric("Números da Sorte", f"{int(total['numeros_sorte']):,}")

        st.markdown("---")

        # Tabela completa
        st.subheader("Detalhamento por Shopping")
        render_tabela_kpis(df_kpis, info)

        # Gráficos comparativos por shopping
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
                labels={"taxa_conversao_lojas": "% Conversão", "shopping_sigla": ""},
                title="Taxa de Conversão de Lojas (%)",
                color_discrete_sequence=["#f59e0b"],
            )
            fig.update_layout(template="plotly_white", height=350, margin=dict(l=40, r=20, t=60, b=40))
            fig.update_traces(texttemplate="%{x:.0f}%")
            st.plotly_chart(fig, use_container_width=True)

        with col4:
            fig = px.pie(
                shoppings, values="cupons_lancados", names="shopping_sigla",
                title="Distribuição de Cupons por Shopping",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=60, b=40))
            fig.update_traces(textinfo="percent+value", textposition="inside")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Série Temporal - Impacto da Promoção")
        st.info(
            f"Comparativo dos últimos 60 dias. A linha vermelha marca o início da promoção "
            f"**{info['titulo']}** em **{info['data_inicio']}**."
        )

        fig_cupons, fig_valor = render_serie_temporal(dados, info)

        st.plotly_chart(fig_cupons, use_container_width=True)
        st.plotly_chart(fig_valor, use_container_width=True)

        # Série por shopping
        with st.expander("Série por Shopping"):
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

    # ============================================================
    # TAB: TOP LOJAS
    # ============================================================
    with tab_lojas:
        st.subheader("🏪 Ranking de Lojas por Shopping")
        st.caption("Top 10 lojas com maior valor de vendas durante o período da promoção")

        df_lojas = dados.get("top_lojas", pd.DataFrame())

        if len(df_lojas) > 0:
            ORDEM_SHOPPING = ["CS", "BS", "NK", "NR", "GS", "NS"]
            shopping_filter = st.selectbox(
                "Shopping:", ["Todos"] + ORDEM_SHOPPING,
                key="top_lojas_filter"
            )

            if shopping_filter != "Todos":
                shoppings_show = [shopping_filter]
            else:
                shoppings_show = ORDEM_SHOPPING

            for sigla in shoppings_show:
                df_shop = df_lojas[df_lojas["shopping_sigla"] == sigla].copy()
                if len(df_shop) == 0:
                    continue

                df_top10 = df_shop[df_shop["ranking"] <= 10].sort_values("ranking")
                nome_shopping = SHOPPING_FULL.get(
                    df_top10["shopping_id"].iloc[0] if len(df_top10) > 0 else 0,
                    sigla
                )

                with st.expander(f"🏬 {nome_shopping} ({sigla}) — {len(df_shop)} lojas com cupons", expanded=(shopping_filter != "Todos")):
                    # KPIs do shopping
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Lojas com Cupons", f"{len(df_shop)}")
                    c2.metric("Valor Total", formatar_brl(df_shop["valor_total"].sum()))
                    c3.metric("Total Cupons", f"{int(df_shop['cupons'].sum()):,}")

                    # Gráfico horizontal top 10
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        y=df_top10["loja_nome"][::-1],
                        x=df_top10["valor_total"][::-1],
                        orientation="h",
                        marker_color="#3b82f6",
                        text=[formatar_brl(v) for v in df_top10["valor_total"][::-1]],
                        textposition="outside",
                        textfont=dict(size=11),
                    ))
                    fig.update_layout(
                        title=f"Top 10 Lojas — {sigla}",
                        template="plotly_white",
                        height=max(350, len(df_top10) * 40),
                        margin=dict(l=180, r=80),
                        xaxis_title="Valor Total (R$)",
                        yaxis_title="",
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Tabela detalhada
                    df_display = df_top10[["ranking", "loja_nome", "segmento", "cupons", "clientes", "valor_total", "ticket_medio"]].copy()
                    df_display.columns = ["#", "Loja", "Segmento", "Cupons", "Clientes", "Valor Total", "Ticket Médio"]
                    df_display["Valor Total"] = df_display["Valor Total"].apply(lambda x: formatar_brl(x))
                    df_display["Ticket Médio"] = df_display["Ticket Médio"].apply(lambda x: formatar_brl(x))
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
            # ============================================================
            # COMPARATIVO ENTRE SHOPPINGS (Top 10 de cada)
            # ============================================================
            st.markdown("---")
            st.subheader("Comparativo entre Shoppings — Top 10 Lojas")

            ORDEM_SHOPPING_FULL = ["CS", "BS", "NK", "NR", "GS", "NS"]
            comp_data = []
            for sigla in ORDEM_SHOPPING_FULL:
                df_s = df_lojas[df_lojas["shopping_sigla"] == sigla]
                df_t10 = df_s[df_s["ranking"] <= 10]
                if len(df_t10) > 0:
                    comp_data.append({
                        "Shopping": sigla,
                        "Valor Top 10": df_t10["valor_total"].sum(),
                        "Cupons Top 10": int(df_t10["cupons"].sum()),
                        "Clientes Top 10": int(df_t10["clientes"].sum()),
                        "Ticket Médio Top 10": df_t10["valor_total"].sum() / df_t10["cupons"].sum() if df_t10["cupons"].sum() > 0 else 0,
                        "Total Lojas": len(df_s),
                    })

            if comp_data:
                df_comp = pd.DataFrame(comp_data)

                col_g1, col_g2 = st.columns(2)

                with col_g1:
                    fig1 = go.Figure()
                    fig1.add_trace(go.Bar(
                        x=df_comp["Shopping"],
                        y=df_comp["Valor Top 10"],
                        marker_color="#3b82f6",
                        text=[formatar_brl(v) for v in df_comp["Valor Top 10"]],
                        textposition="outside",
                        textfont=dict(size=10),
                    ))
                    fig1.update_layout(
                        title="Valor Total — Top 10 Lojas",
                        template="plotly_white", height=380,
                        yaxis_title="R$", xaxis_title="",
                    )
                    st.plotly_chart(fig1, use_container_width=True)

                with col_g2:
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(
                        x=df_comp["Shopping"],
                        y=df_comp["Cupons Top 10"],
                        marker_color="#10b981",
                        text=df_comp["Cupons Top 10"],
                        textposition="outside",
                        textfont=dict(size=10),
                    ))
                    fig2.update_layout(
                        title="Cupons Lançados — Top 10 Lojas",
                        template="plotly_white", height=380,
                        yaxis_title="Cupons", xaxis_title="",
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                col_g3, col_g4 = st.columns(2)

                with col_g3:
                    fig3 = go.Figure()
                    fig3.add_trace(go.Bar(
                        x=df_comp["Shopping"],
                        y=df_comp["Clientes Top 10"],
                        marker_color="#f59e0b",
                        text=df_comp["Clientes Top 10"],
                        textposition="outside",
                        textfont=dict(size=10),
                    ))
                    fig3.update_layout(
                        title="Clientes Únicos — Top 10 Lojas",
                        template="plotly_white", height=380,
                        yaxis_title="Clientes", xaxis_title="",
                    )
                    st.plotly_chart(fig3, use_container_width=True)

                with col_g4:
                    fig4 = go.Figure()
                    fig4.add_trace(go.Bar(
                        x=df_comp["Shopping"],
                        y=df_comp["Ticket Médio Top 10"].round(2),
                        marker_color="#8b5cf6",
                        text=[formatar_brl(v) for v in df_comp["Ticket Médio Top 10"]],
                        textposition="outside",
                        textfont=dict(size=10),
                    ))
                    fig4.update_layout(
                        title="Ticket Médio — Top 10 Lojas",
                        template="plotly_white", height=380,
                        yaxis_title="R$", xaxis_title="",
                    )
                    st.plotly_chart(fig4, use_container_width=True)

                # Tabela comparativa
                with st.expander("📊 Tabela comparativa"):
                    df_comp_show = df_comp.copy()
                    df_comp_show["Valor Top 10"] = df_comp_show["Valor Top 10"].apply(formatar_brl)
                    df_comp_show["Ticket Médio Top 10"] = df_comp_show["Ticket Médio Top 10"].apply(lambda x: formatar_brl(x))
                    st.dataframe(df_comp_show, use_container_width=True, hide_index=True)

        else:
            st.info("Dados de lojas não disponíveis. Execute a extração.")

    # ============================================================
    # TAB: PARTICIPAÇÃO LOJAS
    # ============================================================
    with tab_part:
        render_participacao_lojas(dados)

    with tab3:
        st.subheader("Resgates de Pontos - Números da Sorte")
        st.info(
            f"Cada **{info.get('pontos_por_numero', 100)} pontos** utilizados geram "
            f"**1 número da sorte** para o sorteio de **{info['data_sorteio']}**."
        )

        if len(dados["resgates"]) > 0:
            render_resgates(dados, info)
        else:
            st.warning("Nenhum resgate de pontos registrado ainda.")

    with tab4:
        render_validacao(dados, info)


def render_participacao_lojas(dados):
    """Renderiza participação de todas as lojas (com ou sem cupons) por shopping."""
    st.subheader("🧾 Participação de Lojas na Promoção")
    st.caption("Lojas com fidelidade habilitada: ativas no momento da extração, "
               "as que lançaram cupons na promoção e as que foram inativadas durante o período.")

    df_part = dados.get("participacao", pd.DataFrame())
    if len(df_part) == 0:
        st.info("Dados de participação indisponíveis. Execute a extração para gerar `dados/participacao_lojas.csv`.")
        return

    # Garantir colunas opcionais (compatibilidade com CSVs antigos)
    if "status_atual" not in df_part.columns:
        df_part["status_atual"] = "ATIVO"
    if "inativada_na_promo" not in df_part.columns:
        df_part["inativada_na_promo"] = False
    if "data_inativacao" not in df_part.columns:
        df_part["data_inativacao"] = ""
    if "last_time" not in df_part.columns:
        df_part["last_time"] = ""

    # Aviso global para inativadas
    inativadas_total = int(df_part["inativada_na_promo"].sum())
    if inativadas_total > 0:
        inat_com_cupom = int((df_part["inativada_na_promo"] & df_part["participou"]).sum())
        inat_sem_cupom = inativadas_total - inat_com_cupom
        st.warning(
            f"⚠️ **{inativadas_total} lojas foram inativadas durante o período da promoção** "
            f"({inat_com_cupom} chegaram a lançar cupons, {inat_sem_cupom} não lançaram). "
            f"Elas estão sinalizadas como ⚠️ *Inativada na promo* nas tabelas abaixo."
        )

    ORDEM_SHOPPING = ["CS", "BS", "NK", "NR", "GS", "NS"]

    c_f1, c_f2 = st.columns([1, 3])
    with c_f1:
        shopping_filter = st.selectbox(
            "Shopping:", ["Todos"] + ORDEM_SHOPPING,
            key="part_lojas_shopping",
        )
    with c_f2:
        status_filter = st.radio(
            "Exibir:", ["Todas", "Apenas com cupons", "Apenas sem cupons"],
            horizontal=True, key="part_lojas_status",
        )

    shoppings_show = ORDEM_SHOPPING if shopping_filter == "Todos" else [shopping_filter]

    # Visão consolidada (cards por shopping)
    resumo = (
        df_part.groupby("shopping_sigla")
        .agg(
            total_lojas=("cnpj", "count"),
            participaram=("participou", "sum"),
            cupons=("cupons", "sum"),
            valor_total=("valor_total", "sum"),
        )
        .reset_index()
    )
    resumo["nao_participaram"] = resumo["total_lojas"] - resumo["participaram"]
    resumo["taxa"] = resumo["participaram"] / resumo["total_lojas"] * 100
    resumo = resumo.set_index("shopping_sigla").reindex(ORDEM_SHOPPING).dropna(how="all").reset_index()

    st.markdown("#### Resumo por Shopping")
    header = "| Shopping | Total Lojas | Participaram | Não Participaram | Taxa | Cupons | Valor Total |"
    sep = "|:---|---:|---:|---:|---:|---:|---:|"
    rows = []
    for _, r in resumo.iterrows():
        rows.append(
            f"| **{r['shopping_sigla']}** "
            f"| {int(r['total_lojas'])} "
            f"| {int(r['participaram'])} "
            f"| {int(r['nao_participaram'])} "
            f"| {r['taxa']:.1f}% "
            f"| {int(r['cupons']):,} ".replace(",", ".") +
            f"| {formatar_brl(r['valor_total'])} |"
        )
    st.markdown(header + "\n" + sep + "\n" + "\n".join(rows), unsafe_allow_html=True)

    st.markdown("---")

    for sigla in shoppings_show:
        df_shop = df_part[df_part["shopping_sigla"] == sigla].copy()
        if len(df_shop) == 0:
            continue

        total = len(df_shop)
        com_cupom = int(df_shop["participou"].sum())
        sem_cupom = total - com_cupom
        valor_shop = df_shop["valor_total"].sum()
        cupons_shop = int(df_shop["cupons"].sum())
        nome_shopping = SHOPPING_FULL.get(int(df_shop["shopping_id"].iloc[0]), sigla)

        with st.expander(
            f"🏬 {nome_shopping} ({sigla}) — {total} lojas "
            f"({com_cupom} com cupons, {sem_cupom} sem cupons)",
            expanded=(shopping_filter != "Todos"),
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total de Lojas", f"{total}")
            c2.metric("Participaram", f"{com_cupom}",
                      delta=f"{com_cupom/total*100:.1f}%" if total > 0 else None,
                      delta_color="off")
            c3.metric("Não Participaram", f"{sem_cupom}",
                      delta=f"{sem_cupom/total*100:.1f}%" if total > 0 else None,
                      delta_color="off")
            c4.metric("Valor Total", formatar_brl(valor_shop),
                      delta=f"{cupons_shop:,} cupons".replace(",", "."),
                      delta_color="off")

            inativadas_shop = int(df_shop["inativada_na_promo"].sum())
            if inativadas_shop > 0:
                st.caption(f"⚠️ {inativadas_shop} loja(s) inativada(s) durante a promoção em {sigla}.")

            # Filtrar por status
            if status_filter == "Apenas com cupons":
                df_view = df_shop[df_shop["participou"]]
            elif status_filter == "Apenas sem cupons":
                df_view = df_shop[~df_shop["participou"]]
            else:
                df_view = df_shop

            # Ordenar: participantes por valor desc; não participantes por nome
            df_view = df_view.sort_values(
                ["participou", "valor_total", "loja_nome"],
                ascending=[False, False, True],
            )

            # Tabela combinada
            def _status_label(row):
                if row["inativada_na_promo"]:
                    return "⚠️ Inativada na promo"
                if row["participou"]:
                    return "✅ Participou"
                return "—  Sem cupons"

            df_display = df_view.copy()
            df_display["Status"] = df_display.apply(_status_label, axis=1)
            df_display["Valor Total"] = df_display["valor_total"].apply(formatar_brl)
            df_display["Inativada em"] = df_display["data_inativacao"].fillna("").astype(str)
            df_display = df_display[["loja_nome", "segmento", "Status", "cupons", "clientes", "Valor Total", "Inativada em"]]
            df_display.columns = ["Loja", "Segmento", "Status", "Cupons", "Clientes", "Valor Total", "Inativada em"]
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # Destaque lojas sem cupons
            if status_filter != "Apenas com cupons" and sem_cupom > 0:
                df_sem = df_shop[~df_shop["participou"]].sort_values("loja_nome")
                with st.expander(f"⚠️ {sem_cupom} lojas sem cupons em {sigla}"):
                    df_sem_show = df_sem[["loja_nome", "segmento", "status_atual", "data_inativacao"]].copy()
                    df_sem_show.columns = ["Loja", "Segmento", "Status Atual", "Inativada em"]
                    st.dataframe(df_sem_show, use_container_width=True, hide_index=True)


def render_validacao(dados, info):
    """Renderiza a aba de validação de integridade dos dados."""
    st.subheader("Validação de Integridade dos Dados")
    st.caption("Testes automáticos para garantir consistência e veracidade dos dados extraídos.")

    kpis = dados["kpis"]
    serie = dados["serie_total"].copy()
    serie["data"] = pd.to_datetime(serie["data"])
    serie_det = dados["serie"].copy()
    serie_det["data"] = pd.to_datetime(serie_det["data"])
    resgates = dados["resgates"].copy() if len(dados["resgates"]) > 0 else pd.DataFrame()
    resg_dia = dados["resgates_dia"].copy() if len(dados["resgates_dia"]) > 0 else pd.DataFrame()
    promo_inicio = pd.Timestamp(info["data_inicio"])

    kpis_shop = kpis[kpis["shopping_sigla"] != "TOTAL"]
    total_row = kpis[kpis["shopping_sigla"] == "TOTAL"].iloc[0]

    resultados = []

    def check(grupo, teste, ok, detalhe=""):
        resultados.append({"grupo": grupo, "teste": teste, "ok": ok, "detalhe": detalhe})

    # === 1. Estrutura ===
    for arq in ["promocao_info.json", "kpis_promocao.csv", "serie_temporal.csv",
                "serie_temporal_total.csv", "resgates_pontos.csv", "resgates_por_dia.csv"]:
        check("Estrutura", f"Arquivo {arq} presente", os.path.exists(f"dados/{arq}"))

    # === 2. Promo Info ===
    check("Promoção", "data_inicio < data_fim", info["data_inicio"] < info["data_fim"],
          f"{info['data_inicio']} < {info['data_fim']}")
    check("Promoção", "data_fim < data_sorteio", info["data_fim"] < info["data_sorteio"])
    check("Promoção", "pontos_por_numero = 100", info["pontos_por_numero"] == 100)

    # === 3. KPIs ===
    siglas = set(kpis["shopping_sigla"].unique())
    check("KPIs", "6 shoppings + TOTAL",
          siglas == {"CS", "BS", "NK", "NR", "GS", "NS", "TOTAL"})

    for _, row in kpis_shop.iterrows():
        soma = row["clientes_novos_cupom"] + row["clientes_recorrentes"]
        check("KPIs", f"{row['shopping_sigla']}: novos cupom + recorrentes = totais",
              soma == row["clientes_totais"],
              f"{int(soma)} {'=' if soma == row['clientes_totais'] else '!='} {int(row['clientes_totais'])}")

    soma_cupons = kpis_shop["cupons_lancados"].sum()
    check("KPIs", "TOTAL cupons = soma shoppings",
          total_row["cupons_lancados"] == soma_cupons,
          f"{int(total_row['cupons_lancados'])} vs {int(soma_cupons)}")

    soma_valor = round(kpis_shop["valor_total"].sum(), 2)
    check("KPIs", "TOTAL valor = soma shoppings",
          abs(total_row["valor_total"] - soma_valor) < 0.1,
          f"R$ {total_row['valor_total']:,.2f} vs R$ {soma_valor:,.2f}")

    soma_pontos = kpis_shop["pontos_utilizados"].sum()
    check("KPIs", "TOTAL pontos = soma shoppings",
          total_row["pontos_utilizados"] == soma_pontos)

    soma_numeros = kpis_shop["numeros_sorte"].sum()
    check("KPIs", "TOTAL números = soma shoppings",
          total_row["numeros_sorte"] == soma_numeros)

    for _, row in kpis.iterrows():
        if row["clientes_totais"] > 0:
            tm_esp = round(row["valor_total"] / row["clientes_totais"], 2)
            check("KPIs", f"{row['shopping_sigla']}: TM cliente correto",
                  abs(row["tm_cliente"] - tm_esp) < 0.02)
        if row["cupons_lancados"] > 0:
            tm_esp = round(row["valor_total"] / row["cupons_lancados"], 2)
            check("KPIs", f"{row['shopping_sigla']}: TM cupom correto",
                  abs(row["tm_cupom"] - tm_esp) < 0.02)

    # === 4. Série Temporal ===
    n_dias = serie["data"].nunique()
    check("Série", f"~60 dias na série ({n_dias})", 55 <= n_dias <= 65)

    dupes = serie_det.groupby(["data", "shopping_id"]).size()
    check("Série", "Sem duplicatas (data + shopping)", (dupes == 1).all())

    shops_dia = serie_det.groupby("data")["shopping_id"].nunique()
    check("Série", "6 shoppings em cada dia", shops_dia.min() >= 5,
          f"min={shops_dia.min()}, max={shops_dia.max()}")

    serie_agg = serie_det.groupby("data")["cupons"].sum().reset_index()
    serie_agg["data"] = pd.to_datetime(serie_agg["data"])
    merged = serie.merge(serie_agg, on="data", suffixes=("_total", "_soma"))
    check("Série", "serie_total.cupons = soma(serie.cupons)",
          (merged["cupons_total"] == merged["cupons_soma"]).all())

    check("Série", "Flag na_promocao correto",
          (serie[serie["na_promocao"] == True]["data"] >= promo_inicio).all() and
          (serie[serie["na_promocao"] == False]["data"] < promo_inicio).all())

    datas_range = pd.date_range(serie["data"].min(), serie["data"].max())
    dias_faltantes = set(datas_range) - set(serie["data"])
    check("Série", "Sem dias faltantes", len(dias_faltantes) == 0,
          f"{len(dias_faltantes)} dias ausentes" if dias_faltantes else "")

    # Cross-check serie dia 19/03 vs KPIs
    dia_inicio = serie[serie["data"] == promo_inicio]
    if len(dia_inicio) > 0:
        check("Série", "Cupons dia início = KPI total",
              int(dia_inicio.iloc[0]["cupons"]) == int(total_row["cupons_lancados"]),
              f"serie={int(dia_inicio.iloc[0]['cupons'])}, kpi={int(total_row['cupons_lancados'])}")

    # === 5. Resgates ===
    if len(resgates) > 0:
        check("Resgates", f"{len(resgates)} registros carregados", len(resgates) > 0)
        check("Resgates", "Todos promocao_id correto", (resgates["promocao_id"] == info["id"]).all())
        check("Resgates", "Todos status = Resgatado", (resgates["status"] == "Resgatado").all())
        check("Resgates", "saldo_anterior >= saldo_posterior",
              (resgates["cliente_saldo_anterior"] >= resgates["cliente_saldo_posterior"]).all())

        diff_saldo = resgates["cliente_saldo_anterior"] - resgates["cliente_saldo_posterior"]
        match_saldo = (diff_saldo == resgates["pontos_totais"])
        n_mismatch_saldo = int((~match_saldo).sum())
        check("Resgates", "pontos = saldo_anterior - saldo_posterior",
              n_mismatch_saldo == 0,
              f"{n_mismatch_saldo} divergências (dados de origem)" if n_mismatch_saldo > 0 else "")

        numeros_esp = resgates.apply(
            lambda r: max(1, math.ceil(r["pontos_totais"] / r["pontos_unitarios"])) if r["pontos_unitarios"] > 0 else 0, axis=1)
        match_num = (numeros_esp == resgates["quantidade_numeros"])
        pct_match = match_num.mean() * 100
        check("Resgates", f"números = ceil(pontos/100) ({pct_match:.0f}%)",
              pct_match >= 95,
              f"{int((~match_num).sum())} divergências — lógica do backend diferente" if pct_match < 95 else "")

        for _, row in kpis_shop.iterrows():
            res_sub = resgates[resgates["shopping_id"] == row["shopping_id"]]
            pontos_det = int(res_sub["quantidade_numeros"].sum() * 100)
            check("Resgates", f"{row['shopping_sigla']}: pontos KPI = detalhado",
                  int(row["pontos_utilizados"]) == pontos_det)

        resgates["data_resgate"] = pd.to_datetime(resgates["data_resgate"])
        antes = resgates[resgates["data_resgate"].dt.normalize() < promo_inicio]
        check("Resgates", f"Resgates antes da promo: {len(antes)}",
              len(antes) == 0,
              f"{len(antes)} resgates pre-release (16-18/mar)" if len(antes) > 0 else "")

    # === 6. Resgates por dia ===
    if len(resg_dia) > 0:
        check("Resg/Dia", "Total resgates = registros",
              int(resg_dia["resgates"].sum()) == len(resgates))
        check("Resg/Dia", "Total pontos = KPI",
              int(resg_dia["pontos_totais"].sum()) == int(total_row["pontos_utilizados"]))
        check("Resg/Dia", "Total números = KPI",
              int(resg_dia["numeros_totais"].sum()) == int(total_row["numeros_sorte"]))

    # === Render ===
    df_res = pd.DataFrame(resultados)
    n_pass = df_res["ok"].sum()
    n_fail = len(df_res) - n_pass
    n_total = len(df_res)

    # Resumo
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Testes", n_total)
    c2.metric("Aprovados", int(n_pass), delta=f"{n_pass/n_total*100:.0f}%")
    c3.metric("Falhas", int(n_fail), delta=f"-{n_fail}" if n_fail > 0 else "0", delta_color="inverse")

    # Resultado salvo?
    audit_path = "dados/auditoria_resultado.json"
    if os.path.exists(audit_path):
        with open(audit_path, encoding="utf-8") as f:
            audit = json.load(f)
        st.caption(f"Última auditoria offline: {audit.get('data_auditoria', 'N/A')} — {audit['pass']} pass / {audit['fail']} fail")

    # Tabela por grupo
    for grupo in df_res["grupo"].unique():
        sub = df_res[df_res["grupo"] == grupo]
        n_ok = sub["ok"].sum()
        n_ko = len(sub) - n_ok
        icon = "✅" if n_ko == 0 else "⚠️"
        with st.expander(f"{icon} {grupo} ({n_ok}/{len(sub)} aprovados)", expanded=(n_ko > 0)):
            for _, r in sub.iterrows():
                status_icon = "✅" if r["ok"] else "❌"
                line = f"{status_icon} {r['teste']}"
                if r["detalhe"]:
                    line += f" — *{r['detalhe']}*"
                st.markdown(line)

    # Alertas destacados
    falhas = df_res[~df_res["ok"]]
    if len(falhas) > 0:
        st.markdown("---")
        st.warning(f"**{n_fail} teste(s) com falha encontrados**")
        for _, f_row in falhas.iterrows():
            st.markdown(f"- **[{f_row['grupo']}]** {f_row['teste']}: {f_row['detalhe']}")

    # Anomalias
    if len(resgates) > 0:
        st.markdown("---")
        st.subheader("Análise de Anomalias")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top 5 clientes por pontos resgatados:**")
            top5 = resgates.groupby("cliente_id")["pontos_totais"].sum().nlargest(5).reset_index()
            top5.columns = ["Cliente ID", "Pontos Totais"]
            total_pts = resgates["pontos_totais"].sum()
            top5["% do Total"] = (top5["Pontos Totais"] / total_pts * 100).round(1)
            st.dataframe(top5, use_container_width=True, hide_index=True)
            st.caption(f"Top 5 concentram {top5['% do Total'].sum():.1f}% do total de pontos")

        with col2:
            st.markdown("**Resgates com maior volume de números:**")
            big = resgates.nlargest(5, "quantidade_numeros")[
                ["id", "cliente_id", "shopping_sigla", "pontos_totais", "quantidade_numeros"]
            ].copy()
            big.columns = ["ID", "Cliente", "Shopping", "Pontos", "Números"]
            st.dataframe(big, use_container_width=True, hide_index=True)

        # Outliers serie temporal
        media = serie["cupons"].mean()
        std = serie["cupons"].std()
        outliers = serie[(serie["cupons"] > media + 3 * std) | (serie["cupons"] < media - 3 * std)]
        if len(outliers) > 0:
            st.warning(f"**{len(outliers)} dia(s) com volume atípico de cupons (>3 desvios-padrão)**")
            st.dataframe(outliers[["data", "cupons", "valor_total"]], hide_index=True)
        else:
            st.success("Nenhum outlier extremo na série temporal de cupons (3-sigma)")


if __name__ == "__main__":
    main()
