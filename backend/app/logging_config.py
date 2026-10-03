"""Allowlisted structured events: no bodies, URLs, tokens or exception strings."""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("claimguard")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


def event(name, **fields):
    logger.info(
        json.dumps(
            {"time": datetime.now(timezone.utc).isoformat(), "event": name, **fields}
        )
    )
