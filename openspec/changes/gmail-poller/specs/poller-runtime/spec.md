## Purpose

Beschreibt Betrieb und Einrichtung des Pollers: Container-Stack, einmalige OAuth-Autorisierung und das 30-Minuten-Scheduling.

## ADDED Requirements

### Requirement: Start per Compose
Das System SHALL mit einem einzigen `docker compose up` Postgres und den Poller starten.

#### Scenario: Stack starten
- **WHEN** der Nutzer `docker compose up -d` ausführt, nachdem die Autorisierung erfolgt ist
- **THEN** laufen Postgres und der Poller und die Daten liegen in einem persistenten Volume

### Requirement: Periodische Ausführung
Das System SHALL den Abruf alle 30 Minuten als eigenständigen Lauf starten, der nach Abschluss endet.

#### Scenario: Zeitplan
- **WHEN** der Stack läuft
- **THEN** wird ca. alle 30 Minuten ein Lauf gestartet

#### Scenario: Keine parallelen Läufe
- **WHEN** ein Lauf beim Start des nächsten noch aktiv ist
- **THEN** startet der neue Lauf nicht parallel

### Requirement: Einmalige OAuth-Autorisierung auf dem Host
Das System SHALL einen Befehl bereitstellen, der auf dem Host den Gmail-OAuth-Consent im Browser durchführt und die Zugangsdaten für den Poller-Container ablegt. Der Zugriff SHALL auf Lesen von Mails beschränkt sein.

#### Scenario: Erstautorisierung
- **WHEN** der Nutzer den Auth-Befehl ausführt und im Browser zustimmt
- **THEN** wird ein Token gespeichert, das der Container nutzt, und es enthält nur Lesezugriff

### Requirement: Token-Erneuerung
Das System SHALL den Zugriffstoken über den Refresh-Token selbständig erneuern und den aktualisierten Token persistent halten.

#### Scenario: Abgelaufener Zugriffstoken
- **WHEN** der Zugriffstoken beim Lauf abgelaufen ist
- **THEN** wird er erneuert und der Lauf läuft normal weiter

### Requirement: Fehlerverhalten
Das System SHALL bei Fehlern (Netzwerk, API, Datenbank, Auth) den Lauf mit einem Fehlerstatus und einer Log-Meldung beenden, ohne den Scheduler zu beenden, sodass der nächste Lauf erneut versucht.

#### Scenario: Gmail nicht erreichbar
- **WHEN** die Gmail-API im Lauf nicht erreichbar ist
- **THEN** wird der Fehler geloggt, nichts fortgeschrieben und der nächste planmäßige Lauf versucht es erneut

### Requirement: Geheimnisse außerhalb des Repos
Das System SHALL Client-Secret, Token und Datenbank-Passwort nicht im Repository ablegen.

#### Scenario: Repository-Inhalt
- **WHEN** das Repository geprüft wird
- **THEN** sind Secrets per Ignore-Regel ausgeschlossen und nur Beispielkonfiguration ist enthalten
