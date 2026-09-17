FROM python:3.14-alpine

ENV PYTHONUNBUFFERED=1 \
    CRON_SCHEDULE="0 0 * * *" \
    BACKUP_FOLDER="/var/lib/unifi-os-backup"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY unifi-os-backup.py docker-entrypoint.sh ./
RUN chmod +x /app/unifi-os-backup.py /app/docker-entrypoint.sh \
    && mkdir -p /var/lib/unifi-os-backup

VOLUME ["/var/lib/unifi-os-backup"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]