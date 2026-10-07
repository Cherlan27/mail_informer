## Why

Gmail-Mails sollen dauerhaft und strukturiert in einer eigenen Postgres-Datenbank liegen, damit später ein lokales LLM sie prüfen, zusammenfassen und bei bestimmten Mails eine Home-Assistant-Nachricht auslösen kann. Dafür fehlt zuerst die Grundlage: ein zuverlässiger, periodischer Import.

## What Changes

- Neuer Python-Poller, der alle 30 Minuten neue Gmail-Mails über die Gmail API holt (inkrementell per `historyId`) und in Postgres schreibt.
- Gespeichert werden Metadaten und ausschließlich `body_text` (bei reinen HTML-Mails wird der Text aus dem HTML extrahiert; kein `body_html`).
- Die DB ist ein reines Archiv: es gibt keinen Backfill der Historie, der Import startet ab dem Zeitpunkt der Initialisierung; Löschungen/Statusänderungen in Gmail werden nicht nachgezogen.
- Einmaliger interaktiver `auth`-Schritt auf dem Host für den OAuth-Consent, Token wird per Volume/Secret in den Container gegeben.
- `docker-compose` mit Postgres und Poller-Container; ein interner Scheduler (supercronic) startet den One-shot-Lauf alle 30 Minuten.
- Fallback bei abgelaufener `historyId`: Nachladen per `messages.list` mit Datumsfilter, idempotent über `ON CONFLICT DO NOTHING`.
- Pro Mail ein `analysis_status`-Feld (Standard `pending`) als Übergabepunkt für die spätere LLM-Stufe.

Nicht Teil dieser Änderung (Non-goals): LLM-Analyse, Home-Assistant-Benachrichtigung, Anhänge, Historien-Backfill.

## Capabilities

### New Capabilities
- `mail-sync`: Inkrementelles Abholen neuer Gmail-Mails per API, Initialisierung des Sync-Punkts, Fallback bei abgelaufener historyId, idempotentes Schreiben.
- `mail-storage`: Postgres-Schema und Speicherregeln für Mails (Metadaten, `body_text`, Sync-Zustand, `analysis_status`).
- `poller-runtime`: Betrieb per docker-compose, OAuth-Erstautorisierung auf dem Host und 30-Minuten-Scheduling.

### Modified Capabilities
<!-- keine -->

## Impact

- Neues Projekt ohne bestehenden Code; neue Dateien: Python-Paket, Dockerfile, `docker-compose.yml`, DB-Migration/Schema.
- Abhängigkeiten: Google API Client / OAuth-Bibliotheken, Postgres-Treiber, HTML-zu-Text-Bibliothek.
- Externe Voraussetzungen: Google-Cloud-Projekt mit aktivierter Gmail API und OAuth-Client (App-Status „In production", sonst läuft der Refresh-Token nach 7 Tagen ab).
- Läuft auf dem Windows-Rechner mit Docker Desktop; Lücken durch Ruhezustand werden über die historyId nachgeholt.
