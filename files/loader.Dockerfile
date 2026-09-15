# One-shot image that loads the pipeline artifacts into Postgres.
# Only the deps the loader needs (NOT the heavy NLP stack).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /repo
RUN pip install --no-cache-dir \
    pandas pyarrow numpy \
    SQLAlchemy "psycopg[binary]" GeoAlchemy2 \
    "pydantic>=2.7" pydantic-settings \
    "fastapi-users[sqlalchemy]>=13.0"
# ^ needed because app/models.py imports the User table base from fastapi-users;
#   importing the models module pulls in the auth models too.
# Repo is bind-mounted at runtime (files/, backend/, data/).
CMD ["python", "files/06_load_db.py"]
