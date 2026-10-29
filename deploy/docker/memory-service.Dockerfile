ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app AGNO_TELEMETRY=false
WORKDIR /app
COPY deploy/requirements/memory-service.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY agent_runtime /app/agent_runtime
COPY response_language.py model_protocols.py execution_protocol.py execution_lifecycle.py construction_access.py workspace_storage.py runtime_observability.py /app/
COPY backend/__init__.py backend/data_paths.py /app/backend/
COPY graph_engine/__init__.py graph_engine/tool_execution.py graph_engine/finance_catalog.py graph_engine/borylation_catalog.py /app/graph_engine/
RUN useradd --create-home --uid 10001 memory
USER memory
EXPOSE 21113
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=12 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:21113/internal/memory/health', timeout=2)"
CMD ["python", "-m", "agent_runtime.memory_service"]
