FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NLTK_DATA=/usr/local/nltk_data \
    PRICING_ARTIFACT_DIR=/opt/pricing/artifacts \
    PRICING_TARIFF_CSV=/opt/pricing/tariff.csv

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m nltk.downloader -q -d /usr/local/nltk_data stopwords wordnet \
    && useradd --system --create-home pricing \
    && mkdir -p /opt/pricing/artifacts \
    && chown -R pricing:pricing /opt/pricing
COPY src/ ./src/

USER pricing
EXPOSE 8000
CMD ["uvicorn", "src.deployment:app", "--host", "0.0.0.0", "--port", "8000"]
