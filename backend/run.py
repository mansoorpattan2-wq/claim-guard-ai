import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "vendor"))
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
    )
