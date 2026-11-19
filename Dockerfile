# Imagem da API + tela de cadastro, com Tesseract (português)
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY api ./api
ENV CADASTRO_DB=/home/dados/cadastros.sqlite3 OMP_THREAD_LIMIT=1 PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.app:app --host 0.0.0.0 --port ${PORT}"]
