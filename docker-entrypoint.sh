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
: "${PUID:=0}"
: "${PGID:=0}"
: "${TZ:=UTC}"

case "$PUID" in
  ''|*[!0-9]*) echo "PUID must be a non-negative integer" >&2; exit 1 ;;
esac

case "$PGID" in
  ''|*[!0-9]*) echo "PGID must be a non-negative integer" >&2; exit 1 ;;
esac

if [ "$PUID" = "0" ] && [ "$PGID" != "0" ]; then
  echo "PGID must be 0 when PUID is 0" >&2
  exit 1
fi

if [ ! -f "/usr/share/zoneinfo/$TZ" ]; then
  echo "TZ must name a valid timezone, such as America/Denver" >&2
  exit 1
fi

export TZ
ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime
printf '%s\n' "$TZ" > /etc/timezone

mkdir -p "$BACKUP_FOLDER"
if [ "$PUID" != "0" ]; then
  chown "$PUID:$PGID" "$BACKUP_FOLDER"
fi

export SERVER_ADDRESS USER_NAME PASSWORD BACKUP_FOLDER VALIDATE_TLS_CERT CONVERT_TIMESTAMP_HUMAN_READABLE INCOMPETENT_FILE_SYSTEM BACKUP_CLEANUP_MIN_AGE BACKUP_CLEANUP_MAX_NUMBER TZ
export -p > /etc/unifi-os-backup.env
chmod 600 /etc/unifi-os-backup.env

printf '%s . /etc/unifi-os-backup.env; su-exec %s:%s /usr/local/bin/python3 /app/unifi-os-backup.py >> /proc/1/fd/1 2>> /proc/1/fd/2\n' "$CRON_SCHEDULE" "$PUID" "$PGID" | crontab -

echo "Starting unifi-os-backup with schedule: $CRON_SCHEDULE, UID:GID $PUID:$PGID, timezone: $TZ"
exec crond -f -d 8
