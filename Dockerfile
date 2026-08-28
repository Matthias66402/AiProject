FROM python:3.14-slim

WORKDIR /app

# WeasyPrint (PDF-Erzeugung für die Tools-Seiten) braucht Pango/Cairo zum Rendern von HTML/CSS.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2 \
    libgdk-pixbuf-2.0-0 shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5003

CMD ["python", "app.py"]
