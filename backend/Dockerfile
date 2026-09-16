FROM python:3.10.16-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/worker.py /opt/worker.py
USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "/opt/worker.py"]
