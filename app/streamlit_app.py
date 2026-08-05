import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
from pathlib import Path
import tempfile
import networkx as nx
from pyvis.network import Network
import plotly.graph_objects as go
import plotly.io as pio
import math
import folium
from folium.plugins import MarkerCluster
from collections import defaultdict, Counter
import requests

st.set_page_config(
    page_title="Mapa de IA — Pesquisadores Brasileiros",
    page_icon="🧠",
    layout="wide",
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DATA_RELEASE_URL = "https://github.com/ufpel-gckneip/hub2ia_mapaDeIA/releases/download/data-v1"
REQUIRED_DATA_FILES = [
    "raw/sbc_articles.parquet",
    "clean/researchers_with_topics.parquet",
    "output/coauthorship.json",
    "output/researchers_geo.json",
    "brazil_states.geojson",
]


@st.cache_resource
def ensure_data_files():
    session = requests.Session()
    session.headers.update({"User-Agent": "mapa-de-ia-streamlit-app"})
    for rel_path in REQUIRED_DATA_FILES:
        dest = DATA_DIR / rel_path
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"{DATA_RELEASE_URL}/{Path(rel_path).name}"
        last_error = None
        for attempt in range(3):
            try:
                response = session.get(url, timeout=120)
                response.raise_for_status()
                dest.write_bytes(response.content)
                break
            except requests.RequestException as exc:
                last_error = exc
        else:
            raise RuntimeError(
                f"Falha ao baixar {url} após 3 tentativas: {last_error}"
            ) from last_error


ensure_data_files()


STATE_ABBR_TO_NAME = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
    "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}

NAME_TO_STATE_ABBR = {v: k for k, v in STATE_ABBR_TO_NAME.items()}


@st.cache_data
def load_data(_cache_key: str):
    researchers = pd.read_parquet(DATA_DIR / "clean" / "researchers_with_topics.parquet")
    articles = pd.read_parquet(DATA_DIR / "raw" / "sbc_articles.parquet")
    with open(DATA_DIR / "output" / "coauthorship.json") as f:
        graph_data = json.load(f)
    with open(DATA_DIR / "output" / "researchers_geo.json") as f:
        researchers_geo = json.load(f)
    with open(DATA_DIR / "brazil_states.geojson") as f:
        brazil_states = json.load(f)
    return researchers, articles, graph_data, researchers_geo, brazil_states


_cache_key = str(
    (DATA_DIR / "raw" / "sbc_articles.parquet").stat().st_mtime
)
researchers, articles, graph_data, researchers_geo, brazil_states = load_data(_cache_key)

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

tab_geomap, tab_map, tab_table, tab_topics, tab_stats, tab_articles = st.tabs(
    ["🗺️ Mapa Demográfico", "🗺️ Mapa de Coautoria", "📋 Pesquisadores", "📊 Tópicos", "📈 Estatísticas", "📄 Artigos"]
)

# ── Tab 1: Topic Network ──

with tab_geomap:
    st.subheader("Mapa Demográfico de Pesquisadores")

    with st.expander("⚙️ Filtros do mapa", expanded=False):
        show_edges = st.checkbox("Mostrar interações entre estados", value=True)
        edge_min_weight = st.slider("Força mín. de interação", min_value=1, max_value=20, value=3)
        max_markers = st.slider("Máx. pesquisadores", min_value=100, max_value=8000, value=3000, step=100)
        map_dark = st.toggle("🌙 Mapa escuro", value=False)
    # Filter researchers_geo by sidebar filters
    filtered_geo = [r for r in researchers_geo if r["n_articles"] >= min_articles]
    if selected_topics:
        filtered_geo = [r for r in filtered_geo if r.get("topic_name") in selected_topics]
    if search:
        filtered_geo = [r for r in filtered_geo if search.lower() in r["display_name"].lower()]

    # Limit markers
    filtered_geo = filtered_geo[:max_markers]

    if not filtered_geo:
        st.info("Nenhum pesquisador encontrado com esses filtros.")
    else:
        # Build topic name -> color palette
        palette = [
            "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
            "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
            "#469990", "#dcbeff", "#9a6324", "#800000", "#aaffc3",
            "#808000", "#ffd8b1", "#000075", "#a9a9a9", "#e6beff",
            "#1a1a1a", "#ff7f7f", "#7fff7f", "#7f7fff", "#ffff7f",
        ]
        all_topics_in_view = sorted(set(r.get("topic_name") or "Sem tópico" for r in filtered_geo))
        topic_color = {t: palette[i % len(palette)] for i, t in enumerate(all_topics_in_view)}

        # ── Compute state aggregates ──
        state_counts = Counter()
        state_articles = Counter()
        state_topics = defaultdict(Counter)
        state_institutions = defaultdict(Counter)
        for r in filtered_geo:
            st_abbr = r.get("state", "")
            if st_abbr in STATE_ABBR_TO_NAME:
                state_counts[st_abbr] += 1
                state_articles[st_abbr] += r["n_articles"]
                t = r.get("topic_name")
                if t:
                    state_topics[st_abbr][t] += 1
                inst = r.get("primary_affiliation", "")
                if inst:
                    state_institutions[st_abbr][inst] += 1

        # ── Folium map ──
        tile = "CartoDB dark_matter" if map_dark else "CartoDB positron"
        m = folium.Map(location=[-14.235, -51.925], zoom_start=4, tiles=tile)

        # ── State polygon layer ──
        max_state_count = max(state_counts.values()) if state_counts else 1

        # Enrich GeoJSON features with aggregate data
        state_geojson_enriched = json.loads(json.dumps(brazil_states))
        for feature in state_geojson_enriched["features"]:
            name = feature["properties"]["name"]
            abbr = NAME_TO_STATE_ABBR.get(name, "")
            count = state_counts.get(abbr, 0)
            articles_sum = state_articles.get(abbr, 0)
            top_ts = state_topics[abbr].most_common(5)
            top_insts = state_institutions[abbr].most_common(5)
            feature["properties"]["count"] = count
            feature["properties"]["articles"] = articles_sum
            feature["properties"]["top_topics"] = ", ".join(f"{t} ({c})" for t, c in top_ts)
            feature["properties"]["top_insts"] = ", ".join(f"{i} ({c})" for i, c in top_insts)

        def state_style(feature):
            count = feature["properties"].get("count", 0)
            if count == 0:
                fill_color = "#f0f0f0"
            else:
                intensity = min(count / max_state_count, 1.0)
                r_val = int(255 * (1 - intensity))
                g_val = int(255 * (1 - intensity * 0.3))
                fill_color = f"#{r_val:02x}{g_val:02x}ff"
            return {
                "fillColor": fill_color,
                "color": "#555",
                "weight": 1.5,
                "fillOpacity": 0.5,
            }

        folium.GeoJson(
            state_geojson_enriched,
            style_function=state_style,
            highlight_function=lambda _: {"weight": 3, "color": "#333", "fillOpacity": 0.6},
            tooltip=folium.GeoJsonTooltip(
                fields=["name", "count"],
                aliases=["Estado:", "Pesquisadores:"],
                style="font-size:13px;",
            ),
            popup=folium.GeoJsonPopup(
                fields=["name", "count", "articles", "top_topics", "top_insts"],
                aliases=["Estado:", "Pesquisadores:", "Artigos:", "Top tópicos:", "Top instituições:"],
                style="font-size:13px; min-width:220px;",
                localize=True,
            ),
        ).add_to(m)

        # ── Click-to-zoom on state polygons ──
        map_name = m.get_name()
        zoom_js = f"""
            <script>
            (function() {{
                var stateLayer = null;
                {map_name}.eachLayer(function(layer) {{
                    if (layer instanceof L.GeoJSON && !stateLayer) {{
                        stateLayer = layer;
                    }}
                }});
                if (stateLayer) {{
                    stateLayer.eachLayer(function(feature) {{
                        feature.on('click', function(e) {{
                            {map_name}.fitBounds(e.target.getBounds(), {{padding: [30, 30]}});
                        }});
                    }});
                }}
            }})();
            </script>
            """
        m.get_root().html.add_child(folium.Element(zoom_js))

        # ── MarkerCluster for performance ──
        marker_cluster = MarkerCluster().add_to(m)

        for r in filtered_geo:
            topic = r.get("topic_name") or "Sem tópico"
            color = topic_color.get(topic, "#888888")
            popup_text = f"""
                <b>{r['display_name']}</b><br>
                Artigos: {r['n_articles']}<br>
                Tópico: {topic}<br>
                Instituição: {r.get('primary_affiliation', '—')}<br>
                Cidade: {r.get('city', '—')} / {r.get('state', '—')}
                """
            folium.CircleMarker(
                location=[r["lat"], r["lng"]],
                radius=8 + min(r["n_articles"], 20) * 1.2,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=r["display_name"],
            ).add_to(marker_cluster)

        def bezier_curve(lat1, lng1, lat2, lng2, curvature=0.12, n=40):
            pts = []
            for i in range(n + 1):
                t = i / n
                a = (1 - t) ** 2
                b = 2 * (1 - t) * t
                c = t ** 2
                mx, my = (lat1 + lat2) / 2, (lng1 + lng2) / 2
                dx, dy = lat2 - lat1, lng2 - lng1
                d = math.hypot(dx, dy)
                if d < 1e-12:
                    pts.append([mx, my])
                    continue
                nx, ny = -dy / d, dx / d
                cx, cy = mx + nx * curvature * d, my + ny * curvature * d
                lat = a * lat1 + b * cx + c * lat2
                lng = a * lng1 + b * cy + c * lng2
                pts.append([lat, lng])
            return pts

        # ── Interaction edges ──
        if show_edges and len(filtered_geo) > 1:
            filtered_ids = set(r["normalized_name"] for r in filtered_geo)
            r_state = {r["normalized_name"]: r.get("state") for r in filtered_geo}

            state_interactions = Counter()
            for e in graph_data["edges"]:
                s, t = e["source"], e["target"]
                if s in filtered_ids and t in filtered_ids:
                    ss = r_state.get(s)
                    stt = r_state.get(t)
                    if ss and stt and ss != stt and ss in STATE_ABBR_TO_NAME and stt in STATE_ABBR_TO_NAME:
                        pair = tuple(sorted([ss, stt]))
                        state_interactions[pair] += e.get("weight", 1)

            state_centroids = {}
            state_lats = defaultdict(list)
            state_lngs = defaultdict(list)
            for r in filtered_geo:
                s = r.get("state")
                if s in STATE_ABBR_TO_NAME:
                    state_lats[s].append(r["lat"])
                    state_lngs[s].append(r["lng"])
            for s in state_lats:
                state_centroids[s] = (
                    sum(state_lats[s]) / len(state_lats[s]),
                    sum(state_lngs[s]) / len(state_lngs[s]),
                )

            for edge_idx, ((s1, s2), w) in enumerate(state_interactions.most_common(50)):
                if w >= edge_min_weight:
                    if s1 in state_centroids and s2 in state_centroids:
                        lat1, lng1 = state_centroids[s1]
                        lat2, lng2 = state_centroids[s2]
                        name1 = STATE_ABBR_TO_NAME.get(s1, s1)
                        name2 = STATE_ABBR_TO_NAME.get(s2, s2)
                        opacity = min(w / 20, 0.8)
                        sign = 1 if edge_idx % 2 == 0 else -1
                        pts = bezier_curve(lat1, lng1, lat2, lng2, curvature=0.12 * sign)
                        folium.PolyLine(
                            locations=pts,
                            color="#e74c3c",
                            weight=min(w * 0.4, 6),
                            opacity=opacity,
                            tooltip=f"{name1} ↔ {name2}: {w} coautorias",
                            popup=f"{name1}<br>↔<br>{name2}<br>{w} coautorias",
                        ).add_to(m)

        # ── Legend via HTML ──
        topic_legend_items = []
        for t in all_topics_in_view[:30]:
            c = topic_color.get(t, "#888")
            topic_legend_items.append(
                f'<li><span style="background:{c};display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:6px;"></span>{t}</li>'
            )
        legend_html = f"""
            <div style="position:absolute;z-index:999;bottom:20px;left:20px;background:white;padding:10px;border-radius:6px;box-shadow:0 0 8px rgba(0,0,0,0.15);max-height:300px;overflow-y:auto;font-size:12px;max-width:250px;">
                <b>Tópicos</b>
                <ul style="list-style:none;padding:0;margin:4px 0 0 0;">
                {"".join(topic_legend_items)}
                </ul>
                <span style="color:#888;font-size:10px;">mostrando até 30 tópicos</span>
            </div>
            """
        m.get_root().html.add_child(folium.Element(legend_html))

        # Save map to HTML and render
        map_html = m.get_root().render()
        components.html(map_html, height=860, scrolling=True)

        st.caption(f"{len(filtered_geo)} pesquisadores no mapa • Estados coloridos por densidade • Círculos = pesquisadores • Linhas = coautorias entre estados • Clique no estado para zoom")

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


