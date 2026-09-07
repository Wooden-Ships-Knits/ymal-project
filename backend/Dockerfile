FROM python:3.12-slim

# Faster startup, no .pyc litter in the image, unbuffered logs so a long
# pipeline run streams instead of appearing all at once when it finishes.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Requirements first, so a code change does not reinstall dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default to the pipeline. The api service overrides this with uvicorn once
# backend/app exists.
CMD ["python", "-m", "scripts.build_blocks"]
