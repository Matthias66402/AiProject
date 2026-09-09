# AiProject

Generative-AI-Testprojekt: eine Flask-Webanwendung zur Verwaltung von Stellenanbietern (Kunden), Stellenangeboten und Nutzern, mit einem integrierten KI-Assistenten, der Fragen zur Website, Stellenbewerbung und Stellenveröffentlichung beantwortet.

Die Website ist noch im Aufbau, Struktur und Funktionsumfang können sich häufig ändern.

## Funktionen

- **KI-Assistent** (Startseite — klassisch unter `/`, ebenso im React-PoC unter `frontend/`): beantwortet Fragen zur Website über wählbare KI-Modelle. Der System-Prompt bekommt bei jeder Anfrage automatisch die aktuelle Seitenstruktur (aus den registrierten Flask-Routen erzeugt) mitgegeben, damit der Assistent nichts über nicht existierende Funktionen erfindet. Ohne explizite Auswahl (z.B. bei internen KI-Aufgaben wie dem Extrahieren einer hochgeladenen Stellenanzeige) wird immer `DEFAULT_MODEL` (`gpt-4.1-mini`, OpenAI) verwendet. Modell-Konfiguration und Anfrage-Logik liegen zentral in `services/assistant_service.py` (`ask_assistant()`), genutzt sowohl von der klassischen Route als auch vom JSON-Endpunkt `/api/assistant/ask` für React.
  - Modelle über [Groq](https://groq.com/) (`openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.6-27b`, `groq/compound-mini`) — **optional**: ohne (nicht-leeren) `GROQ_API_KEY` in `.env` werden diese Modelle automatisch aus der Auswahl entfernt und der Groq-Client gar nicht erst erzeugt (`services/assistant_service.py`, `groq_client`)
  - Modelle über [OpenAI](https://platform.openai.com/) (`gpt-5-mini`, `gpt-4o-mini`, `gpt-4.1-mini`) — `OPENAI_API_KEY` ist Pflicht, da auch die Embeddings darüber laufen
- **Login/Registrierung**: Nutzer registrieren sich (immer mit Rolle `user`), melden sich an/ab; Passwörter werden gehasht (Werkzeug) gespeichert.
- **Rollen**: `user` (Standard bei Registrierung), `customer`, `admin` — Liste zentral in `models/user.py` (`ROLES`). `admin` vergibt Rollen und hat vollen Schreibzugriff auf Nutzer-, Stellenanbieter- und Stellenverwaltung. `customer`-Nutzer sind über `users.customer_id` (nullable FK auf `customers`, Zuweisung durch einen Admin im Nutzerformular) genau einem Stellenanbieter zugeordnet und dürfen dadurch **nur ihre eigenen** Stellenangebote anlegen/bearbeiten/löschen sowie ihren eigenen Stellenanbieter-Datensatz bearbeiten (Anlegen/Löschen von Stellenanbietern bleibt `admin` vorbehalten).
- **Nutzerverwaltung** (`/users` — klassisch, ebenso im React-PoC; nur `admin`): Nutzer anlegen, bearbeiten, Rolle zuweisen, optional PLZ/Stadt hinterlegen. Bei Rolle `customer` erscheint zusätzlich eine Selectbox zur Zuordnung eines Stellenanbieters. Zeigt außerdem alle für diesen Nutzer generierten/hochgeladenen Lebensläufe (Tabelle `resumes`, FK auf `users`), falls vorhanden. Kein Löschen (weder klassisch noch React) — dafür gibt es bislang keine Funktion.
- **Eigener Lebenslauf** (`/resumes`, für jeden eingeloggten Nutzer mit Rolle `user`): zeigt den aktuellsten eigenen Lebenslauf (PDF eingebettet, andere Formate als Download-Link); eine Selectbox erlaubt den Zugriff auf ältere Versionen, ein Löschbutton entfernt den ausgewählten Lebenslauf inkl. Datei. Zwei Wege für einen neuen Lebenslauf:
  - **Generieren** — dieselbe KI-Logik wie das Admin-Tool `/tools/resume`: verwendet immer den echten Namen des Nutzers, der Wohnort wird nur übernommen, wenn PLZ **und** Stadt hinterlegt sind (sonst frei erfunden).
  - **Hochladen** (Dropzone mit Drag & Drop) — eigene Datei als PDF/.docx/.odt hochladen; der Text wird ausgelesen (`document_extraction.py`) und wie bei der Generierung vektorisiert.

  Die Dateiauslieferung prüft Besitzerschaft (nur die eigenen Lebensläufe, unabhängig vom Admin-Zugriff auf `/tools/resume/<datei>`).
- **Stellenangebote** (`/jobs`): Stellenanzeigen mit Gültigkeitszeitraum, PLZ/Stadt und Zuordnung zu einem Stellenanbieter. Liste paginiert (Standard 10/Seite, per Selectbox auf 10/25/50/100 einstellbar).
  - `admin`: anlegen/bearbeiten/löschen für jeden Stellenanbieter.
  - `customer`-Nutzer mit zugeordnetem Stellenanbieter: anlegen/bearbeiten/löschen nur für den eigenen Stellenanbieter — serverseitig erzwungen, unabhängig vom Formularinhalt.
  - Alle anderen (inkl. nicht eingeloggt): nur Liste + Lesemodus ("Ansehen") pro Stelle — Position, Kunde, PLZ/Stadt, Gültigkeitszeitraum als Text, bei KI-generierten/hochgeladenen Stellen zusätzlich das Dokument eingebettet (PDF) bzw. als Download-Link (andere Formate) statt der reinen Textbeschreibung.
  - Beim Anlegen kann optional ein Stellenangebot-Dokument (PDF/.docx/.odt) per Dropzone hochgeladen werden (`/jobs/extract-upload`): die KI fasst den Inhalt als Beschreibung zusammen und befüllt Position/PLZ/Stadt, sofern im Text eindeutig erkennbar.
- **Stellenanbieter** (`/customers` — klassisch, ebenso im React-PoC): Kunden (Unternehmen) mit Adresse. Liste paginiert (Standard testweise 2/Seite in der klassischen Ansicht, `CUSTOMERS_PER_PAGE_DEFAULT` in `app.py`; 10/Seite im React-PoC, `api/customers.py`).
  - `admin`: anlegen, bearbeiten, löschen.
  - `customer`-Nutzer mit zugeordnetem Stellenanbieter: dürfen nur ihren eigenen Datensatz bearbeiten (nicht anlegen/löschen).
  - Alle anderen: nur Liste + Lesemodus ("Ansehen"), kein Bearbeiten/Löschen.
  - Die Bearbeiten-Ansicht zeigt zusätzlich die zu diesem Stellenanbieter gehörenden Stellenangebote.
  - Anlegen von neuen Stellen per Dokumenten-Upload wird automatisch dem eingeloggten Stellenanbieter zugeordnet.
- **Tools-Menü** (nur für Rolle `admin`): lässt die KI Inhalte als HTML formulieren und rendert sie per WeasyPrint zu PDF, mit dezentem Lade-Spinner während der Generierung und Link zum Öffnen der fertigen Datei in einem neuen Tab.
  - **Lebenslauf generieren** (`/tools/resume`): ein bestehender Nutzer wird per Selectbox ausgewählt. Sind bei ihm PLZ **und** Stadt hinterlegt, übernimmt die KI dessen echten Namen und Wohnort unverändert (Rest frei erfunden); ansonsten ein komplett fiktiver Dummy-Lebenslauf. Das PDF wird unter `data/resumes/` abgelegt und als neuer Eintrag in `resumes` (FK auf den Nutzer) gespeichert.
  - **Stellenangebot generieren** (`/tools/joboffer`): ein Stellenanbieter wird per Selectbox ausgewählt. Die KI liefert Position, PLZ, Stadt und den Stellentext strukturiert als JSON zurück; das PDF wird unter `data/joboffers/` abgelegt und automatisch ein passender Eintrag in `/jobs` angelegt (inkl. `document_link`, Gültigkeit heute bis +30 Tage).
  - ⚠️ Läuft nur, wo WeasyPrints native Abhängigkeiten (Pango/Cairo) vorhanden sind — siehe [WeasyPrint unter Windows](#weasyprint-unter-windows) weiter unten. Im Docker-Image ist das bereits eingerichtet.

## Embeddings (RAG-Grundlage)

Jeder Job (`jobs.embedding`) und jeder Lebenslauf (`resumes.embedding`) bekommt beim Anlegen/Ändern automatisch ein OpenAI-Embedding (`text-embedding-3-small`) berechnet und als [pgvector](https://github.com/pgvector/pgvector) `vector(1536)`-Spalte gespeichert — sowohl bei manueller Eingabe als auch bei KI-Generierung über die Tools-Seiten. Die Ähnlichkeitssuche läuft nativ in SQL über den Cosine-Distance-Operator `<=>`, indiziert per HNSW-Index (`idx_jobs_embedding_hnsw`/`idx_resumes_embedding_hnsw`), statt Embeddings nach Python zu laden. Zuständig ist `embeddings.py`:

- `strip_html_to_text()` — bereitet die HTML-Inhalte (`content`) für ein sauberes Embedding auf
- `embed_text()` / `embed_texts()` — einzelnes bzw. batch-weises Embedding über die OpenAI-API; API-Fehler (Status-, Verbindungs-, Timeout-Fehler) werden abgefangen und geloggt, statt das eigentliche Anlegen/Ändern zu blockieren
- `to_vector_literal()` — formatiert ein Embedding als pgvector-Text-Literal zum Schreiben über einen `::vector`-Cast

`db.find_matching_jobs(embedding, top_k)` / `db.find_matching_resumes(embedding, top_k)` liefern die ähnlichsten Einträge (Cosine Similarity über `Vector.cosine_distance()`, SQL-nativ, ab einer Mindest-Ähnlichkeit `MIN_MATCH_SIMILARITY` in `models/base.py`) — Grundlage für das Matching zwischen Kandidat und Stellenangebot: passende Stellenangebote erscheinen auf `/resumes` beim jeweiligen Lebenslauf, passende Kandidaten auf der Bearbeiten-Ansicht eines Stellenangebots (`/jobs/<id>/edit`, nur für Admins bzw. den zuständigen `customer`-Nutzer).

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
- **Datenbank**: PostgreSQL 16 (Image `pgvector/pgvector:pg16`), inkl. [pgvector](https://github.com/pgvector/pgvector)-Extension für die Ähnlichkeitssuche. Schema-Erstellung/Migration (`db.init_db()`, `db/db_init.py`) läuft direkt über psycopg2; alle CRUD-/Abfragefunktionen darüber (`models/`) über [SQLAlchemy](https://pypi.org/project/SQLAlchemy/) mit dem [pgvector](https://pypi.org/project/pgvector/)-Python-Paket für den `vector`-Spaltentyp (`Vector(1536)`, `cosine_distance()`)
- **KI**: [Groq](https://pypi.org/project/groq/)- und [OpenAI](https://pypi.org/project/openai/)-Python-SDKs
- **PDF-Erzeugung**: [WeasyPrint](https://pypi.org/project/weasyprint/) rendert vom KI-Modell geliefertes HTML zu PDF. Benötigt native Pango/Cairo-Bibliotheken (siehe unten) — im `Dockerfile` und in der CI bereits per `apt` eingerichtet
- **Datei-Parsing**: [pypdf](https://pypi.org/project/pypdf/), [python-docx](https://pypi.org/project/python-docx/), [odfpy](https://pypi.org/project/odfpy/) — Textextraktion aus hochgeladenen PDF/.docx/.odt-Dateien, reines Python ohne native Abhängigkeiten
- **Frontend (klassisch)**: Jinja2-Templates, Tailwind-Klassen, Font Awesome (lokal in `static/fontawesome`)
- **Frontend (React-PoC)**: [React](https://react.dev/) + [Vite](https://vitejs.dev/) + [react-router-dom](https://reactrouter.com/) (`frontend/`, siehe [Frontend-Migration](#frontend-migration-react-poc) unten) — teilt sich `static/style.css` mit den klassischen Templates für optische Parität
- **Rich-Text-Editor**: [Quill](https://quilljs.com/) für die HTML-Beschreibung von Stellenangeboten, in beiden Frontends (React über npm, klassisch per CDN in `templates/index.html`); [DOMPurify](https://github.com/cure53/DOMPurify) sanitisiert das gespeicherte HTML vor jeder Anzeige/Editor-Befüllung
- **Deployment**: Docker + docker-compose (App + PostgreSQL + React-Dev-Server)
- **CI**: GitHub Actions (Syntaxcheck, Smoke-Test, Docker-Build) — siehe `.github/workflows/main.yml`

## Projektstruktur

```
app.py                     Flask-Routen (klassische Jinja-Seiten), registriert die api/-Blueprints
api/                       JSON-API für das React-PoC-Frontend (frontend/), läuft parallel zu den klassischen Routen
  auth.py                     GET /api/auth/me - Login-Status für React (liest dieselbe Flask-Session)
  jobs.py                      /api/jobs-Endpunkte (Liste/Anlegen/Bearbeiten/Löschen), ersetzt für React die Jobs-Logik aus app.py
  customers.py                  /api/customers-Endpunkte (Liste/Anlegen/Bearbeiten/Löschen), ersetzt für React die Customers-Logik aus app.py
  users.py                      /api/users-Endpunkte (Liste/Anlegen/Bearbeiten, kein Löschen), ersetzt für React die Users-Logik aus app.py; entfernt password_hash aus jeder Antwort
  assistant.py                  /api/assistant(/ask)-Endpunkte (Modellliste, Frage stellen) für die React-Startseite
db/                        DB-Verbindung & Schema (siehe unten), von außen weiterhin per `import db` als Einheit genutzt
  __init__.py                Re-Export der öffentlichen Funktionen/Konstanten aus db_init.py und models/
  db_init.py                  DB-Verbindung (`get_connection()`, psycopg2), Schema-Erstellung/Migration (`init_db()`)
models/                    SQLAlchemy-ORM-Modelle + CRUD-/Abfragefunktionen je Tabelle
  __init__.py                Re-Export der Modelle/Funktionen aller Untermodule
  base.py                     Engine/Session (`get_session()`), `Base`, `MIN_MATCH_SIMILARITY`, `to_dict()`-Hilfsfunktion
  user.py                      Modell `User`, Rollen (`ROLES`, `DEFAULT_ROLE`), zugehörige CRUD-Funktionen
  customer.py                  Modell `Customer`, zugehörige CRUD-Funktionen
  job.py                       Modell `Job`, zugehörige CRUD-Funktionen inkl. `find_matching_jobs()`
  resume.py                    Modell `Resume`, zugehörige CRUD-Funktionen inkl. `find_matching_resumes()`
services/                  KI-/Datei-Erzeugungslogik der Tools-Seiten, aus app.py-Routen ausgelagert
  text_utils.py                Aufbereitung von KI-Antworten (`<think>`-Blöcke, Markdown-Codefences entfernen)
  assistant_service.py          KI-Assistent: Modell-Konfiguration + `ask_assistant()`, von app.py (`/`) und api/assistant.py (`/api/assistant/ask`) genutzt
  pdf_service.py                HTML-zu-PDF-Rendering (WeasyPrint)
  resume_service.py             Lebenslauf generieren/aus Upload anlegen (`RESUME_DIR`, inkl. Embedding)
  joboffer_service.py           Stellenangebot generieren/aus Upload-Text extrahieren (`JOBOFFER_DIR`, inkl. Embedding)
  ai_clients.py                 Zentrale OpenAI-Client-Instanz (von app.py und api/jobs.py genutzt)
  permissions.py                Rollen-/Berechtigungslogik für Stellenangebote + Stellenanbieter (von app.py und api/jobs.py bzw. api/customers.py genutzt)
frontend/                  React-PoC (Vite) - bislang umgezogene Seiten: Startseite (KI-Assistent), Stellenangebote, Stellenanbieter und Nutzer - siehe "Frontend-Migration" unten
  src/pages/                    HomePage.jsx, JobsPage.jsx, JobEditPage.jsx, CustomersPage.jsx, CustomerEditPage.jsx, UsersPage.jsx, UserEditPage.jsx - je eine Komponente pro migrierter Seite
  src/components/               JobForm.jsx, JobTable.jsx, JobUploadDropzone.jsx, CustomerForm.jsx, CustomerTable.jsx, UserForm.jsx, UserTable.jsx, Pager.jsx, RichTextEditor.jsx (Quill-Wrapper)
embeddings.py              Embedding-Erzeugung (einzeln/batch), HTML-Stripping, Cosinus-Ähnlichkeit/Top-Matches
document_extraction.py     Textextraktion aus hochgeladenen PDF/.docx/.odt-Dateien (Lebenslauf- und Stellenangebot-Upload)
backfill_embeddings.py     Einmaliges Nachrechnen fehlender Embeddings für Bestandsdaten
migrate_mysql_to_postgres.py Einmaliges Migrationsskript für den Umstieg von MySQL auf PostgreSQL (Bestandsdaten inkl. IDs übernehmen)
templates/
  index.html                Basis-Layout, bindet navigation.html + content_template ein
  navigation.html            Navigationsleiste inkl. Konto-Dropdown (Anmelden/Registrieren/Abmelden/eigener Lebenslauf), "Nutzer"-Link und Tools-Dropdown (beide nur Admin)
  home.html                  KI-Assistent-Formular (Startseite), auch als React-Variante verfügbar (frontend/src/pages/HomePage.jsx)
  login.html, register.html  Anmeldung/Registrierung (Registrierung fragt PLZ/Stadt verpflichtend ab)
  user.html                  Nutzerverwaltung, inkl. Stellenanbieter-Zuordnung für Rolle 'customer'
  jobs.html                  Stellenangebote, inkl. Upload-Dropzone, Pager und Quill-Rich-Text-Editor für die Beschreibung
  customer.html              Stellenanbieter, inkl. Pager
  resume.html                 Tools: Lebenslauf generieren (nur Admin)
  joboffer.html                Tools: Stellenangebot generieren (nur Admin)
  my_resumes.html              Eigener Lebenslauf ansehen/generieren/hochladen/löschen (jeder eingeloggte Nutzer)
static/
  style.css                  eigenes Stylesheet, wird unverändert auch vom React-Frontend eingebunden (optische Parität)
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
- API-Key für [OpenAI](https://platform.openai.com/), optional für [Groq](https://console.groq.com/)

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

`docker-compose.yml` lädt `.env` per `env_file` **einmalig beim Erstellen des App-Containers** in dessen Umgebung — nicht laufend. Änderungen an `.env` (egal welche Variable) werden erst wirksam, wenn der Container neu erstellt wird:

```bash
docker compose up -d app
```

Reine Python-/Template-Änderungen übernimmt dagegen der Flask-Debug-Reloader automatisch (kein Recreate nötig) — der läuft aber innerhalb desselben Containers weiter mit der zuvor geladenen Umgebung, holt sich also bei einem Neustart durch den Reloader keine aktualisierte `.env`.

### Umgebungsvariablen (`.env`)

| Variable | Bedeutung |
|---|---|
| `GROQ_API_KEY` | API-Key für Groq (Chat-Modelle). **Optional**: leer/fehlend lassen blendet die darüber erreichbaren Modelle in der KI-Assistent-Auswahl automatisch aus, statt die App abstürzen zu lassen |
| `OPENAI_API_KEY` | API-Key für OpenAI (Chat-Modelle + Embeddings). Pflicht |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Verbindungsdaten zur PostgreSQL-Datenbank |
| `SECRET_KEY` | Flask-Session-Secret |

`.env` ist per `.gitignore` von Git ausgeschlossen — nur `.env.example` wird versioniert.

## Frontend-Migration (React-PoC)

Das Projekt wird schrittweise von serverseitig gerenderten Jinja-Templates auf ein
React-Frontend umgestellt, das Flask nur noch als JSON-API anspricht — Seite für
Seite, nicht als Big-Bang-Rewrite. Bislang umgezogen:

- **Startseite / KI-Assistent** (`/`, `frontend/src/pages/HomePage.jsx`): Frage-Formular
  + Modellauswahl + Antwortanzeige, funktional identisch zur klassischen `home.html`.
- **Stellenangebote** (`/jobs`), vollständig inkl. Anlegen/Bearbeiten/Löschen,
  Rollen-Berechtigungen, Datei-Upload-Dropzone mit KI-Extraktion, Quill-Rich-Text-
  Editor für die Beschreibung und der Matching-Kandidaten-Anzeige.
- **Stellenanbieter** (`/customers`), vollständig inkl. Anlegen/Bearbeiten/Löschen,
  Rollen-Berechtigungen (inkl. automatischer Weiterleitung von `customer`-Nutzern
  auf ihren eigenen Datensatz) und der Liste der zugehörigen Stellenangebote mit
  Link auf die jeweilige React-Job-Bearbeiten-Seite.
- **Nutzer** (`/users`, nur `admin` — die React-Navigation zeigt den Menüpunkt
  entsprechend nur eingeloggten Admins), vollständig inkl. Anlegen/Bearbeiten,
  Rollenvergabe mit bedingt eingeblendeter Stellenanbieter-Zuordnung (Rolle
  `customer`) und Anzeige der Lebensläufe des Nutzers. Der Passwort-Hash verlässt
  die API nie (`api/users.py` entfernt ihn aus jeder Antwort); Löschen gibt es wie
  in der klassischen Ansicht nicht.

Alle vier Seiten laufen komplett innerhalb der React-SPA (client-seitiges Routing
via `react-router-dom`) — es wird an keiner Stelle automatisch zur klassischen
Flask-Darstellung gesprungen; ein Link "Zur klassischen Seite" bleibt als bewusster,
expliziter Ausstieg bestehen.

- **`api/`** stellt die dafür nötigen JSON-Endpunkte bereit (`/api/jobs/...`,
  `/api/customers/...`, `/api/users/...`, `/api/assistant(/ask)`, `/api/auth/me`),
  parallel zu den bestehenden Template-Routen in `app.py` — die klassischen Seiten
  funktionieren unverändert weiter, beide Varianten teilen sich die
  zugrundeliegende Logik in `services/` (z.B. `customer_management_permission()`
  für die Bearbeiten-Rechte der Stellenanbieter).
- **`frontend/`** ist ein eigenständiges Vite/React-Projekt, läuft als eigener
  `frontend`-Service in `docker-compose.yml` auf Port 5173 (`docker compose up -d
  frontend`, danach `http://localhost:5173`). Zusätzliche npm-Abhängigkeiten:
  `quill` (Rich-Text-Editor) und `dompurify` (HTML-Sanitisierung vor jeder Anzeige/
  Editor-Befüllung von gespeichertem Beschreibungs-HTML).
- **Login** läuft weiterhin über die klassische Flask-Seite (`http://localhost:5003/login`)
  — React liest den Login-Status nur aus (`/api/auth/me`) und nutzt dieselbe
  Session-Cookie über CORS (`FRONTEND_ORIGIN` in `docker-compose.yml`,
  `flask_cors` in `app.py`). Ein eigenes Login-Formular in React gibt es noch nicht.
- **Layout**: `App.jsx` bildet body-Navigation und Haupt-Container exakt wie im
  klassischen `body`-Flex-Layout nach (`#root { display: contents; }` in
  `static/style.css`, kein zusätzliches Wrapper-`<div>`) — Nav- und Content-Breite
  bleiben dadurch wie bei Flask konstant, unabhängig vom Tabelleninhalt.
- Verlinkungen zu noch nicht umgezogenen Seiten (z.B. Nutzerbearbeitung aus der
  Kandidaten-Matching-Liste) zeigen bewusst auf die klassische Flask-Seite.

Nächster Kandidat für den Umzug wäre analog `/resumes` (eigener Lebenslauf) oder
die Tools-Seiten (`/tools/resume`, `/tools/joboffer`). Login/Registrierung/Abmelden
bleiben bewusst klassisch (siehe "Login" oben).

### Von MySQL migrieren

Bis einschließlich Commit vor dieser Umstellung lief das Projekt auf MySQL
8.0. Wer noch Bestandsdaten in einer alten MySQL-DB hat, migriert sie per
`migrate_mysql_to_postgres.py` (Details/Voraussetzungen im Skript-Docstring):

```bash
docker compose exec app python migrate_mysql_to_postgres.py
```

## KI-Assistent erweitern

Neue Modelle in `services/assistant_service.py` ergänzen: Eintrag in `AVAILABLE_MODELS` (Anzeigename), `AVAILABE_MODEL_NAMES` (Kurzname für Fehlermeldungen) und `MODEL_CLIENTS` (welcher Client — `groq_client` für Groq, `openai_client` für OpenAI — zuständig ist). Ein neues Groq-Modell wird automatisch mit ausgeblendet, solange kein `GROQ_API_KEY` gesetzt ist (`groq_client` ist dann `None`) — dafür ist an dieser Stelle nichts weiter zu tun. Die Änderung wirkt automatisch sowohl auf die klassische Startseite als auch auf `/api/assistant` (React), da beide dieselbe Quelle nutzen.

Neue Seiten/Routen tauchen automatisch im System-Prompt des Assistenten auf (`build_site_map()` liest live aus `app.url_map`). Für eine sprechende Beschreibung im Prompt zusätzlich einen Eintrag in `PAGE_DESCRIPTIONS` ergänzen — fehlt er, erscheint die Route trotzdem mit Platzhalter, damit der Assistent ihre Existenz nicht ignoriert oder erfindet.
