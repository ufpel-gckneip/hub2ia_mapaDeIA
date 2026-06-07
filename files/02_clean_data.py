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
# # 02 — Normalizar e Deduplicar
#
# Carregar os dados brutos, normalizar nomes dos autores (lowercase, remover
# acentos), deduplicar por correspondência exata e unificar todos os eventos.
#
# Saída: `data/clean/researchers.parquet` — um registro por pesquisador.

# %%
import pandas as pd
import unicodedata
import re
from pathlib import Path

# %%
DATA_DIR = Path("data")
RAW_FILE = DATA_DIR / "raw" / "sbc_articles.parquet"
CLEAN_DIR = DATA_DIR / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# %%
df = pd.read_parquet(RAW_FILE)
print(f"Carregados {len(df)} artigos, {df['event_acronym'].nunique()} eventos")

# %%
def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9 ]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def pick_display_name(groups: pd.Series) -> str:
    counts = groups.value_counts()
    return counts.index[0]


# %%
# Explodir autores: cada autor vira uma linha
rows = []
for _, row in df.iterrows():
    for author in row["authors"]:
        rows.append({
            "article_title": row["title"],
            "article_year": row["year"],
            "article_event": row["event_acronym"],
            "article_event_name": row["event_name"],
            "article_track": row["track"],
            "article_url": row["article_url"],
            "article_abstract": row["abstract"],
            "author_name": author.get("name", ""),
            "author_affiliation": author.get("affiliation"),
        })

exploded = pd.DataFrame(rows)
exploded["normalized_name"] = exploded["author_name"].apply(normalize_name)
print(f"Total de linhas (autor-artigo): {len(exploded)}")
print(f"Autores únicos (normalizados): {exploded['normalized_name'].nunique()}")

# %%
# Agrupar por nome normalizado
def consolidate(group):
    return {
        "normalized_name": group.name,
        "display_name": pick_display_name(group["author_name"]),
        "affiliations": list(group["author_affiliation"].dropna().unique()),
        "n_articles": len(group),
        "first_year": group["article_year"].min(),
        "last_year": group["article_year"].max(),
        "events": sorted(group["article_event"].unique().tolist()),
        "articles": group.apply(lambda r: {
            "title": r["article_title"],
            "year": int(r["article_year"]),
            "event": r["article_event"],
            "event_name": r["article_event_name"],
            "track": r["article_track"],
            "url": r["article_url"],
            "abstract": r["article_abstract"],
        }, axis=1).tolist(),
    }


researchers = exploded.groupby("normalized_name", sort=False).apply(
    consolidate, include_groups=False
).tolist()

researchers_df = pd.DataFrame(researchers)
researchers_df = researchers_df.sort_values("n_articles", ascending=False).reset_index(drop=True)

print(f"\nTotal de pesquisadores: {len(researchers_df)}")
print(f"Média de artigos/pesquisador: {researchers_df['n_articles'].mean():.2f}")
print(f"Máx: {researchers_df['n_articles'].max()}")

# %%
researchers_df.to_parquet(CLEAN_DIR / "researchers.parquet")
print(f"\nSalvo em {CLEAN_DIR / 'researchers.parquet'}")
researchers_df.head()
