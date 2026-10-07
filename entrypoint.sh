#!/bin/sh
# Einmal sofort laufen (holt nach Neustart/Ruhezustand direkt nach), dann alle 30 Minuten.
python -m mail_informer run || echo "Erster Lauf fehlgeschlagen, Scheduler startet trotzdem"
exec /usr/local/bin/supercronic /app/crontab
