## 1. Projekt-Setup

- [x] 1.1 Python-Projekt anlegen (pyproject, Paketstruktur `mail_informer/`, Abhängigkeiten: Google API Client/OAuth, psycopg, HTML-zu-Text-Bibliothek, pytest)
- [x] 1.2 `.gitignore` und `.env.example` anlegen (Secrets, `token.json`, `client_secret.json` ausschließen)
- [x] 1.3 Konfiguration aus Umgebungsvariablen laden (DB-URL, Pfade zu Token und Client-Secret)

## 2. Datenbank

- [x] 2.1 SQL-Migration für `messages` und `sync_state` schreiben
- [x] 2.2 Migrationsrunner implementieren, der beim Start fehlende Migrationen anwendet
- [x] 2.3 Repository-Funktionen: Mails per `ON CONFLICT DO NOTHING` speichern, Sync-Punkt lesen/schreiben, Datum der letzten Mail lesen
- [x] 2.4 Tests gegen eine Test-Postgres-Instanz (Idempotenz, Transaktion Mails + Sync-Punkt)

## 3. Gmail-Zugriff und Auth

- [x] 3.1 `auth`-Befehl: OAuth-Flow auf dem Host mit Scope `gmail.readonly`, Token ablegen
- [x] 3.2 Gmail-Client mit Token-Laden, Refresh und Zurückschreiben des erneuerten Tokens
- [x] 3.3 Retry/Backoff bei 429 und 5xx

## 4. Mail-Parsing

- [x] 4.1 Header-Extraktion (Absender, Empfänger, Betreff, Datum) in Datenmodell abbilden
- [x] 4.2 Body-Extraktion: text/plain bevorzugt, rekursiv durch multipart; Fallback HTML zu Text; leerer Body, wenn nichts vorhanden; Anhänge ignorieren
- [x] 4.3 Tests mit Beispiel-Nachrichten (plain, multipart/alternative, nur HTML, ohne Text, mit Anhang)

## 5. Sync-Logik

- [x] 5.1 Erster Lauf: `getProfile`, `historyId` speichern, nichts importieren
- [x] 5.2 Inkrementeller Lauf: `history.list` (nur `messagesAdded`, Paginierung), neue IDs deduplizieren, Mails holen, 404 überspringen
- [x] 5.3 Mails und neuen Sync-Punkt in einer Transaktion schreiben
- [x] 5.4 Fallback bei abgelaufener historyId: `messages.list` mit Datumsfilter, danach neuer Sync-Punkt
- [x] 5.5 Advisory Lock gegen parallele Läufe
- [x] 5.6 Tests mit gemocktem Gmail-Client (erster Lauf, Delta, keine Neuen, Fehler beim Speichern, abgelaufener Sync-Punkt)

## 6. Einstiegspunkt und Logging

- [x] 6.1 CLI mit Unterbefehlen `auth` und `run`
- [x] 6.2 Strukturiertes Logging; bei Fehler Exit-Code ungleich 0

## 7. Container und Betrieb

- [x] 7.1 Dockerfile für den Poller mit supercronic und Crontab (alle 30 Minuten)
- [x] 7.2 `docker-compose.yml` mit Postgres (Volume, Healthcheck) und Poller (Token-Volume, `depends_on` healthy)
- [x] 7.3 README: Google-Cloud-Einrichtung (Gmail API, OAuth-Client, „In production"), `auth` ausführen, Stack starten
- [ ] 7.4 End-to-End-Test: Stack starten, Testmail senden, nach einem Lauf in der DB prüfen
