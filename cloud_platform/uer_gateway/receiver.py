"""
UER Gateway - Receives and validates UERs from Edge Agents
"""
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import uvicorn
import os
from starlette.middleware.sessions import SessionMiddleware

from shared.models.uer_schema import UnifiedEventReport
from shared.utils.logger import get_logger
from sqlalchemy.orm import Session
from shared.utils.db import get_db
from shared.utils.user_store_db import (
    init_db,
    create_user as db_create_user,
    verify_user as db_verify_user,
    get_user as db_get_user,
    password_is_strong,
)

logger = get_logger(__name__, "uer_gateway.log")

app = FastAPI(title="CoMIDF UER Gateway")

# Session configuration
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production-please")
SESSION_COOKIE = os.getenv("SESSION_COOKIE_NAME", "comidf_session")
SESSION_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie=SESSION_COOKIE,
    https_only=SESSION_SECURE,
    same_site=SESSION_SAMESITE,
)


# Ensure DB schema exists on app startup
@app.on_event("startup")
def _startup_init_db():
    try:
        from shared.utils.user_store_db import init_db as _init
        _init()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

# Google OAuth (via Authlib)
try:
    from authlib.integrations.starlette_client import OAuth
    OAUTH_AVAILABLE = True
except Exception:
    OAUTH_AVAILABLE = False

oauth = None
if OAUTH_AVAILABLE:
    oauth = OAuth()
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    if google_client_id and google_client_secret:
        oauth.register(
            name="google",
            client_id=google_client_id,
            client_secret=google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


class UERGateway:
    """Unified Event Report Gateway"""
    
    def __init__(self, gc_client, pr_client):
        self.gc_client = gc_client  # Global Credibility client
        self.pr_client = pr_client  # Priority Reporter client
        self.received_count = 0
        self.error_count = 0
    
    async def receive_uer(self, uer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Receive and process a UER"""
        try:
            # Validate UER
            uer = UnifiedEventReport(**uer_data)
            
            # Forward to Global Credibility module
            result = await self.gc_client.process_uer(uer)
            
            self.received_count += 1
            logger.info(f"Processed UER {uer.event_id} from agent {uer.agent_id}")
            
            return {
                "status": "success",
                "event_id": uer.event_id,
                "processing_result": result
            }
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to process UER: {e}")
            raise HTTPException(status_code=400, detail=str(e))


# Global gateway instance (would be initialized properly in production)
gateway = None


@app.post("/api/v1/uer/receive")
async def receive_unified_event_report(
    uer_data: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """Receive UER from Edge Agent"""
    if not gateway:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    
    return await gateway.receive_uer(uer_data)


@app.get("/api/v1/uer/stats")
async def get_gateway_stats():
    """Get gateway statistics"""
    if not gateway:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    
    return {
        "received_count": gateway.received_count,
        "error_count": gateway.error_count
    }


def create_gateway(gc_client, pr_client) -> UERGateway:
    """Create and initialize gateway"""
    global gateway
    gateway = UERGateway(gc_client, pr_client)
    return gateway


def start_server(host: str = "0.0.0.0", port: int = 9092):
    """Start UER Gateway server"""
    init_db()
    uvicorn.run(app, host=host, port=port)


# Basic UI endpoints (optional) -------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root_page():
    """Landing dashboard (dark, product-grade styling)"""
    return """
    <html>
      <head>
        <title>CoMIDF UER Gateway</title>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <style>
          :root { --bg:#0b1220; --panel:#111827; --panel-border:#1f2937; --text:#e5e7eb; --muted:#9ca3af; --primary:#06b6d4; --accent:#7c3aed; }
          *{box-sizing:border-box}
          body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial}
          .container{max-width:1040px;margin:0 auto;padding:24px}
          .header{display:flex;align-items:center;justify-content:space-between;padding:16px 0}
          .brand{display:flex;align-items:center;gap:12px;font-weight:600}
          .logo{width:28px;height:28px;border-radius:6px;background:linear-gradient(135deg,var(--primary),var(--accent));box-shadow:0 6px 24px rgba(124,58,237,.35)}
          .nav a{color:var(--muted);text-decoration:none;margin-left:16px;font-size:14px}
          .hero{margin-top:12px;display:grid;grid-template-columns:1.2fr .8fr;gap:24px;align-items:stretch}
          .card{background:var(--panel);border:1px solid var(--panel-border);border-radius:14px;padding:24px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
          .card h2{margin:0 0 10px 0;font-size:22px}
          .card p{color:var(--muted);line-height:1.6}
          .actions{margin-top:18px;display:flex;gap:12px;flex-wrap:wrap}
          .btn{appearance:none;border:none;text-decoration:none;cursor:pointer;padding:10px 16px;border-radius:10px;font-weight:600}
          .btn-primary{background:linear-gradient(135deg,var(--primary),#22d3ee);color:#051017;box-shadow:0 6px 20px rgba(34,211,238,.35)}
          .btn-outline{background:transparent;color:var(--text);border:1px solid var(--panel-border)}
          .kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
          .kpi{background:var(--panel);border:1px solid var(--panel-border);border-radius:14px;padding:18px}
          .kpi .label{color:var(--muted);font-size:12px;letter-spacing:.3px;text-transform:uppercase}
          .kpi .value{font-size:20px;font-weight:700;margin-top:6px}
          .foot{margin-top:28px;color:var(--muted);font-size:12px;text-align:center}
        </style>
      </head>
      <body>
        <div class=\"container\">\n          <div class=\"header\">\n            <div class=\"brand\"><div class=\"logo\"></div> CoMIDF Security</div>\n            <div class=\"nav\"><a href=\"/\">Portal</a><a href=\"/api/v1/uer/stats\" target=\"_blank\">Stats</a><a href=\"/healthz\" target=\"_blank\">Health</a><a href=\"/login\">Login</a></div>\n          </div>\n          <div class=\"hero\">\n            <div class=\"card\">\n              <h2>Unified Event Report Gateway</h2>\n              <p>安全加密的 UER 接入點，整合 GC / CTI / LLM 與優先級決策，適用 MSSP/SaaS 多租戶環境。</p>\n              <div class=\"actions\">\n                <a class=\"btn btn-primary\" href=\"/login\">進入管理入口</a>\n                <a class=\"btn btn-outline\" href=\"/api/v1/uer/stats\" target=\"_blank\">查看即時統計</a>\n              </div>\n            </div>\n            <div class=\"kpis\">\n              <div class=\"kpi\"><div class=\"label\">TLS</div><div class=\"value\">Enabled</div></div>\n              <div class=\"kpi\"><div class=\"label\">Mode</div><div class=\"value\">SaaS/MSSP</div></div>\n              <div class=\"kpi\"><div class=\"label\">Health</div><div class=\"value\">OK</div></div>\n            </div>\n          </div>\n          <div class=\"foot\">© CoMIDF Security Platform</div>\n        </div>
      </body>
    </html>
    """


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Login UI"""
    return """
    <html>
      <head>
        <title>登入 - CoMIDF</title>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <style>
          :root { --bg:#0b1220; --panel:#111827; --panel-border:#1f2937; --text:#e5e7eb; --muted:#9ca3af; --primary:#06b6d4; }
          body { margin:0; background:var(--bg); color:var(--text); font-family: Inter, ui-sans-serif, system-ui; }
          .wrap { min-height:100vh; display:flex; align-items:center; justify-content:center; padding: 24px; }
          .card { width:100%; max-width:440px; background:var(--panel); border:1px solid var(--panel-border); border-radius:14px; padding:28px; box-shadow:0 10px 30px rgba(0,0,0,.25); }
          h3 { margin:0 0 8px 0; }
          label { font-size:13px; color:var(--muted); }
          input { width:100%; padding:12px 14px; margin:8px 0 14px 0; border-radius:10px; border:1px solid var(--panel-border); background:#0f172a; color:var(--text); }
          button, .btn { width:100%; padding:12px 14px; border-radius:10px; background:linear-gradient(135deg,var(--primary),#22d3ee); color:#051017; border:none; cursor:pointer; font-weight:600; }
          .hint { color:var(--muted); font-size:12px; margin-top:8px; }
          .minor { margin-top:12px; font-size:13px; color:var(--muted); }
          .oauth { margin-top:12px; }
          .oauth a { display:block; text-align:center; padding:10px 12px; border:1px solid var(--panel-border); border-radius:10px; color:var(--text); text-decoration:none; }
        </style>
      </head>
      <body>
        <div class=\"wrap\"><div class=\"card\">\n          <h3>登入 CoMIDF</h3>\n          <form method=\"post\" action=\"/login\">\n            <label>Email</label>\n            <input type=\"email\" name=\"email\" placeholder=\"you@example.com\" required />\n            <label>密碼</label>\n            <input type=\"password\" name=\"password\" placeholder=\"••••••••\" required />\n            <button type=\"submit\">登入</button>\n            <p class=\"hint\">支援本地 Email / Google 登入。密碼經強雜湊保護。</p>\n          </form>
          <div class=\"minor\">還沒有帳號？<a href=\"/signup\">註冊</a></div>
          <div class=\"oauth\"><a href=\"/auth/google/login\">使用 Google 登入</a></div>
        </div></div>
      </body>
    </html>
    """


@app.post("/login")
async def login_action(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Local email login using hashed passwords"""
    ok = db_verify_user(db, email, password)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    u = db_get_user(db, email)
    request.session["user"] = {"email": email, "name": (u.name if u else email), "provider": "local"}
    return RedirectResponse(url="/", status_code=302)


@app.get("/signup", response_class=HTMLResponse)
async def signup_page():
    return """
    <html>
      <head>
        <title>註冊 - CoMIDF</title>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <style>
          :root { --bg:#0b1220; --panel:#111827; --panel-border:#1f2937; --text:#e5e7eb; --muted:#9ca3af; --primary:#06b6d4; }
          body { margin:0; background:var(--bg); color:var(--text); font-family: Inter, ui-sans-serif, system-ui; }
          .wrap { min-height:100vh; display:flex; align-items:center; justify-content:center; padding: 24px; }
          .card { width:100%; max-width:460px; background:var(--panel); border:1px solid var(--panel-border); border-radius:14px; padding:28px; box-shadow:0 10px 30px rgba(0,0,0,.25); }
          h3 { margin:0 0 8px 0; }
          label { font-size:13px; color:var(--muted); }
          input { width:100%; padding:12px 14px; margin:8px 0 14px 0; border-radius:10px; border:1px solid var(--panel-border); background:#0f172a; color:var(--text); }
          button { width:100%; padding:12px 14px; border-radius:10px; background:linear-gradient(135deg,var(--primary),#22d3ee); color:#051017; border:none; font-weight:600; cursor:pointer; }
          .hint { color:var(--muted); font-size:12px; margin-top:8px; }
        </style>
      </head>
      <body>
        <div class=\"wrap\"><div class=\"card\">\n          <h3>註冊帳號</h3>\n          <form method=\"post\" action=\"/signup\">\n            <label>Email</label>\n            <input type=\"email\" name=\"email\" placeholder=\"you@example.com\" required />\n            <label>名稱（可選）</label>\n            <input type=\"text\" name=\"name\" placeholder=\"Your Name\" />\n            <label>密碼</label>\n            <input type=\"password\" name=\"password\" required />\n            <label>確認密碼</label>\n            <input type=\"password\" name=\"password_confirm\" required />\n            <button type=\"submit\">建立帳號</button>\n            <p class=\"hint\">帳號使用 Email。密碼需 ≥12 字且至少 3 種類別（大小寫/數字/特殊）。</p>\n          </form>
        </div></div>
      </body>
    </html>
    """


@app.post("/signup")
async def signup_action(email: str = Form(...), password: str = Form(...), password_confirm: str = Form(...), name: str = Form(""), db: Session = Depends(get_db) ):
    if password != password_confirm:
        raise HTTPException(status_code=400, detail="Password mismatch")
    email_norm = email.strip().lower()
    if "@" not in email_norm or "." not in email_norm.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid email format")
    if not password_is_strong(password):
        raise HTTPException(status_code=400, detail="Weak password: min 12 chars and 3 of [lower/upper/digit/special]")
    ok = db_create_user(db, email_norm, password, name=name.strip() or None)
    if not ok:
        raise HTTPException(status_code=409, detail="Email already registered")
    return RedirectResponse(url="/login", status_code=302)


@app.get("/healthz")
async def health_check():
    """Health probe endpoint"""
    healthy = bool(gateway is not None)
    return JSONResponse({"status": "ok" if healthy else "init", "gateway_initialized": healthy})


# Google OAuth Endpoints --------------------------------------------------------

@app.get("/auth/google/login")
async def google_login(request: Request):
    if not (OAUTH_AVAILABLE and oauth):
        raise HTTPException(status_code=503, detail="Google OAuth not available")
    client = oauth.create_client("google") if oauth else None
    if client is None:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    redirect_uri = request.url_for("google_auth_callback")
    return await client.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def google_auth_callback(request: Request):
    if not (OAUTH_AVAILABLE and oauth):
        raise HTTPException(status_code=503, detail="Google OAuth not available")
    client = oauth.create_client("google") if oauth else None
    if client is None:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    try:
        token = await client.authorize_access_token(request)
        userinfo = token.get("userinfo")
        if not userinfo:
            # fetch userinfo if not returned in token
            resp = await client.get("userinfo", token=token)
            userinfo = resp.json()

        # Persist user session
        request.session["user"] = {
            "email": userinfo.get("email", ""),
            "name": userinfo.get("name", ""),
            "picture": userinfo.get("picture", ""),
            "provider": "google",
        }
        return RedirectResponse(url="/", status_code=302)
    except Exception as e:
        logger.error(f"Google OAuth failed: {e}")
        raise HTTPException(status_code=400, detail="Google OAuth failed")


@app.get("/me")
async def whoami(request: Request):
    user = request.session.get("user")
    if not user:
        return JSONResponse({"authenticated": False})
    return JSONResponse({"authenticated": True, "user": user})


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)

