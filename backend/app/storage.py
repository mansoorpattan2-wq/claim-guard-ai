"""Local persistent-volume Demo Adapter, not an object-storage connection."""

import os
import re
from pathlib import Path
from .db import ROOT


class LocalStorage:
    def __init__(self):
        self.root = Path(os.getenv("UPLOAD_DIR", str(ROOT / "storage"))).resolve()

    def path(self, key):
        if not re.fullmatch(r"[A-Za-z0-9-]{1,100}", key):
            raise ValueError("Invalid opaque storage key.")
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root / key

    def put(self, key, content):
        self.path(key).write_bytes(content)

    def get(self, key):
        return self.path(key).read_bytes()

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)


storage = LocalStorage()
