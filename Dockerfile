FROM golang:1.26-bookworm AS douyin-cli-builder
RUN GOBIN=/out go install github.com/tamnd/douyin-cli/cmd/douyin@v0.1.1

FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=douyin-cli-builder /out/douyin /usr/local/bin/douyin
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY docs ./docs

ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
