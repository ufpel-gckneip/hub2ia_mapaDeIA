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
# # 01 — Crawlear a SBC Online Library
#
# Extrair títulos, autores, resumo, evento e ano de todos os
# anais de eventos relacionados à IA disponíveis na
# [SBC Online Library](https://sol.sbc.org.br).
#
# ## Estratégia
#
# 1. Para cada evento da lista de IA, descobrir edições (anos) em `/issue/archive`
# 2. Para cada edição, listar artigos em `/issue/view/{id}`
# 3. Para cada artigo, extrair metadados das `<meta>` tags em `/article/view/{id}`
#
# Metadados extraídos via tags no `<head>`:
# - `citation_title`, `citation_author`, `citation_author_institution`
# - `citation_date`, `citation_conference`
# - `citation_firstpage`, `citation_lastpage`
# - `citation_pdf_url`
# - `DC.Description` (abstract)
# - `DC.Type.articleType` (track/section)

# %%
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

LOG_DIR = Path("logs/01_crawl_sbc")
LOG_DIR.mkdir(parents=True, exist_ok=True)
_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_fh = logging.FileHandler(LOG_DIR / f"{_timestamp}.txt", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_fh)

# %%
BASE_URL = "https://sol.sbc.org.br"
HEADERS = {
    "User-Agent": "MapaDeIA/1.0 (research crawler; +https://github.com/gckneip/MapaDeIA)",
}

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Eventos relacionados à IA na SOL
EVENTS = [
    # Conferências
    ("bracis",     "Brazilian Conference on Intelligent Systems"),
    ("kdmile",     "Symposium on Knowledge Discovery, Mining and Learning"),
    ("sbrlars",    "Brazilian/Latin American Robotics Symposium"),
    ("stil",       "Symposium on Brazilian Information Technology and Human Language"),
    ("sibgrapi",   "Conference on Graphics, Patterns and Images"),
    ("laai-ethics","Latin American Conference on Ethics in AI"),
    # Workshops
    ("eniac",      "Encontro Nacional de Inteligência Artificial e Computacional"),
    ("bwaif",      "Brazilian Workshop on Artificial Intelligence in Finance"),
    ("wvc",        "Workshop sobre Visão Computacional"),
    ("wesaac",     "Workshop-Escola sobre Agentes, Ambientes e Aplicações"),
    ("safelife",   "Workshop on Safety, Security, and Privacy in Complex AI based Systems"),
    ("weriaedu",   "Workshop de Ética e Regulação em Inteligência Artificial na Educação"),
]

# %%
def fetch_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def discover_editions(acronym):
    url = f"{BASE_URL}/index.php/{acronym}/issue/archive"
    soup = fetch_soup(url)
    editions = []
    # OJS archive page: <ul class="issues_archive"> → <div class="obj_issue_summary"> → <a class="title">
    for a in soup.select(".obj_issue_summary a.title"):
        href = a.get("href", "")
        label = a.get_text(strip=True)
        year_match = re.search(r"^(\d{4})", label)
        year = int(year_match.group(1)) if year_match else None
        editions.append({
            "acronym": acronym,
            "year": year,
            "label": label,
            "url": href if href.startswith("http") else BASE_URL + href,
        })
    # Paginação no archive: <div class="cmp_pagination">
    pagination = soup.select_one(".cmp_pagination")
    if pagination:
        for a in soup.select(".cmp_pagination a"):
            page_url = a.get("href", "")
            if page_url and page_url != "#":
                full_url = page_url if page_url.startswith("http") else BASE_URL + page_url
                page_soup = fetch_soup(full_url)
                for a2 in page_soup.select(".obj_issue_summary a.title"):
                    href2 = a2.get("href", "")
                    label2 = a2.get_text(strip=True)
                    year_match2 = re.search(r"^(\d{4})", label2)
                    year2 = int(year_match2.group(1)) if year_match2 else None
                    editions.append({
                        "acronym": acronym,
                        "year": year2,
                        "label": label2,
                        "url": href2 if href2.startswith("http") else BASE_URL + href2,
                    })
    # Deduplicar por URL
    seen = set()
    unique = []
    for e in editions:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)
    unique.sort(key=lambda e: e["year"] or 0, reverse=True)
    log.info("  → %d edições encontradas para %s", len(unique), acronym)
    return unique


def discover_articles(edition_url, section_name=None):
    soup = fetch_soup(edition_url)
    articles = []
    for section_div in soup.select("div.section"):
        h2 = section_div.find("h2")
        current_section = h2.get_text(strip=True) if h2 else (section_name or "Geral")
        for summary in section_div.select("div.obj_article_summary"):
            title_el = summary.select_one("div.title a")
            if not title_el:
                continue
            href = title_el["href"]
            articles.append({
                "title": title_el.get_text(strip=True),
                "url": href if href.startswith("http") else BASE_URL + href,
                "section": current_section,
            })
    return articles


def scrape_article_meta(article_url, event_acronym, event_name, year, section):
    soup = fetch_soup(article_url)
    meta = soup.find("head") or soup

    def m(name):
        tag = meta.find("meta", attrs={"name": name})
        return tag["content"] if tag else None

    # Autores + afiliações (pareadas por índice)
    author_tags = meta.find_all("meta", attrs={"name": "citation_author"})
    affiliation_tags = meta.find_all("meta", attrs={"name": "citation_author_institution"})
    authors = []
    for i, atag in enumerate(author_tags):
        aff = affiliation_tags[i]["content"] if i < len(affiliation_tags) else None
        authors.append({"name": atag["content"].strip(), "affiliation": aff})

    # Data → ano
    date_str = m("citation_date") or ""
    year_meta = int(date_str[:4]) if len(date_str) >= 4 else year

    abstract_tag = meta.find("meta", attrs={"name": "DC.Description"})
    abstract = abstract_tag["content"] if abstract_tag else None

    track_tag = meta.find("meta", attrs={"name": "DC.Type.articleType"})
    track = track_tag["content"] if track_tag else section

    return {
        "title": m("citation_title") or "",
        "authors": authors,
        "abstract": abstract,
        "event_acronym": event_acronym,
        "event_name": event_name,
        "year": year_meta,
        "track": track,
        "pages": f"{m('citation_firstpage') or '?'}–{m('citation_lastpage') or '?'}",
        "pdf_url": m("citation_pdf_url"),
        "article_url": article_url,
        "issn": m("citation_issn"),
    }


# %%
def crawl_all():
    all_articles = []

    for acronym, full_name in EVENTS:
        log.info("[%s] %s", acronym, full_name)

        editions = discover_editions(acronym)
        if not editions:
            log.warning("  ⚠ Nenhuma edição encontrada")
            continue

        for ed in editions:
            log.info("  [%s/%s] %s", acronym, ed["year"], ed["label"])
            try:
                article_refs = discover_articles(ed["url"])
            except Exception as e:
                log.error("  ✗ Erro ao listar artigos: %s", e)
                continue

            if not article_refs:
                log.warning("  ⚠ Nenhum artigo listado")
                continue

            for ref in article_refs:
                try:
                    meta = scrape_article_meta(
                        ref["url"], acronym, full_name, ed["year"], ref["section"]
                    )
                    all_articles.append(meta)
                except Exception as e:
                    log.error("  ✗ Erro ao extrair %s: %s", ref["url"], e)

            log.info("  ✓ %d artigos extraídos", len(article_refs))

        # Salvar checkpoint após cada evento
        if all_articles:
            df = pd.DataFrame(all_articles)
            df.to_parquet(DATA_DIR / "sbc_articles.parquet")
            log.info("Checkpoint salvo: %d artigos no total", len(df))

    return pd.DataFrame(all_articles)


# %%
df = crawl_all()
print(f"\nTotal: {len(df)} artigos")
log.info("Total: %d artigos", len(df))
df.head()

# %%
df.to_parquet(DATA_DIR / "sbc_articles.parquet")
print(f"Salvo em {DATA_DIR / 'sbc_articles.parquet'}")
log.info("Salvo em %s", DATA_DIR / "sbc_articles.parquet")
