FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/requirements.txt \
    && python -m playwright install --with-deps chromium

# Development convenience: bake .env into the image for local runs.
# Do NOT do this in production; inject environment at runtime via secrets/CI/CD.
COPY . /app

EXPOSE 8000

CMD ["python", "main.py"]
