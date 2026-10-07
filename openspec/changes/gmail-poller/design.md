## Context

Greenfield-Projekt, siehe proposal.md. Läuft auf einem Windows-Rechner mit Docker Desktop, der nicht dauerhaft an ist. Eine spätere Stufe (lokales LLM, Home Assistant) soll auf den gespeicherten Mails aufsetzen.

## Goals / Non-Goals

**Goals:**
- Robuster, idempotenter Import, der Ausfälle und Ruhezustand selbst nachholt.
- Klare Übergabe an eine spätere Analysestufe nur über die Datenbank.

**Non-Goals:**
- Kein Daemon, keine Push-Benachrichtigung (Gmail Pub/Sub), keine Webschnittstelle.

## Decisions

- **Gmail API statt IMAP.** `history.list` mit `historyId` liefert effiziente Deltas; Labels und Threads sind nativ. Scope `gmail.readonly`. IMAP wäre einfacher einzurichten, ist aber bei Deltas und Labels schlechter.
- **Python, One-shot-Prozess.** Ein Lauf = Sync-Punkt lesen, neue Mails holen, in einer Transaktion schreiben, Sync-Punkt setzen, beenden. Kein Zustand im Prozess, ein Crash kostet höchstens einen Lauf.
- **Scheduling per supercronic im Poller-Container.** Alles liegt im Repo, `docker compose up -d` genügt. Alternative Windows Task Scheduler mit `docker compose run --rm`: robuster gegen Hänger, aber Setup außerhalb des Repos. Gegen Überlappung zusätzlich ein Postgres Advisory Lock (`pg_try_advisory_lock`); wer ihn nicht bekommt, beendet sich still.
- **Initialisierung über `users.getProfile`.** Die zurückgegebene `historyId` wird als Startpunkt gespeichert; kein Backfill.
- **Nur `messagesAdded` aus der History** wird ausgewertet. Je neuer Message-ID wird `messages.get(format=full)` aufgerufen. Fehlt die Mail inzwischen (404, z. B. gelöscht), wird sie übersprungen.
- **Fallback bei 404 auf history.list:** `messages.list` mit `q=after:<Datum der letzten Mail minus Sicherheitspuffer>`, danach neuer Sync-Punkt über `getProfile`. Duplikate fängt `ON CONFLICT (gmail_id) DO NOTHING` ab.
- **Body-Extraktion:** text/plain bevorzugen (rekursiv durch multipart), sonst text/html per HTML-zu-Text-Bibliothek. Kein HTML wird gespeichert (lokales LLM, weniger Tokens).
- **Schema (Postgres):**
  - `messages(gmail_id PK, thread_id, internal_date, from_addr, to_addrs, subject, labels text[], snippet, body_text, fetched_at, analysis_status default 'pending')`
  - `sync_state(id=1 PK, history_id, updated_at)`
  - Schema wird beim Start des Pollers angelegt (einfache versionierte SQL-Migrationen statt ORM).
- **Auth:** `auth`-Befehl läuft auf dem Host (InstalledAppFlow, lokaler Redirect) und schreibt `token.json` in ein Verzeichnis, das als Volume in den Container gemountet wird. Der Poller schreibt erneuerte Tokens dorthin zurück. Secrets liegen in `.env` bzw. `secrets/`, beides in `.gitignore`.
- **Transaktion:** Mails und neuer `history_id` werden in einer DB-Transaktion geschrieben, damit der Sync-Punkt nie vor den Daten fortschreitet.

## Risks / Trade-offs

- OAuth-App im Testing-Status → Refresh-Token verfällt nach 7 Tagen → App auf „In production" stellen (unverified genügt); der Fehler wird geloggt.
- historyId älter als ca. eine Woche → Fallback per Datumsabfrage.
- Rate Limits der Gmail-API bei großen Deltas → sequentielle Abrufe mit Retry/Backoff bei 429/5xx.
- Docker Desktop läuft nicht → Lauf entfällt, wird beim nächsten Start nachgeholt.
- Mails ohne Text bleiben mit leerem Body → für das spätere LLM irrelevant, im Archiv aber sichtbar.
- Gelöschte oder umgelabelte Mails werden nicht nachgezogen (bewusst: Archiv).
