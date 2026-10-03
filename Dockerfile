FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2-dev libjack-dev portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py ampero_mini.py ./

ENV PORT=8080
EXPOSE 8080
CMD ["python", "server.py"]
