# Pipeline — Mapa de IA

Pipeline de 4 etapas: **crawling → limpeza → tópicos → exploração**.

## 01_crawl_sbc.py — Crawlear a SBC Online Library

Extrai metadados de artigos científicos de eventos de IA na [SBC Online Library](https://sol.sbc.org.br).

1. Descobre edições (anos) de cada evento via `/issue/archive`
2. Lista artigos de cada edição via `/issue/view/{id}`
3. Extrai metadados (título, autores, abstract, ano, evento, track, páginas, PDF) das `<meta>` tags em `/article/view/{id}`
4. Salva checkpoint por evento em `data/raw/sbc_articles.parquet`

**Saída:** `data/raw/sbc_articles.parquet` — um registro por artigo.

---

## 02_clean_data.py — Normalizar e Deduplicar

Agrupa artigos por autor, normaliza nomes e deduplica.

1. **Explode autores** — cada autor vira uma linha
2. **Normaliza nomes** — lowercase, remove acentos, remove caracteres especiais
3. **Agrupa por `normalized_name`** — consolida artigos, eventos, afiliações, anos
4. **Salva** `data/clean/researchers.parquet`

**Saída:** `data/clean/researchers.parquet` — um registro por pesquisador.

---

## 03_extract_topics.py — Extração de Tópicos via NLP

Agrupa pesquisadores por similaridade semântica dos seus trabalhos usando `sentence-transformers`.

1. **Concatena** títulos + resumos de todos os artigos de cada pesquisador
2. **Embeddings** com SentenceTransformer (`all-MiniLM-L6-v2`)
3. **Redução** de dimensionalidade com UMAP (384 → 10 dimensões)
4. **Clusterização** com HDBSCAN (mín. 10 pesquisadores por cluster)
5. **Extração de palavras-chave** por cluster via TF-IDF (top 5 unigramas/bigramas)
6. **Salva** `data/clean/researchers_with_topics.parquet`

**Saída:** `data/clean/researchers_with_topics.parquet` — pesquisadores com cluster e tópico.

---

## 04_explore.py — Exploração dos Dados

Análise exploratória, grafos e exportação para visualização interativa.

1. **Estatísticas descritivas** — artigos/pesquisador, eventos, anos
2. **Gráficos 2×2** — distribuição de produtividade, artigos por ano, top 15 pesquisadores, top 15 tópicos
3. **Nuvem de palavras** — títulos dos artigos
4. **Grafo de coautoria** — nós = autores, arestas = coautoria no mesmo artigo (com pesos)
5. **Subgrafo** — apenas nós com grau ≥ 5 para visualização
6. **Exportações:**
   - `overview.png` — gráficos
   - `wordcloud_titles.png` — nuvem de palavras
   - `coauthorship_graph.png` — grafo reduzido
   - `coauthorship.gexf` — grafo completo para Gephi
   - `coauthorship.json` — grafo com layout para web
   - `researchers.json` — dados dos pesquisadores para mapa interativo

**Saída:** `data/output/` — PNGs, GEXF, JSONs.

---

## 05_geocode.py — Georreferenciar Instituições

Mapeia as afiliações institucionais dos pesquisadores para coordenadas geográficas (lat/lng).

1. **Carrega** `data/clean/researchers_with_topics.parquet`
2. **Extrai** todas as afiliações únicas (1314 no total)
3. **Consulta dicionário estático** de ~500 instituições brasileiras e internacionais conhecidas
4. **Fuzzy matching** para nomes completos (ex: "Universidade Federal de Minas Gerais" → UFMG)
5. **Fallback opcional** para Nominatim (OpenStreetMap) se a afiliação não for encontrada no dicionário
6. **Salva** `data/output/institutions_geo.json` (cache de coordenadas) e `data/output/researchers_geo.json` (pesquisadores com localização + tópico)

**Saída:** `data/output/researchers_geo.json` — ~8293 pesquisadores geolocalizados (93% do total).
