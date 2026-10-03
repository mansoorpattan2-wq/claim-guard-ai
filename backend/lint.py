import subprocess
from pathlib import Path

root = Path(__file__).parent
binary = next(
    (
        p
        for p in (
            root / "vendor/bin/ruff.exe",
            root / "tools/bin/ruff.exe",
            root / "vendor/bin/ruff",
            root / "tools/bin/ruff",
        )
        if p.exists()
    ),
    None,
)
if binary is None:
    raise SystemExit(
        "Install lint tooling: python -m pip install --target backend/tools ruff==0.16.10"
    )
raise SystemExit(
    subprocess.call(
        [
            str(binary),
            "check",
            str(root / "app"),
            str(root / "tests"),
            "--select",
            "F,E9",
        ]
    )
)
