#!/bin/bash
cd "$(dirname "$0")/.."
.venv/bin/streamlit run app/streamlit_app.py --server.address localhost --server.port 8501
