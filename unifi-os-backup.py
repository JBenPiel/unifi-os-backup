#!/usr/bin/env python3
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

import requests

def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    if value.lower() in ("true", "1", "yes", "on"):
        return True
    if value.lower() in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"{name} must be true or false")


def env_nonnegative_int(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value

########## START USER CONFIGURATION #############
# your server address including port
SERVER_ADDRESS = os.environ.get("SERVER_ADDRESS", "https://localhost:11443")
# preferably this would be set to True, but the default setup is using a self-signed cert
VALIDATE_TLS_CERT = env_bool("VALIDATE_TLS_CERT", False)
USER_NAME = os.environ.get("USER_NAME", "admin")
PASSWORD = os.environ.get("PASSWORD", "")

# path to the folder, where the backups should be saved
# preferable use an absolute path here
BACKUP_FOLDER = os.environ.get("BACKUP_FOLDER", "/var/lib/unifi-os-backup")

# suggested filenames by Unifi OS are presented with a unix timestamp
# if this option is enabled, the unix timestamp is converted to IS0-8601 timestamps before saving
CONVERT_TIMESTAMP_HUMAN_READABLE = env_bool("CONVERT_TIMESTAMP_HUMAN_READABLE", True)

# some filesystems cannot handle ":", so we replace this with ".", if the option is set
INCOMPETENT_FILE_SYSTEM = env_bool("INCOMPETENT_FILE_SYSTEM", False)

# minimum age for backups to be considered for deletion
# takes precedence over BACKUP_CLEANUP_MAX_NUMBER
# set to 0 to disable
# environment value is a non-negative number of seconds
BACKUP_CLEANUP_MIN_AGE = timedelta(seconds=env_nonnegative_int("BACKUP_CLEANUP_MIN_AGE", 604800))

# maximum numbers of backups to keep after considering minimum age
BACKUP_CLEANUP_MAX_NUMBER = env_nonnegative_int("BACKUP_CLEANUP_MAX_NUMBER", 7)
########## END USER CONFIGURATION ##############

BACKUP_FILE_NAME_PREFIX = "unifi_os_backup_"

LOGIN_URL = "/api/auth/login"
SYSTEM_URL = "/api/system"
BACKUP_URL = "/api/backup/download"

def extract_file_ts(filename: str) -> tuple[str, str]:
    ts, e = filename.removeprefix(BACKUP_FILE_NAME_PREFIX).split("_", 1)
    return ts, e

def get_os_version(sess, server_address: str) -> str | None:
    try:
        with sess.get(
            f"{server_address}{SYSTEM_URL}",
            verify=VALIDATE_TLS_CERT,
            timeout=60
        ) as resp:
            resp.raise_for_status()
            system = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"could not read UniFi OS version: {exc}")
        return None

    if not isinstance(system, dict):
        return None
    hardware = system.get("hardware")
    version = hardware.get("firmwareVersion") if isinstance(hardware, dict) else None
    version = version or system.get("firmwareVersion")
    if isinstance(version, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]*", version):
        return version
    return None


def download():
    server_address = SERVER_ADDRESS.removesuffix("/")
    with requests.Session() as sess:
        print("logging in")
        resp = sess.post(
            f"{server_address}{LOGIN_URL}",
            json={"username": USER_NAME, "password": PASSWORD},
            verify=VALIDATE_TLS_CERT,
            timeout=60
        )
        resp.raise_for_status()
        print("logged in")
        os_version = get_os_version(sess, server_address)
        if os_version is None:
            print("UniFi OS version unavailable; keeping the backup ID in the filename")
        with sess.get(
            f"{server_address}{BACKUP_URL}",
            verify=VALIDATE_TLS_CERT,
            timeout=60,
            stream=True
        ) as resp:
            resp.raise_for_status()
            assert resp.headers["Content-Type"] == "application/octet-stream"
            filename = resp.headers["filename"]
            assert filename.startswith(BACKUP_FILE_NAME_PREFIX)
            file_ts, filename_end = extract_file_ts(filename)
            if CONVERT_TIMESTAMP_HUMAN_READABLE:
                file_ts = datetime.fromtimestamp(int(file_ts) / 1000).isoformat(timespec="seconds")
                if INCOMPETENT_FILE_SYSTEM:
                    file_ts = file_ts.replace(":", ".")
            if os_version is not None:
                filename_end = f"{os_version}{Path(filename_end).suffix}"
            filename = f"{BACKUP_FILE_NAME_PREFIX}{file_ts}_{filename_end}"

            backup_dir = Path(BACKUP_FOLDER)
            backup_dir.mkdir(parents=True, exist_ok=True)
            download_path = backup_dir / filename
            temp_path = None
            try:
                with NamedTemporaryFile(
                    mode="wb", dir=backup_dir, prefix=".unifi-os-backup-", suffix=".tmp", delete=False
                ) as temp_file:
                    temp_path = Path(temp_file.name)
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        temp_file.write(chunk)
                    if temp_file.tell() == 0:
                        raise ValueError("backup download was empty")
                os.replace(temp_path, download_path)
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)

            print(f"saved \"{filename}\" at \"{BACKUP_FOLDER}\"")


def cleanup():
    backups = []
    print("starting clean up")
    for b in Path(BACKUP_FOLDER).iterdir():
        if not b.is_file():
            continue
        if not b.name.startswith(BACKUP_FILE_NAME_PREFIX):
            continue
        file_ts, _ = extract_file_ts(b.name)
        if INCOMPETENT_FILE_SYSTEM:
            file_ts = file_ts.replace(".", ":")
        if CONVERT_TIMESTAMP_HUMAN_READABLE:
            file_ts = datetime.fromisoformat(file_ts)
        else:
            file_ts = datetime.fromtimestamp(int(file_ts) / 1000)
        backups.append((file_ts, b))
    backups.sort(key=lambda x: x[0], reverse=True)
    now = datetime.now()
    for b in backups[BACKUP_CLEANUP_MAX_NUMBER:]:
        backup_path = b[1]
        if now - b[0] < BACKUP_CLEANUP_MIN_AGE:
            print(f"skipping cleanup of backup \"{backup_path}\" because it has not reached minimum age")
            continue
        print(f"deleting backup \"{backup_path}\"")
        backup_path.unlink()


def main():
    download()
    cleanup()
    print("finished")

if __name__ == "__main__":
    main()
