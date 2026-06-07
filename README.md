# Mapa de IA

Mapa de pesquisadores brasileiros de Inteligência Artificial, extraindo dados da
[SBC Online Library](https://sol.sbc.org.br) (BRACIS, ENIAC, SBRC e outros
eventos) e posteriormente do Lattes.

## Stack

- Python scripts com células (`# %%`)
- `requests` + `BeautifulSoup` para crawling
- `sentence-transformers` para extração semântica de tópicos
- NetworkX + Plotly para visualização

## Plano de Execução

### Scripts

| # | Script | Descrição |
|---|--------|-----------|
| 1 | `01_crawl_sbc.py` | **Crawlear a SBC Online Library** — percorrer anais de eventos SBC relacionados à IA (BRACIS, ENIAC, KDMile, etc.), extraindo título, autores, resumo, evento e ano via `<meta>` tags do HTML |
| 2 | `02_clean_data.py` | **Normalizar e deduplicar** — correspondência exata por nome normalizado (lowercase, sem acentos); unificar dados de todos os eventos |
| 3 | `03_extract_topics.py` | **Extração de tópicos via NLP** — usar `sentence-transformers` (`all-MiniLM-L6-v2`) para embedar títulos + resumos de cada pesquisador, reduzir dimensionalidade com UMAP e clusterizar com HDBSCAN. Gera 168 clusters temáticos (ex: "multi-agent systems", "computer vision", "NLP", "robotics") |
| 4 | `04_explore.py` | **Exploração dos dados** — estatísticas descritivas, gráficos de distribuição, nuvem de palavras dos títulos, grafo de coautoria (9k nós, 23k arestas), exportação para Gephi (GEXF) e web (JSON) |

### Decisões Tomadas

| Item | Decisão |
|------|---------|
| **Escopo inicial** | Apenas SBC Online Library (eventos relacionados à IA). Lattes fica para depois. |
| **Crawler** | Breadth-first: descobrir edições → listar artigos → extrair metadados de `<meta>` tags no HTML de cada artigo. Sem delay inicial — adicionado apenas se o site retornar 429. |
| **Eventos-alvo** | BRACIS, KDMile, SBR/LARS, STIL, SIBGRAPI, LAAI-Ethics, ENIAC, BWAIF, WVC, WESAAC, SAFELIFE, WER-IAEdu |
| **Deduplicação** | Exata por nome normalizado. Fuzzy pode ser adicionado depois para comparação. |
| **NLP** | `sentence-transformers` com `all-MiniLM-L6-v2` — gratuito, roda em CPU, boa qualidade semântica. |
| **Saída** | DataFrame + grafo simples por enquanto. Mapa interativo será implementado em etapa futura. |

### Estrutura de Arquivos

```
MapaDeIA/
├── README.md
├── requirements.txt
├── files/
│   ├── 01_crawl_sbc.py              # Crawler da SOL
│   ├── 02_clean_data.py             # Limpeza e deduplicação
│   ├── 03_extract_topics.py         # NLP e clusterização
│   └── 04_explore.py                # Análise exploratória
├── data/
│   ├── raw/
│   │   └── sbc_articles.parquet     # 3.596 artigos crus
│   ├── clean/
│   │   ├── researchers.parquet      # 8.895 pesquisadores (deduplicados)
│   │   └── researchers_with_topics.parquet  # + clusters e tópicos
│   └── output/
│       ├── overview.png              # Gráficos de distribuição
│       ├── wordcloud_titles.png      # Nuvem de palavras
│       ├── coauthorship_graph.png    # Grafo de coautoria
│       ├── coauthorship.gexf         # Grafo para Gephi
│       ├── coauthorship.json         # Grafo para web
│       └── researchers.json          # Pesquisadores para web
```

## Crawler — Detalhes Técnicos

O script `01_crawl_sbc.py` implementa um crawler breadth-first para a
[SBC Online Library](https://sol.sbc.org.br) (SOL), que roda sobre
[Open Journal Systems (OJS)](https://pkp.sfu.ca/ojs/).

### Pipeline

```
EVENTS (lista fixa de 12 eventos AI)
  └─ discover_editions()
       └─ /index.php/{event}/issue/archive → lista de edições/anos
            └─ discover_articles()
                 └─ /index.php/{event}/issue/view/{id} → lista de artigos
                      └─ scrape_article_meta()
                           └─ /index.php/{event}/article/view/{id}
                                └─ metadados extraídos de <meta> tags no <head>
```

### Metadados extraídos

De `<meta>` tags no `<head>` de cada página de artigo:

| Tag | Campo |
|-----|-------|
| `citation_title` | Título |
| `citation_author` + `citation_author_institution` | Autores e afiliações |
| `citation_date` | Data de publicação (ano) |
| `citation_conference` | Nome do evento |
| `citation_firstpage` / `citation_lastpage` | Páginas |
| `citation_pdf_url` | URL do PDF |
| `DC.Description` | Resumo (abstract) |
| `DC.Type.articleType` | Trilha/Seção |

### Saída

`data/raw/sbc_articles.parquet` com colunas:
`title`, `authors` (lista de {name, affiliation}), `abstract`,
`event_acronym`, `event_name`, `year`, `track`, `pages`,
`pdf_url`, `article_url`, `issn`

Checkpoint salvo após cada evento — permite interromper e retomar.

