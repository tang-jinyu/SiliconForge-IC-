FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends iverilog yosys \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY digital_ic_agent ./digital_ic_agent
COPY project_prompt ./project_prompt
COPY skills ./skills
COPY benchmarks ./benchmarks
COPY examples ./examples
COPY picture ./picture
RUN python -m pip install --upgrade pip && python -m pip install .

RUN useradd --create-home --uid 10001 agent \
    && mkdir -p /app/runs /app/.agent_queue \
    && chown -R agent:agent /app
USER agent

EXPOSE 8000
VOLUME ["/app/runs", "/app/.agent_queue"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["digital-ic-agent", "serve", "--host", "0.0.0.0", "--port", "8000"]
