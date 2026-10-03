# Demo sequence

The final presenter runbook is [JUDGE_DEMO.md](JUDGE_DEMO.md). It contains the exact four-minute clicks, expected states, narration and failure fallbacks. [TECHNICAL_DEFENSE.md](TECHNICAL_DEFENSE.md), [LIMITATIONS.md](LIMITATIONS.md) and [PRODUCTION_ROADMAP.md](PRODUCTION_ROADMAP.md) separate the working prototype from production targets.

Start, restore and check the presentation from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
powershell -ExecutionPolicy Bypass -File .\reset-demo.ps1
powershell -ExecutionPolicy Bypass -File .\preflight-demo.ps1
```

Open `http://127.0.0.1:3000/dashboard`. Require **DEMO READY** before judging. Normal preflight does not change persistent data. Reset restores CG001 READY/98%, CG021 NEEDS_RESOLUTION/63%, CG030 HUMAN_REVIEW/86% and CG048 INVESTIGATION/95%. It restores tasks and clears active human decisions, archives imported claims and prior audit/trace/decision history, and reuses baseline traces. Historical audit remains available with `/api/audit?include_history=true`. The Reset presentation button asks for confirmation; Cancel changes nothing.

With services stopped, the offline alternative is `python backend/manage.py reset-demo`, then `start.ps1`. Sessions are ephemeral; reconnect after backend restart.

Outside the timed sequence, `/claims/new` can load `backend/demo/operative-report.txt` and `backend/demo/final-bill.txt` to demonstrate classification, identity confirmation and eight persisted checks. This browser tab resumes its analysed intake after refresh. Unreadable sources and unsupported/outdated policy remain human-review cases.
