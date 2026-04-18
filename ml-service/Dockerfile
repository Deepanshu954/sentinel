FROM python:3.11-slim

RUN groupadd -r sentinel && useradd -r -g sentinel sentinel

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY model_weights/ /app/models/
COPY service/ /app/service/
COPY ml/ /app/ml/
COPY scripts/ /app/scripts/

RUN chown -R sentinel:sentinel /app

USER sentinel

EXPOSE 8000

CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
