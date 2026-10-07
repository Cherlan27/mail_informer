# mail_informer

Pollt alle 30 Minuten dein Gmail-Postfach und archiviert neue Mails (Metadaten + Klartext-Body) in Postgres. Import startet ab dem Zeitpunkt der Initialisierung, es gibt keinen Historien-Backfill.

## Einrichtung

### 1. Google Cloud (einmalig)

1. Projekt auf https://console.cloud.google.com anlegen.
2. „APIs & Dienste → Bibliothek": **Gmail API** aktivieren.
3. OAuth-Zustimmungsbildschirm: Nutzertyp *Extern*, Scope `https://www.googleapis.com/auth/gmail.readonly`, Status **„In production"** setzen. Bei „Testing" läuft der Refresh-Token nach 7 Tagen ab.
4. „Anmeldedaten → OAuth-Client-ID" vom Typ **Desktop-App** erstellen, JSON herunterladen und als `secrets/client_secret.json` ablegen.

### 2. Konfiguration

```
copy .env.example .env     # POSTGRES_PASSWORD setzen
```

### 3. Autorisieren (einmalig, auf dem Host)

```
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m mail_informer auth
```

Der Browser öffnet sich; nach der Zustimmung liegt `secrets/token.json` bereit. Bei der Warnung „Nicht verifizierte App": *Erweitert → Weiter*.

### 4. Starten

```
docker compose up -d
docker compose logs -f poller
```

Beim Start läuft sofort ein Lauf (holt nach Ruhezustand nach), danach alle 30 Minuten. Der allererste Lauf setzt nur den Startpunkt; Mails, die danach eintreffen, werden importiert.

## Hinweise

- Verbindung vom Host zur DB: `127.0.0.1:5432` verwenden, nicht `localhost` (unter Windows wird sonst IPv6 versucht und die Verbindung hängt).
- Ist der Sync-Punkt bei Gmail abgelaufen (Pause > ca. 1 Woche), lädt der Poller per Datumsabfrage nach.
- Neue Mails haben `analysis_status = 'pending'`; das ist die Übergabe an die spätere LLM-Stufe.

## Entwicklung

```
.venv\Scripts\pip install -e ".[dev]"
docker compose up -d postgres
set TEST_DATABASE_URL=postgresql://mail_informer:<passwort>@127.0.0.1:5432/mail_informer
.venv\Scripts\python -m pytest
```
