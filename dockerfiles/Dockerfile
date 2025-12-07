FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN apt-get update && mkdir /app

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Warsaw

ARG PG_VERSION=17
# ARG ELASTIC_VERSION=latest
# ARG QDRANT_CLIENT_VERSION=latest
# ARG HVAC_VERSION=latest

RUN apt update && apt install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    tzdata

RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-archive-keyring.gpg

RUN echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list

RUN apt update && apt install -y --no-install-recommends \
    postgresql-client-${PG_VERSION} \
    && rm -rf /var/lib/apt/lists/*

ADD . /app
WORKDIR /app

RUN uv sync --locked

RUN uv add \
    elasticsearch${ELASTIC_VERSION:+==${ELASTIC_VERSION}} \
    qdrant-client${QDRANT_CLIENT_VERSION:+==${QDRANT_CLIENT_VERSION}} \
    hvac${HVAC_VERSION:+==${HVAC_VERSION}}

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]