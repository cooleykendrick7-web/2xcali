import os, sqlite3, hashlib, secrets, re
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
STATIC = BASE / "static"
DB_PATH = os.environ.get("TWOCALI_DB", str(BASE / "leads.db"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "2xcali-admin-2026")
# store hash for comparison without keeping plain in code path beyond env
ADMIN_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

app = FastAPI(title="2xcali")

def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        email_consent INTEGER NOT NULL DEFAULT 0,
        sms_consent INTEGER NOT NULL DEFAULT 0,
        ip TEXT,
        user_agent TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_email ON leads(email)")
    conn.commit()
    return conn

@app.on_event("startup")
def startup():
    db().close()

@app.get("/health")
def health():
    return {"ok": True, "service": "2xcali"}

@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC / "index.html").read_text()

@app.get("/success.html", response_class=HTMLResponse)
def success_page():
    return (STATIC / "success.html").read_text()

@app.get("/success", response_class=HTMLResponse)
def success_page2():
    return (STATIC / "success.html").read_text()

@app.post("/signup")
async def signup(request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
):
    form = await request.form()
    # honeypot
    if form.get("bot-field"):
        return RedirectResponse("/success.html", status_code=303)
    email_consent = 1 if form.get("email-consent") else 0
    sms_consent = 1 if form.get("sms-consent") else 0
    name = name.strip()
    email = email.strip().lower()
    phone = phone.strip()
    if not name or not email or not phone:
        return JSONResponse({"error": "Name, email and phone are required"}, status_code=400)
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return JSONResponse({"error": "Invalid email"}, status_code=400)
    if not email_consent:
        return JSONResponse({"error": "Email consent is required"}, status_code=400)
    now = datetime.now(timezone.utc).isoformat()
    conn = db()
    try:
        conn.execute(
            "INSERT INTO leads (name,email,phone,email_consent,sms_consent,ip,user_agent,created_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET name=excluded.name, phone=excluded.phone, email_consent=excluded.email_consent, sms_consent=excluded.sms_consent, created_at=excluded.created_at",
            (name, email, phone, email_consent, sms_consent, request.client.host if request.client else "", request.headers.get("user-agent",""), now)
        )
        conn.commit()
    finally:
        conn.close()
    # support both browser form and API callers
    if "application/json" in (request.headers.get("accept") or ""):
        return JSONResponse({"ok": True})
    return RedirectResponse("/success.html", status_code=303)

@app.post("/api/signup")
async def api_signup(request: Request):
    data = {}
    ct = request.headers.get("content-type","")
    if "application/json" in ct:
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)
    name = str(data.get("name","")).strip()
    email = str(data.get("email","")).strip().lower()
    phone = str(data.get("phone","")).strip()
    email_consent = 1 if data.get("email-consent") or data.get("email_consent") else 0
    sms_consent = 1 if data.get("sms-consent") or data.get("sms_consent") else 0
    if data.get("bot-field"):
        return {"ok": True}
    if not name or not email or not phone:
        return JSONResponse({"error": "Name, email and phone are required"}, status_code=400)
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return JSONResponse({"error": "Invalid email"}, status_code=400)
    if not email_consent:
        return JSONResponse({"error": "Email consent is required"}, status_code=400)
    now = datetime.now(timezone.utc).isoformat()
    conn = db()
    try:
        conn.execute(
            "INSERT INTO leads (name,email,phone,email_consent,sms_consent,ip,user_agent,created_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET name=excluded.name, phone=excluded.phone, email_consent=excluded.email_consent, sms_consent=excluded.sms_consent, created_at=excluded.created_at",
            (name, email, phone, email_consent, sms_consent, request.client.host if request.client else "", request.headers.get("user-agent",""), now)
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

def check_admin(request: Request):
    pwd = request.query_params.get("key") or request.headers.get("x-admin-key") or ""
    # also accept cookie-less simple key param named password
    if not pwd:
        pwd = request.query_params.get("password","")
    return hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_HASH

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    if not check_admin(request):
        return HTMLResponse("""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>2xcali Admin</title><style>body{background:#090909;color:#eee9df;font-family:Arial;display:grid;place-items:center;min-height:100vh;margin:0}form{display:grid;gap:12px;background:#111;padding:28px;border:1px solid #30302e;min-width:300px}input{padding:14px;background:#090909;border:1px solid #41403d;color:#fff}button{background:#c9a875;border:0;padding:14px;font-weight:900;letter-spacing:1px;cursor:pointer}</style></head><body><form method="get" action="/admin"><h2 style="margin:0">2xcali — Leads</h2><p style="color:#aaa59c;font-size:13px;margin:0">Enter admin password to view signups.</p><input type="password" name="key" placeholder="Admin password" required><button>VIEW LEADS</button></form></body></html>""", status_code=200)
    conn = db()
    rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    conn.close()
    items = "".join(f"<tr><td>{r['id']}</td><td>{r['name']}</td><td>{r['email']}</td><td>{r['phone']}</td><td>{'Yes' if r['email_consent'] else 'No'}</td><td>{'Yes' if r['sms_consent'] else 'No'}</td><td>{r['created_at']}</td></tr>" for r in rows)
    if not items:
        items = "<tr><td colspan=7 style='color:#aaa59c'>No signups yet — share your link and they'll show up here live.</td></tr>"
    html = f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>2xcali Leads</title><style>body{{background:#090909;color:#eee9df;font-family:Arial;margin:0;padding:24px}}h1{{letter-spacing:-1px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{border:1px solid #30302e;padding:10px;text-align:left}}th{{background:#111;color:#c9a875;letter-spacing:1px;font-size:11px}}a{{color:#c9a875}}</style></head><body><h1>2xcali — Signups ({len(rows)})</h1><p><a href="/">← Back to site</a> &nbsp; <a href="/api/leads?key={request.query_params.get('key','')}">Download JSON</a></p><div style="overflow:auto"><table><tr><th>ID</th><th>NAME</th><th>EMAIL</th><th>PHONE</th><th>EMAIL OK</th><th>SMS OK</th><th>DATE (UTC)</th></tr>{items}</table></div></body></html>"""
    return HTMLResponse(html)

@app.get("/api/leads")
def api_leads(request: Request):
    if not check_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    conn = db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()]
    conn.close()
    return {"count": len(rows), "leads": rows}

# static assets
app.mount("/assets", StaticFiles(directory=str(STATIC / "assets")), name="assets")
