# AiProject

Generative-AI-Testprojekt: eine Flask-Webanwendung zur Verwaltung von Stellenanbietern (Kunden), Stellenangeboten und Nutzern, mit einem integrierten KI-Assistenten, der Fragen zur Website, Stellenbewerbung und Stellenveröffentlichung beantwortet.

Jede Seite existiert doppelt: klassisch als Jinja-Template und als React-SPA (`frontend/`) über eine JSON-API (`api/`). **React ist die Standard-Oberfläche** — siehe [Frontend](#frontend-react--klassisch) unten. Die Website ist noch im Aufbau, Struktur und Funktionsumfang können sich häufig ändern.

## Funktionen

- **KI-Assistent** (Startseite `/`): beantwortet Fragen zur Website über wählbare KI-Modelle. Der System-Prompt bekommt bei jeder Anfrage automatisch die aktuelle Seitenstruktur mitgegeben (`build_site_map()` in `app.py`, live aus `app.url_map`), damit der Assistent nichts über nicht existierende Funktionen erfindet. Modell-Logik zentral in `services/assistant_service.py` (`ask_assistant()`).
  - Modelle über [Groq](https://groq.com/) — **optional**: ohne `GROQ_API_KEY` werden diese Modelle automatisch ausgeblendet.
  - Modelle über [OpenAI](https://platform.openai.com/) — `OPENAI_API_KEY` ist Pflicht, da auch die Embeddings darüber laufen.
- **Login/Registrierung** (`/login`, `/register`): Nutzer registrieren sich (immer mit Rolle `user`), melden sich an/ab; Passwörter gehasht (Werkzeug).
- **Rollen**: `user` (Standard), `customer`, `admin` (`models/user.py`, `ROLES`). `admin` hat vollen Schreibzugriff. `customer`-Nutzer sind über `users.customer_id` genau einem Stellenanbieter zugeordnet und dürfen dadurch **nur ihre eigenen** Stellenangebote und ihren eigenen Stellenanbieter-Datensatz bearbeiten.
- **Nutzerverwaltung** (`/users`, nur `admin`): anlegen, bearbeiten, Rolle zuweisen, Stellenanbieter-Zuordnung bei Rolle `customer`, Übersicht der Lebensläufe des Nutzers. Kein Löschen — dafür gibt es keine Funktion.
- **Eigener Lebenslauf** (`/resumes`, jeder eingeloggte Nutzer): aktuellster Lebenslauf eingebettet (PDF) bzw. als Download; Selectbox für ältere Versionen; Löschen. Neuen Lebenslauf per KI **generieren** (echter Name, Wohnort nur bei hinterlegter PLZ+Stadt) oder eigene Datei **hochladen** (Dropzone, PDF/.docx/.odt, Text via `document_extraction.py` ausgelesen und vektorisiert).
- **Stellenangebote** (`/jobs`): Stellenanzeigen mit Gültigkeitszeitraum, PLZ/Stadt, Stellenanbieter-Zuordnung; paginierte Liste.
  - `admin`: anlegen/bearbeiten/löschen für jeden Stellenanbieter. `customer`-Nutzer: nur für den eigenen (serverseitig erzwungen). Alle anderen: nur Lesemodus.
  - Optionaler Dokumenten-Upload (PDF/.docx/.odt) beim Anlegen (`/jobs/extract-upload`): KI fasst Inhalt zusammen und befüllt Position/PLZ/Stadt.
- **Stellenanbieter** (`/customers`): Kunden (Unternehmen) mit Adresse, paginierte Liste, inkl. Liste der zugehörigen Stellenangebote in der Bearbeiten-Ansicht.
  - `admin`: anlegen/bearbeiten/löschen. `customer`-Nutzer: nur der eigene Datensatz bearbeiten. Alle anderen: nur Lesemodus.
- **Tools-Menü** (nur `admin`): lässt die KI Inhalte als HTML formulieren und rendert sie per WeasyPrint zu PDF.
  - **Lebenslauf generieren** (`/tools/resume`): Nutzer per Selectbox wählen, PDF wird unter `resumes` gespeichert.
  - **Stellenangebot generieren** (`/tools/joboffer`): Stellenanbieter per Selectbox wählen, legt automatisch einen passenden Eintrag unter `/jobs` an.
  - ⚠️ Läuft nur, wo WeasyPrints native Abhängigkeiten (Pango/Cairo) vorhanden sind — siehe [WeasyPrint unter Windows](#weasyprint-unter-windows). Im Docker-Image bereits eingerichtet.

## Embeddings (RAG-Grundlage)

Jeder Job und jeder Lebenslauf bekommt beim Anlegen/Ändern automatisch ein OpenAI-Embedding (`text-embedding-3-small`) und wird als [pgvector](https://github.com/pgvector/pgvector) `vector(1536)` gespeichert. Die Ähnlichkeitssuche läuft nativ in SQL über Cosine-Distance, indiziert per HNSW-Index. Zuständig ist `embeddings.py` (`strip_html_to_text()`, `embed_text()`/`embed_texts()`, `to_vector_literal()`); API-Fehler werden abgefangen/geloggt statt das Anlegen zu blockieren.

`db.find_matching_jobs()` / `db.find_matching_resumes()` liefern die ähnlichsten Einträge ab einer Mindest-Ähnlichkeit (`MIN_MATCH_SIMILARITY`, `models/base.py`) — Grundlage für das Matching zwischen Kandidat und Stellenangebot (angezeigt auf `/resumes` bzw. `/jobs/<id>/edit`).

`backfill_embeddings.py` berechnet einmalig fehlende Embeddings für Bestandsdaten nach:

```bash
docker compose exec app python backfill_embeddings.py
```

## Datei-Uploads

`/resumes` und `/jobs` (Anlegen) bieten neben der KI-Generierung eine Dropzone für PDF/.docx/.odt (`.doc` bewusst nicht unterstützt). `document_extraction.py` liest den Text aus (`pypdf`/`python-docx`/`odfpy`). Beim Stellenangebot durchläuft der Text zusätzlich eine KI-Zusammenfassung. Originaldateien landen unverändert unter `data/resumes/` bzw. `data/joboffers/` (Uploads auf 10 MB begrenzt).

## Tech-Stack

- **Backend**: Flask (Python 3.14)
- **Datenbank**: PostgreSQL 16 (`pgvector/pgvector:pg16`) + [pgvector](https://github.com/pgvector/pgvector). Schema/Migration über psycopg2 (`db/db_init.py`); CRUD über [SQLAlchemy](https://pypi.org/project/SQLAlchemy/) (`models/`)
- **KI**: [Groq](https://pypi.org/project/groq/)- und [OpenAI](https://pypi.org/project/openai/)-SDKs
- **PDF-Erzeugung**: [WeasyPrint](https://pypi.org/project/weasyprint/) (HTML → PDF), braucht native Pango/Cairo-Bibliotheken (im Dockerfile eingerichtet)
- **Datei-Parsing**: [pypdf](https://pypi.org/project/pypdf/), [python-docx](https://pypi.org/project/python-docx/), [odfpy](https://pypi.org/project/odfpy/)
- **Frontend (klassisch)**: Jinja2-Templates, Tailwind-Klassen, Font Awesome
- **Frontend (React)**: [React](https://react.dev/) + [Vite](https://vitejs.dev/) + [react-router-dom](https://reactrouter.com/) (`frontend/`) — teilt sich `static/style.css` mit den klassischen Templates
- **Rich-Text-Editor**: [Quill](https://quilljs.com/) (Stellenangebot-Beschreibung, beide Frontends) + [DOMPurify](https://github.com/cure53/DOMPurify) zur Sanitisierung
- **Deployment**: Docker + docker-compose (App + PostgreSQL + React-Dev-Server)
- **CI**: GitHub Actions (Syntaxcheck, Smoke-Test, Docker-Build) — `.github/workflows/main.yml`

## Projektstruktur

```
app.py                     Flask-Routen (klassische Jinja-Seiten), React-Default-Redirect, registriert die api/-Blueprints
api/                       JSON-API fürs React-Frontend, läuft parallel zu den klassischen Routen
  auth.py                     /api/auth/me + login/register/logout
  jobs.py                     /api/jobs-Endpunkte
  customers.py                /api/customers-Endpunkte
  users.py                    /api/users-Endpunkte (kein Löschen; entfernt password_hash aus jeder Antwort)
  resumes.py                  /api/resumes-Endpunkte (Liste/Anzeige/Generieren/Hochladen/Löschen)
  tools.py                    /api/tools/resume + /api/tools/joboffer (KI-Generierung)
  assistant.py                /api/assistant(/ask) für die Startseite
db/                        DB-Verbindung & Schema, von außen per `import db` genutzt
models/                    SQLAlchemy-ORM-Modelle + CRUD je Tabelle (user/customer/job/resume, base.py mit Engine/Session)
services/                  Von app.py und api/ gemeinsam genutzte Logik
  assistant_service.py        KI-Assistent-Logik (`ask_assistant()`)
  auth_service.py              Login-Session befüllen (`log_in_user()`)
  permissions.py                Rollen-/Berechtigungslogik
  resume_service.py / joboffer_service.py   KI-Generierung + Uploads (inkl. Embedding)
  pdf_service.py                HTML-zu-PDF (WeasyPrint)
  ai_clients.py / text_utils.py Client-Instanzen, KI-Antworten aufbereiten
frontend/                  React-SPA (Vite) - alle Seiten umgezogen, siehe "Frontend" unten
  src/pages/                   je eine Komponente pro Seite (Home, Jobs, Customers, Users, Tools, Resumes, Login, Register)
  src/components/              JobForm/-Table, CustomerForm/-Table, UserForm/-Table, JobUploadDropzone, Pager, RichTextEditor (Quill)
embeddings.py              Embedding-Erzeugung, HTML-Stripping, Ähnlichkeits-Matching
document_extraction.py     Textextraktion aus PDF/.docx/.odt-Uploads
backfill_embeddings.py     Einmaliges Nachrechnen fehlender Embeddings
migrate_mysql_to_postgres.py  Einmaliges Migrationsskript MySQL → PostgreSQL
templates/                 Klassische Jinja-Seiten (index.html als Layout, navigation.html, home/jobs/customer/user/login/register/my_resumes/resume/joboffer.html)
static/                    style.css (gemeinsam mit React genutzt), lokales Font Awesome
data/                      Generierte/hochgeladene Dateien, von Git ausgeschlossen, per Bind-Mount persistent (./data)
Dockerfile                 Python-3.14-slim-Image für die App
docker-compose.yml         App + PostgreSQL + React-Dev-Server
.github/workflows/main.yml CI: Syntaxcheck, Smoke-Test, Docker-Build
.env.example                Vorlage für Umgebungsvariablen
```

## Setup

### Voraussetzungen

- Python 3.14
- PostgreSQL-Server (lokal oder über Docker)
- API-Key für [OpenAI](https://platform.openai.com/), optional für [Groq](https://console.groq.com/)

### Lokal ohne Docker

```bash
pip install -r requirements.txt
cp .env.example .env   # Werte eintragen, siehe unten
python app.py
```

Die App läuft danach auf `http://localhost:5003`.

⚠️ React ist die Standard-Oberfläche (siehe [Frontend](#frontend-react--klassisch)) — ohne separat laufenden React-Dev-Server (`frontend/`, Port 5173) leiten `http://localhost:5003/...`-Aufrufe ins Leere. Entweder zusätzlich `npm install && npm run dev` in `frontend/` starten, oder einmalig `http://localhost:5003/?classic=1` aufrufen, um dauerhaft bei der klassischen Ansicht zu bleiben.

#### WeasyPrint unter Windows

`pip install weasyprint` reicht unter Windows **nicht**: Der Import schlägt fehl, weil WeasyPrint native GTK-Bibliotheken (Pango/Cairo/GObject) lädt, die kein reines Python-Package sind. Betroffen sind nur die Tools-Seiten — **außer** der komplette App-Import schlägt fehl (`from weasyprint import HTML` steht ganz oben in `app.py`). Lokale Entwicklung unter Windows ohne Docker wird dafür nicht unterstützt — bitte über Docker Compose laufen lassen, dort ist alles eingerichtet.

### Mit Docker Compose

```bash
cp .env.example .env   # Werte eintragen
docker compose up --build
```

Startet App, PostgreSQL und den React-Dev-Server zusammen; DB-Daten in einem benannten Volume (`aiproject_postgres_data`), generierte PDFs unter `./data`. `http://localhost:5003` leitet automatisch auf `http://localhost:5173` weiter — beide Adressen funktionieren.

`docker-compose.yml` lädt `.env` nur **einmalig beim Erstellen** des App-Containers. Änderungen werden erst nach `docker compose up -d app` (Neuerstellung) wirksam. Reine Python-/Template-Änderungen übernimmt dagegen der Flask-Debug-Reloader automatisch.

### Umgebungsvariablen (`.env`)

| Variable | Bedeutung |
|---|---|
| `GROQ_API_KEY` | API-Key für Groq. **Optional**: leer/fehlend blendet die darüber erreichbaren Modelle automatisch aus |
| `OPENAI_API_KEY` | API-Key für OpenAI (Chat-Modelle + Embeddings). Pflicht |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Verbindungsdaten zur PostgreSQL-Datenbank |
| `SECRET_KEY` | Flask-Session-Secret |

`.env` ist per `.gitignore` von Git ausgeschlossen — nur `.env.example` wird versioniert.

## Frontend (React + klassisch)

Alle Seiten sind sowohl als klassisches Jinja-Template als auch als React-Komponente (`frontend/`, eigenständiges Vite-Projekt, Port 5173) verfügbar; beide sprechen dieselbe Flask-Session (CORS via `FRONTEND_ORIGIN`) und dieselbe Business-Logik in `services/`. React ruft ausschließlich die JSON-API unter `api/` an — es wird an keiner Stelle zur klassischen Darstellung gesprungen; ein "Klassisch"-Link im React-Menü bleibt als bewusster Ausstieg bestehen.

Erwähnenswerte Details:
- **`/api/users`** entfernt `password_hash` aus jeder Antwort.
- **`/api/resumes`** entfernt `embedding`/`content`; die PDF-Auslieferung bleibt die klassische, besitzerschaftsgeprüfte Route `/resumes/<id>/file`. Beim Datei-Upload per Drag & Drop wird die Datei zusätzlich in den nativen `<input type="file">` übernommen, sonst schlägt die HTML5-`required`-Prüfung beim Absenden fehl.
- **Login/Registrieren/Abmelden**: eigene React-Formulare rufen `/api/auth/login` bzw. `/register` auf; `App.jsx` reicht `refreshUser()` per Outlet-Context an die Seiten weiter. Abmelden läuft im Konto-Menü als Button (`POST /api/auth/logout`), ohne Seitenwechsel.
- **Layout**: `App.jsx` bildet das klassische `body`-Flex-Layout 1:1 nach (`#root { display: contents; }` in `static/style.css`), damit Nav- und Content-Breite wie bei Flask konstant bleiben.
- npm-Abhängigkeiten über die Standardkomponenten hinaus: `quill`, `dompurify`.

### React als Standard-Oberfläche

Ein `@app.before_request`-Hook in `app.py` (`redirect_to_react_by_default()`) leitet GET-Aufrufe einer klassischen Seite automatisch auf `FRONTEND_ORIGIN` um (`_REACT_PAGE_ROUTES` listet die betroffenen Endpunkte; Datei-Auslieferungsrouten, Lösch-Endpunkte, `/api/*` und `/static/*` bleiben immer außen vor). POST/PUT/DELETE werden nie umgeleitet, sonst würden Formularabsendungen der klassischen Seiten ins Leere laufen.

Der "Klassisch"-Link im React-Menü hängt `?classic=1` an und merkt sich das in der Flask-Session (`session["ui_pref"]`) — bleibt bis Browser-Neustart oder Abmelden (`session.clear()`) bestehen und hält sämtliche Folgenavigation auf der klassischen Seite. `?classic=0` macht die Wahl rückgängig und leitet sofort wieder auf React um.

## Von MySQL migrieren

Bis einschließlich Commit vor der Postgres-Umstellung lief das Projekt auf MySQL 8.0. Bestandsdaten migriert `migrate_mysql_to_postgres.py` (Details im Skript-Docstring):

```bash
docker compose exec app python migrate_mysql_to_postgres.py
```

## KI-Assistent erweitern

Neue Modelle in `services/assistant_service.py` ergänzen: Eintrag in `AVAILABLE_MODELS`, `AVAILABE_MODEL_NAMES` und `MODEL_CLIENTS`. Ohne `GROQ_API_KEY` werden neue Groq-Modelle automatisch ausgeblendet. Die Änderung wirkt automatisch auf klassische Startseite und React (`/api/assistant`), da beide dieselbe Quelle nutzen.

Neue Seiten/Routen tauchen automatisch im System-Prompt auf (`build_site_map()`); für eine sprechende Beschreibung zusätzlich einen Eintrag in `PAGE_DESCRIPTIONS` ergänzen.
