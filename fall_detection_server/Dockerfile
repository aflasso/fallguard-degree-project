FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY config.py main.py ./
COPY domain/       domain/
COPY application/  application/
COPY infrastructure/ infrastructure/
COPY api/          api/

RUN pip install --no-cache-dir -e .

# credentials/ y .env se montan en runtime — nunca se hornean en la imagen
RUN mkdir -p credentials

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
