FROM python:3.11-slim
RUN pip install --no-cache-dir requests requests-unixsocket
COPY exporter.py /app/exporter.py
EXPOSE 9200
CMD ["python3", "-u", "/app/exporter.py"]
