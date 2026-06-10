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
def load_data(_cache_key: str):
    researchers = pd.read_parquet(DATA_DIR / "clean" / "researchers_with_topics.parquet")
    articles = pd.read_parquet(DATA_DIR / "raw" / "sbc_articles.parquet")
    with open(DATA_DIR / "output" / "coauthorship.json") as f:
        graph_data = json.load(f)
    return researchers, articles, graph_data


_cache_key = str(
    (DATA_DIR / "raw" / "sbc_articles.parquet").stat().st_mtime
)
researchers, articles, graph_data = load_data(_cache_key)

# Handle pending topic selection from topic network tab
if "pending_topic" in st.session_state:
    st.session_state["topic_sync"] = [st.session_state.pop("pending_topic")]

# ── Sidebar ──

st.sidebar.title("🧠 Mapa de IA")
st.sidebar.markdown("Pesquisadores brasileiros de IA — SBC Online Library")

topic_options = sorted(researchers["topic_name"].dropna().unique())
selected_topics = st.sidebar.multiselect(
    "Tópicos",
    options=topic_options,
    default=st.session_state.get("topic_sync", []),
    key="topic_sync",
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

tab_topicnet, tab_map, tab_table, tab_topics, tab_stats, tab_articles = st.tabs(
    ["🗺️ Mapa", "🗺️ Mapa de Coautoria", "📋 Pesquisadores", "📊 Tópicos", "📈 Estatísticas", "📄 Artigos"]
)

# ── Tab 1: Topic Network ──

with tab_topicnet:
    st.subheader("Rede de Tópicos")

    researcher_topic = (
        researchers[researchers["cluster"] >= 0]
        .set_index("normalized_name")["topic_name"]
        .to_dict()
    )

    topic_counts = (
        researchers[researchers["cluster"] >= 0]["topic_name"]
        .value_counts()
        .to_dict()
    )

    topic_weights = {}
    for e in graph_data["edges"]:
        t1 = researcher_topic.get(e["source"])
        t2 = researcher_topic.get(e["target"])
        if t1 and t2 and t1 != t2:
            pair = tuple(sorted([t1, t2]))
            topic_weights[pair] = topic_weights.get(pair, 0) + 1

    palette = [
        "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
        "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
        "#469990", "#dcbeff", "#9a6324", "#800000", "#aaffc3",
        "#808000", "#ffd8b1", "#000075", "#a9a9a9",
    ]
    topics_sorted = sorted(topic_counts.keys())
    topic_colors = {t: palette[i % len(palette)] for i, t in enumerate(topics_sorted)}

    net = Network(height="500px", width="100%", bgcolor="#ffffff", font_color="#333333")

    for topic in topics_sorted:
        count = topic_counts[topic]
        net.add_node(
            topic,
            label=topic,
            size=min(max(count * 0.15, 15), 60),
            title=f"{topic}\n{count} pesquisadores",
            color=topic_colors[topic],
        )

    for (t1, t2), w in sorted(topic_weights.items(), key=lambda x: -x[1]):
        net.add_edge(
            t1, t2,
            value=min(w * 0.3, 10),
            width=min(w * 0.3, 8),
            title=f"{w} coautorias entre tópicos",
        )

    net.set_options("""
    {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -3000,
          "springConstant": 0.005,
          "springLength": 200
        },
        "minVelocity": 0.75,
        "timestep": 0.5
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 200
      },
      "edges": {
        "color": {"inherit": true},
        "smooth": false
      }
    }
    """)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        st.components.v1.html(open(tmp.name).read(), height=520, scrolling=True)

    st.divider()
    st.markdown("### Selecionar Tópico")
    st.caption("Clique em um tópico para filtrar o Mapa de Coautoria")

    cols_per_row = 4
    for i in range(0, len(topics_sorted), cols_per_row):
        row_topics = topics_sorted[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, topic in zip(cols, row_topics):
            with col:
                if st.button(topic, use_container_width=True, key=f"tbtn_{topic}"):
                    st.session_state["pending_topic"] = topic
                    st.rerun()

    if st.session_state.get("topic_sync"):
        st.info(f"Tópico ativo: {st.session_state['topic_sync'][0]}")

# ── Tab 2: Coauthorship Map ──

with tab_map:
    st.subheader("Mapa de Coautoria")

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
            min_value=10, max_value=len(researchers), value=150, step=10,
        )

    with col1:
        degree_map = {node["id"]: node["degree"] for node in graph_data["nodes"]}
        adjacency = {}
        for e in graph_data["edges"]:
            adjacency.setdefault(e["source"], set()).add(e["target"])
            adjacency.setdefault(e["target"], set()).add(e["source"])

        # -- Montar conjunto de IDs para o grafo --
        if search:
            # Pool de pesquisadores que passam topic + min_articles (gate)
            base_mask = researchers["n_articles"] >= min_articles
            if selected_topics:
                base_mask &= researchers["topic_name"].isin(selected_topics)
            pool_ids = set(researchers[base_mask]["normalized_name"])

            # Pesquisador(es) buscado(s)
            searched_ids = set(filtered["normalized_name"].tolist())

            # Coautores dos buscados que também passam topic/articles
            coauthor_ids = set()
            for s_id in searched_ids:
                coauthor_ids.update(adjacency.get(s_id, set()) & pool_ids)

            candidate_ids = searched_ids | coauthor_ids
        else:
            candidate_ids = set(filtered["normalized_name"].tolist())

        # Ordenar candidatos por grau
        sorted_nodes = sorted(
            [n for n in graph_data["nodes"] if n["id"] in candidate_ids],
            key=lambda n: degree_map.get(n["id"], 0),
            reverse=True,
        )

        # Top N pelo slider
        filtered_nodes = sorted_nodes[:max_nodes]

        # Garantir que o pesquisador buscado esteja presente
        if search:
            existing_ids = {n["id"] for n in filtered_nodes}
            missing = [n for n in sorted_nodes if n["id"] in searched_ids and n["id"] not in existing_ids]
            filtered_nodes.extend(missing)

        filtered_ids = {n["id"] for n in filtered_nodes}

        # Filtrar arestas entre os nós selecionados
        filtered_edges = [
            e for e in graph_data["edges"]
            if e["source"] in filtered_ids and e["target"] in filtered_ids
        ]

        if not filtered_edges or not filtered_nodes:
            st.info("Nenhum resultado com esses filtros. Tente aumentar o número de nós.")
        else:
            THRESHOLD = 500
            use_physics = len(filtered_nodes) < THRESHOLD
            has_positions = "x" in filtered_nodes[0]

            if not use_physics:
                st.caption(f"⚙️ Physics desligado ({len(filtered_nodes)} nós) — reduza o slider para ativar interatividade")

            net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="#333333")

            # Adicionar nós
            for n in filtered_nodes:
                display = n.get("display_name", n["id"])
                size = min(
                    max(degree_map.get(n["id"], 1) * 2, 10),
                    80,
                )
                kwargs = dict(
                    label=display if show_labels else "",
                    title=f"{display}\nCoautorias: {degree_map.get(n['id'], 0)}",
                    size=size,
                    color="#4a90d9",
                )
                if not use_physics and has_positions:
                    kwargs["x"] = float(n["x"])
                    kwargs["y"] = float(n["y"])
                    kwargs["fixed"] = True
                net.add_node(n["id"], **kwargs)

            # Adicionar arestas (com peso)
            for e in filtered_edges:
                w = e.get("weight", 1)
                net.add_edge(e["source"], e["target"], value=w, width=min(w * 2, 10))

            net.set_options(f"""
            {{
              "physics": {{
                "enabled": {str(use_physics).lower()},
                "barnesHut": {{
                  "gravitationalConstant": -8000,
                  "springConstant": 0.002,
                  "springLength": 200
                }},
                "minVelocity": 0.75,
                "timestep": 0.5
              }},
              "interaction": {{
                "hover": true,
                "tooltipDelay": 200
              }}
            }}
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

    display_articles = filtered_articles[
        ["title", "event_acronym", "year", "track", "article_url"]
    ].copy()
    display_articles.columns = ["Título", "Evento", "Ano", "Track", "_url"]
    display_articles = display_articles.sort_values(
        ["Ano", "Evento"], ascending=[False, True]
    ).reset_index(drop=True)

    selection = st.dataframe(
        display_articles[["Título", "Evento", "Ano", "Track"]],
        on_select="rerun",
        selection_mode="single-row",
        use_container_width=True,
        hide_index=True,
    )

    st.caption("Clique em uma linha para ver detalhes do artigo.")

    if selection and selection.selection and selection.selection.rows:
        row_idx = selection.selection.rows[0]
        sel_url = display_articles.iloc[row_idx]["_url"]
        row = filtered_articles[filtered_articles["article_url"] == sel_url].iloc[0]

        st.divider()
        authors_list = row.get("authors", [])
        author_line = "; ".join(
            f"{a['name']} ({a['affiliation']})" if a.get("affiliation") else a["name"]
            for a in authors_list
        ) if isinstance(authors_list, list) else str(authors_list)

        st.markdown(f"### {row['title']}")
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


