FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN useradd --create-home --uid 10002 nexus
COPY pyproject.toml README.md ./
COPY nexus_mcp ./nexus_mcp
RUN pip install .

USER nexus
# MCP over stdio: no port is exposed. Attach with `docker compose run --rm mcp`.
CMD ["python", "-m", "nexus_mcp.server"]
