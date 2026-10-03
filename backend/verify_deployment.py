"""Real CG021 persistence across a Compose backend stop/start, no fabricated results."""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "vendor"))
import httpx

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker",
    "--context",
    "desktop-linux",
    "compose",
    "--env-file",
    str(ROOT / "deploy.env"),
    "-p",
    "claimguard-deploy",
]


def main():
    values = dict(
        line.split("=", 1)
        for line in (ROOT / "deploy.env").read_text().splitlines()
        if "=" in line
    )
    reset_key = values["DEMO_RESET_KEY"]
    url = "http://127.0.0.1:8100"
    client = httpx.Client(base_url=url, timeout=20)

    def call(method, path, body=None):
        response = client.request(
            method, path, **({"json": body} if body is not None else {})
        )
        response.raise_for_status()
        return response.json()

    def login(role):
        client.headers["Authorization"] = (
            "Bearer " + call("POST", "/api/session", {"role": role})["token"]
        )

    login("Claims Executive")
    assert client.post("/api/demo/reset-all").status_code == 403
    client.headers["X-Demo-Reset-Key"] = reset_key
    call("POST", "/api/demo/reset-all")
    assert call("GET", "/api/demo/preflight")["status"] == "DEMO READY"
    assert call("GET", "/api/claims/CG021")["readiness"] == 63
    call("POST", "/api/findings/CG021-F14/resolve")
    for action in ["generate", "simulate_send"]:
        call("POST", "/api/resolutions/RT-CG021/request", {"action": action})
    call("POST", "/api/resolutions/RT-CG021/simulate-response")
    result = call("POST", "/api/resolutions/RT-CG021/complete")
    assert (result["readiness"], result["status"]) == (94, "READY")
    login("Medical Reviewer")
    call(
        "POST",
        "/api/review/CG030-F04/decision",
        {"decision": "OVERRIDE", "reason": "Synthetic deployment persistence review"},
    )
    login("Claims Executive")
    before = {
        "claim": call("GET", "/api/claims/CG021"),
        "audit": call("GET", "/api/audit?claim_id=CG021"),
        "human": call("GET", "/api/claims/CG030")["decisions"],
    }
    intake = call("POST", "/api/intakes")
    uploaded = client.post(
        f"/api/intakes/{intake['id']}/files",
        files={
            "files": (
                "deployment-probe.txt",
                b"SYNTHETIC persistent upload probe",
                "text/plain",
            )
        },
    )
    uploaded.raise_for_status()
    upload_key = uploaded.json()["files"][0]["id"]
    subprocess.run(COMPOSE + ["stop", "backend"], check=True)
    subprocess.run(COMPOSE + ["up", "-d", "--wait", "backend"], check=True)
    for _ in range(20):
        try:
            if client.get("/ready").status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    # Sessions are intentionally process-local. A fresh role session is required.
    assert client.get("/api/claims/CG021").status_code == 401
    login("Claims Executive")
    after = {
        "claim": call("GET", "/api/claims/CG021"),
        "audit": call("GET", "/api/audit?claim_id=CG021"),
        "human": call("GET", "/api/claims/CG030")["decisions"],
    }
    assert after == before, (
        "Persisted passport, task/run history, audit and human metadata changed across restart."
    )
    probe = (
        "from app.storage import storage; assert storage.get('"
        + upload_key
        + "') == b'SYNTHETIC persistent upload probe'; print('Upload bytes survived restart')"
    )
    subprocess.run(
        COMPOSE + ["exec", "-T", "backend", "python", "-c", probe], check=True
    )
    call("POST", "/api/demo/reset-all")
    call("POST", "/api/demo/reset-all")
    assert call("GET", "/api/demo/preflight")["status"] == "DEMO READY"
    assert len(call("GET", "/api/claims")) == 50
    report = {
        "database": "PostgreSQL",
        "cg021_before_restart": [94, "READY"],
        "cg021_after_restart": [94, "READY"],
        "passport_task_runs_equal": True,
        "audit_equal": True,
        "human_decisions_equal": True,
        "original_upload_retained": True,
        "reset_twice": "DEMO READY",
        "active_claims": 50,
        "sessions_require_reconnect": True,
    }
    folder = ROOT / "docs" / "deployment"
    folder.mkdir(exist_ok=True)
    (folder / "persistence.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "PostgreSQL restart persistence: PASS; CG021 63 -> 94 -> restart 94 -> reset 63; 50 active claims."
    )


if __name__ == "__main__":
    main()
