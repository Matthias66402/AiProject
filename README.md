# AiProject

Generative-AI-Testprojekt: eine Flask-Webanwendung zur Verwaltung von Stellenanbietern (Kunden), Stellenangeboten und Nutzern, mit einem integrierten KI-Assistenten, der Fragen zur Website, Stellenbewerbung und Stellenveröffentlichung beantwortet.

Die Website ist noch im Aufbau, Struktur und Funktionsumfang können sich häufig ändern.

## Funktionen

- **KI-Assistent** (Startseite): beantwortet Fragen zur Website über wählbare KI-Modelle. Der System-Prompt bekommt bei jeder Anfrage automatisch die aktuelle Seitenstruktur (aus den registrierten Flask-Routen erzeugt) mitgegeben, damit der Assistent nichts über nicht existierende Funktionen erfindet.
  - Modelle über [Groq](https://groq.com/) (`openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.6-27b`, `groq/compound-mini`)
  - Modelle über [OpenAI](https://platform.openai.com/) (`gpt-5-mini`, `gpt-4o-mini`, `gpt-4.1-mini`)
- **Login/Registrierung**: Nutzer registrieren sich (immer mit Rolle `user`), melden sich an/ab; Passwörter werden gehasht (Werkzeug) gespeichert.
- **Rollen**: `user` (Standard bei Registrierung), `customer`, `admin`. Nur `admin` kann Rollen vergeben und hat Schreibzugriff auf Nutzer-, Stellenanbieter- und Stellenverwaltung; die Rollenliste ist in `db.py` (`ROLES`) zentral gepflegt.
- **Nutzerverwaltung** (`/users`, nur `admin`): Nutzer anlegen, bearbeiten, Rolle zuweisen, optional PLZ/Stadt hinterlegen. Zeigt außerdem alle für diesen Nutzer generierten Lebenslauf-PDFs (Tabelle `resumes`, FK auf `users`), falls vorhanden.
- **Eigener Lebenslauf** (`/resumes`, für jeden eingeloggten Nutzer): zeigt den aktuellsten eigenen Lebenslauf als eingebettetes PDF; eine Selectbox erlaubt den Zugriff auf ältere Versionen. Ein eingeklapptes Formular lässt den Nutzer sich selbst per KI (dieselbe Logik wie das Admin-Tool `/tools/resume`) einen neuen Lebenslauf erstellen. Die PDF-Auslieferung prüft Besitzerschaft (nur die eigenen Lebensläufe, unabhängig vom Admin-Zugriff auf `/tools/resume/<datei>`). Der Menüpunkt selbst ist nur für Rolle `user` im Konto-Dropdown verlinkt.
- **Stellenangebote** (`/jobs`): Stellenanzeigen mit Gültigkeitszeitraum, PLZ/Stadt und Zuordnung zu einem Stellenanbieter.
  - `admin`: anlegen, bearbeiten, löschen.
  - Alle anderen (inkl. nicht eingeloggt): nur Liste + Lesemodus ("Ansehen") pro Stelle — Position, Kunde, PLZ/Stadt, Gültigkeitszeitraum als Text, bei KI-generierten Stellen zusätzlich das PDF eingebettet statt der Beschreibung.
- **Stellenanbieter** (`/customers`): Kunden (Unternehmen) mit Adresse.
  - `admin`: anlegen, bearbeiten, löschen.
  - Alle anderen: nur Liste + Lesemodus ("Ansehen"), kein Bearbeiten/Löschen.
  - Jede Zeile verlinkt zusätzlich auf `/jobs?customer_id=<id>`, die auf diesen Stellenanbieter gefilterte Stellenliste.
- **Tools-Menü** (nur für Rolle `admin`): lässt die KI Inhalte als HTML formulieren und rendert sie per WeasyPrint zu PDF, mit dezentem Lade-Spinner während der Generierung und Link zum Öffnen der fertigen Datei in einem neuen Tab.
  - **Lebenslauf generieren** (`/tools/resume`): ein bestehender Nutzer wird per Selectbox ausgewählt. Sind bei ihm PLZ **und** Stadt hinterlegt, übernimmt die KI dessen echten Namen und Wohnort unverändert (Rest frei erfunden); ansonsten ein komplett fiktiver Dummy-Lebenslauf. Das PDF wird unter `data/resumes/` abgelegt und als neuer Eintrag in `resumes` (FK auf den Nutzer) gespeichert.
  - **Stellenangebot generieren** (`/tools/joboffer`): ein Stellenanbieter wird per Selectbox ausgewählt. Die KI liefert Position, PLZ, Stadt und den Stellentext strukturiert als JSON zurück; das PDF wird unter `data/joboffers/` abgelegt und automatisch ein passender Eintrag in `/jobs` angelegt (inkl. `document_link`, Gültigkeit heute bis +30 Tage).
  - ⚠️ Läuft nur, wo WeasyPrints native Abhängigkeiten (Pango/Cairo) vorhanden sind — siehe [WeasyPrint unter Windows](#weasyprint-unter-windows) weiter unten. Im Docker-Image ist das bereits eingerichtet.

## Embeddings (RAG-Grundlage)

Jeder Job (`jobs.embedding`) und jeder Lebenslauf (`resumes.embedding`) bekommt beim Anlegen/Ändern automatisch ein OpenAI-Embedding (`text-embedding-3-small`) berechnet und als JSON-Array in der jeweiligen Spalte gespeichert — sowohl bei manueller Eingabe als auch bei KI-Generierung über die Tools-Seiten. Zuständig ist `embeddings.py`:

- `strip_html_to_text()` — bereitet die HTML-Inhalte (`content`) für ein sauberes Embedding auf
- `embed_text()` / `embed_texts()` — einzelnes bzw. batch-weises Embedding über die OpenAI-API; API-Fehler (Status-, Verbindungs-, Timeout-Fehler) werden abgefangen und geloggt, statt das eigentliche Anlegen/Ändern zu blockieren
- `cosine_similarity()` / `top_matches()` — Ähnlichkeitssuche in reinem Python (keine zusätzliche Vektor-DB nötig bei der aktuellen Datenmenge)

`backfill_embeddings.py` berechnet einmalig Embeddings für bestehende Jobs/Lebensläufe ohne Embedding nach (z.B. nach der Einführung dieses Features oder bei einem Modellwechsel):

```bash
docker compose exec app python backfill_embeddings.py
```

Aktuell dient das als Grundlage für eine spätere Matching-Funktion (Kandidat ↔ Stellenangebot per Ähnlichkeit) — es gibt noch keine UI dafür.

## Tech-Stack

- **Backend**: Flask (Python 3.14)
- **Datenbank**: MySQL 8.0 über PyMySQL; Schema wird beim App-Start automatisch angelegt und migriert (`db.init_db()`)
- **KI**: [Groq](https://pypi.org/project/groq/)- und [OpenAI](https://pypi.org/project/openai/)-Python-SDKs
- **PDF-Erzeugung**: [WeasyPrint](https://pypi.org/project/weasyprint/) rendert vom KI-Modell geliefertes HTML zu PDF. Benötigt native Pango/Cairo-Bibliotheken (siehe unten) — im `Dockerfile` und in der CI bereits per `apt` eingerichtet
- **Frontend**: Jinja2-Templates, Tailwind-Klassen, Font Awesome (lokal in `static/fontawesome`)
- **Deployment**: Docker + docker-compose (App + MySQL)
- **CI**: GitHub Actions (Syntaxcheck, Smoke-Test, Docker-Build) — siehe `.github/workflows/main.yml`

## Projektstruktur

```
app.py                     Flask-Routen, KI-Assistent-Logik, Modellauswahl
db.py                      DB-Verbindung, Schema-Erstellung/Migration, CRUD-Funktionen
embeddings.py              Embedding-Erzeugung (einzeln/batch), HTML-Stripping, Cosinus-Ähnlichkeit/Top-Matches
backfill_embeddings.py     Einmaliges Nachrechnen fehlender Embeddings für Bestandsdaten
templates/
  index.html                Basis-Layout, bindet navigation.html + content_template ein
  navigation.html            Navigationsleiste inkl. Konto-Dropdown (Anmelden/Registrieren/Abmelden/eigener Lebenslauf), "Benutzer"-Link und Tools-Dropdown (beide nur Admin)
  home.html                  KI-Assistent-Formular (Startseite)
  login.html, register.html  Anmeldung/Registrierung
  user.html                  Nutzerverwaltung
  jobs.html                  Stellenangebote
  customer.html              Stellenanbieter
  resume.html                 Tools: Lebenslauf generieren (nur Admin)
  joboffer.html                Tools: Stellenangebot generieren (nur Admin)
  my_resumes.html              Eigener Lebenslauf ansehen/generieren (jeder eingeloggte Nutzer)
static/
  style.css                  eigenes Stylesheet
  fontawesome/                lokal eingebundene Icon-Bibliothek
data/                        generierte PDFs (Lebensläufe/Stellenangebote), von Git ausgeschlossen; im Docker-Setup per Bind-Mount (./data:/app/data) persistent auf dem Host
  resumes/
  joboffers/
Dockerfile                  Python-3.14-slim-Image für die App
docker-compose.yml          App + MySQL-Service für lokalen/Produktions-Betrieb, mountet ./data in den App-Container
.github/workflows/main.yml  CI: Syntaxcheck, Smoke-Test, Docker-Build
.env.example                Vorlage für benötigte Umgebungsvariablen
```

## Setup

### Voraussetzungen

- Python 3.14
- MySQL-Server (lokal oder über Docker)
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

Startet App und MySQL zusammen; die DB-Daten liegen in einem benannten Volume (`aiproject_mysql_data`), generierte PDFs unter `./data` (Bind-Mount, direkt im Projektordner sichtbar).

### Umgebungsvariablen (`.env`)

| Variable | Bedeutung |
|---|---|
| `GROQ_API_KEY` | API-Key für Groq (Chat-Modelle) |
| `OPENAI_API_KEY` | API-Key für OpenAI (Chat-Modelle + Embeddings) |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Verbindungsdaten zur MySQL-Datenbank |
| `SECRET_KEY` | Flask-Session-Secret |

`.env` ist per `.gitignore` von Git ausgeschlossen — nur `.env.example` wird versioniert.

## KI-Assistent erweitern

Neue Modelle in `app.py` ergänzen: Eintrag in `AVAILABLE_MODELS` (Anzeigename), `AVAILABE_MODEL_NAMES` (Kurzname für Fehlermeldungen) und `MODEL_CLIENTS` (welcher Client — `client` für Groq, `openai_client` für OpenAI — zuständig ist).

Neue Seiten/Routen tauchen automatisch im System-Prompt des Assistenten auf (`build_site_map()` liest live aus `app.url_map`). Für eine sprechende Beschreibung im Prompt zusätzlich einen Eintrag in `PAGE_DESCRIPTIONS` ergänzen — fehlt er, erscheint die Route trotzdem mit Platzhalter, damit der Assistent ihre Existenz nicht ignoriert oder erfindet.
