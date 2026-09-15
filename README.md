# Mapa de IA

[![CI](https://github.com/ufpel-gckneip/hub2ia_mapaDeIA/actions/workflows/ci.yml/badge.svg)](https://github.com/ufpel-gckneip/hub2ia_mapaDeIA/actions/workflows/ci.yml)

Mapa interativo de pesquisadores brasileiros de Inteligência Artificial. Os dados
são extraídos da [SBC Online Library](https://sol.sbc.org.br) (BRACIS, ENIAC,
SBRC, SIBGRAPI e outros eventos), consolidados por pesquisador, agrupados por
tópico via NLP, geolocalizados por instituição e servidos em uma aplicação web.

O projeto tem **duas partes**:

1. **Pipeline de dados** (Python) — crawling → limpeza → tópicos → exploração →
   geocoding → carga no banco. Roda ocasionalmente e produz artefatos.
2. **Aplicação web** (Postgres + FastAPI + SvelteKit) — serve os dados de forma
   interativa: mapa demográfico, grafo de coautoria, tabelas, contas de usuário e
   analytics.

```
Pipeline (Python)                         Aplicação web (self-hosted)
 01 crawl → 05 geocode ──► data/*  ──►  06_load_db ──► Postgres + PostGIS
                                                            │
                                                            ▼
                                        FastAPI (REST + auth JWT + tracking)
                                                            │  /api /auth /users
                                                            ▼
                                        SvelteKit SPA (Caddy) — MapLibre + deck.gl,
                                                            Sigma.js
```

## Como rodar

- **Local (para testar):** veja [`LOCAL.md`](LOCAL.md) — em resumo, com Docker:
  `make up && make load`, depois abra http://localhost.
- **Produção (self-hosted):** veja [`DEPLOY.md`](DEPLOY.md).
- **Detalhes técnicos:** veja [`DOCUMENTATION.md`](DOCUMENTATION.md).
- **Pipeline de dados:** veja [`docs/pipeline.md`](docs/pipeline.md).

## Funcionalidades da aplicação

- **🗺️ Mapa Demográfico** — um marcador por **universidade** (dimensionado pelo nº
  de pesquisadores); clicar expande os autores em torno do campus (spider), com
  linhas até o centro e painel de detalhes por autor. Coropleth por estado e
  **arcos de coautoria** selecionáveis entre **estados**, **universidades** ou
  **autores**, com filtro por força mínima.
- **🕸️ Mapa de Coautoria** — grafo completo (~8,9k nós / ~23k arestas) renderizado
  com Sigma.js, com corte por grau mínimo.
- **📋 Pesquisadores / 📄 Artigos** — tabelas filtráveis e busca full-text.
- **📊 Tópicos / 📈 Estatísticas** — distribuições e KPIs.
- **Contas + LGPD** — registro/login (JWT), buscas salvas, favoritos, e analytics
  de uso anônimas com banner de consentimento.
- **🛠️ Admin** — painel para superusuários (usuários, eventos de analytics).

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Pipeline | Python, `requests` + BeautifulSoup, `sentence-transformers`, UMAP, HDBSCAN, NetworkX |
| Banco | PostgreSQL + PostGIS |
| Backend | FastAPI, SQLAlchemy, Alembic, fastapi-users (JWT) |
| Frontend | SvelteKit, MapLibre GL + deck.gl (mapa), Sigma.js (grafo) |
| Deploy | Docker Compose, Caddy (TLS + SPA + proxy) |

## Estrutura

```
MapaDeIA/
├── files/            # pipeline (01–05) + 06_load_db.py (carga no Postgres)
├── backend/          # FastAPI: app/ (models, routers, auth) + alembic/
├── frontend/         # SvelteKit SPA
├── data/             # artefatos do pipeline (git-ignored)
├── docs/pipeline.md  # detalhes do pipeline
├── docker-compose.yml + Makefile
├── LOCAL.md · DEPLOY.md · DOCUMENTATION.md
```

## Dados (medidos)

3.597 artigos · 12 eventos · 2007–2025 · 8.898 pesquisadores · 165 tópicos ·
grafo de 8.898 nós / ~23k arestas · ~93% geolocalizados.
