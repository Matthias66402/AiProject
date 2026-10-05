# AiProject

Generative-AI-Testprojekt: eine React-SPA (`frontend/`) zur Verwaltung von Stellenanbietern (Kunden), Stellenangeboten und Nutzern, mit einem integrierten KI-Assistenten, der Fragen zur Website, Stellenbewerbung und Stellenveröffentlichung beantwortet. Das Backend ist eine Flask-JSON-API (`api/`) inkl. interaktiver [Swagger/OpenAPI-Dokumentation](#api-dokumentation-swagger--openapi). Die Website ist noch im Aufbau, Struktur und Funktionsumfang können sich häufig ändern.

Flask liefert **keine eigenen Seiten** mehr aus — nur noch JSON (`/api/*`) sowie einige Datei-Auslieferungsrouten für hochgeladene/generierte PDFs (`/tools/resume/<datei>`, `/tools/joboffer/<datei>`, `/resumes/<id>/file`, `/jobs/extract-upload`). Die komplette Oberfläche läuft über React.

## Funktionen

- **KI-Assistent** (React-Startseite `/`): beantwortet Fragen zur Website über wählbare KI-Modelle. Der System-Prompt bekommt bei jeder Anfrage automatisch die aktuelle React-Seitenliste mitgegeben (`build_site_map()` in `app.py`), damit der Assistent nichts über nicht existierende Funktionen erfindet. Modell-Logik zentral in `services/assistant_service.py` (`ask_assistant()`).
  - Modelle über [Groq](https://groq.com/) — **optional**: ohne `GROQ_API_KEY` werden diese Modelle automatisch ausgeblendet.
  - Modelle über [OpenAI](https://platform.openai.com/) — `OPENAI_API_KEY` ist Pflicht, da auch die Embeddings darüber laufen.
- **Login/Registrierung** (`/login`, `/register`): Nutzer registrieren sich (immer mit Rolle `user`), melden sich an/ab; Passwörter gehasht (Werkzeug), Session-Cookie-Auth.
- **Rollen**: `user` (Standard), `customer`, `admin` (`models/user.py`, `ROLES`). `admin` hat vollen Schreibzugriff. `customer`-Nutzer sind über `users.customer_id` genau einem Stellenanbieter zugeordnet und dürfen dadurch **nur ihre eigenen** Stellenangebote und ihren eigenen Stellenanbieter-Datensatz bearbeiten.
- **Nutzerverwaltung** (`/users`, nur `admin`): anlegen, bearbeiten, Rolle zuweisen, Stellenanbieter-Zuordnung bei Rolle `customer`, Übersicht der Lebensläufe des Nutzers. Kein Löschen — dafür gibt es keine Funktion.
- **Eigener Lebenslauf** (`/resumes`, jeder eingeloggte Nutzer): aktuellster Lebenslauf eingebettet (PDF) bzw. als Download; Selectbox für ältere Versionen; Löschen. Neuen Lebenslauf per KI **generieren** (echter Name, Wohnort nur bei hinterlegter PLZ+Stadt) oder eigene Datei **hochladen** (Dropzone, PDF/.docx/.odt, Text via `document_extraction.py` ausgelesen und vektorisiert).
- **Stellenangebote** (`/jobs`): Stellenanzeigen mit Gültigkeitszeitraum, PLZ/Stadt, Stellenanbieter-Zuordnung; paginierte Liste mit Suche, Zeilenklick öffnet die Detailansicht.
  - `admin`: anlegen/bearbeiten/löschen für jeden Stellenanbieter. `customer`-Nutzer: nur für den eigenen (serverseitig erzwungen). Alle anderen: nur Lesemodus.
  - Optionaler Dokumenten-Upload (PDF/.docx/.odt) beim Anlegen (`/jobs/extract-upload`): KI fasst Inhalt zusammen und befüllt Position/PLZ/Stadt.
- **Stellenanbieter** (`/customers`): Kunden (Unternehmen) mit Adresse, paginierte Liste mit Suche, inkl. Liste der zugehörigen Stellenangebote in der Bearbeiten-Ansicht.
  - `admin`: anlegen/bearbeiten/löschen. `customer`-Nutzer: nur der eigene Datensatz bearbeiten. Alle anderen: nur Lesemodus.
- **Tools-Menü** (nur `admin`): lässt die KI Inhalte als HTML formulieren und rendert sie per WeasyPrint zu PDF.
  - **Lebenslauf generieren** (`/tools/resume`): Nutzer per Selectbox wählen, PDF wird unter `resumes` gespeichert.
  - **Stellenangebot generieren** (`/tools/joboffer`): Stellenanbieter per Selectbox wählen, legt automatisch einen passenden Eintrag unter `/jobs` an.
  - ⚠️ Läuft nur, wo WeasyPrints native Abhängigkeiten (Pango/Cairo) vorhanden sind — siehe [WeasyPrint unter Windows](#weasyprint-unter-windows). Im Docker-Image bereits eingerichtet.

### Löschen = Deaktivieren

„Löschen" bei Stellenangeboten, Stellenanbietern und Lebensläufen entfernt die Datenbankzeile **nicht** wirklich, sondern setzt nur ein `deleted`-Flag (`jobs`, `customers`, `resumes`, Migration in `db/db_init.py`). Alle Listen-/Detail-Abfragen (`models/job.py`, `models/customer.py`, `models/resume.py`) blenden `deleted = true`-Zeilen konsequent aus — für Nutzer:innen unterscheidet sich das nicht von einem echten Löschen, verhindert aber z.B. Fremdschlüssel-Probleme (ein Stellenanbieter mit bestehenden Stellenangeboten lässt sich so problemlos "löschen"). Es gibt aktuell **keine** Oberfläche zum Wiederherstellen — dafür müsste das Flag direkt in der Datenbank zurückgesetzt werden. Im React-Frontend fragt vor dem Löschen ein Modal-Dialog nach (`frontend/src/components/ConfirmProvider.jsx`) statt des Browser-`confirm()`.

## API-Dokumentation (Swagger / OpenAPI)

Alle `/api/*`-Endpunkte sind über [Swagger UI](https://swagger.io/tools/swagger-ui/) ([flasgger](https://github.com/flasgger/flasgger)) interaktiv dokumentiert und direkt im Browser testbar:

- **UI**: `http://localhost:5003/apidocs/`
- **Rohe OpenAPI-Spec**: `http://localhost:5003/apispec.json`

Auth läuft über das Flask-Session-Cookie: Endpoint `POST /api/auth/login` in Swagger UI mit „Try it out" ausführen (setzt das Cookie im Browser), danach funktionieren auch geschützte Endpunkte, solange `/apidocs/` und die App unter derselben Origin geöffnet sind. Die eigentlichen Parameter-/Response-Beschreibungen stehen als YAML-Docstrings direkt bei den jeweiligen Routen in `api/*.py`; die Konfiguration (Titel, Security-Definition fürs Session-Cookie, gemeinsame Error-/Success-Schemas) sitzt in `app.py`. Klassische Datei-Auslieferungsrouten (`/tools/resume/<datei>` etc.) tauchen bewusst **nicht** in der Spec auf (`rule_filter` beschränkt sie auf `/api/*`).

## Embeddings (RAG-Grundlage)

Jeder Job und jeder Lebenslauf bekommt beim Anlegen/Ändern automatisch ein OpenAI-Embedding (`text-embedding-3-small`) und wird als [pgvector](https://github.com/pgvector/pgvector) `vector(1536)` gespeichert. Die Ähnlichkeitssuche läuft nativ in SQL über Cosine-Distance, indiziert per HNSW-Index. Zuständig ist `embeddings.py` (`strip_html_to_text()`, `embed_text()`/`embed_texts()`, `to_vector_literal()`); API-Fehler werden abgefangen/geloggt statt das Anlegen zu blockieren.

`db.find_matching_jobs()` / `db.find_matching_resumes()` liefern die ähnlichsten Einträge ab einer Mindest-Ähnlichkeit (`MIN_MATCH_SIMILARITY`, `models/base.py`) — Grundlage für das Matching zwischen Kandidat und Stellenangebot (angezeigt auf `/resumes` bzw. `/jobs/<id>/edit`). Deaktivierte (gelöschte) Jobs/Lebensläufe fließen dabei nicht mit ein.

`backfill_embeddings.py` berechnet einmalig fehlende Embeddings für Bestandsdaten nach:

```bash
docker compose exec app python backfill_embeddings.py
```

## Datei-Uploads

`/resumes` und `/jobs` (Anlegen) bieten neben der KI-Generierung eine Dropzone für PDF/.docx/.odt (`.doc` bewusst nicht unterstützt). `document_extraction.py` liest den Text aus (`pypdf`/`python-docx`/`odfpy`). Beim Stellenangebot durchläuft der Text zusätzlich eine KI-Zusammenfassung. Originaldateien landen unverändert unter `data/resumes/` bzw. `data/joboffers/` (Uploads auf 10 MB begrenzt) und bleiben auch nach dem Löschen des zugehörigen Eintrags erhalten (siehe [Löschen = Deaktivieren](#löschen--deaktivieren)).

## Tech-Stack

- **Backend**: Flask (Python 3.14), reine JSON-API + Datei-Auslieferung, keine eigenen HTML-Seiten mehr
- **API-Doku**: [flasgger](https://github.com/flasgger/flasgger) (Swagger UI/OpenAPI) — siehe [API-Dokumentation](#api-dokumentation-swagger--openapi)
- **Datenbank**: PostgreSQL 16 (`pgvector/pgvector:pg16`) + [pgvector](https://github.com/pgvector/pgvector). Schema/Migration über psycopg2 (`db/db_init.py`); CRUD über [SQLAlchemy](https://pypi.org/project/SQLAlchemy/) (`models/`)
- **KI**: [Groq](https://pypi.org/project/groq/)- und [OpenAI](https://pypi.org/project/openai/)-SDKs
- **PDF-Erzeugung**: [WeasyPrint](https://pypi.org/project/weasyprint/) (HTML → PDF), braucht native Pango/Cairo-Bibliotheken (im Dockerfile eingerichtet)
- **Datei-Parsing**: [pypdf](https://pypi.org/project/pypdf/), [python-docx](https://pypi.org/project/python-docx/), [odfpy](https://pypi.org/project/odfpy/)
- **Frontend**: [React](https://react.dev/) + [Vite](https://vitejs.dev/) + [react-router-dom](https://reactrouter.com/) (`frontend/`), einzige Oberfläche der App
- **Styling**: `static/style.css` (von Flask ausgeliefert, per CORS für React freigegeben), Font Awesome
- **Rich-Text-Editor**: [Quill](https://quilljs.com/) (Stellenangebot-Beschreibung) + [DOMPurify](https://github.com/cure53/DOMPurify) zur Sanitisierung
- **Deployment**: Docker + docker-compose (App + PostgreSQL + React-Dev-Server)
- **CI**: GitHub Actions (Syntaxcheck, Smoke-Test, Docker-Build) — `.github/workflows/main.yml`

## Projektstruktur

```
app.py                     Flask-App-Setup, Swagger-Config, registriert die api/-Blueprints, Datei-Auslieferungsrouten, KI-Assistent-Seitenliste (build_site_map())
api/                       JSON-API fürs React-Frontend, inkl. YAML-Docstrings für Swagger
  auth.py                     /api/auth/me + login/register/logout
  jobs.py                     /api/jobs-Endpunkte
  customers.py                /api/customers-Endpunkte
  users.py                    /api/users-Endpunkte (kein Löschen; entfernt password_hash aus jeder Antwort)
  resumes.py                  /api/resumes-Endpunkte (Liste/Anzeige/Generieren/Hochladen/Löschen)
  tools.py                    /api/tools/resume + /api/tools/joboffer (KI-Generierung)
  assistant.py                /api/assistant(/ask) für die Startseite
db/                        DB-Verbindung & Schema, von außen per `import db` genutzt
models/                    SQLAlchemy-ORM-Modelle + CRUD je Tabelle (user/customer/job/resume, base.py mit Engine/Session; job/customer/resume mit "deleted"-Flag statt Hard-Delete)
services/                  Von app.py und api/ gemeinsam genutzte Logik
  assistant_service.py        KI-Assistent-Logik (`ask_assistant()`)
  auth_service.py              Login-Session befüllen (`log_in_user()`)
  permissions.py                Rollen-/Berechtigungslogik
  resume_service.py / joboffer_service.py   KI-Generierung + Uploads (inkl. Embedding)
  pdf_service.py                HTML-zu-PDF (WeasyPrint)
  ai_clients.py / text_utils.py Client-Instanzen, KI-Antworten aufbereiten
frontend/                  React-SPA (Vite) - einzige Oberfläche
  src/pages/                   je eine Komponente pro Seite (Home, Jobs, Customers, Users, Tools, Resumes, Login, Register)
  src/components/              JobForm/-Table, CustomerForm/-Table, UserForm/-Table, JobUploadDropzone, Pager, RichTextEditor (Quill), ConfirmProvider (Lösch-Bestätigungsmodal)
embeddings.py              Embedding-Erzeugung, HTML-Stripping, Ähnlichkeits-Matching
document_extraction.py     Textextraktion aus PDF/.docx/.odt-Uploads
backfill_embeddings.py     Einmaliges Nachrechnen fehlender Embeddings
migrate_mysql_to_postgres.py  Einmaliges Migrationsskript MySQL → PostgreSQL
static/                    style.css (von React genutzt), lokales Font Awesome, Logo (static/pics/)
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
- Node.js (für den React-Dev-Server, `frontend/`)

### Lokal ohne Docker

```bash
pip install -r requirements.txt
cp .env.example .env   # Werte eintragen, siehe unten
python app.py
```

Der Flask-Server läuft danach auf `http://localhost:5003` — liefert aber nur noch `/api/*` und ein paar Datei-Routen aus, **keine Seiten**. Für die eigentliche Oberfläche zusätzlich den React-Dev-Server starten:

```bash
cd frontend
npm install
npm run dev
```

Die App ist dann unter `http://localhost:5173` erreichbar.

#### WeasyPrint unter Windows

`pip install weasyprint` reicht unter Windows **nicht**: Der Import schlägt fehl, weil WeasyPrint native GTK-Bibliotheken (Pango/Cairo/GObject) lädt, die kein reines Python-Package sind. Betroffen sind nur die Tools-Endpunkte — **außer** der komplette App-Import schlägt fehl (`from weasyprint import HTML` steht ganz oben in `services/pdf_service.py`). Lokale Entwicklung unter Windows ohne Docker wird dafür nicht unterstützt — bitte über Docker Compose laufen lassen, dort ist alles eingerichtet.

### Mit Docker Compose

```bash
cp .env.example .env   # Werte eintragen
docker compose up --build
```

Startet App, PostgreSQL und den React-Dev-Server zusammen; DB-Daten in einem benannten Volume (`aiproject_postgres_data`), generierte PDFs unter `./data`. Die Oberfläche läuft unter `http://localhost:5173`; `http://localhost:5003` liefert nur noch die JSON-API/Swagger-Doku.

`docker-compose.yml` lädt `.env` nur **einmalig beim Erstellen** des App-Containers. Änderungen werden erst nach `docker compose up -d app` (Neuerstellung) wirksam. Reine Python-Änderungen übernimmt dagegen der Flask-Debug-Reloader automatisch; Änderungen an `requirements.txt`/dem `Dockerfile` brauchen `docker compose build app`.

### Umgebungsvariablen (`.env`)

| Variable | Bedeutung |
|---|---|
| `GROQ_API_KEY` | API-Key für Groq. **Optional**: leer/fehlend blendet die darüber erreichbaren Modelle automatisch aus |
| `OPENAI_API_KEY` | API-Key für OpenAI (Chat-Modelle + Embeddings). Pflicht |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Verbindungsdaten zur PostgreSQL-Datenbank |
| `SECRET_KEY` | Flask-Session-Secret |
| `FLASK_DEBUG` | `1` aktiviert Flask-Debug-Modus (Auto-Reloader + Werkzeug-Debugger). Standard: aus. In `docker-compose.yml` für die Entwicklung gesetzt; **nie im öffentlichen Betrieb**, da der Debugger Codeausführung erlaubt |

`.env` ist per `.gitignore` von Git ausgeschlossen — nur `.env.example` wird versioniert.

### Ersten Admin-Nutzer anlegen

Es gibt bewusst keinen automatischen Bootstrap-Admin: Jede Registrierung über `/register` legt den Nutzer immer mit Rolle `user` an (`DEFAULT_ROLE` in `models/user.py`), unabhängig davon, ob es der erste Nutzer ist. Um die Anwendung überhaupt administrieren zu können (Nutzer-/Rollenverwaltung, Stellenanbieter anlegen, Tools-Menü), nach der Installation also:

1. Einmal ganz normal über `/register` registrieren.
2. Diesem Nutzer danach **direkt in der Datenbank** die Rolle `admin` zuweisen, z.B. mit Docker Compose:

   ```bash
   docker compose exec postgres psql -U <DB_USER> -d <DB_NAME> -c "UPDATE users SET role = 'admin' WHERE email = '<E-Mail des Nutzers>';"
   ```

   `<DB_USER>`/`<DB_NAME>` wie in der eigenen `.env` (siehe Tabelle oben). Die Rolle landet beim Login einmalig in der Flask-Session (`log_in_user()` in `services/auth_service.py`) und wird danach nicht live nachgeladen — ein bereits eingeloggter Nutzer muss sich also nach dem Rollenwechsel einmal ab- und wieder anmelden, damit die neue Rolle (und damit Zugriff auf Nutzerverwaltung, Tools-Menü etc.) wirksam wird.

## Frontend (React)

`frontend/` ist ein eigenständiges Vite-Projekt (Port 5173), das ausschließlich die JSON-API unter `api/` anspricht (CORS via `FRONTEND_ORIGIN`) und dieselbe Flask-Session/Business-Logik in `services/` nutzt.

Erwähnenswerte Details:
- **`/api/users`** entfernt `password_hash` aus jeder Antwort.
- **`/api/resumes`** entfernt `embedding`/`content`; die PDF-Auslieferung läuft über die eigene, besitzerschaftsgeprüfte Datei-Route `/resumes/<id>/file` (kein CORS nötig, da nur per `<iframe>`/`<a href>` eingebunden, nicht per `fetch()`).
- **Login/Registrieren/Abmelden**: eigene React-Formulare rufen `/api/auth/login` bzw. `/register` auf; `App.jsx` reicht `refreshUser()` per Outlet-Context an die Seiten weiter. Abmelden läuft im Konto-Menü als Button (`POST /api/auth/logout`), ohne Seitenwechsel.
- **Lösch-Bestätigung**: `ConfirmProvider`/`useConfirm()` (`src/components/ConfirmProvider.jsx`) ersetzt `window.confirm()` durch ein Modal im Look der restlichen Oberfläche; einmal in `App.jsx` um die ganze App gelegt.
- npm-Abhängigkeiten über die Standardkomponenten hinaus: `quill`, `dompurify`.

## Von MySQL migrieren

Bis einschließlich Commit vor der Postgres-Umstellung lief das Projekt auf MySQL 8.0. Bestandsdaten migriert `migrate_mysql_to_postgres.py` (Details im Skript-Docstring):

```bash
docker compose exec app python migrate_mysql_to_postgres.py
```

## KI-Assistent erweitern

Neue Modelle in `services/assistant_service.py` ergänzen: Eintrag in `AVAILABLE_MODELS`, `AVAILABE_MODEL_NAMES` und `MODEL_CLIENTS`. Ohne `GROQ_API_KEY` werden neue Groq-Modelle automatisch ausgeblendet.

Neue React-Seiten tauchen **nicht** automatisch im System-Prompt auf — dafür in `app.py` einen Eintrag in `REACT_PAGES` (Pfad + Kurzbeschreibung) ergänzen; `build_site_map()` baut daraus die Seitenliste, die der KI-Assistent bei jeder Anfrage als Systemkontext bekommt.
