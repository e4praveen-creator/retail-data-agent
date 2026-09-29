FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY retail_app/requirements.lock.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd --uid 10001 --create-home retail
COPY retail_app/backend /workspace/retail_app/backend
COPY retail_app/__init__.py /workspace/retail_app/__init__.py
COPY retail_app/static /workspace/retail_app/static
COPY retail_app/docs /workspace/retail_app/docs
COPY retail_app/knowledge /workspace/retail_app/knowledge
COPY retail-data-analyst /workspace/retail-data-analyst
COPY retail_playbook_library.md /workspace/retail_playbook_library.md
COPY retail_data/docs /workspace/retail_data/docs
COPY retail_data/sql /workspace/retail_data/sql
COPY retail_data/src /workspace/retail_data/src
RUN mkdir -p /workspace/retail_app/state && chown retail:retail /workspace/retail_app/state
USER retail
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health/ready', timeout=4)"
CMD ["uvicorn", "retail_app.backend.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1", "--limit-concurrency", "32", "--timeout-keep-alive", "5", "--timeout-graceful-shutdown", "15", "--no-server-header", "--no-access-log"]
