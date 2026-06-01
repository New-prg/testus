FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt ./
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["bash", "-lc", "alembic upgrade head && python -m app.cli seed-demo-admin && (python -u -m app.cli seed-demo-data &) && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
