#!/bin/sh
# Run once right away (catches up after a restart or sleep), then on a schedule.
# RUN_COMMAND is the mail_informer command to run. CRONTAB is the schedule file.
python -m mail_informer "${RUN_COMMAND:-run}" || echo "First run failed, starting the scheduler anyway"
exec /usr/local/bin/supercronic "${CRONTAB:-/app/crontab}"
