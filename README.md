# Unifi OS Server backup

Automated backups outside the cloud.

# Configuration

All settings are environment variables. Docker requires `SERVER_ADDRESS`, `USER_NAME`, and `PASSWORD` to be set to non-empty values; the container exits at startup if any is missing. The script also runs directly with its own fallback values, shown below.

| Variable | Required in Docker | Default if unset | What it does |
| --- | --- | --- | --- |
| `SERVER_ADDRESS` | Yes | Script: `https://localhost:11443`; Docker: none | Base URL of the UniFi OS Server, including its port. |
| `USER_NAME` | Yes | Script: `admin`; Docker: none | Username used to log in to the server. |
| `PASSWORD` | Yes | Script: empty string; Docker: none | Password used to log in to the server. |
| `BACKUP_FOLDER` | No | `/var/lib/unifi-os-backup` | Directory where downloaded backups are saved. Mount it to persistent storage in Docker. |
| `VALIDATE_TLS_CERT` | No | `false` | Whether to verify the server's HTTPS certificate. Set to `true` when the certificate is trusted. |
| `CONVERT_TIMESTAMP_HUMAN_READABLE` | No | `true` | Convert the Unix millisecond timestamp in backup filenames to a readable ISO 8601 date and time. |
| `INCOMPETENT_FILE_SYSTEM` | No | `false` | Replace `:` with `.` in converted timestamps for filesystems that do not allow colons. |
| `BACKUP_CLEANUP_MIN_AGE` | No | `604800` (7 days) | Minimum backup age in seconds before cleanup may delete it. `0` removes the age limit. |
| `BACKUP_CLEANUP_MAX_NUMBER` | No | `7` | Keep the configured number of newest backups; older backups are deleted only after reaching the minimum age. |
| `CRON_SCHEDULE` | No | `0 0 * * *` | Docker-only five-field cron schedule; runs daily at midnight by default. |
| `PUID` | No | `0` | Numeric user ID used to run the backup process. Set it to the owner of the mounted backup directory. |
| `PGID` | No | `0` | Numeric group ID used to run the backup process. Set it to the group of the mounted backup directory. |
| `TZ` | No | `UTC` | IANA timezone used for cron scheduling and generated timestamps, such as `America/Denver`. |

Downloaded files use the format `unifi_os_backup_<timestamp>_<version>.unifi`. The version is the installed UniFi OS version reported by the server's authenticated `/api/system` endpoint. If that endpoint does not provide a usable version, the original backup ID is retained. Existing backups with IDs remain valid and are still considered for cleanup.

Boolean settings accept `true`/`false`, `1`/`0`, `yes`/`no`, or `on`/`off` (case-insensitive). Cleanup values must be non-negative integers.

# Docker setup

The Docker image runs the backup script from cron. The schedule defaults to midnight every day and can be changed with `CRON_SCHEDULE`. Set `PUID` and `PGID` to the numeric IDs that own the host backup directory. The cron daemon remains root so it can schedule jobs and forward logs, while the Python backup process runs as those IDs. `TZ` controls both the cron schedule and timestamps.

```bash
docker run -d \
  --name unifi-os-backup \
  -e SERVER_ADDRESS="https://unifi.example.com:11443" \
  -e USER_NAME="admin" \
  -e PASSWORD="your-password" \
  -e BACKUP_FOLDER="/var/lib/unifi-os-backup" \
  -e VALIDATE_TLS_CERT="false" \
  -e CONVERT_TIMESTAMP_HUMAN_READABLE="true" \
  -e INCOMPETENT_FILE_SYSTEM="false" \
  -e BACKUP_CLEANUP_MIN_AGE="604800" \
  -e BACKUP_CLEANUP_MAX_NUMBER="7" \
  -e CRON_SCHEDULE="0 0 * * *" \
  -e PUID="1000" \
  -e PGID="1000" \
  -e TZ="America/Denver" \
  -v /srv/unifi-os-backup:/var/lib/unifi-os-backup \
  jpiel/unifi-os-backup:latest
```

For Docker Compose, save this as `compose.yaml`:

```yaml
services:
  unifi-os-backup:
    image: jpiel/unifi-os-backup:latest
    restart: unless-stopped
    environment:
      SERVER_ADDRESS: "https://unifi.example.com:11443"
      USER_NAME: "admin"
      PASSWORD: "password"
      BACKUP_FOLDER: "/var/lib/unifi-os-backup"
      VALIDATE_TLS_CERT: "false"
      CONVERT_TIMESTAMP_HUMAN_READABLE: "true"
      INCOMPETENT_FILE_SYSTEM: "false"
      BACKUP_CLEANUP_MIN_AGE: "604800"
      BACKUP_CLEANUP_MAX_NUMBER: "7"
      CRON_SCHEDULE: "0 0 * * *"
      PUID: "1000"
      PGID: "1000"
      TZ: "America/Denver"
    volumes:
      - /srv/unifi-os-backup:/var/lib/unifi-os-backup
```

Replace the Compose example's `password` value with your password, then run `docker compose up -d` from this directory. Backups are written to `/srv/unifi-os-backup` on the host.
