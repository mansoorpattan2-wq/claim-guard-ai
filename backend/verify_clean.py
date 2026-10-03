"""Exercise migrations, idempotent seed and real startup on an isolated SQLite DB."""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="clean-verification-", dir=root) as folder:
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + str(Path(folder) / "clean.db")}
    for command in ["migrate", "seed", "seed"]:
        subprocess.run(
            [sys.executable, str(root / "manage.py"), command], env=env, check=True
        )
    server = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys;sys.path.insert(0,'vendor');import uvicorn;from app.main import app;uvicorn.run(app,host='127.0.0.1',port=8001)",
        ],
        cwd=root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for attempt in range(100):
            try:
                urllib.request.urlopen(
                    "http://127.0.0.1:8001/api/health", timeout=1
                ).close()
                break
            except OSError:
                if server.poll() is not None:
                    raise RuntimeError("Clean backend failed to start.")
                time.sleep(0.1)
        else:
            raise RuntimeError("Clean backend startup timed out.")
        request = urllib.request.Request(
            "http://127.0.0.1:8001/api/session",
            data=b'{"role":"Claims Executive"}',
            headers={"Content-Type": "application/json"},
        )
        token = json.load(urllib.request.urlopen(request))["token"]
        request = urllib.request.Request(
            "http://127.0.0.1:8001/api/demo/preflight",
            headers={"Authorization": "Bearer " + token},
        )
        result = json.load(urllib.request.urlopen(request))
        assert result["status"] == "DEMO READY" and result["schema_version"] == 3, (
            result
        )
        print(
            "CLEAN SQLITE STARTUP PASSED: migrations v1-v3, idempotent seed, real API, four initial states and knowledge available."
        )
    finally:
        server.terminate()
        server.wait(timeout=10)
