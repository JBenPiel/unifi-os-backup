#!/bin/sh
set -eu

if [ -z "${SERVER_ADDRESS:-}" ]; then
  echo "SERVER_ADDRESS is required" >&2
  exit 1
fi

if [ -z "${USER_NAME:-}" ]; then
  echo "USER_NAME is required" >&2
  exit 1
fi

if [ -z "${PASSWORD:-}" ]; then
  echo "PASSWORD is required" >&2
  exit 1
fi

: "${BACKUP_FOLDER:=/var/lib/unifi-os-backup}"
: "${CRON_SCHEDULE:=0 0 * * *}"

mkdir -p "$BACKUP_FOLDER"

export SERVER_ADDRESS USER_NAME PASSWORD BACKUP_FOLDER VALIDATE_TLS_CERT CONVERT_TIMESTAMP_HUMAN_READABLE INCOMPETENT_FILE_SYSTEM BACKUP_CLEANUP_MIN_AGE BACKUP_CLEANUP_MAX_NUMBER
export -p > /etc/unifi-os-backup.env
printf '%s . /etc/unifi-os-backup.env; /usr/local/bin/python3 /app/unifi-os-backup.py >> /proc/1/fd/1 2>> /proc/1/fd/2\n' "$CRON_SCHEDULE" | crontab -

echo "Starting unifi-os-backup with schedule: $CRON_SCHEDULE"
exec crond -f -d 8