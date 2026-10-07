## Purpose

Beschreibt, wie neue Gmail-Mails inkrementell und idempotent vom Gmail-Konto abgeholt werden, ohne Historie nachzuladen.

## ADDED Requirements

### Requirement: Initialisierung ab jetzt
Beim allerersten Lauf SHALL das System den aktuellen Sync-Punkt des Gmail-Kontos als Startpunkt speichern und KEINE bestehenden Mails importieren.

#### Scenario: Erster Lauf
- **WHEN** kein Sync-Zustand existiert und der Poller läuft
- **THEN** wird der aktuelle Sync-Punkt gespeichert und keine Mail in die Datenbank geschrieben

### Requirement: Inkrementeller Abruf neuer Mails
Das System SHALL bei jedem Lauf alle Mails importieren, die seit dem gespeicherten Sync-Punkt neu im Konto eingegangen sind, und den Sync-Punkt anschließend fortschreiben.

#### Scenario: Neue Mails vorhanden
- **WHEN** seit dem letzten Lauf drei neue Mails eingegangen sind
- **THEN** werden drei Mails gespeichert und der Sync-Punkt auf den neuesten Stand gesetzt

#### Scenario: Keine neuen Mails
- **WHEN** seit dem letzten Lauf nichts eingegangen ist
- **THEN** ändert sich der Mailbestand nicht und der Lauf endet erfolgreich

### Requirement: Idempotenz
Das System SHALL dieselbe Mail höchstens einmal speichern, auch wenn sie in mehreren Läufen oder mehrfach in einer Antwort der Gmail-API auftaucht.

#### Scenario: Wiederholter Lauf
- **WHEN** ein Lauf nach einem Abbruch denselben Bereich erneut verarbeitet
- **THEN** entstehen keine doppelten Einträge

### Requirement: Sync-Punkt erst nach erfolgreichem Schreiben
Das System SHALL den Sync-Punkt nur fortschreiben, nachdem alle zugehörigen Mails erfolgreich gespeichert wurden.

#### Scenario: Fehler beim Speichern
- **WHEN** das Speichern einer Mail fehlschlägt
- **THEN** bleibt der alte Sync-Punkt erhalten und der nächste Lauf holt die Mail erneut

### Requirement: Fallback bei abgelaufenem Sync-Punkt
Ist der gespeicherte Sync-Punkt von Gmail nicht mehr gültig, SHALL das System Mails stattdessen anhand des Datums der zuletzt gespeicherten Mail nachladen und danach einen neuen Sync-Punkt setzen.

#### Scenario: Lange Pause
- **WHEN** der Poller länger als die Gültigkeit des Sync-Punkts nicht lief
- **THEN** werden die in der Zwischenzeit eingegangenen Mails ohne Duplikate nachgeladen und ein neuer Sync-Punkt gespeichert

### Requirement: Nur neue Mails, keine Nachführung
Das System SHALL nur dem Konto hinzugefügte Mails berücksichtigen; Löschungen und Label- oder Statusänderungen bestehender Mails SHALL nicht in die Datenbank übernommen werden.

#### Scenario: Mail gelöscht
- **WHEN** eine bereits gespeicherte Mail in Gmail gelöscht wird
- **THEN** bleibt sie unverändert in der Datenbank
