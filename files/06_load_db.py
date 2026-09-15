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
# # 06 — Load pipeline artifacts into Postgres
#
# Reads the committed artifacts (scripts 01–05) and loads them into the
# normalized Postgres schema (see `backend/app/models.py`).
#
# Strategy: **truncate-and-reload** inside one transaction, with explicit
# surrogate primary keys assigned in Python so foreign keys resolve without a
# round-trip. Re-running is deterministic — clustering/layout change wholesale on
# each pipeline run, so a clean reload is the right idempotency model.
#
# Usage:
#   python files/06_load_db.py --dry-run     # shape rows, assert counts, NO DB
#   ALLOW_DB_RELOAD=1 python files/06_load_db.py   # truncate + load Postgres
#
# The destructive TRUNCATE is guarded behind ALLOW_DB_RELOAD=1 so an accidental
# import can never wipe the database.

# %%
import argparse
import json
import logging
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

LOG_DIR = Path("logs/06_load_db")
LOG_DIR.mkdir(parents=True, exist_ok=True)
_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_fh = logging.FileHandler(LOG_DIR / f"{_timestamp}.txt", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_fh)

DATA_DIR = Path("data")
RAW_FILE = DATA_DIR / "raw" / "sbc_articles.parquet"
CLEAN_FILE = DATA_DIR / "clean" / "researchers_with_topics.parquet"
GEO_FILE = DATA_DIR / "output" / "researchers_geo.json"
INST_FILE = DATA_DIR / "output" / "institutions_geo.json"
GRAPH_FILE = DATA_DIR / "output" / "coauthorship.json"


# %%
def normalize_name(name: str) -> str:
    """Identical to files/02_clean_data.py — must stay in sync so author names
    map to the same researchers produced by the clean step."""
    name = (name or "").lower().strip()
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9 ]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


# %% [markdown]
# ## Data shaping (pure — no DB, no SQLAlchemy)
#
# Every function below reads the artifacts and returns plain Python rows with
# explicit surrogate ids. This is exactly what `--dry-run` exercises.


# %%
def shape_all() -> dict:
    articles_raw = pd.read_parquet(RAW_FILE)
    researchers_df = pd.read_parquet(CLEAN_FILE)
    with open(GEO_FILE, encoding="utf-8") as f:
        geo_list = json.load(f)
    with open(INST_FILE, encoding="utf-8") as f:
        inst_map = json.load(f)
    with open(GRAPH_FILE, encoding="utf-8") as f:
        graph = json.load(f)

    report = {}

    # ── events ── (unique acronym → id; name + first non-null issn) ──
    events_rows = []
    acronym_to_eid = {}
    issn_by_acronym = {}
    for _, r in articles_raw.iterrows():
        acr = r["event_acronym"]
        if acr not in acronym_to_eid:
            acronym_to_eid[acr] = len(acronym_to_eid) + 1
            events_rows.append({"event_id": acronym_to_eid[acr], "acronym": acr,
                                 "name": r["event_name"], "issn": None})
        if acr not in issn_by_acronym and pd.notna(r.get("issn")):
            issn_by_acronym[acr] = r["issn"]
    for row in events_rows:
        row["issn"] = issn_by_acronym.get(row["acronym"])

    # ── topics ── (topic_id = cluster, incl. -1 as noise) ──
    topics_rows = []
    seen_clusters = set()
    for _, r in researchers_df.iterrows():
        cid = int(r["cluster"])
        if cid in seen_clusters:
            continue
        seen_clusters.add(cid)
        kws = list(r["topic_keywords"]) if _is_seq(r["topic_keywords"]) else []
        topics_rows.append({
            "topic_id": cid,
            "topic_name": r["topic_name"] if pd.notna(r["topic_name"]) else "Outros",
            "topic_keywords": kws,
            "is_noise": cid == -1,
        })

    # ── institutions ── (from geocoded affiliation strings; dedupe on CITEXT key) ──
    institutions_rows = []
    affkey_to_iid = {}  # lowercased affiliation string → institution_id
    inst_collisions = 0
    for aff, info in inst_map.items():
        key = aff.strip()
        lkey = key.lower()
        if lkey in affkey_to_iid:
            inst_collisions += 1
            continue
        affkey_to_iid[lkey] = len(institutions_rows) + 1
        institutions_rows.append({
            "institution_id": affkey_to_iid[lkey],
            "affiliation_key": key,
            "full_name": info.get("full_name"),
            "city": info.get("city") or None,
            "state": (info.get("state") or None) or None,
            "lat": info["lat"], "lng": info["lng"],
        })
    report["institution_collisions"] = inst_collisions

    # ── researchers ── (+ geo columns from researchers_geo.json) ──
    geo_by_name = {g["normalized_name"]: g for g in geo_list}
    researchers_rows = []
    normname_to_rid = {}
    researcher_events_rows = []
    researcher_institutions_rows = []
    ungeocoded = 0
    for _, r in researchers_df.iterrows():
        nn = r["normalized_name"]
        rid = len(researchers_rows) + 1
        normname_to_rid[nn] = rid
        g = geo_by_name.get(nn)
        affs = list(r["affiliations"]) if _is_seq(r["affiliations"]) else []
        primary_aff = None
        lat = lng = city = state = None
        if g:
            primary_aff = g.get("primary_affiliation")
            lat, lng = g.get("lat"), g.get("lng")
            city, state = g.get("city"), g.get("state")
        else:
            primary_aff = affs[0] if affs else None
            ungeocoded += 1
        events = list(r["events"]) if _is_seq(r["events"]) else []
        researchers_rows.append({
            "researcher_id": rid,
            "normalized_name": nn,
            "display_name": r["display_name"],
            "n_articles": int(r["n_articles"]),
            "first_year": int(r["first_year"]) if pd.notna(r["first_year"]) else None,
            "last_year": int(r["last_year"]) if pd.notna(r["last_year"]) else None,
            "topic_id": int(r["cluster"]),
            "primary_affiliation": primary_aff,
            "city": city, "state": state, "lat": lat, "lng": lng,
            "events": events,
        })
        # researcher_events (normalized many-to-many)
        for acr in events:
            eid = acronym_to_eid.get(acr)
            if eid:
                researcher_events_rows.append({"researcher_id": rid, "event_id": eid})
        # researcher_institutions (each affiliation that geocoded)
        primary_lkey = primary_aff.strip().lower() if primary_aff else None
        seen_iid = set()
        for aff in affs:
            iid = affkey_to_iid.get(aff.strip().lower())
            if iid and iid not in seen_iid:
                seen_iid.add(iid)
                researcher_institutions_rows.append({
                    "researcher_id": rid, "institution_id": iid,
                    "is_primary": aff.strip().lower() == primary_lkey,
                })
    report["ungeocoded_researchers"] = ungeocoded

    # ── articles + authorships ── (dedupe articles on (title,event_id,year)) ──
    articles_rows = []
    authorships_rows = []
    article_key_to_id = {}
    seen_authorship = set()
    merged_articles = 0
    skipped_authorships = 0
    for _, r in articles_raw.iterrows():
        eid = acronym_to_eid[r["event_acronym"]]
        akey = (r["title"], eid, int(r["year"]))
        if akey in article_key_to_id:
            aid = article_key_to_id[akey]
            merged_articles += 1
        else:
            aid = len(articles_rows) + 1
            article_key_to_id[akey] = aid
            articles_rows.append({
                "article_id": aid, "title": r["title"],
                "abstract": r["abstract"] if pd.notna(r["abstract"]) else None,
                "event_id": eid, "year": int(r["year"]),
                "track": r["track"] if pd.notna(r["track"]) else None,
                "pages": r["pages"] if pd.notna(r["pages"]) else None,
                "pdf_url": r["pdf_url"] if pd.notna(r["pdf_url"]) else None,
                "article_url": r["article_url"] if pd.notna(r["article_url"]) else None,
            })
        authors = r["authors"] if _is_seq(r["authors"]) else []
        for order, a in enumerate(authors):
            rid = normname_to_rid.get(normalize_name(a.get("name", "")))
            if rid is None:
                skipped_authorships += 1
                continue
            if (aid, rid) in seen_authorship:
                continue
            seen_authorship.add((aid, rid))
            authorships_rows.append({
                "article_id": aid, "researcher_id": rid,
                "author_order": order, "raw_affiliation": a.get("affiliation"),
            })
    report["merged_duplicate_articles"] = merged_articles
    report["skipped_authorships"] = skipped_authorships

    # ── coauthorship nodes + edges ──
    # NOTE: the committed coauthorship.json was generated by an OLDER normalization
    # that only lowercased (accents preserved), while researchers use the current
    # accent-stripping normalize_name(). We therefore RE-NORMALIZE every node/edge
    # id to the canonical researcher key. This recovers all nodes/edges (vs. ~1980
    # nodes / 8686 edges silently dropped by a naive direct match) and collapses
    # accent-variant duplicates of the same person. Upstream fix: re-run 04_explore.
    node_by_rid = {}  # researcher_id -> best (highest-degree) node dict
    unmatched_nodes = 0
    collapsed_nodes = 0
    for n in graph["nodes"]:
        rid = normname_to_rid.get(normalize_name(n["id"]))
        if rid is None:
            unmatched_nodes += 1
            continue
        deg = int(n.get("degree", 0))
        x = float(n["x"]) if "x" in n else None
        y = float(n["y"]) if "y" in n else None
        cur = node_by_rid.get(rid)
        if cur is None:
            node_by_rid[rid] = {
                "normalized_name": researchers_rows[rid - 1]["normalized_name"],
                "researcher_id": rid, "display_name": n.get("display_name"),
                "degree": deg, "x": x, "y": y,
            }
        else:
            collapsed_nodes += 1
            if deg > cur["degree"]:
                cur.update(degree=deg, display_name=n.get("display_name"), x=x, y=y)
    nodes_rows = [{"node_id": i, **nd} for i, nd in enumerate(node_by_rid.values(), start=1)]
    report["unmatched_graph_nodes"] = unmatched_nodes
    report["collapsed_accent_variant_nodes"] = collapsed_nodes

    seen_edge = {}
    skipped_edges = 0
    for e in graph["edges"]:
        a = normname_to_rid.get(normalize_name(e["source"]))
        b = normname_to_rid.get(normalize_name(e["target"]))
        if a is None or b is None or a == b:
            skipped_edges += 1
            continue
        src, dst = (a, b) if a < b else (b, a)
        # Sum weights when accent-variant edges merge onto the same researcher pair.
        seen_edge[(src, dst)] = seen_edge.get((src, dst), 0) + int(e.get("weight", 1))
    edges_rows = [{"src_id": s, "dst_id": d, "weight": w} for (s, d), w in seen_edge.items()]
    report["skipped_edges"] = skipped_edges

    return {
        "events": events_rows,
        "topics": topics_rows,
        "institutions": institutions_rows,
        "researchers": researchers_rows,
        "researcher_events": researcher_events_rows,
        "researcher_institutions": researcher_institutions_rows,
        "articles": articles_rows,
        "authorships": authorships_rows,
        "coauthorship_nodes": nodes_rows,
        "coauthorship_edges": edges_rows,
        "_report": report,
    }


def _is_seq(x) -> bool:
    import numpy as np
    return isinstance(x, (list, tuple, np.ndarray))


# %% [markdown]
# ## Load into Postgres (imports SQLAlchemy + models only here)


# %%
def load_to_db(shaped: dict) -> None:
    if os.environ.get("ALLOW_DB_RELOAD") != "1":
        raise SystemExit(
            "Refusing to load: set ALLOW_DB_RELOAD=1 to allow the destructive "
            "truncate-and-reload. (Use --dry-run to shape without a DB.)"
        )

    import sys
    sys.path.insert(0, str(Path("backend").resolve()))
    from geoalchemy2 import WKTElement
    from sqlalchemy import create_engine, insert, text, update

    from app.config import settings  # type: ignore
    from app import models as M  # type: ignore

    engine = create_engine(settings.sync_database_url, future=True)

    def geom(lng, lat):
        if lng is None or lat is None:
            return None
        return WKTElement(f"POINT({lng} {lat})", srid=4326)

    # Attach geom to geo-bearing rows; drop the loose lat/lng keys.
    inst_vals = [{**{k: v for k, v in r.items() if k not in ("lat", "lng")},
                  "geom": geom(r["lng"], r["lat"])} for r in shaped["institutions"]]
    res_vals = [{**{k: v for k, v in r.items() if k not in ("lat", "lng")},
                 "geom": geom(r["lng"], r["lat"])} for r in shaped["researchers"]]

    # Truncate in FK order, then insert reference → entities → junctions → graph.
    order = [
        "coauthorship_edges", "coauthorship_nodes", "authorships",
        "researcher_institutions", "researcher_events", "articles",
        "researchers", "institutions", "topics", "events",
    ]
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE {} RESTART IDENTITY CASCADE".format(
            ", ".join(order))))

        conn.execute(insert(M.Event), shaped["events"])
        conn.execute(insert(M.Topic), shaped["topics"])
        if inst_vals:
            conn.execute(insert(M.Institution), inst_vals)
        conn.execute(insert(M.Researcher), res_vals)
        if shaped["researcher_events"]:
            conn.execute(insert(M.ResearcherEvent), shaped["researcher_events"])
        if shaped["researcher_institutions"]:
            conn.execute(insert(M.ResearcherInstitution), shaped["researcher_institutions"])
        conn.execute(insert(M.Article), shaped["articles"])
        if shaped["authorships"]:
            conn.execute(insert(M.Authorship), shaped["authorships"])
        conn.execute(insert(M.CoauthorshipNode), shaped["coauthorship_nodes"])
        if shaped["coauthorship_edges"]:
            conn.execute(insert(M.CoauthorshipEdge), shaped["coauthorship_edges"])

        # Bump data_version for cache invalidation.
        conn.execute(text(
            "INSERT INTO meta(key, value) VALUES('data_version', :v) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        ), {"v": _timestamp})

    log.info("Load committed.")


# %%
def print_report(shaped: dict) -> None:
    counts = {k: len(v) for k, v in shaped.items() if not k.startswith("_")}
    log.info("=" * 56)
    log.info("ROW COUNTS")
    for k, v in counts.items():
        log.info("  %-26s %8d", k, v)
    log.info("RECONCILIATION")
    for k, v in shaped["_report"].items():
        log.info("  %-26s %8d", k, v)
    log.info("=" * 56)


# %%
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Shape rows and print report without touching the DB.")
    args, _ = parser.parse_known_args()

    shaped = shape_all()
    print_report(shaped)

    if args.dry_run:
        # Sanity assertions against the known artifact scale.
        c = {k: len(v) for k, v in shaped.items() if not k.startswith("_")}
        rep = shaped["_report"]
        assert c["events"] == 12, c["events"]
        assert c["researchers"] == 8898, c["researchers"]
        assert c["topics"] >= 166, c["topics"]  # 165 clusters + noise
        # After re-normalization, every graph node must resolve to a researcher.
        assert rep["unmatched_graph_nodes"] == 0, rep["unmatched_graph_nodes"]
        # The full graph must be recovered (naive direct-match dropped ~37%).
        assert c["coauthorship_edges"] > 20000, c["coauthorship_edges"]
        # Every FK target used by junction/graph rows must exist.
        rids = {r["researcher_id"] for r in shaped["researchers"]}
        for e in shaped["coauthorship_edges"]:
            assert e["src_id"] in rids and e["dst_id"] in rids and e["src_id"] < e["dst_id"]
        for a in shaped["authorships"]:
            assert a["researcher_id"] in rids
        for n in shaped["coauthorship_nodes"]:
            assert n["researcher_id"] in rids
        log.info("DRY RUN OK — shaping + FK integrity assertions passed.")
        return

    load_to_db(shaped)


if __name__ == "__main__":
    main()
