## Purpose

Legt fest, welche Mail-Daten dauerhaft in Postgres gespeichert werden und wie der Zustand für Sync und spätere Analyse abgelegt ist.

## ADDED Requirements

### Requirement: Gespeicherte Mail-Felder
Das System SHALL pro Mail die Gmail-Message-ID, Thread-ID, Empfangsdatum, Absender, Empfänger, Betreff, Labels, Snippet, `body_text` und den Abrufzeitpunkt speichern. Die Gmail-Message-ID SHALL die Mail eindeutig identifizieren.

#### Scenario: Normale Mail
- **WHEN** eine Mail mit text/plain-Teil importiert wird
- **THEN** sind alle genannten Felder gespeichert und `body_text` enthält den Klartext

### Requirement: Nur Klartext-Body
Das System SHALL ausschließlich Klartext als Body speichern und KEIN HTML ablegen. Enthält eine Mail nur einen HTML-Teil, SHALL daraus Klartext abgeleitet und gespeichert werden.

#### Scenario: Reine HTML-Mail
- **WHEN** eine Mail nur text/html enthält
- **THEN** wird `body_text` aus dem HTML extrahiert und es wird kein HTML gespeichert

#### Scenario: Mail ohne Text
- **WHEN** eine Mail weder text/plain noch text/html enthält
- **THEN** wird sie mit leerem `body_text` gespeichert

### Requirement: Vollständiger Body
Das System SHALL den Body ungekürzt speichern.

#### Scenario: Lange Mail
- **WHEN** eine sehr lange Mail importiert wird
- **THEN** wird der gesamte Text gespeichert

### Requirement: Keine Anhänge
Das System SHALL keine Anhänge speichern.

#### Scenario: Mail mit Anhang
- **WHEN** eine Mail mit Anhang importiert wird
- **THEN** wird der Anhang nicht gespeichert, Text und Metadaten schon

### Requirement: Analysestatus
Das System SHALL pro Mail einen Analysestatus führen, der für neue Mails den Wert `pending` hat, und SHALL diesen im Poller nie ändern.

#### Scenario: Neue Mail
- **WHEN** eine Mail importiert wird
- **THEN** hat sie den Analysestatus `pending`

### Requirement: Persistenter Sync-Zustand
Das System SHALL den Sync-Punkt in der Datenbank speichern, sodass er Neustarts von Containern überdauert.

#### Scenario: Neustart
- **WHEN** Container neu gestartet werden
- **THEN** setzt der nächste Lauf am gespeicherten Sync-Punkt fort

### Requirement: Schema-Initialisierung
Das System SHALL das Datenbankschema bei Bedarf selbständig anlegen bzw. auf den aktuellen Stand bringen.

#### Scenario: Leere Datenbank
- **WHEN** der Poller gegen eine leere Datenbank startet
- **THEN** werden die benötigten Tabellen angelegt
