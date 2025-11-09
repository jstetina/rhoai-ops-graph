FROM python:3.12-slim

ARG JENKINS_MCP_LIB_PATH=../jenkins_mcp

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY . /app/jenkins-agent

COPY ${JENKINS_MCP_LIB_PATH} /app/lib/jenkins_mcp

WORKDIR /app/jenkins-agent

RUN uv sync

EXPOSE 8501

ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV JENKINS_MCP_LIB_PATH=${JENKINS_MCP_LIB_PATH:-/app}
ENV PYTHONPATH=/app/lib:${PYTHONPATH}

CMD [".venv/bin/streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
