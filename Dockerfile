FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_PORT=3000

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 3000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${APP_PORT:-3000} app:app"]
