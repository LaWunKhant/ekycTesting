FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    default-libmysqlclient-dev \
    gcc \
    libglib2.0-0 \
    libgl1 \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/staticfiles && \
    python manage.py collectstatic --noinput

EXPOSE 10000

CMD ["./bin/render-start.sh"]
