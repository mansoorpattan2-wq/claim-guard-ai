from html import escape
from .engine import now


def render(p):
    def e(value):
        return escape(str(value))

    def heading(title):
        return f"<h2>{e(title)}</h2>"

    def source(c):
        return f'<div class="citation"><b>{e(c.get("id", ""))} · {e(c.get("source", ""))}</b><p>{e(c.get("text", ""))}</p><small>Page {e(c.get("page", ""))} · section {e(c.get("section", ""))} · version {e(c.get("version", ""))} · effective {e(c.get("effective_date", ""))}–{e(c.get("expiry_date", ""))} · {e(c.get("authority", ""))}</small></div>'

    findings = (
        "".join(
            f"<article><h3>{e(f['title'])} <span>{e(f['status'])}</span></h3><p>{e(f['data']['description'])}</p><small>Rule {e(f['rule'])} · {e(f['data']['agent'])} agent</small>"
            + "".join(source(c) for c in f["data"]["evidence"])
            + "</article>"
            for f in p["findings"]
        )
        or "<p>No findings generated.</p>"
    )
    decisions = (
        "".join(
            f"<article><b>{e(d['data']['decision'])} · {e(d['data']['reviewer'])}</b><p>{e(d['data']['reason'])}</p><small>{e(d['data']['timestamp'])}</small></article>"
            for d in p["decisions"]
        )
        or "<p>No human decisions recorded.</p>"
    )
    checks = "".join(
        f"<tr><td>{e(k.title())}</td><td>{e(round(v * p['data']['weights'][k], 2))} / {e(p['data']['weights'][k])}</td><td>{'PASS' if v == 1 else 'REVIEW / RESERVE'}</td></tr>"
        for k, v in p["data"]["checks"].items()
    )
    docs = "".join(
        f"<tr><td>{e(d['title'])}</td><td>{e(d['kind'])}</td><td>{e(d['hash'])}</td></tr>"
        for d in p["documents"]
    )
    open_items = [
        f for f in p["findings"] if f["status"] not in ["RESOLVED", "OVERRIDDEN"]
    ]
    unresolved = (
        "<ul>"
        + "".join(f"<li>{e(f['title'])} · {e(f['status'])}</li>" for f in open_items)
        + "</ul>"
        if open_items
        else "<p>No unresolved findings. Readiness does not constitute claim approval.</p>"
    )
    css = """@page{size:A4;margin:16mm}*{box-sizing:border-box}body{font:12px Arial,sans-serif;line-height:1.6;color:#213b48;max-width:860px;margin:30px auto;padding:30px}header{display:flex;justify-content:space-between;border-bottom:3px solid #147e79;padding-bottom:20px}h1{font-size:29px;margin:3px 0}h2{font-size:18px;border-bottom:1px solid #dce6e8;padding-bottom:7px;margin-top:30px}h3{font-size:14px}small{color:#70858e;font-size:10px}p{margin:6px 0}.score{font-size:40px;color:#147e79;font-weight:bold}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}.grid b{display:block}table{width:100%;border-collapse:collapse}th,td{text-align:left;border-bottom:1px solid #e5ecee;padding:8px;vertical-align:top}td:last-child{overflow-wrap:anywhere;font-size:10px}article{padding:15px 0;break-inside:avoid}h3 span{font-size:9px;background:#eef3f4;padding:5px;margin-left:10px}.citation{padding:12px;background:#f2f7f6;border-left:3px solid #4d9b90;margin-top:12px}.stamp{font-size:10px;letter-spacing:1px;color:#7c8f97}footer{border-top:1px solid #dce6e8;margin-top:35px;padding-top:15px;font-size:10px;color:#71878f}@media print{body{margin:0;padding:0}.citation{background:#fff}}"""
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(p["id"])} — Claim Readiness Passport</title><style>{css}</style></head><body><header><div><div class="stamp">CLAIMGUARD AI · SYNTHETIC DEMONSTRATION</div><h1>Claim Readiness Passport</h1><b>{e(p["id"])} · {e(p["status"])}</b></div><div class="score">{e(p["readiness"])}%</div></header><p>Prototype operational readiness score — not probability of approval. Humans retain consequential authority.</p><div class="grid"><div>Beneficiary<b>{e(p["patient"])}</b></div><div>Hospital<b>{e(p["hospital"])}</b></div><div>Payer<b>{e(p["data"]["payer"])}</b></div><div>Procedure<b>{e(p["procedure"])}</b></div><div>Admission / discharge<b>{e(p["data"]["admission"])} / {e(p["data"]["discharge"])}</b></div><div>Amount<b>INR {e(format(p["amount"], ","))}</b></div></div>{heading("Check results")}<table><thead><tr><th>Dimension</th><th>Weighted points</th><th>Check</th></tr></thead><tbody>{checks}</tbody></table>{heading("Unresolved issues")}{unresolved}{heading("Findings and source citations")}{findings}{heading("Human decisions")}{decisions}{heading("Document provenance")}<table><thead><tr><th>Source document</th><th>Classification</th><th>SHA-256 fingerprint</th></tr></thead><tbody>{docs}</tbody></table><footer>Generated {e(now())} (UTC) · synthetic patient/provider/policy data only.<br>Source versions, structured agent runs and action history are retained in the application. No autonomous approval, denial or fraud determination.</footer></body></html>'
