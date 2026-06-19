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
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

LOG_DIR = Path("logs/03_extract_topics")
LOG_DIR.mkdir(parents=True, exist_ok=True)
_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_fh = logging.FileHandler(LOG_DIR / f"{_timestamp}.txt", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_fh)

# %%
DATA_DIR = Path("data")
CLEAN_FILE = DATA_DIR / "clean" / "researchers.parquet"
OUTPUT_FILE = DATA_DIR / "clean" / "researchers_with_topics.parquet"

df = pd.read_parquet(CLEAN_FILE)
print(f"Carregados {len(df)} pesquisadores")
log.info("Carregados %d pesquisadores", len(df))

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
log.info("Textos criados. Comprimento médio: %.0f palavras", np.mean([len(t.split()) for t in texts]))

# %%
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Modelo carregado. Gerando embeddings...")
log.info("Modelo carregado. Gerando embeddings...")

embeddings = model.encode(
    texts,
    show_progress_bar=True,
    batch_size=64,
    normalize_embeddings=True,
)
print(f"Embeddings: {embeddings.shape}")
log.info("Embeddings: %s", embeddings.shape)

# %%
# Reduzir dimensionalidade para clustering
reducer = umap.UMAP(n_components=10, metric="cosine", random_state=42, n_jobs=1)
reduced = reducer.fit_transform(embeddings)
print(f"Reduzido: {reduced.shape}")
log.info("Reduzido UMAP: %s", reduced.shape)

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
log.info("Clusterização: %d clusters + %d pontos de ruído", n_clusters, n_noise)

# %%
# Extrair tópicos: TF-IDF por cluster
PT_STOPWORDS = [
    "a", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo",
    "as", "até", "com", "como", "da", "das", "de", "dela", "delas", "dele",
    "deles", "depois", "do", "dos", "e", "ela", "elas", "ele", "eles",
    "em", "entre", "era", "eram", "essa", "essas", "esse", "esses", "esta",
    "estamos", "estas", "estava", "estavam", "este", "esteja", "estejam",
    "estes", "esteve", "estivemos", "estiver", "estivera", "estiveram",
    "estivesse", "estivessem", "estou", "eu", "foi", "fomos", "for",
    "fora", "foram", "forem", "fosse", "fossem", "haja", "hajam", "hão",
    "isso", "isto", "já", "lhe", "lhes", "lo", "mas", "me", "mesmo",
    "meu", "meus", "minha", "minhas", "muita", "muitas", "muito", "muitos",
    "na", "não", "nas", "nem", "nenhum", "nessa", "nessas", "nesta", "nestas",
    "ninguém", "no", "nos", "nós", "nossa", "nossas", "nosso", "nossos",
    "num", "numa", "numas", "nuns", "o", "os", "ou", "para", "pela", "pelas",
    "pelo", "pelos", "pode", "podem", "podendo", "poder", "poderia",
    "poderiam", "pois", "por", "porém", "porque", "posso", "pouca", "poucas",
    "pouco", "poucos", "primeiro", "próprio", "quais", "qual", "quando",
    "quanto", "quantos", "que", "quem", "são", "se", "seja", "sejam", "sem",
    "sempre", "sendo", "ser", "será", "serão", "seria", "seriam", "seu",
    "seus", "si", "sido", "só", "sob", "sobre", "suas", "tal", "também",
    "tampouco", "tais", "tanto", "te", "tem", "temos", "tendo", "tenha",
    "tenham", "ter", "teu", "teus", "teve", "tive", "tivemos", "tiver",
    "tivera", "tiveram", "tivesse", "tivessem", "to", "tu", "tua", "tuas",
    "tudo", "um", "uma", "umas", "uns", "você", "vocês", "vós",
]

def extract_topics(texts_by_cluster, top_n=5):
    cluster_ids = sorted(texts_by_cluster.keys())
    corpus = [" ".join(texts_by_cluster[cid]) for cid in cluster_ids]
    vec = TfidfVectorizer(
        stop_words=PT_STOPWORDS,
        max_features=1000,
        ngram_range=(1, 2),
        max_df=0.8,
    )
    tfidf = vec.fit_transform(corpus)
    feature_names = vec.get_feature_names_out()

    topics = {}
    for i, cid in enumerate(cluster_ids):
        scores = tfidf[i].toarray().flatten()
        top_indices = scores.argsort()[-top_n:][::-1]
        keywords = [
            (feature_names[idx], float(scores[idx]))
            for idx in top_indices if scores[idx] > 0
        ]
        topics[cid] = keywords
    return topics


def assign_unique_topic_names(topics_with_scores):
    from collections import defaultdict

    word_best_cluster = {}
    for cid, kw_scores in topics_with_scores.items():
        for kw, score in kw_scores:
            if kw not in word_best_cluster or score > word_best_cluster[kw][1]:
                word_best_cluster[kw] = (cid, score)

    cluster_words = defaultdict(list)
    for word, (cid, _) in word_best_cluster.items():
        cluster_words[cid].append(word)

    topic_names = {}
    for cid, words in cluster_words.items():
        topic_names[cid] = words[0]

    return topic_names


df["cluster"] = cluster_labels
texts_by_cluster = {
    cid: df[df["cluster"] == cid]["text"].tolist()
    for cid in sorted(set(cluster_labels))
}
topics = extract_topics(texts_by_cluster, top_n=5)

# Mapear cluster_id → tópico (palavra única por cluster)
topic_names = assign_unique_topic_names(topics)
topic_names[-1] = "Outros"

df["topic_keywords"] = df["cluster"].map(
    lambda c: [kw for kw, _ in topics.get(c, [])]
)
df["topic_name"] = df["cluster"].map(topic_names)

# %%
print("\nTópicos encontrados:")
for cid, name in sorted(topic_names.items()):
    n = (df["cluster"] == cid).sum()
    label = "RUÍDO" if cid == -1 else f"Cluster {cid}"
    print(f"  {label:12s} ({n:4d}) → {name}")
    log.info("  %-12s (%4d) → %s", label, n, name)

# %%
drop_cols = ["text"]
out = df.drop(columns=[c for c in drop_cols if c in df.columns])
out.to_parquet(OUTPUT_FILE)
print(f"\nSalvo em {OUTPUT_FILE}")
log.info("Salvo em %s", OUTPUT_FILE)
out.head()
