"""Explicit deployment administration; normal production startup never seeds/resets."""

import argparse
import sys
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "vendor"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate", "seed", "reset-demo"])
    args = parser.parse_args()
    from app.db import migrate, Session
    from app.logging_config import event

    try:
        if args.command == "migrate":
            migrate()
        elif args.command == "seed":
            importlib.import_module("app.main")  # existing router import order
            from app.engine import seed
            from app.p1 import bootstrap
            from app.p2 import bootstrap as bootstrap_p2

            with Session() as s:
                seed(s)
                bootstrap(s)
                bootstrap_p2(s)
            event("seed_complete", synthetic=True)
        else:
            importlib.import_module("app.main")
            from app.p1 import reset_demo

            with Session() as s:
                result = reset_demo(
                    s, {"role": "Claims Executive", "org_id": "demo-hospital"}
                )
                event("demo_reset", restored_claims=result["restored_claims"])
    except Exception as exc:
        event(
            "administration_failed", command=args.command, error_type=type(exc).__name__
        )
        print(
            "Administration failed. Check database access, migrations and installed dependencies.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
