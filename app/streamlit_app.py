import streamlit as st
import pandas as pd
import json
from pathlib import Path
from pyvis.network import Network
import tempfile

st.set_page_config(
    page_title="Mapa de IA — Pesquisadores Brasileiros",
    page_icon="🧠",
    layout="wide",
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_data
def load_data():
    researchers = pd.read_parquet(DATA_DIR / "clean" / "researchers_with_topics.parquet")
    articles = pd.read_parquet(DATA_DIR / "raw" / "sbc_articles.parquet")
    with open(DATA_DIR / "output" / "coauthorship.json") as f:
        graph_data = json.load(f)
    return researchers, articles, graph_data


researchers, articles, graph_data = load_data()

# ── Sidebar ──

st.sidebar.title("🧠 Mapa de IA")
st.sidebar.markdown("Pesquisadores brasileiros de IA — SBC Online Library")

topic_options = sorted(researchers["topic_name"].dropna().unique())
selected_topics = st.sidebar.multiselect(
    "Tópicos",
    options=topic_options,
    default=[],
)

min_articles = st.sidebar.slider(
    "Mínimo de artigos", min_value=1, max_value=20, value=1
)

search = st.sidebar.text_input("Buscar pesquisador", placeholder="Nome...")

# Aplicar filtros
mask = researchers["n_articles"] >= min_articles
if selected_topics:
    mask &= researchers["topic_name"].isin(selected_topics)
if search:
    mask &= researchers["display_name"].str.contains(search, case=False, na=False)

filtered = researchers[mask].copy()
st.sidebar.markdown(f"**{len(filtered)}** pesquisadores filtrados")

# ── Tabs ──

tab_map, tab_table, tab_topics, tab_stats, tab_articles = st.tabs(
    ["🗺️ Mapa", "📋 Pesquisadores", "📊 Tópicos", "📈 Estatísticas", "📄 Artigos"]
)

# ── Tab 1: Interactive Map ──

with tab_map:
    st.subheader("Grafo de Coautoria")

    col1, col2 = st.columns([3, 1])

    with col2:
        show_labels = st.checkbox("Mostrar nomes", value=False)
        node_size_by = st.radio(
            "Tamanho dos nós",
            options=["artigos", "coautorias"],
            index=0,
        )
        max_nodes = st.slider(
            "Máx. de pesquisadores no grafo",
            min_value=10, max_value=500, value=150, step=10,
        )

    with col1:
        # Mapear researcher names para os IDs do grafo
        node_ids = set(filtered["normalized_name"].tolist())
        degree_map = {}
        for node in graph_data["nodes"]:
            degree_map[node["id"]] = node["degree"]

        # Filtrar nós do grafo que estão nos pesquisadores filtrados
        # Pegar os top N por grau
        filtered_nodes = sorted(
            [n for n in graph_data["nodes"] if n["id"] in node_ids],
            key=lambda n: degree_map.get(n["id"], 0),
            reverse=True,
        )[:max_nodes]

        filtered_ids = {n["id"] for n in filtered_nodes}

        # Filtrar arestas entre os nós selecionados
        filtered_edges = [
            e for e in graph_data["edges"]
            if e["source"] in filtered_ids and e["target"] in filtered_ids
        ]

        if not filtered_edges or not filtered_nodes:
            st.info("Nenhum resultado com esses filtros. Tente aumentar o número de nós.")
        else:
            net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="#333333")

            # Adicionar nós
            for n in filtered_nodes:
                display = n.get("display_name", n["id"])
                size = min(
                    max(
                        degree_map.get(n["id"], 1) * 2,
                        10,
                    ),
                    80,
                )
                net.add_node(
                    n["id"],
                    label=display if show_labels else "",
                    title=f"{display}\nCoautorias: {degree_map.get(n['id'], 0)}",
                    size=size,
                    color="#4a90d9",
                )

            # Adicionar arestas (com peso)
            for e in filtered_edges:
                w = e.get("weight", 1)
                net.add_edge(e["source"], e["target"], value=w, width=min(w * 2, 10))

            net.set_options("""
            {
              "physics": {
                "barnesHut": {
                  "gravitationalConstant": -8000,
                  "springConstant": 0.002,
                  "springLength": 200
                },
                "minVelocity": 0.75,
                "timestep": 0.5
              },
              "interaction": {
                "hover": true,
                "tooltipDelay": 200
              }
            }
            """)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                net.save_graph(tmp.name)
                st.components.v1.html(open(tmp.name).read(), height=620, scrolling=True)

# ── Tab 2: Researcher Table ──

with tab_table:
    st.subheader("Pesquisadores")

    cols = ["display_name", "n_articles", "first_year", "last_year", "topic_name", "events", "affiliations"]
    display = filtered[cols].copy()
    display.columns = ["Nome", "Artigos", "Início", "Fim", "Tópico", "Eventos", "Afiliações"]
    display["Afiliações"] = display["Afiliações"].apply(
        lambda x: ", ".join(x[:3]) + ("..." if len(x) > 3 else "") if isinstance(x, list) else ""
    )
    display["Eventos"] = display["Eventos"].apply(
        lambda x: ", ".join(x[:5]) if isinstance(x, list) else str(x)
    )

    st.dataframe(
        display.sort_values("Artigos", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Artigos": st.column_config.NumberColumn(width=60),
            "Início": st.column_config.NumberColumn(width=50),
            "Fim": st.column_config.NumberColumn(width=50),
        },
    )

# ── Tab 3: Topics ──

with tab_topics:
    st.subheader("Distribuição por Tópico")

    topic_dist = (
        researchers[researchers["cluster"] != -1]
        .groupby("topic_name")
        .agg(
            pesquisadores=("normalized_name", "count"),
            artigos=("n_articles", "sum"),
        )
        .sort_values("pesquisadores", ascending=False)
        .reset_index()
    )
    topic_dist.columns = ["Tópico", "Pesquisadores", "Artigos"]

    st.bar_chart(topic_dist.set_index("Tópico")["Pesquisadores"])

    with st.expander("Ver tabela completa"):
        st.dataframe(topic_dist, use_container_width=True, hide_index=True)

# ── Tab 4: Statistics ──

with tab_stats:
    st.subheader("Estatísticas Gerais")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Pesquisadores", f"{len(researchers):,}")
    k2.metric("Artigos", f"{len(articles):,}")
    k3.metric("Eventos", articles["event_acronym"].nunique())
    k4.metric("Tópicos", researchers[researchers["cluster"] >= 0]["cluster"].nunique())

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Artigos por Ano")
        year_dist = articles["year"].value_counts().sort_index()
        st.bar_chart(year_dist)

    with col2:
        st.subheader("Artigos por Evento")
        event_dist = articles["event_acronym"].value_counts()
        st.bar_chart(event_dist)

# ── Tab 5: Articles ──

with tab_articles:
    st.subheader("Artigos Brutos")

    show_cols = ["title", "event_acronym", "year", "track"]
    with st.expander("Filtros", expanded=False):
        colf1, colf2, colf3 = st.columns(3)
        with colf1:
            filter_events = st.multiselect(
                "Evento", options=sorted(articles["event_acronym"].unique()), default=[]
            )
        with colf2:
            filter_years = st.multiselect(
                "Ano", options=sorted(articles["year"].dropna().unique(), reverse=True), default=[]
            )
        with colf3:
            filter_tracks = st.multiselect(
                "Track", options=sorted(articles["track"].dropna().unique()), default=[]
            )

    art_mask = pd.Series(True, index=articles.index)
    if filter_events:
        art_mask &= articles["event_acronym"].isin(filter_events)
    if filter_years:
        art_mask &= articles["year"].isin(filter_years)
    if filter_tracks:
        art_mask &= articles["track"].isin(filter_tracks)

    filtered_articles = articles[art_mask].copy()

    search_article = st.text_input("Buscar no título ou resumo", placeholder="Palavra-chave...")
    if search_article:
        masked = (
            filtered_articles["title"].str.contains(search_article, case=False, na=False)
            | filtered_articles["abstract"].str.contains(search_article, case=False, na=False)
        )
        filtered_articles = filtered_articles[masked]

    st.markdown(f"**{len(filtered_articles)}** artigos")

    display_articles = filtered_articles[["title", "event_acronym", "year", "track"]].copy()
    display_articles.columns = ["Título", "Evento", "Ano", "Track"]

    st.dataframe(
        display_articles.sort_values(["Ano", "Evento"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Ver detalhes de um artigo"):
        sel_title = st.selectbox(
            "Selecione um artigo",
            options=filtered_articles["title"].tolist(),
            index=None,
            placeholder="Escolha um título...",
        )
        if sel_title:
            row = filtered_articles[filtered_articles["title"] == sel_title].iloc[0]
            authors_list = row.get("authors", [])
            author_line = "; ".join(
                f"{a['name']} ({a['affiliation']})" if a.get("affiliation") else a["name"]
                for a in authors_list
            ) if isinstance(authors_list, list) else str(authors_list)

            st.markdown(f"**Título:** {row['title']}")
            st.markdown(f"**Autores:** {author_line}")
            st.markdown(f"**Evento:** {row['event_name']} ({row['event_acronym']})")
            st.markdown(f"**Ano:** {row['year']}  |  **Track:** {row.get('track', '—')}")
            st.markdown(f"**Páginas:** {row.get('pages', '—')}")
            if row.get("abstract"):
                st.markdown("**Resumo:**")
                st.write(row["abstract"])
            if row.get("pdf_url"):
                st.markdown(f"[📄 PDF]({row['pdf_url']})")
            if row.get("article_url"):
                st.markdown(f"[🔗 Artigo na SOL]({row['article_url']})")
