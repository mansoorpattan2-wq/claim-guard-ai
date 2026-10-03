FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000 APP_ENV=production
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home appuser
COPY app ./app
COPY demo ./demo
COPY run.py manage.py ./
RUN mkdir -p /data/uploads && chown -R appuser:appuser /data /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=7s --retries=10 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=5)"
CMD ["python", "run.py"]
