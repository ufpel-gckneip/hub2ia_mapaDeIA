# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 04 — Exploração dos Dados
#
# Análise exploratória: estatísticas descritivas, ranking de pesquisadores,
# distribuição por tópico, nuvem de palavras, grafo de coautoria e exportação
# para visualização interativa.

# %%
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from wordcloud import WordCloud
from collections import Counter
from pathlib import Path
import json
import logging
from datetime import datetime
import unicodedata
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

LOG_DIR = Path("logs/04_explore")
LOG_DIR.mkdir(parents=True, exist_ok=True)
_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_fh = logging.FileHandler(LOG_DIR / f"{_timestamp}.txt", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_fh)

plt.rcParams.update({
    "figure.dpi": 120,
    "font.size": 10,
})

# %%
DATA_DIR = Path("data")
CLEAN_DIR = DATA_DIR / "clean"
RAW_DIR = DATA_DIR / "raw"
OUT_DIR = DATA_DIR / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

researchers = pd.read_parquet(CLEAN_DIR / "researchers_with_topics.parquet")
articles_raw = pd.read_parquet(RAW_DIR / "sbc_articles.parquet")
print(f"Pesquisadores: {len(researchers)}")
print(f"Artigos brutos: {len(articles_raw)}")
log.info("Pesquisadores: %d", len(researchers))
log.info("Artigos brutos: %d", len(articles_raw))

# %%
# ── 1. Estatísticas descritivas ──

print("=" * 50)
print("ESTATÍSTICAS DESCRITIVAS")
print("=" * 50)

print(f"\nArtigos por pesquisador:")
print(f"  Média:  {researchers['n_articles'].mean():.2f}")
print(f"  Mediana: {researchers['n_articles'].median():.1f}")
print(f"  Máx:    {researchers['n_articles'].max()}")
print(f"  ≥5 artigos: {(researchers['n_articles'] >= 5).sum()} pesquisadores")
print(f"  ≥10 artigos: {(researchers['n_articles'] >= 10).sum()} pesquisadores")
log.info("Artigos por pesquisador — Média: %.2f, Mediana: %.1f, Máx: %d, ≥5: %d, ≥10: %d",
         researchers["n_articles"].mean(), researchers["n_articles"].median(),
         researchers["n_articles"].max(), (researchers["n_articles"] >= 5).sum(),
         (researchers["n_articles"] >= 10).sum())

print(f"\nEventos:")
event_counts = articles_raw["event_acronym"].value_counts()
for evt, cnt in event_counts.items():
    print(f"  {evt:12s} {cnt:5d} artigos")
    log.info("Evento %s: %d artigos", evt, cnt)

print(f"\nAnos ({articles_raw['year'].min()}–{articles_raw['year'].max()}):")
year_counts = articles_raw["year"].value_counts().sort_index()
for yr, cnt in year_counts.items():
    print(f"  {yr}: {cnt}")
    log.info("Ano %d: %d artigos", yr, cnt)

# %%
# ── 2. Gráficos ──

fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# (a) Artigos por pesquisador (distribuição)
ax = axes[0, 0]
bins = [1, 2, 3, 4, 5, 10, 20, 50, 100]
researchers["n_articles"].plot.hist(
    bins=bins, ax=ax, edgecolor="white", color="steelblue"
)
ax.set_xlabel("Artigos")
ax.set_ylabel("Pesquisadores")
ax.set_title("Distribuição de produtividade")

# (b) Artigos por ano
ax = axes[0, 1]
year_counts.plot.bar(ax=ax, color="coral", width=0.8)
ax.set_xlabel("Ano")
ax.set_ylabel("Artigos")
ax.set_title("Artigos por ano")
ax.tick_params(axis="x", rotation=45)

# (c) Top 15 pesquisadores
ax = axes[1, 0]
top15 = researchers.head(15)
ax.barh(
    range(len(top15)),
    top15["n_articles"],
    color="seagreen",
)
ax.set_yticks(range(len(top15)))
ax.set_yticklabels([n[:25] for n in top15["display_name"]])
ax.set_xlabel("Artigos")
ax.set_title("Top 15 pesquisadores")
ax.invert_yaxis()

# (d) Top 15 tópicos
ax = axes[1, 1]
topic_sizes = (
    researchers[researchers["cluster"] != -1]
    .groupby("topic_name")
    .size()
    .sort_values(ascending=False)
    .head(15)
)
ax.barh(range(len(topic_sizes)), topic_sizes.values, color="purple")
ax.set_yticks(range(len(topic_sizes)))
ax.set_yticklabels([t[:30] for t in topic_sizes.index])
ax.set_xlabel("Pesquisadores")
ax.set_title("Top 15 tópicos de pesquisa")
ax.invert_yaxis()

plt.tight_layout()
plt.savefig(OUT_DIR / "overview.png", dpi=150)
plt.show()
print(f"Gráfico salvo: {OUT_DIR / 'overview.png'}")
log.info("Gráfico salvo: %s", OUT_DIR / "overview.png")

# %%
# ── 3. Nuvem de palavras (títulos) ──

all_titles = " ".join(str(t) for t in articles_raw["title"].dropna())

wc = WordCloud(
    width=1200,
    height=600,
    background_color="white",
    max_words=200,
    collocations=False,
    stopwords={"using", "based", "para", "com", "uma", "dos", "das", "em", "de", "da", "um", "e"},
).generate(all_titles)

plt.figure(figsize=(14, 7))
plt.imshow(wc, interpolation="bilinear")
plt.axis("off")
plt.title("Nuvem de palavras — Títulos dos artigos", fontsize=14)
plt.savefig(OUT_DIR / "wordcloud_titles.png", dpi=150)
plt.show()
print(f"Nuvem salva: {OUT_DIR / 'wordcloud_titles.png'}")
log.info("Nuvem salva: %s", OUT_DIR / "wordcloud_titles.png")

# %%
# ── 4. Grafo de coautoria ──

G = nx.Graph()

# Nós: todos os autores normalizados (mesma normalização de 02_clean_data.py)
def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9 ]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

norm_map = {}
for _, row in articles_raw.iterrows():
    for author in row["authors"]:
        name = author.get("name", "").strip()
        if name:
            norm = normalize_name(name)
            norm_map[name] = norm
            if norm not in G:
                G.add_node(norm, display_name=name)

# Arestas: coautoria no mesmo artigo
edges = Counter()
for _, row in articles_raw.iterrows():
    authors = [a.get("name", "").strip() for a in row["authors"] if a.get("name")]
    norms = [norm_map.get(a, a.lower()) for a in authors]
    # Conectar todos os pares
    for i in range(len(norms)):
        for j in range(i + 1, len(norms)):
            if norms[i] != norms[j]:
                pair = tuple(sorted([norms[i], norms[j]]))
                edges[pair] += 1

# ADICIONAR arestas (com pesos)
for (u, v), w in edges.items():
    G.add_edge(u, v, weight=w)

print(f"Grafo de coautoria:")
print(f"  Nós:     {G.number_of_nodes()}")
print(f"  Arestas: {G.number_of_edges()}")
log.info("Grafo: %d nós, %d arestas", G.number_of_nodes(), G.number_of_edges())

# Estatísticas do grafo
degrees = [d for _, d in G.degree()]
print(f"  Grau médio: {np.mean(degrees):.2f}")
print(f"  Grau máximo: {max(degrees)}")

# Componentes conectados
components = list(nx.connected_components(G))
print(f"  Componentes: {len(components)}")
largest = max(components, key=len)
print(f"  Maior componente: {len(largest)} nós")

# Top 10 hubs
top_hubs = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:10]
print(f"\nTop 10 pesquisadores por número de coautorias:")
for node, degree in top_hubs:
    display = G.nodes[node].get("display_name", node)
    print(f"  {degree:4d} coautorias — {display}")
    log.info("Top coautor: %4d — %s", degree, display)

# %%
# ── 5. Visualizar o grafo (versão reduzida) ──

# Subgrafo: apenas nós com grau ≥ threshold
threshold = 5
sub_nodes = [n for n, d in G.degree() if d >= threshold]
sub = G.subgraph(sub_nodes).copy()

print(f"Subgrafo (grau ≥ {threshold}): {sub.number_of_nodes()} nós, {sub.number_of_edges()} arestas")
log.info("Subgrafo (grau ≥ %d): %d nós, %d arestas", threshold, sub.number_of_nodes(), sub.number_of_edges())

plt.figure(figsize=(16, 12))
pos = nx.spring_layout(sub, k=0.3, seed=42, iterations=50)
nx.draw_networkx_nodes(sub, pos, node_size=20, node_color="steelblue", alpha=0.7)
nx.draw_networkx_edges(sub, pos, alpha=0.15, width=0.5)
top30 = [node for node, _ in sorted(sub.degree(), key=lambda x: x[1], reverse=True)[:30]]
labels = {
    n: sub.nodes[n].get("display_name", n)[:20]
    for n in top30
}
nx.draw_networkx_labels(sub, pos, labels, font_size=6)
plt.title(f"Grafo de coautoria (grau ≥ {threshold})")
plt.axis("off")
plt.savefig(OUT_DIR / "coauthorship_graph.png", dpi=150)
plt.show()
print(f"Grafo salvo: {OUT_DIR / 'coauthorship_graph.png'}")
log.info("Grafo salvo: %s", OUT_DIR / "coauthorship_graph.png")

# %%
# ── 6. Exportar para visualização interativa ──

# GEXF para Gephi
gexf_path = OUT_DIR / "coauthorship.gexf"
nx.write_gexf(G, gexf_path)
print(f"GEXF exportado: {gexf_path}")
log.info("GEXF exportado: %s", gexf_path)

# JSON para web (com layout pré-computado)
edges_data = []
for u, v, d in G.edges(data=True):
    edges_data.append({
        "source": u,
        "target": v,
        "weight": d.get("weight", 1),
    })

pos = nx.spring_layout(G, k=0.3, seed=42, iterations=50)

nodes_data = []
for n, attr in G.nodes(data=True):
    x, y = pos.get(n, (0.0, 0.0))
    nodes_data.append({
        "id": n,
        "display_name": attr.get("display_name", n),
        "degree": G.degree(n),
        "x": float(x),
        "y": float(y),
    })

graph_json = {"nodes": nodes_data, "edges": edges_data}
json_path = OUT_DIR / "coauthorship.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(graph_json, f, ensure_ascii=False, indent=2)
print(f"JSON exportado: {json_path}")
log.info("JSON exportado: %s", json_path)

# Dados dos pesquisadores para o mapa interativo
researchers_json = []
for _, r in researchers.iterrows():
    researchers_json.append({
        "id": r["normalized_name"],
        "name": r["display_name"],
        "n_articles": int(r["n_articles"]),
        "first_year": int(r["first_year"]),
        "last_year": int(r["last_year"]),
        "events": list(r["events"]),
        "affiliations": list(r["affiliations"]),
        "topic": r["topic_name"] if r["cluster"] >= 0 else None,
        "topic_keywords": list(r["topic_keywords"]) if r["cluster"] >= 0 else [],
    })

json_path2 = OUT_DIR / "researchers.json"
with open(json_path2, "w", encoding="utf-8") as f:
    json.dump(researchers_json, f, ensure_ascii=False, indent=2)
print(f"Pesquisadores exportados: {json_path2} ({len(researchers_json)} registros)")
log.info("Pesquisadores exportados: %s (%d registros)", json_path2, len(researchers_json))

# %%
print("\nTodos os arquivos exportados:")
for f in sorted(OUT_DIR.glob("*")):
    size = f.stat().st_size
    print(f"  {f.name:40s} {size:>8,} bytes")
    log.info("Exportado: %s (%d bytes)", f.name, size)
