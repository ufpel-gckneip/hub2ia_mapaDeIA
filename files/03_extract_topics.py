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
# # 03 — Extração de Tópicos via NLP
#
# Usar `sentence-transformers` com o modelo `all-MiniLM-L6-v2` para embedar
# títulos + resumos de cada pesquisador e agrupar por similaridade semântica.
#
# Pipeline:
# 1. Concatenar títulos + resumos por pesquisador
# 2. Gerar embeddings com SentenceTransformer
# 3. Reduzir dimensionalidade com UMAP
# 4. Clusterizar com HDBSCAN
# 5. Extrair palavras representativas por cluster (TF-IDF)
# 6. Salvar DataFrame com tópicos

# %%
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import umap
import hdbscan
from sklearn.feature_extraction.text import TfidfVectorizer
from pathlib import Path

# %%
DATA_DIR = Path("data")
CLEAN_FILE = DATA_DIR / "clean" / "researchers.parquet"
OUTPUT_FILE = DATA_DIR / "clean" / "researchers_with_topics.parquet"

df = pd.read_parquet(CLEAN_FILE)
print(f"Carregados {len(df)} pesquisadores")

# %%
# Concatenar títulos + resumos de todos os artigos de cada pesquisador
texts = []
for _, row in df.iterrows():
    parts = []
    for a in row["articles"]:
        title = (a.get("title") or "").strip()
        abstract = (a.get("abstract") or "").strip()
        parts.append(f"{title}. {abstract}")
    texts.append(" ".join(parts))

df["text"] = texts
print(f"Textos criados. Comprimento médio: {np.mean([len(t.split()) for t in texts]):.0f} palavras")

# %%
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Modelo carregado. Gerando embeddings...")

embeddings = model.encode(
    texts,
    show_progress_bar=True,
    batch_size=64,
    normalize_embeddings=True,
)
print(f"Embeddings: {embeddings.shape}")

# %%
# Reduzir dimensionalidade para clustering
reducer = umap.UMAP(n_components=10, metric="cosine", random_state=42, n_jobs=1)
reduced = reducer.fit_transform(embeddings)
print(f"Reduzido: {reduced.shape}")

# %%
# Clusterizar com HDBSCAN
clusterer = hdbscan.HDBSCAN(
    min_cluster_size=10,
    metric="euclidean",
    cluster_selection_epsilon=0.5,
    prediction_data=True,
)
cluster_labels = clusterer.fit_predict(reduced)
n_clusters = len(set(cluster_labels) - {-1})
n_noise = (cluster_labels == -1).sum()
print(f"Clusterização: {n_clusters} clusters + {n_noise} pontos de ruído")

# %%
# Extrair tópicos: TF-IDF por cluster
def extract_topics(texts_by_cluster, top_n=5):
    cluster_ids = sorted(texts_by_cluster.keys())
    corpus = [" ".join(texts_by_cluster[cid]) for cid in cluster_ids]
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=5000,
        ngram_range=(1, 2),
    )
    tfidf = vec.fit_transform(corpus)
    feature_names = vec.get_feature_names_out()

    topics = {}
    for i, cid in enumerate(cluster_ids):
        scores = tfidf[i].toarray().flatten()
        top_indices = scores.argsort()[-top_n:][::-1]
        keywords = [feature_names[idx] for idx in top_indices if scores[idx] > 0]
        topics[cid] = keywords
    return topics


df["cluster"] = cluster_labels
texts_by_cluster = {
    cid: df[df["cluster"] == cid]["text"].tolist()
    for cid in sorted(set(cluster_labels))
}
topics = extract_topics(texts_by_cluster, top_n=5)

# Mapear cluster_id → tópico
topic_names = {}
for cid, keywords in topics.items():
    if cid == -1:
        topic_names[cid] = "Outros"
    else:
        topic_names[cid] = ", ".join(keywords[:3])

df["topic_keywords"] = df["cluster"].map(
    lambda c: topics.get(c, [])
)
df["topic_name"] = df["cluster"].map(topic_names)

# %%
print("\nTópicos encontrados:")
for cid, name in sorted(topic_names.items()):
    n = (df["cluster"] == cid).sum()
    label = "RUÍDO" if cid == -1 else f"Cluster {cid}"
    print(f"  {label:12s} ({n:4d}) → {name}")

# %%
drop_cols = ["text"]
out = df.drop(columns=[c for c in drop_cols if c in df.columns])
out.to_parquet(OUTPUT_FILE)
print(f"\nSalvo em {OUTPUT_FILE}")
out.head()
