FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
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
COPY config/ ./config/
RUN cp config/tariffs/mpesa_p2p_users_2026-08-04.csv /opt/pricing/tariff.csv \
    && chown -R pricing:pricing /opt/pricing /app

USER pricing
EXPOSE 10000 8000
CMD ["sh", "-c", "if [ -n \"$APP_MODULE\" ]; then MODULE=\"$APP_MODULE\"; elif [ \"$RENDER\" = \"true\" ]; then MODULE=\"src.api.hosted:app\"; else MODULE=\"src.api.deployment:app\"; fi; exec uvicorn \"$MODULE\" --host 0.0.0.0 --port \"${PORT:-10000}\""]
