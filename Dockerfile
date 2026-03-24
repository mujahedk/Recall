FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# storage/ holds uploaded PDFs and the FAISS index at runtime.
# Mount a persistent volume here in production — the directory is gitignored
# and its contents are lost on container restart without a volume.
RUN mkdir -p storage

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
