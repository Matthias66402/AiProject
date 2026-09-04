# AiProject

Generative-AI-Testprojekt: eine Flask-Webanwendung zur Verwaltung von Stellenanbietern (Kunden), Stellenangeboten und Nutzern, mit einem integrierten KI-Assistenten, der Fragen zur Website, Stellenbewerbung und Stellenveröffentlichung beantwortet.

Die Website ist noch im Aufbau, Struktur und Funktionsumfang können sich häufig ändern.

## Funktionen

- **KI-Assistent** (Startseite): beantwortet Fragen zur Website über wählbare KI-Modelle. Der System-Prompt bekommt bei jeder Anfrage automatisch die aktuelle Seitenstruktur (aus den registrierten Flask-Routen erzeugt) mitgegeben, damit der Assistent nichts über nicht existierende Funktionen erfindet.
  - Modelle über [Groq](https://groq.com/) (`openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.6-27b`, `groq/compound-mini`)
  - Modelle über [OpenAI](https://platform.openai.com/) (`gpt-5-mini`, `gpt-4o-mini`, `gpt-4.1-mini`)
- **Login/Registrierung**: Nutzer registrieren sich (immer mit Rolle `user`), melden sich an/ab; Passwörter werden gehasht (Werkzeug) gespeichert.
- **Rollen**: `user` (Standard bei Registrierung), `customer`, `admin` — Liste zentral in `db.py` (`ROLES`). `admin` vergibt Rollen und hat vollen Schreibzugriff auf Nutzer-, Stellenanbieter- und Stellenverwaltung. `customer`-Nutzer sind über `users.customer_id` (nullable FK auf `customers`, Zuweisung durch einen Admin im Nutzerformular) genau einem Stellenanbieter zugeordnet und dürfen dadurch **nur ihre eigenen** Stellenangebote anlegen/bearbeiten/löschen sowie ihren eigenen Stellenanbieter-Datensatz bearbeiten (Anlegen/Löschen von Stellenanbietern bleibt `admin` vorbehalten).
- **Nutzerverwaltung** (`/users`, nur `admin`): Nutzer anlegen, bearbeiten, Rolle zuweisen, optional PLZ/Stadt hinterlegen. Bei Rolle `customer` erscheint zusätzlich eine Selectbox zur Zuordnung eines Stellenanbieters. Zeigt außerdem alle für diesen Nutzer generierten/hochgeladenen Lebensläufe (Tabelle `resumes`, FK auf `users`), falls vorhanden.
- **Eigener Lebenslauf** (`/resumes`, für jeden eingeloggten Nutzer mit Rolle `user`): zeigt den aktuellsten eigenen Lebenslauf (PDF eingebettet, andere Formate als Download-Link); eine Selectbox erlaubt den Zugriff auf ältere Versionen, ein Löschbutton entfernt den ausgewählten Lebenslauf inkl. Datei. Zwei Wege für einen neuen Lebenslauf:
  - **Generieren** — dieselbe KI-Logik wie das Admin-Tool `/tools/resume`: verwendet immer den echten Namen des Nutzers, der Wohnort wird nur übernommen, wenn PLZ **und** Stadt hinterlegt sind (sonst frei erfunden).
  - **Hochladen** (Dropzone mit Drag & Drop) — eigene Datei als PDF/.docx/.odt hochladen; der Text wird ausgelesen (`document_extraction.py`) und wie bei der Generierung vektorisiert.

  Die Dateiauslieferung prüft Besitzerschaft (nur die eigenen Lebensläufe, unabhängig vom Admin-Zugriff auf `/tools/resume/<datei>`).
- **Stellenangebote** (`/jobs`): Stellenanzeigen mit Gültigkeitszeitraum, PLZ/Stadt und Zuordnung zu einem Stellenanbieter. Liste paginiert (Standard 10/Seite, per Selectbox auf 10/25/50/100 einstellbar).
  - `admin`: anlegen/bearbeiten/löschen für jeden Stellenanbieter.
  - `customer`-Nutzer mit zugeordnetem Stellenanbieter: anlegen/bearbeiten/löschen nur für den eigenen Stellenanbieter — serverseitig erzwungen, unabhängig vom Formularinhalt.
  - Alle anderen (inkl. nicht eingeloggt): nur Liste + Lesemodus ("Ansehen") pro Stelle — Position, Kunde, PLZ/Stadt, Gültigkeitszeitraum als Text, bei KI-generierten/hochgeladenen Stellen zusätzlich das Dokument eingebettet (PDF) bzw. als Download-Link (andere Formate) statt der reinen Textbeschreibung.
  - Beim Anlegen kann optional ein Stellenangebot-Dokument (PDF/.docx/.odt) per Dropzone hochgeladen werden (`/jobs/extract-upload`): die KI fasst den Inhalt als Beschreibung zusammen und befüllt Position/PLZ/Stadt, sofern im Text eindeutig erkennbar.
- **Stellenanbieter** (`/customers`): Kunden (Unternehmen) mit Adresse. Liste paginiert (Standard testweise 2/Seite, `CUSTOMERS_PER_PAGE_DEFAULT` in `app.py`).
  - `admin`: anlegen, bearbeiten, löschen.
  - `customer`-Nutzer mit zugeordnetem Stellenanbieter: dürfen nur ihren eigenen Datensatz bearbeiten (nicht anlegen/löschen).
  - Alle anderen: nur Liste + Lesemodus ("Ansehen"), kein Bearbeiten/Löschen.
  - Die Bearbeiten-Ansicht zeigt zusätzlich die zu diesem Stellenanbieter gehörenden Stellenangebote.
- **Tools-Menü** (nur für Rolle `admin`): lässt die KI Inhalte als HTML formulieren und rendert sie per WeasyPrint zu PDF, mit dezentem Lade-Spinner während der Generierung und Link zum Öffnen der fertigen Datei in einem neuen Tab.
  - **Lebenslauf generieren** (`/tools/resume`): ein bestehender Nutzer wird per Selectbox ausgewählt. Sind bei ihm PLZ **und** Stadt hinterlegt, übernimmt die KI dessen echten Namen und Wohnort unverändert (Rest frei erfunden); ansonsten ein komplett fiktiver Dummy-Lebenslauf. Das PDF wird unter `data/resumes/` abgelegt und als neuer Eintrag in `resumes` (FK auf den Nutzer) gespeichert.
  - **Stellenangebot generieren** (`/tools/joboffer`): ein Stellenanbieter wird per Selectbox ausgewählt. Die KI liefert Position, PLZ, Stadt und den Stellentext strukturiert als JSON zurück; das PDF wird unter `data/joboffers/` abgelegt und automatisch ein passender Eintrag in `/jobs` angelegt (inkl. `document_link`, Gültigkeit heute bis +30 Tage).
  - ⚠️ Läuft nur, wo WeasyPrints native Abhängigkeiten (Pango/Cairo) vorhanden sind — siehe [WeasyPrint unter Windows](#weasyprint-unter-windows) weiter unten. Im Docker-Image ist das bereits eingerichtet.

## Embeddings (RAG-Grundlage)

Jeder Job (`jobs.embedding`) und jeder Lebenslauf (`resumes.embedding`) bekommt beim Anlegen/Ändern automatisch ein OpenAI-Embedding (`text-embedding-3-small`) berechnet und als [pgvector](https://github.com/pgvector/pgvector) `vector(1536)`-Spalte gespeichert — sowohl bei manueller Eingabe als auch bei KI-Generierung über die Tools-Seiten. Die Ähnlichkeitssuche läuft nativ in SQL über den Cosine-Distance-Operator `<=>`, indiziert per HNSW-Index (`idx_jobs_embedding_hnsw`/`idx_resumes_embedding_hnsw`), statt Embeddings nach Python zu laden. Zuständig ist `embeddings.py`:

- `strip_html_to_text()` — bereitet die HTML-Inhalte (`content`) für ein sauberes Embedding auf
- `embed_text()` / `embed_texts()` — einzelnes bzw. batch-weises Embedding über die OpenAI-API; API-Fehler (Status-, Verbindungs-, Timeout-Fehler) werden abgefangen und geloggt, statt das eigentliche Anlegen/Ändern zu blockieren
- `to_vector_literal()` — formatiert ein Embedding als pgvector-Text-Literal zum Schreiben über einen `::vector`-Cast

`db.find_matching_jobs(embedding, top_k)` / `db.find_matching_resumes(embedding, top_k)` liefern die ähnlichsten Einträge (Cosine Similarity, SQL-nativ, ab einer Mindest-Ähnlichkeit `MIN_MATCH_SIMILARITY` in `db.py`) — Grundlage für das Matching zwischen Kandidat und Stellenangebot: passende Stellenangebote erscheinen auf `/resumes` beim jeweiligen Lebenslauf, passende Kandidaten auf der Bearbeiten-Ansicht eines Stellenangebots (`/jobs/<id>/edit`, nur für Admins bzw. den zuständigen `customer`-Nutzer).

## Datei-Uploads (Lebenslauf & Stellenangebot)

Sowohl `/resumes` (eigener Lebenslauf) als auch `/jobs` (Stelle anlegen) bieten neben der KI-Generierung eine Dropzone zum Hochladen einer eigenen Datei — PDF, Word (`.docx`) oder LibreOffice/OpenDocument (`.odt`); das alte binäre `.doc`-Format wird bewusst nicht unterstützt. Zuständig ist `document_extraction.py`:

- `extract_document_text(filename, file_stream)` — liest den reinen Text aus PDF (`pypdf`), `.docx` (`python-docx`) oder `.odt` (`odfpy`) aus
- `ALLOWED_DOCUMENT_UPLOAD_EXTENSIONS` — die erlaubten Endungen, zentral für beide Upload-Flows

Beim Lebenslauf wird der ausgelesene Text direkt gespeichert und vektorisiert. Beim Stellenangebot (`/jobs/extract-upload`) durchläuft der Text zusätzlich eine KI-Zusammenfassung (JSON-Antwort mit `position`/`zip`/`city`/`content`), die das Formular vorbefüllt, bevor der Admin bzw. `customer`-Nutzer die Stelle final anlegt. In beiden Fällen wird die Originaldatei unverändert unter `data/resumes/` bzw. `data/joboffers/` abgelegt (`app.config["MAX_CONTENT_LENGTH"]` begrenzt Uploads auf 10 MB).

`backfill_embeddings.py` berechnet einmalig Embeddings für bestehende Jobs/Lebensläufe ohne Embedding nach (z.B. nach der Einführung dieses Features oder bei einem Modellwechsel):

```bash
docker compose exec app python backfill_embeddings.py
```

## Tech-Stack

- **Backend**: Flask (Python 3.14)
- **Datenbank**: PostgreSQL 16 (Image `pgvector/pgvector:pg16`) über psycopg2, inkl. [pgvector](https://github.com/pgvector/pgvector)-Extension für die Ähnlichkeitssuche; Schema wird beim App-Start automatisch angelegt und migriert (`db.init_db()`)
- **KI**: [Groq](https://pypi.org/project/groq/)- und [OpenAI](https://pypi.org/project/openai/)-Python-SDKs
- **PDF-Erzeugung**: [WeasyPrint](https://pypi.org/project/weasyprint/) rendert vom KI-Modell geliefertes HTML zu PDF. Benötigt native Pango/Cairo-Bibliotheken (siehe unten) — im `Dockerfile` und in der CI bereits per `apt` eingerichtet
- **Datei-Parsing**: [pypdf](https://pypi.org/project/pypdf/), [python-docx](https://pypi.org/project/python-docx/), [odfpy](https://pypi.org/project/odfpy/) — Textextraktion aus hochgeladenen PDF/.docx/.odt-Dateien, reines Python ohne native Abhängigkeiten
- **Frontend**: Jinja2-Templates, Tailwind-Klassen, Font Awesome (lokal in `static/fontawesome`)
- **Deployment**: Docker + docker-compose (App + PostgreSQL)
- **CI**: GitHub Actions (Syntaxcheck, Smoke-Test, Docker-Build) — siehe `.github/workflows/main.yml`

## Projektstruktur

```
app.py                     Flask-Routen, KI-Assistent-Logik, Modellauswahl
db.py                      DB-Verbindung, Schema-Erstellung/Migration, CRUD-Funktionen
embeddings.py              Embedding-Erzeugung (einzeln/batch), HTML-Stripping, Cosinus-Ähnlichkeit/Top-Matches
document_extraction.py     Textextraktion aus hochgeladenen PDF/.docx/.odt-Dateien (Lebenslauf- und Stellenangebot-Upload)
backfill_embeddings.py     Einmaliges Nachrechnen fehlender Embeddings für Bestandsdaten
migrate_mysql_to_postgres.py Einmaliges Migrationsskript für den Umstieg von MySQL auf PostgreSQL (Bestandsdaten inkl. IDs übernehmen)
templates/
  index.html                Basis-Layout, bindet navigation.html + content_template ein
  navigation.html            Navigationsleiste inkl. Konto-Dropdown (Anmelden/Registrieren/Abmelden/eigener Lebenslauf), "Nutzer"-Link und Tools-Dropdown (beide nur Admin)
  home.html                  KI-Assistent-Formular (Startseite)
  login.html, register.html  Anmeldung/Registrierung (Registrierung fragt PLZ/Stadt verpflichtend ab)
  user.html                  Nutzerverwaltung, inkl. Stellenanbieter-Zuordnung für Rolle 'customer'
  jobs.html                  Stellenangebote, inkl. Upload-Dropzone und Pager
  customer.html              Stellenanbieter, inkl. Pager
  resume.html                 Tools: Lebenslauf generieren (nur Admin)
  joboffer.html                Tools: Stellenangebot generieren (nur Admin)
  my_resumes.html              Eigener Lebenslauf ansehen/generieren/hochladen/löschen (jeder eingeloggte Nutzer)
static/
  style.css                  eigenes Stylesheet
  fontawesome/                lokal eingebundene Icon-Bibliothek
data/                        generierte und hochgeladene Lebenslauf-/Stellenangebot-Dateien, von Git ausgeschlossen; im Docker-Setup per Bind-Mount (./data:/app/data) persistent auf dem Host
  resumes/
  joboffers/
Dockerfile                  Python-3.14-slim-Image für die App
docker-compose.yml          App + PostgreSQL-Service für lokalen/Produktions-Betrieb, mountet ./data in den App-Container
.github/workflows/main.yml  CI: Syntaxcheck, Smoke-Test, Docker-Build
.env.example                Vorlage für benötigte Umgebungsvariablen
```

## Setup

### Voraussetzungen

- Python 3.14
- PostgreSQL-Server (lokal oder über Docker)
- API-Keys für [Groq](https://console.groq.com/) und [OpenAI](https://platform.openai.com/)

### Lokal ohne Docker

```bash
pip install -r requirements.txt
cp .env.example .env   # Werte eintragen, siehe unten
python app.py
```

Die App läuft danach auf `http://localhost:5003`.

#### WeasyPrint unter Windows

`pip install weasyprint` reicht unter Windows **nicht** aus: Der Import schlägt mit `OSError: cannot load library ... libgobject-2.0-0.dll` fehl, weil WeasyPrint zur Laufzeit native GTK-Bibliotheken (Pango/Cairo/GObject) über `cffi` lädt, die kein reines Python-Package sind. Betroffen sind ausschließlich die beiden Tools-Seiten (`/tools/resume`, `/tools/joboffer`) — der Rest der App läuft davon unberührt, **außer** der komplette App-Import schlägt fehl, weil `from weasyprint import HTML` ganz oben in `app.py` steht.

Lokale Entwicklung unter Windows ohne Docker wird für dieses Feature aktuell nicht unterstützt/dokumentiert — für die Tools-Seiten (und damit zum vollständigen Start der App) bitte über Docker Compose laufen lassen; dort ist alles Nötige bereits eingerichtet.

### Mit Docker Compose

```bash
cp .env.example .env   # Werte eintragen
docker compose up --build
```

Startet App und PostgreSQL zusammen; die DB-Daten liegen in einem benannten Volume (`aiproject_postgres_data`), generierte PDFs unter `./data` (Bind-Mount, direkt im Projektordner sichtbar).

### Umgebungsvariablen (`.env`)

| Variable | Bedeutung |
|---|---|
| `GROQ_API_KEY` | API-Key für Groq (Chat-Modelle) |
| `OPENAI_API_KEY` | API-Key für OpenAI (Chat-Modelle + Embeddings) |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Verbindungsdaten zur PostgreSQL-Datenbank |
| `SECRET_KEY` | Flask-Session-Secret |

`.env` ist per `.gitignore` von Git ausgeschlossen — nur `.env.example` wird versioniert.

### Von MySQL migrieren

Bis einschließlich Commit vor dieser Umstellung lief das Projekt auf MySQL
8.0. Wer noch Bestandsdaten in einer alten MySQL-DB hat, migriert sie per
`migrate_mysql_to_postgres.py` (Details/Voraussetzungen im Skript-Docstring):

```bash
docker compose exec app python migrate_mysql_to_postgres.py
```

## KI-Assistent erweitern

Neue Modelle in `app.py` ergänzen: Eintrag in `AVAILABLE_MODELS` (Anzeigename), `AVAILABE_MODEL_NAMES` (Kurzname für Fehlermeldungen) und `MODEL_CLIENTS` (welcher Client — `client` für Groq, `openai_client` für OpenAI — zuständig ist).

Neue Seiten/Routen tauchen automatisch im System-Prompt des Assistenten auf (`build_site_map()` liest live aus `app.url_map`). Für eine sprechende Beschreibung im Prompt zusätzlich einen Eintrag in `PAGE_DESCRIPTIONS` ergänzen — fehlt er, erscheint die Route trotzdem mit Platzhalter, damit der Assistent ihre Existenz nicht ignoriert oder erfindet.
