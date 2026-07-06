FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && chown app:app /app

COPY --chown=app:app . .

RUN mkdir -p /app/staticfiles \
    && chown app:app /app/staticfiles

USER app

EXPOSE 8003

CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8003"]
