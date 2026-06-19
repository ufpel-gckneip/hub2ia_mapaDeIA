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
# # 05 — Geocode Institutional Affiliations
#
# Maps researcher affiliations (university acronyms, full names) to
# geographic coordinates (lat, lng) for the Folium geological map.
#
# Strategy:
# 1. Static dictionary of ~350 known Brazilian institutions (covers 95%)
# 2. International institutions dictionary for foreign co-authors
# 3. Keyword-based matching for full names
# 4. Nominatim fallback for anything not found

# %%
import pandas as pd
import numpy as np
import json
import re
import time
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

LOG_DIR = Path("logs/05_geocode")
LOG_DIR.mkdir(parents=True, exist_ok=True)
_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_fh = logging.FileHandler(LOG_DIR / f"{_timestamp}.txt", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_fh)

DATA_DIR = Path("data")
CLEAN_DIR = DATA_DIR / "clean"
OUT_DIR = DATA_DIR / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Static Institution Coordinates
#
# Format: key -> (lat, lng, city, state, full_name)
# Keys are normalized (lowercase, stripped).

# %%
def _inst(lat, lng, city, state, full_name):
    """Helper to create an institution tuple and return it plus common name variants."""
    entry = (lat, lng, city, state, full_name)
    return entry


# ── Brazilian Federal Universities ──
INSTITUTIONS_BR = {
    # AC
    "ufac": _inst(-9.974, -67.824, "Rio Branco", "AC", "Universidade Federal do Acre"),
    "universidade federal do acre": _inst(-9.974, -67.824, "Rio Branco", "AC", "Universidade Federal do Acre"),
    "federal university of acre": _inst(-9.974, -67.824, "Rio Branco", "AC", "Universidade Federal do Acre"),
    # AL
    "ufal": _inst(-9.556, -35.773, "Maceió", "AL", "Universidade Federal de Alagoas"),
    "universidade federal de alagoas": _inst(-9.556, -35.773, "Maceió", "AL", "Universidade Federal de Alagoas"),
    "federal university of alagoas": _inst(-9.556, -35.773, "Maceió", "AL", "Universidade Federal de Alagoas"),
    # AM
    "ufam": _inst(-3.091, -59.970, "Manaus", "AM", "Universidade Federal do Amazonas"),
    "universidade federal do amazonas": _inst(-3.091, -59.970, "Manaus", "AM", "Universidade Federal do Amazonas"),
    "federal university of amazonas": _inst(-3.091, -59.970, "Manaus", "AM", "Universidade Federal do Amazonas"),
    "university of amazonas": _inst(-3.091, -59.970, "Manaus", "AM", "Universidade Federal do Amazonas"),
    "universidade do amazonas": _inst(-3.091, -59.970, "Manaus", "AM", "Universidade Federal do Amazonas"),
    "uea": _inst(-3.091, -59.970, "Manaus", "AM", "Universidade do Estado do Amazonas"),
    "universidade do estado do amazonas": _inst(-3.091, -59.970, "Manaus", "AM", "Universidade do Estado do Amazonas"),
    # AP
    "unifap": _inst(0.034, -51.050, "Macapá", "AP", "Universidade Federal do Amapá"),
    "universidade federal do amapá": _inst(0.034, -51.050, "Macapá", "AP", "Universidade Federal do Amapá"),
    # BA
    "ufba": _inst(-12.996, -38.521, "Salvador", "BA", "Universidade Federal da Bahia"),
    "universidade federal da bahia": _inst(-12.996, -38.521, "Salvador", "BA", "Universidade Federal da Bahia"),
    "federal university of bahia": _inst(-12.996, -38.521, "Salvador", "BA", "Universidade Federal da Bahia"),
    "ufrb": _inst(-12.669, -39.108, "Cruz das Almas", "BA", "Universidade Federal do Recôncavo da Bahia"),
    "ufsb": _inst(-16.441, -39.064, "Porto Seguro", "BA", "Universidade Federal do Sul da Bahia"),
    "ufob": _inst(-12.147, -44.999, "Barreiras", "BA", "Universidade Federal do Oeste da Bahia"),
    "uneb": _inst(-12.954, -38.497, "Salvador", "BA", "Universidade do Estado da Bahia"),
    "universidade do estado da bahia": _inst(-12.954, -38.497, "Salvador", "BA", "Universidade do Estado da Bahia"),
    "uefs": _inst(-12.264, -38.966, "Feira de Santana", "BA", "Universidade Estadual de Feira de Santana"),
    "universidade estadual de feira de santana": _inst(-12.264, -38.966, "Feira de Santana", "BA", "Universidade Estadual de Feira de Santana"),
    "state university of feira de santana": _inst(-12.264, -38.966, "Feira de Santana", "BA", "Universidade Estadual de Feira de Santana"),
    "uesc": _inst(-14.789, -39.049, "Ilhéus", "BA", "Universidade Estadual de Santa Cruz"),
    "universidade estadual de santa cruz": _inst(-14.789, -39.049, "Ilhéus", "BA", "Universidade Estadual de Santa Cruz"),
    "uesb": _inst(-14.851, -40.840, "Vitória da Conquista", "BA", "Universidade Estadual do Sudoeste da Bahia"),
    "unifacs": _inst(-12.970, -38.462, "Salvador", "BA", "Universidade Salvador"),
    "universidade salvador": _inst(-12.970, -38.462, "Salvador", "BA", "Universidade Salvador"),
    "universidade de fortaleza": _inst(-3.771, -38.483, "Fortaleza", "CE", "Universidade de Fortaleza"),
    # CE
    "ufc": _inst(-3.745, -38.523, "Fortaleza", "CE", "Universidade Federal do Ceará"),
    "universidade federal do ceará": _inst(-3.745, -38.523, "Fortaleza", "CE", "Universidade Federal do Ceará"),
    "universidade federal do ceara": _inst(-3.745, -38.523, "Fortaleza", "CE", "Universidade Federal do Ceará"),
    "federal university of ceará": _inst(-3.745, -38.523, "Fortaleza", "CE", "Universidade Federal do Ceará"),
    "federal university of ceara": _inst(-3.745, -38.523, "Fortaleza", "CE", "Universidade Federal do Ceará"),
    "ufca": _inst(-7.212, -39.316, "Juazeiro do Norte", "CE", "Universidade Federal do Cariri"),
    "unilab": _inst(-4.226, -38.730, "Redenção", "CE", "Universidade da Integração Internacional da Lusofonia Afro-Brasileira"),
    "uece": _inst(-3.780, -38.558, "Fortaleza", "CE", "Universidade Estadual do Ceará"),
    "universidade estadual do ceará": _inst(-3.780, -38.558, "Fortaleza", "CE", "Universidade Estadual do Ceará"),
    "unifor": _inst(-3.771, -38.483, "Fortaleza", "CE", "Universidade de Fortaleza"),
    "uva": _inst(-3.689, -40.350, "Sobral", "CE", "Universidade Estadual Vale do Acaraú"),
    "urca": _inst(-7.238, -39.416, "Crato", "CE", "Universidade Regional do Cariri"),
    # DF
    "unb": _inst(-15.763, -47.868, "Brasília", "DF", "Universidade de Brasília"),
    "universidade de brasília": _inst(-15.763, -47.868, "Brasília", "DF", "Universidade de Brasília"),
    "universidade de brasilia": _inst(-15.763, -47.868, "Brasília", "DF", "Universidade de Brasília"),
    "university of brasília": _inst(-15.763, -47.868, "Brasília", "DF", "Universidade de Brasília"),
    "university of brasilia": _inst(-15.763, -47.868, "Brasília", "DF", "Universidade de Brasília"),
    # ES
    "ufes": _inst(-20.276, -40.306, "Vitória", "ES", "Universidade Federal do Espírito Santo"),
    "universidade federal do espírito santo": _inst(-20.276, -40.306, "Vitória", "ES", "Universidade Federal do Espírito Santo"),
    "federal university of espírito santo": _inst(-20.276, -40.306, "Vitória", "ES", "Universidade Federal do Espírito Santo"),
    "federal university of espirito santo": _inst(-20.276, -40.306, "Vitória", "ES", "Universidade Federal do Espírito Santo"),
    "ifes": _inst(-20.316, -40.337, "Vitória", "ES", "Instituto Federal do Espírito Santo"),
    "instituto federal do espírito santo": _inst(-20.316, -40.337, "Vitória", "ES", "Instituto Federal do Espírito Santo"),
    # GO
    "ufg": _inst(-16.604, -49.264, "Goiânia", "GO", "Universidade Federal de Goiás"),
    "universidade federal de goiás": _inst(-16.604, -49.264, "Goiânia", "GO", "Universidade Federal de Goiás"),
    "universidade federal de goias": _inst(-16.604, -49.264, "Goiânia", "GO", "Universidade Federal de Goiás"),
    "federal university of goiás": _inst(-16.604, -49.264, "Goiânia", "GO", "Universidade Federal de Goiás"),
    "ufcat": _inst(-18.167, -47.942, "Catalão", "GO", "Universidade Federal de Catalão"),
    "ufj": _inst(-15.934, -50.140, "Jataí", "GO", "Universidade Federal de Jataí"),
    "ueg": _inst(-16.328, -48.953, "Anápolis", "GO", "Universidade Estadual de Goiás"),
    # MA
    "ufma": _inst(-2.531, -44.303, "São Luís", "MA", "Universidade Federal do Maranhão"),
    "universidade federal do maranhão": _inst(-2.531, -44.303, "São Luís", "MA", "Universidade Federal do Maranhão"),
    "federal university of maranhão": _inst(-2.531, -44.303, "São Luís", "MA", "Universidade Federal do Maranhão"),
    "uema": _inst(-2.531, -44.303, "São Luís", "MA", "Universidade Estadual do Maranhão"),
    "universidade estadual do maranhão": _inst(-2.531, -44.303, "São Luís", "MA", "Universidade Estadual do Maranhão"),
    # MG
    "ufmg": _inst(-19.861, -43.967, "Belo Horizonte", "MG", "Universidade Federal de Minas Gerais"),
    "universidade federal de minas gerais": _inst(-19.861, -43.967, "Belo Horizonte", "MG", "Universidade Federal de Minas Gerais"),
    "federal university of minas gerais": _inst(-19.861, -43.967, "Belo Horizonte", "MG", "Universidade Federal de Minas Gerais"),
    "ufu": _inst(-18.919, -48.277, "Uberlândia", "MG", "Universidade Federal de Uberlândia"),
    "universidade federal de uberlândia": _inst(-18.919, -48.277, "Uberlândia", "MG", "Universidade Federal de Uberlândia"),
    "universidade federal de uberlandia": _inst(-18.919, -48.277, "Uberlândia", "MG", "Universidade Federal de Uberlândia"),
    "federal university of uberlândia": _inst(-18.919, -48.277, "Uberlândia", "MG", "Universidade Federal de Uberlândia"),
    "federal university of uberlandia": _inst(-18.919, -48.277, "Uberlândia", "MG", "Universidade Federal de Uberlândia"),
    "ufv": _inst(-20.754, -42.882, "Viçosa", "MG", "Universidade Federal de Viçosa"),
    "universidade federal de viçosa": _inst(-20.754, -42.882, "Viçosa", "MG", "Universidade Federal de Viçosa"),
    "federal university of viçosa": _inst(-20.754, -42.882, "Viçosa", "MG", "Universidade Federal de Viçosa"),
    "ufop": _inst(-20.385, -43.504, "Ouro Preto", "MG", "Universidade Federal de Ouro Preto"),
    "universidade federal de ouro preto": _inst(-20.385, -43.504, "Ouro Preto", "MG", "Universidade Federal de Ouro Preto"),
    "federal university of ouro preto": _inst(-20.385, -43.504, "Ouro Preto", "MG", "Universidade Federal de Ouro Preto"),
    "ufjf": _inst(-21.771, -43.375, "Juiz de Fora", "MG", "Universidade Federal de Juiz de Fora"),
    "universidade federal de juiz de fora": _inst(-21.771, -43.375, "Juiz de Fora", "MG", "Universidade Federal de Juiz de Fora"),
    "federal university of juiz de fora": _inst(-21.771, -43.375, "Juiz de Fora", "MG", "Universidade Federal de Juiz de Fora"),
    "ufla": _inst(-21.245, -45.000, "Lavras", "MG", "Universidade Federal de Lavras"),
    "universidade federal de lavras": _inst(-21.245, -45.000, "Lavras", "MG", "Universidade Federal de Lavras"),
    "ufsj": _inst(-21.136, -44.262, "São João del-Rei", "MG", "Universidade Federal de São João del-Rei"),
    "universidade federal de são joão del-rei": _inst(-21.136, -44.262, "São João del-Rei", "MG", "Universidade Federal de São João del-Rei"),
    "ufvjm": _inst(-18.245, -43.600, "Diamantina", "MG", "Universidade Federal dos Vales do Jequitinhonha e Mucuri"),
    "unifal": _inst(-21.429, -45.947, "Alfenas", "MG", "Universidade Federal de Alfenas"),
    "universidade federal de alfenas": _inst(-21.429, -45.947, "Alfenas", "MG", "Universidade Federal de Alfenas"),
    "unifei": _inst(-22.424, -45.461, "Itajubá", "MG", "Universidade Federal de Itajubá"),
    "federal university of itajubá": _inst(-22.424, -45.461, "Itajubá", "MG", "Universidade Federal de Itajubá"),
    "cefet-mg": _inst(-19.924, -43.991, "Belo Horizonte", "MG", "Centro Federal de Educação Tecnológica de Minas Gerais"),
    "puc minas": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Pontifícia Universidade Católica de Minas Gerais"),
    "pucminas": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Pontifícia Universidade Católica de Minas Gerais"),
    "puc-mg": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Pontifícia Universidade Católica de Minas Gerais"),
    "puc-minas": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Pontifícia Universidade Católica de Minas Gerais"),
    "puc mg": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Pontifícia Universidade Católica de Minas Gerais"),
    "pontifícia universidade católica de minas gerais": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Pontifícia Universidade Católica de Minas Gerais"),
    "pontifical catholic university of minas gerais": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Pontifícia Universidade Católica de Minas Gerais"),
    "fumec university": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Universidade FUMEC"),
    "universidade fumec": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Universidade FUMEC"),
    # MS
    "ufms": _inst(-20.499, -54.620, "Campo Grande", "MS", "Universidade Federal de Mato Grosso do Sul"),
    "universidade federal de mato grosso do sul": _inst(-20.499, -54.620, "Campo Grande", "MS", "Universidade Federal de Mato Grosso do Sul"),
    "federal university of mato grosso do sul": _inst(-20.499, -54.620, "Campo Grande", "MS", "Universidade Federal de Mato Grosso do Sul"),
    "ufgd": _inst(-22.221, -54.806, "Dourados", "MS", "Universidade Federal da Grande Dourados"),
    "ucdb": _inst(-20.479, -54.605, "Campo Grande", "MS", "Universidade Católica Dom Bosco"),
    "universidade católica dom bosco": _inst(-20.479, -54.605, "Campo Grande", "MS", "Universidade Católica Dom Bosco"),
    # MT
    "ufmt": _inst(-15.601, -56.097, "Cuiabá", "MT", "Universidade Federal de Mato Grosso"),
    "universidade federal de mato grosso": _inst(-15.601, -56.097, "Cuiabá", "MT", "Universidade Federal de Mato Grosso"),
    "unemat": _inst(-15.601, -56.097, "Cuiabá", "MT", "Universidade do Estado de Mato Grosso"),
    # PA
    "ufpa": _inst(-1.476, -48.454, "Belém", "PA", "Universidade Federal do Pará"),
    "universidade federal do pará": _inst(-1.476, -48.454, "Belém", "PA", "Universidade Federal do Pará"),
    "universidade federal do para": _inst(-1.476, -48.454, "Belém", "PA", "Universidade Federal do Pará"),
    "federal university of pará": _inst(-1.476, -48.454, "Belém", "PA", "Universidade Federal do Pará"),
    "federal university of para": _inst(-1.476, -48.454, "Belém", "PA", "Universidade Federal do Pará"),
    "ufopa": _inst(-2.443, -54.708, "Santarém", "PA", "Universidade Federal do Oeste do Pará"),
    "universidade federal do oeste do pará": _inst(-2.443, -54.708, "Santarém", "PA", "Universidade Federal do Oeste do Pará"),
    "ufra": _inst(-1.476, -48.454, "Belém", "PA", "Universidade Federal Rural da Amazônia"),
    "unifesspa": _inst(-5.368, -49.177, "Marabá", "PA", "Universidade Federal do Sul e Sudeste do Pará"),
    # PB
    "ufpb": _inst(-7.140, -34.845, "João Pessoa", "PB", "Universidade Federal da Paraíba"),
    "universidade federal da paraíba": _inst(-7.140, -34.845, "João Pessoa", "PB", "Universidade Federal da Paraíba"),
    "federal university of paraiba": _inst(-7.140, -34.845, "João Pessoa", "PB", "Universidade Federal da Paraíba"),
    "ufcg": _inst(-7.215, -35.908, "Campina Grande", "PB", "Universidade Federal de Campina Grande"),
    "universidade federal de campina grande": _inst(-7.215, -35.908, "Campina Grande", "PB", "Universidade Federal de Campina Grande"),
    "federal university of campina grande": _inst(-7.215, -35.908, "Campina Grande", "PB", "Universidade Federal de Campina Grande"),
    "uepb": _inst(-7.230, -35.881, "Campina Grande", "PB", "Universidade Estadual da Paraíba"),
    # PE
    "ufpe": _inst(-8.050, -34.951, "Recife", "PE", "Universidade Federal de Pernambuco"),
    "universidade federal de pernambuco": _inst(-8.050, -34.951, "Recife", "PE", "Universidade Federal de Pernambuco"),
    "federal university of pernambuco": _inst(-8.050, -34.951, "Recife", "PE", "Universidade Federal de Pernambuco"),
    "ufrpe": _inst(-8.067, -34.958, "Recife", "PE", "Universidade Federal Rural de Pernambuco"),
    "universidade federal rural de pernambuco": _inst(-8.067, -34.958, "Recife", "PE", "Universidade Federal Rural de Pernambuco"),
    "federal rural university of pernambuco": _inst(-8.067, -34.958, "Recife", "PE", "Universidade Federal Rural de Pernambuco"),
    "upe": _inst(-8.063, -34.871, "Recife", "PE", "Universidade de Pernambuco"),
    "universidade de pernambuco": _inst(-8.063, -34.871, "Recife", "PE", "Universidade de Pernambuco"),
    "univasf": _inst(-9.399, -40.504, "Petrolina", "PE", "Universidade Federal do Vale do São Francisco"),
    "ufape": _inst(-8.882, -36.493, "Garanhuns", "PE", "Universidade Federal do Agreste de Pernambuco"),
    # PI
    "ufpi": _inst(-5.092, -42.803, "Teresina", "PI", "Universidade Federal do Piauí"),
    "universidade federal do piauí": _inst(-5.092, -42.803, "Teresina", "PI", "Universidade Federal do Piauí"),
    "federal university of piauí": _inst(-5.092, -42.803, "Teresina", "PI", "Universidade Federal do Piauí"),
    "uespi": _inst(-5.092, -42.803, "Teresina", "PI", "Universidade Estadual do Piauí"),
    # PR
    "ufpr": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Federal do Paraná"),
    "universidade federal do paraná": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Federal do Paraná"),
    "universidade federal do parana": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Federal do Paraná"),
    "federal university of paraná": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Federal do Paraná"),
    "federal university of parana": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Federal do Paraná"),
    "utfpr": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Tecnológica Federal do Paraná"),
    "universidade tecnológica federal do paraná": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Tecnológica Federal do Paraná"),
    "universidade tecnologica federal do paraná": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Tecnológica Federal do Paraná"),
    "federal university of technology - paraná": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Tecnológica Federal do Paraná"),
    "federal university of technology of parana": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Tecnológica Federal do Paraná"),
    "federal university of technology – paraná (utfpr)": _inst(-25.449, -49.237, "Curitiba", "PR", "Universidade Tecnológica Federal do Paraná"),
    "unila": _inst(-25.517, -54.585, "Foz do Iguaçu", "PR", "Universidade Federal da Integração Latino-Americana"),
    "uel": _inst(-23.324, -51.203, "Londrina", "PR", "Universidade Estadual de Londrina"),
    "uem": _inst(-23.409, -51.938, "Maringá", "PR", "Universidade Estadual de Maringá"),
    "universidade estadual de maringá (uem)": _inst(-23.409, -51.938, "Maringá", "PR", "Universidade Estadual de Maringá"),
    "uepg": _inst(-25.090, -50.154, "Ponta Grossa", "PR", "Universidade Estadual de Ponta Grossa"),
    "unioeste": _inst(-24.957, -53.455, "Cascavel", "PR", "Universidade Estadual do Oeste do Paraná"),
    "unicentro": _inst(-25.392, -51.460, "Guarapuava", "PR", "Universidade Estadual do Centro-Oeste"),
    "state university in the midwest of paraná": _inst(-25.392, -51.460, "Guarapuava", "PR", "Universidade Estadual do Centro-Oeste"),
    "uenp": _inst(-23.160, -50.042, "Jacarezinho", "PR", "Universidade Estadual do Norte do Paraná"),
    "pucpr": _inst(-25.449, -49.237, "Curitiba", "PR", "Pontifícia Universidade Católica do Paraná"),
    "puc-pr": _inst(-25.449, -49.237, "Curitiba", "PR", "Pontifícia Universidade Católica do Paraná"),
    "pontifícia universidade católica do paraná": _inst(-25.449, -49.237, "Curitiba", "PR", "Pontifícia Universidade Católica do Paraná"),
    "pucp": _inst(-25.449, -49.237, "Curitiba", "PR", "Pontifícia Universidade Católica do Paraná"),
    "unicap": _inst(-8.063, -34.871, "Recife", "PE", "Universidade Católica de Pernambuco"),
    # RJ
    "ufrj": _inst(-22.862, -43.223, "Rio de Janeiro", "RJ", "Universidade Federal do Rio de Janeiro"),
    "universidade federal do rio de janeiro": _inst(-22.862, -43.223, "Rio de Janeiro", "RJ", "Universidade Federal do Rio de Janeiro"),
    "federal university of rio de janeiro": _inst(-22.862, -43.223, "Rio de Janeiro", "RJ", "Universidade Federal do Rio de Janeiro"),
    "federal univeristy of rio de janeiro": _inst(-22.862, -43.223, "Rio de Janeiro", "RJ", "Universidade Federal do Rio de Janeiro"),
    "uff": _inst(-22.886, -43.117, "Niterói", "RJ", "Universidade Federal Fluminense"),
    "universidade federal fluminense": _inst(-22.886, -43.117, "Niterói", "RJ", "Universidade Federal Fluminense"),
    "federal fluminense university": _inst(-22.886, -43.117, "Niterói", "RJ", "Universidade Federal Fluminense"),
    "fluminense federal university": _inst(-22.886, -43.117, "Niterói", "RJ", "Universidade Federal Fluminense"),
    "ufrrj": _inst(-22.754, -43.694, "Seropédica", "RJ", "Universidade Federal Rural do Rio de Janeiro"),
    "unirio": _inst(-22.906, -43.178, "Rio de Janeiro", "RJ", "Universidade Federal do Estado do Rio de Janeiro"),
    "federal university of the state of rio de janeiro": _inst(-22.906, -43.178, "Rio de Janeiro", "RJ", "Universidade Federal do Estado do Rio de Janeiro"),
    "cefet-rj": _inst(-22.903, -43.174, "Rio de Janeiro", "RJ", "Centro Federal de Educação Tecnológica Celso Suckow da Fonseca"),
    "cefet/rj": _inst(-22.903, -43.174, "Rio de Janeiro", "RJ", "Centro Federal de Educação Tecnológica Celso Suckow da Fonseca"),
    "centro federal de educação tecnológica celso suckow da fonseca": _inst(-22.903, -43.174, "Rio de Janeiro", "RJ", "Centro Federal de Educação Tecnológica Celso Suckow da Fonseca"),
    "uerj": _inst(-22.903, -43.233, "Rio de Janeiro", "RJ", "Universidade do Estado do Rio de Janeiro"),
    "state university of rio de janeiro": _inst(-22.903, -43.233, "Rio de Janeiro", "RJ", "Universidade do Estado do Rio de Janeiro"),
    "uenf": _inst(-21.762, -41.323, "Campos dos Goytacazes", "RJ", "Universidade Estadual do Norte Fluminense"),
    "puc-rio": _inst(-22.933, -43.178, "Rio de Janeiro", "RJ", "Pontifícia Universidade Católica do Rio de Janeiro"),
    "puc-rio and holistic ai": _inst(-22.933, -43.178, "Rio de Janeiro", "RJ", "Pontifícia Universidade Católica do Rio de Janeiro"),
    "pontifícia universidade católica do rio de janeiro": _inst(-22.933, -43.178, "Rio de Janeiro", "RJ", "Pontifícia Universidade Católica do Rio de Janeiro"),
    "pontifical catholic university rio de janeiro": _inst(-22.933, -43.178, "Rio de Janeiro", "RJ", "Pontifícia Universidade Católica do Rio de Janeiro"),
    # RN
    "ufrn": _inst(-5.838, -35.206, "Natal", "RN", "Universidade Federal do Rio Grande do Norte"),
    "universidade federal do rio grande do norte": _inst(-5.838, -35.206, "Natal", "RN", "Universidade Federal do Rio Grande do Norte"),
    "federal university of rio grande do norte": _inst(-5.838, -35.206, "Natal", "RN", "Universidade Federal do Rio Grande do Norte"),
    "ufersa": _inst(-5.188, -37.344, "Mossoró", "RN", "Universidade Federal Rural do Semi-Árido"),
    "uern": _inst(-5.188, -37.344, "Mossoró", "RN", "Universidade do Estado do Rio Grande do Norte"),
    "universidade do estado do rio grande do norte": _inst(-5.188, -37.344, "Mossoró", "RN", "Universidade do Estado do Rio Grande do Norte"),
    # RO
    "unir": _inst(-8.761, -63.904, "Porto Velho", "RO", "Universidade Federal de Rondônia"),
    # RR
    "ufrr": _inst(2.823, -60.675, "Boa Vista", "RR", "Universidade Federal de Roraima"),
    # RS
    "ufrgs": _inst(-30.075, -51.121, "Porto Alegre", "RS", "Universidade Federal do Rio Grande do Sul"),
    "universidade federal do rio grande do sul": _inst(-30.075, -51.121, "Porto Alegre", "RS", "Universidade Federal do Rio Grande do Sul"),
    "federal university of rio grande do sul": _inst(-30.075, -51.121, "Porto Alegre", "RS", "Universidade Federal do Rio Grande do Sul"),
    "federal university of rio grande do sui": _inst(-30.075, -51.121, "Porto Alegre", "RS", "Universidade Federal do Rio Grande do Sul"),
    "ufpel": _inst(-31.772, -52.343, "Pelotas", "RS", "Universidade Federal de Pelotas"),
    "universidade federal de pelotas": _inst(-31.772, -52.343, "Pelotas", "RS", "Universidade Federal de Pelotas"),
    "federal university of pelotas": _inst(-31.772, -52.343, "Pelotas", "RS", "Universidade Federal de Pelotas"),
    "ufcspa": _inst(-30.046, -51.174, "Porto Alegre", "RS", "Universidade Federal de Ciências da Saúde de Porto Alegre"),
    "furg": _inst(-32.033, -52.099, "Rio Grande", "RS", "Universidade Federal do Rio Grande"),
    "universidade federal do rio grande": _inst(-32.033, -52.099, "Rio Grande", "RS", "Universidade Federal do Rio Grande"),
    "ufsm": _inst(-29.720, -53.720, "Santa Maria", "RS", "Universidade Federal de Santa Maria"),
    "universidade federal de santa maria": _inst(-29.720, -53.720, "Santa Maria", "RS", "Universidade Federal de Santa Maria"),
    "federal university of santa maria": _inst(-29.720, -53.720, "Santa Maria", "RS", "Universidade Federal de Santa Maria"),
    "unipampa": _inst(-31.330, -54.106, "Bagé", "RS", "Universidade Federal do Pampa"),
    "pucrs": _inst(-30.057, -51.175, "Porto Alegre", "RS", "Pontifícia Universidade Católica do Rio Grande do Sul"),
    "puc-rs": _inst(-30.057, -51.175, "Porto Alegre", "RS", "Pontifícia Universidade Católica do Rio Grande do Sul"),
    "unisinos": _inst(-29.789, -51.147, "São Leopoldo", "RS", "Universidade do Vale do Rio dos Sinos"),
    "universidade do vale do rio dos sinos": _inst(-29.789, -51.147, "São Leopoldo", "RS", "Universidade do Vale do Rio dos Sinos"),
    "ucpel": _inst(-31.766, -52.341, "Pelotas", "RS", "Universidade Católica de Pelotas"),
    "universidade católica de pelotas": _inst(-31.766, -52.341, "Pelotas", "RS", "Universidade Católica de Pelotas"),
    "unisc": _inst(-29.642, -52.430, "Santa Cruz do Sul", "RS", "Universidade de Santa Cruz do Sul"),
    "ucs": _inst(-29.168, -51.179, "Caxias do Sul", "RS", "Universidade de Caxias do Sul"),
    "ufn": _inst(-29.686, -53.808, "Santa Maria", "RS", "Universidade Franciscana"),
    "univates": _inst(-29.381, -51.975, "Lajeado", "RS", "Univates"),
    "feevale": _inst(-29.672, -51.131, "Novo Hamburgo", "RS", "Universidade Feevale"),
    "upf": _inst(-28.252, -52.406, "Passo Fundo", "RS", "Universidade de Passo Fundo"),
    "ifsul": _inst(-31.770, -52.342, "Pelotas", "RS", "Instituto Federal Sul-rio-grandense"),
    "uniritter": _inst(-30.043, -51.169, "Porto Alegre", "RS", "UniRitter"),
    # SC
    "ufsc": _inst(-27.601, -48.520, "Florianópolis", "SC", "Universidade Federal de Santa Catarina"),
    "universidade federal de santa catarina": _inst(-27.601, -48.520, "Florianópolis", "SC", "Universidade Federal de Santa Catarina"),
    "federal university of santa catarina": _inst(-27.601, -48.520, "Florianópolis", "SC", "Universidade Federal de Santa Catarina"),
    "uffs": _inst(-27.097, -52.618, "Chapecó", "SC", "Universidade Federal da Fronteira Sul"),
    "udesc": _inst(-27.596, -48.549, "Florianópolis", "SC", "Universidade do Estado de Santa Catarina"),
    "universidade do estado de santa catarina": _inst(-27.596, -48.549, "Florianópolis", "SC", "Universidade do Estado de Santa Catarina"),
    "universidade do estado de santa catarina (udesc)": _inst(-27.596, -48.549, "Florianópolis", "SC", "Universidade do Estado de Santa Catarina"),
    "univali": _inst(-26.908, -48.662, "Itajaí", "SC", "Universidade do Vale do Itajaí"),
    "unisul": _inst(-28.467, -49.007, "Tubarão", "SC", "Universidade do Sul de Santa Catarina"),
    "univille": _inst(-26.304, -48.846, "Joinville", "SC", "Universidade da Região de Joinville"),
    "ifsc": _inst(-27.596, -48.549, "Florianópolis", "SC", "Instituto Federal de Santa Catarina"),
    "católica sc": _inst(-26.482, -49.095, "Joinville", "SC", "Católica de Santa Catarina"),
    "unesc": _inst(-28.718, -49.370, "Criciúma", "SC", "Universidade do Extremo Sul Catarinense"),
    # SE
    "ufs": _inst(-10.925, -37.106, "Aracaju", "SE", "Universidade Federal de Sergipe"),
    "universidade federal de sergipe": _inst(-10.925, -37.106, "Aracaju", "SE", "Universidade Federal de Sergipe"),
    "federal university of sergipe": _inst(-10.925, -37.106, "Aracaju", "SE", "Universidade Federal de Sergipe"),
    # SP
    "usp": _inst(-23.561, -46.731, "São Paulo", "SP", "Universidade de São Paulo"),
    "universidade de são paulo": _inst(-23.561, -46.731, "São Paulo", "SP", "Universidade de São Paulo"),
    "universidade de sao paulo": _inst(-23.561, -46.731, "São Paulo", "SP", "Universidade de São Paulo"),
    "university of são paulo": _inst(-23.561, -46.731, "São Paulo", "SP", "Universidade de São Paulo"),
    "university of sao paulo": _inst(-23.561, -46.731, "São Paulo", "SP", "Universidade de São Paulo"),
    "unicamp": _inst(-22.817, -47.062, "Campinas", "SP", "Universidade Estadual de Campinas"),
    "universidade estadual de campinas": _inst(-22.817, -47.062, "Campinas", "SP", "Universidade Estadual de Campinas"),
    "universidade de campinas": _inst(-22.817, -47.062, "Campinas", "SP", "Universidade Estadual de Campinas"),
    "university of campinas": _inst(-22.817, -47.062, "Campinas", "SP", "Universidade Estadual de Campinas"),
    "unesp": _inst(-22.314, -49.055, "Bauru", "SP", "Universidade Estadual Paulista"),
    "universidade estadual paulista": _inst(-22.314, -49.055, "Bauru", "SP", "Universidade Estadual Paulista"),
    "sao paulo state university": _inst(-22.314, -49.055, "Bauru", "SP", "Universidade Estadual Paulista"),
    "universidade estadual paulista júlio de mesquita filho (unesp)": _inst(-22.314, -49.055, "Bauru", "SP", "Universidade Estadual Paulista"),
    "ufscar": _inst(-21.980, -47.890, "São Carlos", "SP", "Universidade Federal de São Carlos"),
    "universidade federal de são carlos": _inst(-21.980, -47.890, "São Carlos", "SP", "Universidade Federal de São Carlos"),
    "federal university of são carlos (ufscar)": _inst(-21.980, -47.890, "São Carlos", "SP", "Universidade Federal de São Carlos"),
    "unifesp": _inst(-23.574, -46.636, "São Paulo", "SP", "Universidade Federal de São Paulo"),
    "universidade federal de são paulo": _inst(-23.574, -46.636, "São Paulo", "SP", "Universidade Federal de São Paulo"),
    "federal university of são paulo": _inst(-23.574, -46.636, "São Paulo", "SP", "Universidade Federal de São Paulo"),
    "ufabc": _inst(-23.659, -46.529, "Santo André", "SP", "Universidade Federal do ABC"),
    "universidade federal do abc": _inst(-23.659, -46.529, "Santo André", "SP", "Universidade Federal do ABC"),
    "federal university of abc": _inst(-23.659, -46.529, "Santo André", "SP", "Universidade Federal do ABC"),
    "ita": _inst(-23.213, -45.873, "São José dos Campos", "SP", "Instituto Tecnológico de Aeronáutica"),
    "instituto tecnológico de aeronáutica": _inst(-23.213, -45.873, "São José dos Campos", "SP", "Instituto Tecnológico de Aeronáutica"),
    "instituto tecnológico da aeronáutica": _inst(-23.213, -45.873, "São José dos Campos", "SP", "Instituto Tecnológico de Aeronáutica"),
    "technological institute of aeronautics": _inst(-23.213, -45.873, "São José dos Campos", "SP", "Instituto Tecnológico de Aeronáutica"),
    "inpe": _inst(-23.208, -45.862, "São José dos Campos", "SP", "Instituto Nacional de Pesquisas Espaciais"),
    "pucsp": _inst(-23.551, -46.647, "São Paulo", "SP", "Pontifícia Universidade Católica de São Paulo"),
    "puc-sp": _inst(-23.551, -46.647, "São Paulo", "SP", "Pontifícia Universidade Católica de São Paulo"),
    "mackenzie": _inst(-23.548, -46.653, "São Paulo", "SP", "Universidade Presbiteriana Mackenzie"),
    "mackenzie presbyterian university": _inst(-23.548, -46.653, "São Paulo", "SP", "Universidade Presbiteriana Mackenzie"),
    "insper": _inst(-23.590, -46.685, "São Paulo", "SP", "Insper"),
    "fei": _inst(-23.724, -46.577, "São Bernardo do Campo", "SP", "Centro Universitário FEI"),
    "centro universitário fei": _inst(-23.724, -46.577, "São Bernardo do Campo", "SP", "Centro Universitário FEI"),
    "fei university center": _inst(-23.724, -46.577, "São Bernardo do Campo", "SP", "Centro Universitário FEI"),
    "fei university": _inst(-23.724, -46.577, "São Bernardo do Campo", "SP", "Centro Universitário FEI"),
    "university center of fei": _inst(-23.724, -46.577, "São Bernardo do Campo", "SP", "Centro Universitário FEI"),
    "centro universitário da fei": _inst(-23.724, -46.577, "São Bernardo do Campo", "SP", "Centro Universitário FEI"),
    "puc-campinas": _inst(-22.891, -47.061, "Campinas", "SP", "Pontifícia Universidade Católica de Campinas"),
    "puc campinas": _inst(-22.891, -47.061, "Campinas", "SP", "Pontifícia Universidade Católica de Campinas"),
    "ufscar": _inst(-21.980, -47.890, "São Carlos", "SP", "Universidade Federal de São Carlos"),
    "faccamp": _inst(-22.733, -47.332, "Campinas", "SP", "Faculdade Campo Limpo Paulista"),
    "unifaccamp": _inst(-22.733, -47.332, "Campinas", "SP", "Faculdade Campo Limpo Paulista"),
    "centro universitário campo limpo paulista": _inst(-22.733, -47.332, "Campinas", "SP", "Faculdade Campo Limpo Paulista"),
    # TO
    "uft": _inst(-10.185, -48.334, "Palmas", "TO", "Universidade Federal do Tocantins"),
    "ufnt": _inst(-7.201, -48.208, "Araguaína", "TO", "Universidade Federal do Norte do Tocantins"),
}


# ── Research Institutes & Government ──
INSTITUTES = {
    "impa": _inst(-22.538, -43.132, "Rio de Janeiro", "RJ", "Instituto de Matemática Pura e Aplicada"),
    "inpe": _inst(-23.208, -45.862, "São José dos Campos", "SP", "Instituto Nacional de Pesquisas Espaciais"),
    "lncc": _inst(-22.456, -43.114, "Petrópolis", "RJ", "Laboratório Nacional de Computação Científica"),
    "laboratório nacional de computação científica": _inst(-22.456, -43.114, "Petrópolis", "RJ", "Laboratório Nacional de Computação Científica"),
    "laboratorio nacional de computacao cientifica": _inst(-22.456, -43.114, "Petrópolis", "RJ", "Laboratório Nacional de Computação Científica"),
    "national laboratory for scientific computing": _inst(-22.456, -43.114, "Petrópolis", "RJ", "Laboratório Nacional de Computação Científica"),
    "embrapa": _inst(-15.789, -47.904, "Brasília", "DF", "Empresa Brasileira de Pesquisa Agropecuária"),
    "fiocruz": _inst(-22.874, -43.244, "Rio de Janeiro", "RJ", "Fundação Oswaldo Cruz"),
    "ipt": _inst(-23.545, -46.648, "São Paulo", "SP", "Instituto de Pesquisas Tecnológicas"),
    "cti": _inst(-22.748, -47.334, "Campinas", "SP", "Centro de Tecnologia da Informação Renato Archer"),
    "cti renato archer": _inst(-22.748, -47.334, "Campinas", "SP", "Centro de Tecnologia da Informação Renato Archer"),
    "cpqd": _inst(-22.837, -47.076, "Campinas", "SP", "Centro de Pesquisa e Desenvolvimento em Telecomunicações"),
    "cemaden": _inst(-22.997, -45.555, "Cachoeira Paulista", "SP", "Centro Nacional de Monitoramento e Alertas de Desastres Naturais"),
    "iesb": _inst(-15.791, -47.893, "Brasília", "DF", "Instituto de Educação Superior de Brasília"),
    "ibict": _inst(-15.791, -47.893, "Brasília", "DF", "Instituto Brasileiro de Informação em Ciência e Tecnologia"),
    "ibge": _inst(-22.904, -43.176, "Rio de Janeiro", "RJ", "Instituto Brasileiro de Geografia e Estatística"),
    "inmetro": _inst(-22.542, -43.148, "Rio de Janeiro", "RJ", "Instituto Nacional de Metrologia"),
    "cemig": _inst(-19.925, -43.991, "Belo Horizonte", "MG", "Companhia Energética de Minas Gerais"),
    "petrobras": _inst(-22.870, -43.263, "Rio de Janeiro", "RJ", "Petrobras"),
    "cpfl": _inst(-22.903, -47.056, "Campinas", "SP", "CPFL Energia"),
    "eletrobras": _inst(-22.903, -43.176, "Rio de Janeiro", "RJ", "Eletrobras"),
    "itv": _inst(-1.476, -48.454, "Belém", "PA", "Instituto Tecnológico Vale"),
    "instituto tecnológico vale": _inst(-1.476, -48.454, "Belém", "PA", "Instituto Tecnológico Vale"),
    "instituto tecnológico vale": _inst(-1.476, -48.454, "Belém", "PA", "Instituto Tecnológico Vale"),
    "industrial technology architecture vale s.a.": _inst(-1.476, -48.454, "Belém", "PA", "Instituto Tecnológico Vale"),
    "vale institute of technology": _inst(-1.476, -48.454, "Belém", "PA", "Instituto Tecnológico Vale"),
    "cnpq": _inst(-15.790, -47.891, "Brasília", "DF", "Conselho Nacional de Desenvolvimento Científico e Tecnológico"),
    "capes": _inst(-15.789, -47.893, "Brasília", "DF", "Coordenação de Aperfeiçoamento de Pessoal de Nível Superior"),
    "fgv": _inst(-22.932, -43.176, "Rio de Janeiro", "RJ", "Fundação Getulio Vargas"),
    "ime": _inst(-22.864, -43.231, "Rio de Janeiro", "RJ", "Instituto Militar de Engenharia"),
    "instituto militar de engenharia": _inst(-22.864, -43.231, "Rio de Janeiro", "RJ", "Instituto Militar de Engenharia"),
    "senai cimatec": _inst(-12.965, -38.424, "Salvador", "BA", "SENAI CIMATEC"),
    "senai/cimatec": _inst(-12.965, -38.424, "Salvador", "BA", "SENAI CIMATEC"),
    "cimatec": _inst(-12.965, -38.424, "Salvador", "BA", "SENAI CIMATEC"),
    "cesar": _inst(-8.057, -34.873, "Recife", "PE", "CESAR"),
    "cesar school": _inst(-8.057, -34.873, "Recife", "PE", "CESAR School"),
    "recife center for advanced studies and systems (cesar school)": _inst(-8.057, -34.873, "Recife", "PE", "CESAR School"),
    "cesar innovation center": _inst(-8.057, -34.873, "Recife", "PE", "CESAR Innovation Center"),
    "centro de estudos e sistemas avançados do recife": _inst(-8.057, -34.873, "Recife", "PE", "CESAR"),
    "instituto de pesquisas eldorado": _inst(-22.837, -47.076, "Campinas", "SP", "Instituto de Pesquisas Eldorado"),
    "eldorado institute": _inst(-22.837, -47.076, "Campinas", "SP", "Instituto de Pesquisas Eldorado"),
    "eldorado institute of research": _inst(-22.837, -47.076, "Campinas", "SP", "Instituto de Pesquisas Eldorado"),
    "cpqd": _inst(-22.837, -47.076, "Campinas", "SP", "CPQD"),
    "ieav": _inst(-23.215, -45.869, "São José dos Campos", "SP", "Instituto de Estudos Avançados"),
    "ieav-dcta": _inst(-23.215, -45.869, "São José dos Campos", "SP", "Instituto de Estudos Avançados"),
    "cepetro": _inst(-22.862, -43.223, "Rio de Janeiro", "RJ", "Centro de Estudos de Petróleo"),
    "cenpes": _inst(-22.870, -43.263, "Rio de Janeiro", "RJ", "Centro de Pesquisas da Petrobras"),
    "bndes": _inst(-22.912, -43.199, "Rio de Janeiro", "RJ", "Banco Nacional de Desenvolvimento Econômico e Social"),
    "radix engineering and software development": _inst(-22.903, -43.174, "Rio de Janeiro", "RJ", "Radix Engineering"),
    "sidi": _inst(-22.837, -47.076, "Campinas", "SP", "SiDi"),
    "eldorado research institute": _inst(-22.837, -47.076, "Campinas", "SP", "Instituto de Pesquisas Eldorado"),
    "venturus - innovation & technology": _inst(-22.837, -47.076, "Campinas", "SP", "Venturus"),
    "samsung r&d institute": _inst(-23.561, -46.731, "São Paulo", "SP", "Samsung R&D Institute Brazil"),
    "samsung r&d institute brazil": _inst(-23.561, -46.731, "São Paulo", "SP", "Samsung R&D Institute Brazil"),
    "samsung r&d brazil": _inst(-23.561, -46.731, "São Paulo", "SP", "Samsung R&D Institute Brazil"),
    "ibm research": _inst(-23.561, -46.731, "São Paulo", "SP", "IBM Research Brasil"),
    "ibm research brasil": _inst(-23.561, -46.731, "São Paulo", "SP", "IBM Research Brasil"),
    "icmc-usp": _inst(-22.005, -47.895, "São Carlos", "SP", "ICMC-USP"),
    "nilc": _inst(-22.005, -47.895, "São Carlos", "SP", "Núcleo Interinstitucional de Linguística Computacional"),
    "certi foundation": _inst(-27.596, -48.549, "Florianópolis", "SC", "Fundação Centros de Referência em Tecnologias Inovadoras"),
    "lactec": _inst(-25.449, -49.237, "Curitiba", "PR", "Instituto de Tecnologia para o Desenvolvimento"),
    "institutos lactec": _inst(-25.449, -49.237, "Curitiba", "PR", "Instituto de Tecnologia para o Desenvolvimento"),
    "cpfl energia": _inst(-22.903, -47.056, "Campinas", "SP", "CPFL Energia"),
    "btg pactual": _inst(-23.561, -46.731, "São Paulo", "SP", "BTG Pactual"),
    "btgpactual": _inst(-23.561, -46.731, "São Paulo", "SP", "BTG Pactual"),
    "embraer": _inst(-23.226, -45.872, "São José dos Campos", "SP", "Embraer"),
    "embraer s.a.": _inst(-23.226, -45.872, "São José dos Campos", "SP", "Embraer"),
    "grupo embaer s.a.": _inst(-23.226, -45.872, "São José dos Campos", "SP", "Embraer"),
    "motora technologies": _inst(-23.561, -46.731, "São Paulo", "SP", "Motora Technologies"),
    "nvidia": _inst(37.395, -122.078, "Santa Clara", "CA, USA", "NVIDIA Corporation"),
    "nvidia corporation": _inst(37.395, -122.078, "Santa Clara", "CA, USA", "NVIDIA Corporation"),
    "google": _inst(37.422, -122.084, "Mountain View", "CA, USA", "Google"),
    "americanas s. a.": _inst(-22.912, -43.199, "Rio de Janeiro", "RJ", "Americanas S.A."),
    "americanas s.a.": _inst(-22.912, -43.199, "Rio de Janeiro", "RJ", "Americanas S.A."),
    "hp inc": _inst(-23.561, -46.731, "São Paulo", "SP", "HP Inc Brasil"),
    "hewlett packard enterprise": _inst(-23.561, -46.731, "São Paulo", "SP", "Hewlett Packard Enterprise Brasil"),
    "hpe": _inst(-23.561, -46.731, "São Paulo", "SP", "Hewlett Packard Enterprise Brasil"),
    "ifood": _inst(-23.561, -46.731, "São Paulo", "SP", "iFood"),
    "ifood brasil": _inst(-23.561, -46.731, "São Paulo", "SP", "iFood"),
    "luizalabs": _inst(-23.561, -46.731, "São Paulo", "SP", "LuizaLabs"),
    "unico – idtech": _inst(-23.561, -46.731, "São Paulo", "SP", "unico-idTech"),
    "serasa experian": _inst(-23.561, -46.731, "São Paulo", "SP", "Serasa Experian"),
    "instituto de ciência e tecnologia itaú": _inst(-23.561, -46.731, "São Paulo", "SP", "Instituto de Ciência e Tecnologia Itaú"),
    "instituto lawgorithm": _inst(-23.561, -46.731, "São Paulo", "SP", "Instituto Lawgorithm"),
    "maritaca ai": _inst(-23.561, -46.731, "São Paulo", "SP", "Maritaca AI"),
}

# ── Federal Institutes (IFs) ──
IFS = {
    "ifac": _inst(-9.967, -67.826, "Rio Branco", "AC", "Instituto Federal do Acre"),
    "ifal": _inst(-9.556, -35.773, "Maceió", "AL", "Instituto Federal de Alagoas"),
    "ifam": _inst(-3.091, -59.970, "Manaus", "AM", "Instituto Federal do Amazonas"),
    "ifap": _inst(0.034, -51.050, "Macapá", "AP", "Instituto Federal do Amapá"),
    "ifba": _inst(-12.996, -38.521, "Salvador", "BA", "Instituto Federal da Bahia"),
    "ifbaiano": _inst(-12.996, -38.521, "Salvador", "BA", "Instituto Federal Baiano"),
    "ifce": _inst(-3.745, -38.523, "Fortaleza", "CE", "Instituto Federal do Ceará"),
    "ifb": _inst(-15.763, -47.868, "Brasília", "DF", "Instituto Federal de Brasília"),
    "ifes": _inst(-20.316, -40.337, "Vitória", "ES", "Instituto Federal do Espírito Santo"),
    "ifg": _inst(-16.604, -49.264, "Goiânia", "GO", "Instituto Federal de Goiás"),
    "ifgoiano": _inst(-16.604, -49.264, "Goiânia", "GO", "Instituto Federal Goiano"),
    "ifma": _inst(-2.531, -44.303, "São Luís", "MA", "Instituto Federal do Maranhão"),
    "ifmg": _inst(-19.861, -43.967, "Belo Horizonte", "MG", "Instituto Federal de Minas Gerais"),
    "ifsudestemg": _inst(-21.771, -43.375, "Juiz de Fora", "MG", "Instituto Federal do Sudeste de Minas Gerais"),
    "ifnmg": _inst(-16.370, -44.176, "Montes Claros", "MG", "Instituto Federal do Norte de Minas Gerais"),
    "iftm": _inst(-18.919, -48.277, "Uberlândia", "MG", "Instituto Federal do Triângulo Mineiro"),
    "ifsuldeminas": _inst(-21.771, -43.375, "Juiz de Fora", "MG", "Instituto Federal do Sul de Minas Gerais"),
    "ifms": _inst(-20.499, -54.620, "Campo Grande", "MS", "Instituto Federal de Mato Grosso do Sul"),
    "ifmt": _inst(-15.601, -56.097, "Cuiabá", "MT", "Instituto Federal de Mato Grosso"),
    "ifpa": _inst(-1.476, -48.454, "Belém", "PA", "Instituto Federal do Pará"),
    "ifpb": _inst(-7.140, -34.845, "João Pessoa", "PB", "Instituto Federal da Paraíba"),
    "ifpe": _inst(-8.050, -34.951, "Recife", "PE", "Instituto Federal de Pernambuco"),
    "ifsertão-pe": _inst(-9.399, -40.504, "Petrolina", "PE", "Instituto Federal do Sertão Pernambucano"),
    "ifpi": _inst(-5.092, -42.803, "Teresina", "PI", "Instituto Federal do Piauí"),
    "ifpr": _inst(-25.449, -49.237, "Curitiba", "PR", "Instituto Federal do Paraná"),
    "ifrj": _inst(-22.903, -43.174, "Rio de Janeiro", "RJ", "Instituto Federal do Rio de Janeiro"),
    "iff": _inst(-21.762, -41.323, "Campos dos Goytacazes", "RJ", "Instituto Federal Fluminense"),
    "ifrn": _inst(-5.838, -35.206, "Natal", "RN", "Instituto Federal do Rio Grande do Norte"),
    "ifro": _inst(-8.761, -63.904, "Porto Velho", "RO", "Instituto Federal de Rondônia"),
    "ifrr": _inst(2.823, -60.675, "Boa Vista", "RR", "Instituto Federal de Roraima"),
    "ifrs": _inst(-30.075, -51.121, "Porto Alegre", "RS", "Instituto Federal do Rio Grande do Sul"),
    "iffar": _inst(-28.252, -52.406, "Passo Fundo", "RS", "Instituto Federal Farroupilha"),
    "ifsul": _inst(-31.770, -52.342, "Pelotas", "RS", "Instituto Federal Sul-rio-grandense"),
    "ifsc": _inst(-27.596, -48.549, "Florianópolis", "SC", "Instituto Federal de Santa Catarina"),
    "ifc": _inst(-26.908, -48.662, "Itajaí", "SC", "Instituto Federal Catarinense"),
    "ifsp": _inst(-23.561, -46.731, "São Paulo", "SP", "Instituto Federal de São Paulo"),
    "ifs": _inst(-10.925, -37.106, "Aracaju", "SE", "Instituto Federal de Sergipe"),
    "ifto": _inst(-10.185, -48.334, "Palmas", "TO", "Instituto Federal do Tocantins"),
}

# Generate full-name variants for IFs
_full_if_names = {
    "ifac": "Instituto Federal do Acre",
    "ifal": "Instituto Federal de Alagoas",
    "ifam": "Instituto Federal do Amazonas",
    "ifap": "Instituto Federal do Amapá",
    "ifba": "Instituto Federal da Bahia",
    "ifce": "Instituto Federal do Ceará",
    "ifb": "Instituto Federal de Brasília",
    "ifes": "Instituto Federal do Espírito Santo",
    "ifg": "Instituto Federal de Goiás",
    "ifma": "Instituto Federal do Maranhão",
    "ifmg": "Instituto Federal de Minas Gerais",
    "ifms": "Instituto Federal de Mato Grosso do Sul",
    "ifmt": "Instituto Federal de Mato Grosso",
    "ifpa": "Instituto Federal do Pará",
    "ifpb": "Instituto Federal da Paraíba",
    "ifpe": "Instituto Federal de Pernambuco",
    "ifpi": "Instituto Federal do Piauí",
    "ifpr": "Instituto Federal do Paraná",
    "ifrj": "Instituto Federal do Rio de Janeiro",
    "ifrn": "Instituto Federal do Rio Grande do Norte",
    "ifro": "Instituto Federal de Rondônia",
    "ifrr": "Instituto Federal de Roraima",
    "ifrs": "Instituto Federal do Rio Grande do Sul",
    "ifsc": "Instituto Federal de Santa Catarina",
    "ifsp": "Instituto Federal de São Paulo",
    "ifs": "Instituto Federal de Sergipe",
    "ifto": "Instituto Federal do Tocantins",
}
for k, v in _full_if_names.items():
    IFS[v.lower()] = IFS[k]

# ── International Universities (common ones from data) ──
INTERNATIONAL = {
    "mit": _inst(42.360, -71.094, "Cambridge", "MA, USA", "Massachusetts Institute of Technology"),
    "massachusetts institute of technology": _inst(42.360, -71.094, "Cambridge", "MA, USA", "Massachusetts Institute of Technology"),
    "harvard": _inst(42.374, -71.117, "Cambridge", "MA, USA", "Harvard University"),
    "harvard university": _inst(42.374, -71.117, "Cambridge", "MA, USA", "Harvard University"),
    "stanford": _inst(37.427, -122.170, "Stanford", "CA, USA", "Stanford University"),
    "stanford university": _inst(37.427, -122.170, "Stanford", "CA, USA", "Stanford University"),
    "oxford": _inst(51.755, -1.254, "Oxford", "UK", "University of Oxford"),
    "university of oxford": _inst(51.755, -1.254, "Oxford", "UK", "University of Oxford"),
    "cambridge": _inst(52.205, 0.113, "Cambridge", "UK", "University of Cambridge"),
    "university of cambridge": _inst(52.205, 0.113, "Cambridge", "UK", "University of Cambridge"),
    "eth zurich": _inst(47.376, 8.547, "Zurich", "Switzerland", "ETH Zurich"),
    "inria": _inst(48.714, 2.198, "Paris", "France", "Inria"),
    "cnrs": _inst(48.851, 2.298, "Paris", "France", "Centre National de la Recherche Scientifique"),
    "universidade de coimbra": _inst(40.208, -8.428, "Coimbra", "Portugal", "Universidade de Coimbra"),
    "university of coimbra": _inst(40.208, -8.428, "Coimbra", "Portugal", "Universidade de Coimbra"),
    "u coimbra": _inst(40.208, -8.428, "Coimbra", "Portugal", "Universidade de Coimbra"),
    "universidade de lisboa": _inst(38.737, -9.137, "Lisbon", "Portugal", "Universidade de Lisboa"),
    "university of lisbon": _inst(38.737, -9.137, "Lisbon", "Portugal", "Universidade de Lisboa"),
    "universidade do porto": _inst(41.151, -8.630, "Porto", "Portugal", "Universidade do Porto"),
    "university of porto": _inst(41.151, -8.630, "Porto", "Portugal", "Universidade do Porto"),
    "universidade de évora": _inst(38.573, -7.904, "Évora", "Portugal", "Universidade de Évora"),
    "university of évora": _inst(38.573, -7.904, "Évora", "Portugal", "Universidade de Évora"),
    "university of aveiro": _inst(40.629, -8.656, "Aveiro", "Portugal", "University of Aveiro"),
    "universidade de aveiro": _inst(40.629, -8.656, "Aveiro", "Portugal", "University of Aveiro"),
    "university of grenoble": _inst(45.188, 5.724, "Grenoble", "France", "University Grenoble Alpes"),
    "university grenoble alpes": _inst(45.188, 5.724, "Grenoble", "France", "University Grenoble Alpes"),
    "sorbonne": _inst(48.849, 2.342, "Paris", "France", "Sorbonne Université"),
    "sorbonne université": _inst(48.849, 2.342, "Paris", "France", "Sorbonne Université"),
    "telecom paris": _inst(48.710, 2.197, "Palaiseau", "France", "Télécom Paris"),
    "kcl": _inst(51.512, -0.116, "London", "UK", "King's College London"),
    "king's college london": _inst(51.512, -0.116, "London", "UK", "King's College London"),
    "king's college university": _inst(51.512, -0.116, "London", "UK", "King's College London"),
    "ucl": _inst(51.524, -0.134, "London", "UK", "University College London"),
    "imperial": _inst(51.499, -0.175, "London", "UK", "Imperial College London"),
    "imperial college london": _inst(51.499, -0.175, "London", "UK", "Imperial College London"),
    "university of tokyo": _inst(35.713, 139.762, "Tokyo", "Japan", "The University of Tokyo"),
    "kyoto university": _inst(35.029, 135.780, "Kyoto", "Japan", "Kyoto University"),
    "naist": _inst(34.672, 135.826, "Nara", "Japan", "Nara Institute of Science and Technology"),
    "nara institute of science and technology": _inst(34.672, 135.826, "Nara", "Japan", "Nara Institute of Science and Technology"),
    "osaka university": _inst(34.802, 135.458, "Osaka", "Japan", "Osaka University"),
    "kyushu university": _inst(33.595, 130.218, "Fukuoka", "Japan", "Kyushu University"),
    "university of tsukuba": _inst(36.109, 140.103, "Tsukuba", "Japan", "University of Tsukuba"),
    "university of waterloo": _inst(43.473, -80.537, "Waterloo", "Canada", "University of Waterloo"),
    "mcgill": _inst(45.504, -73.577, "Montreal", "Canada", "McGill University"),
    "mcgill university": _inst(45.504, -73.577, "Montreal", "Canada", "McGill University"),
    "university of calgary": _inst(51.078, -114.137, "Calgary", "Canada", "University of Calgary"),
    "ucalgary": _inst(51.078, -114.137, "Calgary", "Canada", "University of Calgary"),
    "utoronto": _inst(43.662, -79.396, "Toronto", "Canada", "University of Toronto"),
    "university of toronto": _inst(43.662, -79.396, "Toronto", "Canada", "University of Toronto"),
    "carnegie mellon": _inst(40.443, -79.943, "Pittsburgh", "USA", "Carnegie Mellon University"),
    "carnegie mellon university": _inst(40.443, -79.943, "Pittsburgh", "USA", "Carnegie Mellon University"),
    "berkeley": _inst(37.872, -122.260, "Berkeley", "CA, USA", "UC Berkeley"),
    "university of california": _inst(37.872, -122.260, "Berkeley", "CA, USA", "University of California"),
    "uc berkeley": _inst(37.872, -122.260, "Berkeley", "CA, USA", "UC Berkeley"),
    "university of michigan": _inst(42.278, -83.738, "Ann Arbor", "MI, USA", "University of Michigan"),
    "purdue": _inst(40.424, -86.921, "West Lafayette", "IN, USA", "Purdue University"),
    "purdue university": _inst(40.424, -86.921, "West Lafayette", "IN, USA", "Purdue University"),
    "university of illinois": _inst(40.106, -88.227, "Urbana-Champaign", "IL, USA", "University of Illinois at Urbana-Champaign"),
    "university of illinois urbana-champaign": _inst(40.106, -88.227, "Urbana-Champaign", "IL, USA", "University of Illinois at Urbana-Champaign"),
    "northwestern": _inst(42.056, -87.676, "Evanston", "IL, USA", "Northwestern University"),
    "northwestern university": _inst(42.056, -87.676, "Evanston", "IL, USA", "Northwestern University"),
    "columbia": _inst(40.808, -73.962, "New York", "NY, USA", "Columbia University"),
    "columbia university": _inst(40.808, -73.962, "New York", "NY, USA", "Columbia University"),
    "nyu": _inst(40.730, -73.996, "New York", "NY, USA", "New York University"),
    "new york university": _inst(40.730, -73.996, "New York", "NY, USA", "New York University"),
    "university of texas": _inst(30.287, -97.734, "Austin", "TX, USA", "University of Texas at Austin"),
    "university of texas at austin": _inst(30.287, -97.734, "Austin", "TX, USA", "University of Texas at Austin"),
    "yale": _inst(41.312, -72.925, "New Haven", "CT, USA", "Yale University"),
    "yale university": _inst(41.312, -72.925, "New Haven", "CT, USA", "Yale University"),
    "brown university": _inst(41.826, -71.402, "Providence", "RI, USA", "Brown University"),
    "duke university": _inst(36.001, -78.939, "Durham", "NC, USA", "Duke University"),
    "university of pennsylvania": _inst(39.952, -75.193, "Philadelphia", "PA, USA", "University of Pennsylvania"),
    "johns hopkins": _inst(39.330, -76.620, "Baltimore", "MD, USA", "Johns Hopkins University"),
    "cornell": _inst(42.453, -76.474, "Ithaca", "NY, USA", "Cornell University"),
    "tu delft": _inst(52.006, 4.371, "Delft", "Netherlands", "Delft University of Technology"),
    "delft university of technology": _inst(52.006, 4.371, "Delft", "Netherlands", "Delft University of Technology"),
    "tu eindhoven": _inst(51.448, 5.488, "Eindhoven", "Netherlands", "Eindhoven University of Technology"),
    "eindhoven university of technology": _inst(51.448, 5.488, "Eindhoven", "Netherlands", "Eindhoven University of Technology"),
    "university of amsterdam": _inst(52.355, 4.955, "Amsterdam", "Netherlands", "University of Amsterdam"),
    "kth": _inst(59.347, 18.073, "Stockholm", "Sweden", "KTH Royal Institute of Technology"),
    "aalto": _inst(60.186, 24.827, "Espoo", "Finland", "Aalto University"),
    "aalto university": _inst(60.186, 24.827, "Espoo", "Finland", "Aalto University"),
    "max planck": _inst(48.147, 11.577, "Munich", "Germany", "Max Planck Institute"),
    "university of zurich": _inst(47.375, 8.550, "Zurich", "Switzerland", "University of Zurich"),
    "uzh": _inst(47.375, 8.550, "Zurich", "Switzerland", "University of Zurich"),
    "epfl": _inst(46.519, 6.566, "Lausanne", "Switzerland", "École Polytechnique Fédérale de Lausanne"),
    "university of lausanne": _inst(46.524, 6.581, "Lausanne", "Switzerland", "University of Lausanne"),
    "lausanne university": _inst(46.524, 6.581, "Lausanne", "Switzerland", "University of Lausanne"),
    "uc san diego": _inst(32.880, -117.236, "San Diego", "CA, USA", "UC San Diego"),
    "university of southern california": _inst(34.022, -118.285, "Los Angeles", "CA, USA", "USC"),
    "georgia tech": _inst(33.775, -84.396, "Atlanta", "GA, USA", "Georgia Institute of Technology"),
    "georgia institute of technology": _inst(33.775, -84.396, "Atlanta", "GA, USA", "Georgia Institute of Technology"),
    "charles university": _inst(50.089, 14.402, "Prague", "Czech Republic", "Charles University"),
    "czech technical university in prague": _inst(50.104, 14.391, "Prague", "Czech Republic", "Czech Technical University in Prague"),
    "university of helsinki": _inst(60.170, 24.950, "Helsinki", "Finland", "University of Helsinki"),
    "university of oslo": _inst(59.940, 10.721, "Oslo", "Norway", "University of Oslo"),
    "ntnu": _inst(63.417, 10.403, "Trondheim", "Norway", "Norwegian University of Science and Technology"),
    "norwegian university of science and technology": _inst(63.417, 10.403, "Trondheim", "Norway", "Norwegian University of Science and Technology"),
    "university of copenhagen": _inst(55.680, 12.572, "Copenhagen", "Denmark", "University of Copenhagen"),
    "copenhagen university": _inst(55.680, 12.572, "Copenhagen", "Denmark", "University of Copenhagen"),
    "university of milan": _inst(45.464, 9.190, "Milan", "Italy", "Università degli Studi di Milano"),
    "politecnico di milano": _inst(45.478, 9.228, "Milan", "Italy", "Politecnico di Milano"),
    "sapienza": _inst(41.903, 12.516, "Rome", "Italy", "Sapienza Università di Roma"),
    "university of bologna": _inst(44.494, 11.347, "Bologna", "Italy", "University of Bologna"),
    "university of trento": _inst(46.069, 11.122, "Trento", "Italy", "University of Trento"),
    "unitrento": _inst(46.069, 11.122, "Trento", "Italy", "University of Trento"),
    "universidad católica san pablo": _inst(-16.399, -71.537, "Arequipa", "Peru", "Universidad Católica San Pablo"),
    "universidad catolica san pablo": _inst(-16.399, -71.537, "Arequipa", "Peru", "Universidad Católica San Pablo"),
    "ucsp": _inst(-16.399, -71.537, "Arequipa", "Peru", "Universidad Católica San Pablo"),
    "catholic university san pablo": _inst(-16.399, -71.537, "Arequipa", "Peru", "Universidad Católica San Pablo"),
    "catholic university of san pablo": _inst(-16.399, -71.537, "Arequipa", "Peru", "Universidad Católica San Pablo"),
    "san pablo catholic university": _inst(-16.399, -71.537, "Arequipa", "Peru", "Universidad Católica San Pablo"),
    "universidad de sevilla": _inst(37.380, -5.985, "Seville", "Spain", "Universidad de Sevilla"),
    "universidade de sevilha": _inst(37.380, -5.985, "Seville", "Spain", "Universidad de Sevilla"),
    "university of the basque country": _inst(43.331, -2.976, "Bilbao", "Spain", "University of the Basque Country"),
    "granada university": _inst(37.180, -3.600, "Granada", "Spain", "University of Granada"),
    "university of granada": _inst(37.180, -3.600, "Granada", "Spain", "University of Granada"),
    "universidad de la república": _inst(-34.900, -56.167, "Montevideo", "Uruguay", "Universidad de la República"),
    "udelar": _inst(-34.900, -56.167, "Montevideo", "Uruguay", "Universidad de la República"),
    "technological university of uruguay": _inst(-34.900, -56.167, "Montevideo", "Uruguay", "Universidad Tecnológica del Uruguay"),
    "utec": _inst(-34.900, -56.167, "Montevideo", "Uruguay", "Universidad Tecnológica del Uruguay"),
    "universidad tecnológica del uruguay": _inst(-34.900, -56.167, "Montevideo", "Uruguay", "Universidad Tecnológica del Uruguay"),
    "university of bristol": _inst(51.457, -2.603, "Bristol", "UK", "University of Bristol"),
    "university of southampton": _inst(50.935, -1.394, "Southampton", "UK", "University of Southampton"),
    "university of manchester": _inst(53.466, -2.229, "Manchester", "UK", "University of Manchester"),
    "university of sheffield": _inst(53.381, -1.487, "Sheffield", "UK", "University of Sheffield"),
    "university of liverpool": _inst(53.403, -2.970, "Liverpool", "UK", "University of Liverpool"),
    "university of york": _inst(53.946, -1.052, "York", "UK", "University of York"),
    "university of kent": _inst(51.296, 1.067, "Canterbury", "UK", "University of Kent"),
    "queen mary university of london": _inst(51.524, -0.040, "London", "UK", "Queen Mary University of London"),
    "university of aberdeen": _inst(57.165, -2.098, "Aberdeen", "UK", "University of Aberdeen"),
    "aston university": _inst(52.487, -1.889, "Birmingham", "UK", "Aston University"),
    "university of wolverhampton": _inst(52.585, -2.128, "Wolverhampton", "UK", "University of Wolverhampton"),
    "university of greenwich": _inst(51.483, 0.006, "London", "UK", "University of Greenwich"),
    "university of stirling": _inst(56.146, -3.920, "Stirling", "UK", "University of Stirling"),
    "lehigh university": _inst(40.599, -75.370, "Bethlehem", "PA, USA", "Lehigh University"),
    "university of maryland": _inst(38.987, -76.936, "College Park", "MD, USA", "University of Maryland"),
    "university of maryland baltimore": _inst(39.290, -76.612, "Baltimore", "MD, USA", "University of Maryland Baltimore"),
    "university of colorado": _inst(40.007, -105.267, "Boulder", "CO, USA", "University of Colorado Boulder"),
    "university of virginia": _inst(38.034, -78.508, "Charlottesville", "VA, USA", "University of Virginia"),
    "worcester polytechnic institute": _inst(42.274, -71.807, "Worcester", "MA, USA", "Worcester Polytechnic Institute"),
    "university of nebraska": _inst(40.820, -96.700, "Lincoln", "NE, USA", "University of Nebraska-Lincoln"),
    "university of rhode island": _inst(41.486, -71.530, "Kingston", "RI, USA", "University of Rhode Island"),
    "university of idaho": _inst(46.728, -117.015, "Moscow", "ID, USA", "University of Idaho"),
    "university of louisiana at lafayette": _inst(30.212, -92.019, "Lafayette", "LA, USA", "University of Louisiana at Lafayette"),
    "virginia tech": _inst(37.229, -80.415, "Blacksburg", "VA, USA", "Virginia Tech"),
    "penn state": _inst(40.798, -77.861, "State College", "PA, USA", "Penn State University"),
    "ohio state": _inst(40.005, -83.019, "Columbus", "OH, USA", "Ohio State University"),
    "michigan state": _inst(42.722, -84.483, "East Lansing", "MI, USA", "Michigan State University"),
    "university of florida": _inst(29.648, -82.345, "Gainesville", "FL, USA", "University of Florida"),
    "university of washington": _inst(47.655, -122.308, "Seattle", "WA, USA", "University of Washington"),
    "university of chicago": _inst(41.789, -87.599, "Chicago", "IL, USA", "University of Chicago"),
    "northeastern university": _inst(42.340, -71.089, "Boston", "MA, USA", "Northeastern University"),
    "boston university": _inst(42.350, -71.105, "Boston", "MA, USA", "Boston University"),
    "indiana university": _inst(39.169, -86.525, "Bloomington", "IN, USA", "Indiana University"),
    "university of pittsburgh": _inst(40.443, -79.953, "Pittsburgh", "PA, USA", "University of Pittsburgh"),
    "university of notre dame": _inst(41.703, -86.239, "Notre Dame", "IN, USA", "University of Notre Dame"),
    "university of minnesota": _inst(44.977, -93.234, "Minneapolis", "MN, USA", "University of Minnesota"),
    "university of wisconsin": _inst(43.074, -89.405, "Madison", "WI, USA", "University of Wisconsin-Madison"),
    "university of arizona": _inst(32.233, -110.950, "Tucson", "AZ, USA", "University of Arizona"),
    "arizona state": _inst(33.422, -111.939, "Tempe", "AZ, USA", "Arizona State University"),
    "university of utah": _inst(40.765, -111.837, "Salt Lake City", "UT, USA", "University of Utah"),
    "cincinnati": _inst(39.132, -84.522, "Cincinnati", "OH, USA", "University of Cincinnati"),
    "university of massachusetts": _inst(42.390, -72.526, "Amherst", "MA, USA", "UMass Amherst"),
    "syracuse university": _inst(43.037, -76.137, "Syracuse", "NY, USA", "Syracuse University"),
    "tulane university": _inst(29.939, -90.120, "New Orleans", "LA, USA", "Tulane University"),
    "vanderbilt": _inst(36.144, -86.802, "Nashville", "TN, USA", "Vanderbilt University"),
    "university of miami": _inst(25.721, -80.279, "Coral Gables", "FL, USA", "University of Miami"),
    "university of alabama": _inst(33.214, -87.543, "Tuscaloosa", "AL, USA", "University of Alabama"),
    "clemson university": _inst(34.681, -82.835, "Clemson", "SC, USA", "Clemson University"),
    "texas a&m": _inst(30.620, -96.337, "College Station", "TX, USA", "Texas A&M University"),
    "rice university": _inst(29.717, -95.401, "Houston", "TX, USA", "Rice University"),
    "caltech": _inst(34.138, -118.125, "Pasadena", "CA, USA", "California Institute of Technology"),
    "university of rochester": _inst(43.130, -77.629, "Rochester", "NY, USA", "University of Rochester"),
    "university of south-eastern norway": _inst(59.148, 9.633, "Porsgrunn", "Norway", "University of South-Eastern Norway"),
    "university of southern denmark": _inst(55.369, 10.431, "Odense", "Denmark", "University of Southern Denmark"),
    "university of antwerp": _inst(51.213, 4.452, "Antwerp", "Belgium", "University of Antwerp"),
    "university of wolverhampton": _inst(52.585, -2.128, "Wolverhampton", "UK", "University of Wolverhampton"),
    "university of duisburg-essen": _inst(51.458, 7.015, "Essen", "Germany", "University of Duisburg-Essen"),
    "humboldt university of berlin": _inst(52.518, 13.393, "Berlin", "Germany", "Humboldt University of Berlin"),
    "technical university of munich": _inst(48.149, 11.568, "Munich", "Germany", "Technical University of Munich"),
    "tum": _inst(48.149, 11.568, "Munich", "Germany", "Technical University of Munich"),
    "university of bonn": _inst(50.726, 7.083, "Bonn", "Germany", "University of Bonn"),
    "university of hannover": _inst(52.382, 9.718, "Hannover", "Germany", "Leibniz University Hannover"),
    "university of stuttgart": _inst(48.781, 9.177, "Stuttgart", "Germany", "University of Stuttgart"),
    "university of tübingen": _inst(48.524, 9.062, "Tübingen", "Germany", "University of Tübingen"),
    "universität tübingen": _inst(48.524, 9.062, "Tübingen", "Germany", "University of Tübingen"),
    "ruhr-university": _inst(51.444, 7.261, "Bochum", "Germany", "Ruhr University Bochum"),
    "linköping university": _inst(58.399, 15.575, "Linköping", "Sweden", "Linköping University"),
    "umeå university": _inst(63.817, 20.303, "Umeå", "Sweden", "Umeå University"),
    "blekinge institute of technology": _inst(56.243, 15.430, "Karlskrona", "Sweden", "Blekinge Institute of Technology"),
    "linnaeus university": _inst(56.877, 14.808, "Växjö", "Sweden", "Linnaeus University"),
    "chalmers university of tech.": _inst(57.687, 11.977, "Gothenburg", "Sweden", "Chalmers University of Technology"),
    "wageningen university and research": _inst(51.967, 5.666, "Wageningen", "Netherlands", "Wageningen University and Research"),
    "university of groningen": _inst(53.242, 6.537, "Groningen", "Netherlands", "University of Groningen"),
    "utrecht university": _inst(52.091, 5.120, "Utrecht", "Netherlands", "Utrecht University"),
    "maastricht university": _inst(50.847, 5.687, "Maastricht", "Netherlands", "Maastricht University"),
    "radboud university": _inst(51.818, 5.862, "Nijmegen", "Netherlands", "Radboud University"),
    "university of new south wales": _inst(-33.918, 151.232, "Sydney", "Australia", "UNSW Sydney"),
    "university of sydney": _inst(-33.888, 151.188, "Sydney", "Australia", "University of Sydney"),
    "university of melbourne": _inst(-37.796, 144.961, "Melbourne", "Australia", "University of Melbourne"),
    "queensland university of technology": _inst(-27.478, 153.028, "Brisbane", "Australia", "Queensland University of Technology"),
    "university of adelaide": _inst(-34.921, 138.604, "Adelaide", "Australia", "University of Adelaide"),
    "antoine university": _inst(-33.896, 151.212, "Sydney", "Australia", "University of Technology Sydney"),
    "university of canberra": _inst(-35.237, 149.085, "Canberra", "Australia", "University of Canberra"),
    "pohang university of science and technology": _inst(36.009, 129.323, "Pohang", "South Korea", "POSTECH"),
    "kaist": _inst(36.370, 127.367, "Daejeon", "South Korea", "KAIST"),
    "seoul national university": _inst(37.459, 126.952, "Seoul", "South Korea", "Seoul National University"),
    "nanyang technological university": _inst(1.348, 103.683, "Singapore", "Singapore", "Nanyang Technological University"),
    "national university of singapore": _inst(1.296, 103.776, "Singapore", "Singapore", "National University of Singapore"),
    "university of puerto rico": _inst(18.403, -66.050, "San Juan", "PR, USA", "University of Puerto Rico"),
    "universidad de ingeniería y tecnología": _inst(-12.115, -77.029, "Lima", "Peru", "Universidad de Ingeniería y Tecnología"),
    "universidad nacional de san agustín": _inst(-16.409, -71.537, "Arequipa", "Peru", "Universidad Nacional de San Agustín"),
    "universidad católica del perú": _inst(-12.071, -77.063, "Lima", "Peru", "Pontificia Universidad Católica del Perú"),
    "pontificia universidad católica del perú": _inst(-12.071, -77.063, "Lima", "Peru", "Pontificia Universidad Católica del Perú"),
    "universidad católica de santa maría": _inst(-16.415, -71.535, "Arequipa", "Peru", "Universidad Católica de Santa María"),
    "cinvestav": _inst(19.350, -99.166, "Mexico City", "Mexico", "CINVESTAV"),
    "unam": _inst(19.330, -99.183, "Mexico City", "Mexico", "Universidad Nacional Autónoma de México"),
    "tec de monterrey": _inst(25.652, -100.293, "Monterrey", "Mexico", "Tecnológico de Monterrey"),
    "instituto politécnico nacional": _inst(19.497, -99.135, "Mexico City", "Mexico", "Instituto Politécnico Nacional"),
    "university of the republic": _inst(-34.900, -56.167, "Montevideo", "Uruguay", "Universidad de la República"),
    "university of buenos aires": _inst(-34.600, -58.373, "Buenos Aires", "Argentina", "Universidad de Buenos Aires"),
    "university of chile": _inst(-33.457, -70.663, "Santiago", "Chile", "Universidad de Chile"),
    "pontificia universidad católica de chile": _inst(-33.456, -70.634, "Santiago", "Chile", "Pontificia Universidad Católica de Chile"),
    "university of cyprus": _inst(35.146, 33.413, "Nicosia", "Cyprus", "University of Cyprus"),
    "politecnico di torino": _inst(45.064, 7.661, "Turin", "Italy", "Politecnico di Torino"),
    "university of pisa": _inst(43.716, 10.398, "Pisa", "Italy", "University of Pisa"),
    "university of padua": _inst(45.412, 11.909, "Padua", "Italy", "University of Padua"),
    "university of trieste": _inst(45.656, 13.776, "Trieste", "Italy", "University of Trieste"),
    "university of genova": _inst(44.415, 8.926, "Genoa", "Italy", "University of Genoa"),
    "university of bergamo": _inst(45.702, 9.667, "Bergamo", "Italy", "University of Bergamo"),
    "university of salento": _inst(40.352, 18.172, "Lecce", "Italy", "University of Salento"),
    "university of málaga": _inst(36.717, -4.425, "Málaga", "Spain", "University of Málaga"),
    "université de rennes 1": _inst(48.116, -1.679, "Rennes", "France", "Université de Rennes 1"),
    "université gustave eiffel": _inst(48.855, 2.779, "Paris", "France", "Université Gustave Eiffel"),
    "avignon université": _inst(43.951, 4.808, "Avignon", "France", "Avignon Université"),
    "université toulouse i": _inst(43.610, 1.440, "Toulouse", "France", "Université Toulouse I"),
    "university of toulouse": _inst(43.610, 1.440, "Toulouse", "France", "Université de Toulouse"),
    "centre inria de l'université de lille": _inst(50.612, 3.129, "Lille", "France", "Inria Lille"),
    "inria université de lille": _inst(50.612, 3.129, "Lille", "France", "Inria Lille"),
    "inria sophia antipolis": _inst(43.625, 7.009, "Sophia Antipolis", "France", "Inria Sophia Antipolis"),
    "univ. lille": _inst(50.629, 3.075, "Lille", "France", "Université de Lille"),
    "université bourgogne franche-comté": _inst(47.322, 5.041, "Dijon", "France", "Université Bourgogne Franche-Comté"),
    "paris seine university": _inst(49.014, 2.378, "Cergy", "France", "Paris Seine University"),
    "université catholique de louvain": _inst(50.668, 4.611, "Louvain-la-Neuve", "Belgium", "Université Catholique de Louvain"),
    "university of abuja": _inst(9.021, 7.483, "Abuja", "Nigeria", "University of Abuja"),
    "university of lagos": _inst(6.518, 3.385, "Lagos", "Nigeria", "University of Lagos"),
    "university of zimbabwe": _inst(-17.789, 31.051, "Harare", "Zimbabwe", "University of Zimbabwe"),
    "university of engineering & management": _inst(22.531, 88.344, "Kolkata", "India", "University of Engineering & Management"),
    "indian statistical institute": _inst(22.653, 88.395, "Kolkata", "India", "Indian Statistical Institute"),
    "indian institute of technology": _inst(12.988, 80.232, "Chennai", "India", "IIT Madras"),
    "indian institute of technology masdras": _inst(12.988, 80.232, "Chennai", "India", "IIT Madras"),
    "indraprastha institute of information technology delhi": _inst(28.594, 77.267, "New Delhi", "India", "IIIT Delhi"),
    "university of hong kong": _inst(22.283, 114.139, "Hong Kong", "China", "University of Hong Kong"),
    "tsinghua university": _inst(39.996, 116.326, "Beijing", "China", "Tsinghua University"),
    "pekking university": _inst(39.995, 116.331, "Beijing", "China", "Peking University"),
    "shanghai jiao tong university": _inst(31.204, 121.431, "Shanghai", "China", "Shanghai Jiao Tong University"),
    "zhejiang university": _inst(30.274, 120.094, "Hangzhou", "China", "Zhejiang University"),
    "university of science and technology of china": _inst(31.825, 117.281, "Hefei", "China", "USTC"),
    "nankai university": _inst(39.100, 117.174, "Tianjin", "China", "Nankai University"),
    "sun yat-sen university": _inst(23.094, 113.354, "Guangzhou", "China", "Sun Yat-sen University"),
    "wuhan university": _inst(30.541, 114.358, "Wuhan", "China", "Wuhan University"),
    "nanjing university": _inst(32.056, 118.772, "Nanjing", "China", "Nanjing University"),
    "beijing institute of technology": _inst(39.965, 116.321, "Beijing", "China", "Beijing Institute of Technology"),
    "zhongyuan university of technology": _inst(34.749, 113.614, "Zhengzhou", "China", "Zhongyuan University of Technology"),
    "los alamos national laboratory": _inst(35.881, -106.302, "Los Alamos", "NM, USA", "Los Alamos National Laboratory"),
    "nasa": _inst(38.883, -77.016, "Washington", "DC, USA", "NASA"),
    "ibm research": _inst(41.196, -73.795, "Yorktown Heights", "NY, USA", "IBM Research"),
    "ibm": _inst(41.196, -73.795, "Yorktown Heights", "NY, USA", "IBM"),
    "microsoft": _inst(47.640, -122.129, "Redmond", "WA, USA", "Microsoft Research"),
    "google research": _inst(37.422, -122.084, "Mountain View", "CA, USA", "Google Research"),
    "meta": _inst(37.485, -122.148, "Menlo Park", "CA, USA", "Meta AI"),
    "amazon": _inst(47.615, -122.340, "Seattle", "WA, USA", "Amazon"),
    "apple": _inst(37.331, -122.030, "Cupertino", "CA, USA", "Apple"),
    "nasa ames": _inst(37.415, -122.068, "Moffett Field", "CA, USA", "NASA Ames Research Center"),
    "jet propulsion laboratory": _inst(34.201, -118.171, "Pasadena", "CA, USA", "JPL"),
    "max planck institute": _inst(48.147, 11.577, "Munich", "Germany", "Max Planck Institute"),
    "mpi": _inst(48.147, 11.577, "Munich", "Germany", "Max Planck Institute"),
    "mines saint-etienne": _inst(45.420, 4.392, "Saint-Étienne", "France", "Mines Saint-Étienne"),
    "ensmm": _inst(47.322, 5.041, "Besançon", "France", "ENSMM"),
    "university of beira interior": _inst(40.277, -7.509, "Covilhã", "Portugal", "University of Beira Interior"),
    "inesc": _inst(38.737, -9.137, "Lisbon", "Portugal", "INESC"),
    "instituto superior técnico": _inst(38.737, -9.137, "Lisbon", "Portugal", "Instituto Superior Técnico"),
    "instituto politécnico de bragança": _inst(41.805, -6.759, "Bragança", "Portugal", "Instituto Politécnico de Bragança"),
    "ipb": _inst(41.805, -6.759, "Bragança", "Portugal", "Instituto Politécnico de Bragança"),
    "polytechnic institute of tomar": _inst(39.604, -8.420, "Tomar", "Portugal", "Polytechnic Institute of Tomar"),
    "portalegre polytechnic university": _inst(39.291, -7.431, "Portalegre", "Portugal", "Portalegre Polytechnic University"),
    "university of algarve": _inst(37.014, -7.933, "Faro", "Portugal", "University of the Algarve"),
    "ualg": _inst(37.014, -7.933, "Faro", "Portugal", "University of the Algarve"),
    "universidade do algarve": _inst(37.014, -7.933, "Faro", "Portugal", "University of the Algarve"),
    "universidade portucalense": _inst(41.167, -8.607, "Porto", "Portugal", "Universidade Portucalense"),
    "university of minho": _inst(41.559, -8.397, "Braga", "Portugal", "University of Minho"),
    "uminho": _inst(41.559, -8.397, "Braga", "Portugal", "University of Minho"),
    "new university of lisbon": _inst(38.738, -9.137, "Lisbon", "Portugal", "NOVA University Lisbon"),
    "north eastern university london": _inst(51.528, -0.045, "London", "UK", "Northeastern University London"),
    "instituto de educação": _inst(-22.755, -43.459, "Rio de Janeiro", "RJ", "Instituto de Educação"),
    "universidad de nariño": _inst(1.214, -77.277, "Pasto", "Colombia", "Universidad de Nariño"),
    "escuela superior politécnica del litoral": _inst(-2.150, -79.890, "Guayaquil", "Ecuador", "ESPOL"),
    "universidad nacional de trujillo": _inst(-8.113, -79.028, "Trujillo", "Peru", "Universidad Nacional de Trujillo"),
    "universidad estatal de milagro": _inst(-2.129, -79.586, "Milagro", "Ecuador", "Universidad Estatal de Milagro"),
    "universidad ricardo palma": _inst(-12.092, -77.045, "Lima", "Peru", "Universidad Ricardo Palma"),
    "universidad nacional tecnologica de lima sur": _inst(-12.203, -76.797, "Lima", "Peru", "UNTELS"),
}

# Merge all dictionaries (last defined key wins if duplicates exist)
ALL_INSTITUTIONS = {}
for d in [INSTITUTIONS_BR, INSTITUTES, IFS, INTERNATIONAL]:
    ALL_INSTITUTIONS.update(d)

# Add common case variants for all keys
_keys = list(ALL_INSTITUTIONS.keys())
for k in _keys:
    for variant in [k.upper(), k.lower(), k.capitalize(), k.title()]:
        if variant not in ALL_INSTITUTIONS:
            ALL_INSTITUTIONS[variant] = ALL_INSTITUTIONS[k]


def normalize_affiliation(aff: str) -> str:
    """Normalize an affiliation string for dictionary lookup."""
    s = aff.strip()
    s = s.strip('"\'.,;:()[]{} ')
    # Remove parenthetical qualifiers like (UNIFESP), (USP)
    s = re.sub(r'\s*\([^)]*\)\s*', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s.lower()


def clean_compound(aff: str) -> str:
    """Take the first part of compound affiliations like 'FURG / UFAM'."""
    s = aff.strip()
    parts = re.split(r'\s*/\s*', s)
    return parts[0].strip()


def lookup_institution(aff: str):
    """Try to find coordinates for an affiliation string. Multi-strategy."""
    norm = normalize_affiliation(aff)

    # Strategy 1: Direct lookup
    if norm in ALL_INSTITUTIONS:
        return ALL_INSTITUTIONS[norm]

    # Strategy 2: Try stripping common prefixes
    prefixes = [
        "universidade federal do ", "universidade federal de ", "universidade federal da ",
        "universidade estadual do ", "universidade estadual de ", "universidade estadual da ",
        "universidade do ", "universidade de ", "universidade da ",
        "universidad nacional de ", "universidad de ", "universidad del ",
        "federal university of ", "university of ", "state university of ",
        "pontifícia universidade católica de ", "pontifícia universidade católica do ",
        "pontifical catholic university of ",
        "instituto federal do ", "instituto federal de ", "instituto federal da ",
        "instituto de ", "instituto do ", "instituto da ",
        "centro universitário ", "centro federal de ",
        "universidade ", "universidad ", "university ",
        "instituto ", "institute ", "faculdade ", "facultad ",
    ]
    for prefix in prefixes:
        if norm.startswith(prefix):
            stripped = norm[len(prefix):].strip()
            if stripped in ALL_INSTITUTIONS:
                return ALL_INSTITUTIONS[stripped]

    # Strategy 3: Check if any known key is a substring of norm or vice versa
    # (sort longest first to avoid short false matches)
    for key in sorted(ALL_INSTITUTIONS.keys(), key=len, reverse=True):
        if len(key) >= 4 and (key in norm or norm in key):
            return ALL_INSTITUTIONS[key]

    # Strategy 4: Try each word in the name as a potential acronym
    words = norm.split()
    for w in words:
        if len(w) >= 3 and w in ALL_INSTITUTIONS:
            return ALL_INSTITUTIONS[w]

    # Strategy 5: Remove non-alphanumeric characters and try matching
    alphanum = re.sub(r'[^a-z0-9]', '', norm)
    for key in sorted(ALL_INSTITUTIONS.keys(), key=len, reverse=True):
        key_alphanum = re.sub(r'[^a-z0-9]', '', key)
        if len(key_alphanum) >= 4 and (key_alphanum in alphanum or alphanum in key_alphanum):
            return ALL_INSTITUTIONS[key]

    return None


# %% [markdown]
# ## Load researchers and geocode

# %%
log.info("Loading researchers...")
researchers = pd.read_parquet(CLEAN_DIR / "researchers_with_topics.parquet")
log.info("Loaded %d researchers", len(researchers))

# Collect all unique affiliations from the dataset
all_affiliations = set()
for affs in researchers["affiliations"]:
    if isinstance(affs, (list, np.ndarray)):
        for aff in affs:
            all_affiliations.add(str(aff).strip())

log.info("Total unique affiliations: %d", len(all_affiliations))

# For each affiliation, try the primary name first, then compound-cleaned versions
geo_cache = {}
unmatched = []

for aff in sorted(all_affiliations):
    # Try original
    result = lookup_institution(aff)
    if result:
        geo_cache[aff] = result
        continue

    # Try compound-cleaned
    cleaned = clean_compound(aff)
    if cleaned != aff:
        result = lookup_institution(cleaned)
        if result:
            geo_cache[aff] = result
            continue

    # Try further - remove everything after comma too
    simple = re.split(r'\s*[,;]\s*', aff)[0].strip()
    if simple != aff and simple != cleaned:
        result = lookup_institution(simple)
        if result:
            geo_cache[aff] = result
            continue

    unmatched.append(aff)

log.info("Matched: %d / %d", len(geo_cache), len(all_affiliations))
log.info("Unmatched: %d", len(unmatched))
for aff in unmatched[:50]:
    log.info("  UNMATCHED: %s", aff)

# %% [markdown]
# ## Fallback: Nominatim geocoding for unmatched

# %%
GEOCODED_PATHS = {}

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

USE_NOMINATIM = False  # Skip Nominatim (slow); use manual additions in the dict

if USE_NOMINATIM:
    log.info("Attempting Nominatim fallback for %d institutions...", len(unmatched))
    geolocator = Nominatim(user_agent="mapa_de_ia_geocoder")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.5)

    for i, aff in enumerate(unmatched):
        try:
            # Try with "Brazil" suffix for Brazilian institutions
            query = f"{aff}, Brazil"
            location = geocode(query)
            if location is None:
                location = geocode(aff)
            if location:
                geo_cache[aff] = (
                    location.latitude,
                    location.longitude,
                    location.address.split(",")[0].strip() if location.address else aff,
                    "",
                    aff,
                )
                log.info("  [%d/%d] ✓ %s -> (%.4f, %.4f)", i + 1, len(unmatched), aff[:50], location.latitude, location.longitude)
            else:
                log.info("  [%d/%d] ✗ %s -> not found", i + 1, len(unmatched), aff[:50])
        except Exception as e:
            log.warning("  [%d/%d] ✗ %s -> error: %s", i + 1, len(unmatched), aff[:50], str(e))
            time.sleep(2)
else:
    log.info("Skipping Nominatim (%d unmatched, threshold < 500 needed)", len(unmatched))

# %% [markdown]
# ## Map each researcher to their primary institution's coordinates

# %%
# For each researcher, take their FIRST listed affiliation as primary institution
researcher_locations = []
missed = 0

for _, r in researchers.iterrows():
    affs = r["affiliations"]
    if isinstance(affs, (list, np.ndarray)) and len(affs) > 0:
        primary = str(affs[0]).strip()
        if primary in geo_cache:
            lat, lng, city, state, full_name = geo_cache[primary]
            researcher_locations.append({
                "normalized_name": r["normalized_name"],
                "display_name": r["display_name"],
                "n_articles": int(r["n_articles"]),
                "first_year": int(r["first_year"]),
                "last_year": int(r["last_year"]),
                "cluster": int(r["cluster"]),
                "topic_name": r["topic_name"] if not pd.isna(r.get("topic_name")) else None,
                "topic_keywords": list(r["topic_keywords"]) if isinstance(r.get("topic_keywords"), (list, np.ndarray)) else [],
                "primary_affiliation": primary,
                "lat": float(lat),
                "lng": float(lng),
                "city": city,
                "state": state,
            })
        else:
            missed += 1
    else:
        missed += 1

log.info("Researchers with location: %d / %d", len(researcher_locations), len(researchers))
log.info("Missed (no location): %d", missed)

# %% [markdown]
# ## Save outputs

# %%
# Save institution coordinates cache
out_cache = {}
for aff, (lat, lng, city, state, full_name) in geo_cache.items():
    out_cache[aff] = {
        "lat": lat, "lng": lng,
        "city": city, "state": state,
        "full_name": full_name,
    }

with open(OUT_DIR / "institutions_geo.json", "w", encoding="utf-8") as f:
    json.dump(out_cache, f, ensure_ascii=False, indent=2)
log.info("Saved institutions_geo.json (%d entries)", len(out_cache))

# Save researcher locations
with open(OUT_DIR / "researchers_geo.json", "w", encoding="utf-8") as f:
    json.dump(researcher_locations, f, ensure_ascii=False, indent=2)
log.info("Saved researchers_geo.json (%d researchers)", len(researcher_locations))

# %% [markdown]
# ## Summary

# %%
print(f"\n{'='*50}")
print("GEOCODING SUMMARY")
print(f"{'='*50}")
print(f"  Total unique affiliations:  {len(all_affiliations)}")
print(f"  Matched via dictionary:     {len(geo_cache)}")
print(f"  Unmatched (no coords):      {len(unmatched)}")
print(f"  Researchers with location:  {len(researcher_locations)} / {len(researchers)}")
print(f"  Researchers missed:         {missed}")
print(f"\n  Output files:")
print(f"    data/output/institutions_geo.json    — coordinate cache for all institutions")
print(f"    data/output/researchers_geo.json     — researcher-level locations with topics")
