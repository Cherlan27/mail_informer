#!/bin/sh
# Run once right away (catches up after a restart or sleep), then every 30 minutes.
python -m mail_informer run || echo "First run failed, starting the scheduler anyway"
exec /usr/local/bin/supercronic /app/crontab
