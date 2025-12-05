FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && mkdir /app

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Warsaw
RUN apt-get install -y tzdata

ADD . /app
WORKDIR /app

RUN uv sync --locked

RUN uv run alembic upgrade head

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]