FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py ampero_mini.py usbmidi.py ./

ENV PORT=8080
EXPOSE 8080
CMD ["python", "server.py"]
