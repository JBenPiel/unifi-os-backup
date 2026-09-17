import importlib.util
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "unifi-os-backup.py"
FILENAME = "unifi_os_backup_123_backup.unf"
VERSION_FILENAME = "unifi_os_backup_123_5.1.19.unf"


class FakeResponse:
    headers = {"Content-Type": "application/octet-stream", "filename": FILENAME}

    def __init__(self, fail=False, empty=False):
        self.fail = fail
        self.empty = empty

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        assert chunk_size > 0
        if self.empty:
            return
        yield b"new"
        if self.fail:
            raise OSError("download interrupted")
        yield b" backup"


class FakeSystemResponse:
    def __init__(self, version=None):
        self.version = version

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    def json(self):
        return {"hardware": {"firmwareVersion": self.version}}


class FakeSession:
    def __init__(self, response, version="5.1.19"):
        self.response = response
        self.version = version

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, *_, **__):
        return types.SimpleNamespace(raise_for_status=lambda: None)

    def get(self, url, **kwargs):
        if url.endswith("/api/system"):
            assert kwargs["timeout"] == 60
            return FakeSystemResponse(self.version)
        assert kwargs["stream"] is True
        return self.response


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests_stub = types.ModuleType("requests")
        requests_stub.Session = lambda: None
        requests_stub.RequestException = Exception
        spec = importlib.util.spec_from_file_location("unifi_os_backup", SCRIPT)
        cls.script = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"requests": requests_stub}):
            spec.loader.exec_module(cls.script)

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.backup_dir = Path(self.directory.name)
        self.destination = self.backup_dir / VERSION_FILENAME
        self.destination.write_bytes(b"old backup")
        self.script.BACKUP_FOLDER = self.directory.name
        self.script.CONVERT_TIMESTAMP_HUMAN_READABLE = False

    def test_complete_stream_replaces_existing_backup(self):
        with patch.object(self.script.requests, "Session", return_value=FakeSession(FakeResponse())):
            self.script.download()

        self.assertEqual(self.destination.read_bytes(), b"new backup")
        self.assertEqual(list(self.backup_dir.iterdir()), [self.destination])

    def test_interrupted_stream_keeps_existing_backup(self):
        with patch.object(self.script.requests, "Session", return_value=FakeSession(FakeResponse(fail=True))):
            with self.assertRaisesRegex(OSError, "download interrupted"):
                self.script.download()

        self.assertEqual(self.destination.read_bytes(), b"old backup")
        self.assertEqual(list(self.backup_dir.iterdir()), [self.destination])

    def test_empty_stream_keeps_existing_backup(self):
        with patch.object(self.script.requests, "Session", return_value=FakeSession(FakeResponse(empty=True))):
            with self.assertRaisesRegex(ValueError, "backup download was empty"):
                self.script.download()

        self.assertEqual(self.destination.read_bytes(), b"old backup")
        self.assertEqual(list(self.backup_dir.iterdir()), [self.destination])

    def test_missing_version_keeps_backup_id(self):
        with patch.object(self.script.requests, "Session", return_value=FakeSession(FakeResponse(), version=None)):
            self.script.download()

        self.assertEqual((self.backup_dir / FILENAME).read_bytes(), b"new backup")

    def test_invalid_version_keeps_backup_id(self):
        with patch.object(self.script.requests, "Session", return_value=FakeSession(FakeResponse(), version="../bad")):
            self.script.download()

        self.assertEqual((self.backup_dir / FILENAME).read_bytes(), b"new backup")


if __name__ == "__main__":
    unittest.main()
