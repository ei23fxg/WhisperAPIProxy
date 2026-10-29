# Whisper-API-Proxy mit lokalen Fallback-Engines (Parakeet/Whistle)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg: Opus-Archivierung, Audio-Normalisierung für die lokalen Engines,
#         und das, was pydub ohnehin erwartet
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 5431

# Ein Worker: die Modelle und die Zustände (local_service_available) sind
# prozesslokal, mehrere Worker würden sie vervielfachen.
ENTRYPOINT ["./docker-entrypoint.sh"]
