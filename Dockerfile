FROM python:3.11-slim

# librsvg2-bin provides rsvg-convert to rasterise the EuroLeague SVG logo
RUN apt-get update && apt-get install -y --no-install-recommends librsvg2-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Convert EuroLeague SVG → PNG at build time (falls back silently if it fails)
RUN rsvg-convert -w 300 -h 300 assets/euroleague_logo.svg \
        -o assets/euroleague_logo.png 2>/dev/null || true

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
