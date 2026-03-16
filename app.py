import os
import secrets
import threading
import time
from datetime import datetime
from urllib.request import urlopen

from flask import Flask, render_template, request, g
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from data.content import FEATURE_CARDS, TRUST_NOTES
from data.morning_azkar import MORNING_AZKAR
from data.evening_azkar import EVENING_AZKAR
from data.post_salah_azkar import POST_SALAH_AZKAR
from data.tasabeeh import TASABEEH
from data.jawami_dua import JAWAMI_DUA
from data.prophet_duas import PROPHET_DUAS
from data.quran_duas import QURAN_DUAS
from data.prophets_quran_duas import PROPHETS_QURAN_DUAS
from data.laylat_alqadr import LAYLAT_ALQADR_DUAS

app = Flask(__name__)

# ── Core Security Config ──
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", secrets.token_hex(32)),
    SESSION_COOKIE_SECURE=os.environ.get("RENDER", False),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,  # 1 MB max request size
)

# ── Content Security Policy ──
csp = {
    "default-src": "'self'",
    "script-src": [
        "'self'",
        "cdn.jsdelivr.net",
    ],
    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "cdn.jsdelivr.net",
        "fonts.googleapis.com",
    ],
    "font-src": [
        "'self'",
        "fonts.gstatic.com",
        "cdn.jsdelivr.net",
    ],
    "img-src": "'self' data:",
    "connect-src": "'self'",
    "frame-src": "'none'",
    "object-src": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
}

# ── Talisman — Security Headers ──
talisman = Talisman(
    app,
    content_security_policy=csp,
    content_security_policy_nonce_in=["script-src"],
    force_https=os.environ.get("RENDER", False),  # Auto-True on Render
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    strict_transport_security_include_subdomains=True,
    session_cookie_secure=not app.debug,
    frame_options="DENY",
    x_content_type_options=True,
    x_xss_protection=True,
    referrer_policy="strict-origin-when-cross-origin",
    permissions_policy={
        "camera": "()",
        "microphone": "()",
        "geolocation": "(self)",
        "payment": "()",
    },
)

# ── Rate Limiting ──
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per minute", "5000 per hour"],
    storage_uri="memory://",
)


# ── Nonce for inline scripts ──
@app.context_processor
def inject_globals():
    return {
        "current_year": datetime.now().year,
        "csp_nonce": getattr(g, "_csp_nonce", ""),
    }


@app.after_request
def add_security_headers(response):
    # Cache control for static assets
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

    # Extra hardening headers
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    return response


# ── Error Handlers (no info leaks) ──
@app.errorhandler(404)
def page_not_found(_):
    return render_template("404.html"), 404


@app.errorhandler(429)
def rate_limit_exceeded(_):
    return render_template("404.html"), 429


@app.errorhandler(500)
def internal_error(_):
    return render_template("404.html"), 500


@app.route("/")
@limiter.limit("60 per minute")
def home():
    return render_template("home.html", feature_cards=FEATURE_CARDS, trust_notes=TRUST_NOTES)


@app.route("/azkar/morning")
def azkar_morning():
    return render_template("azkar_morning.html", items=MORNING_AZKAR)


@app.route("/azkar/evening")
def azkar_evening():
    return render_template("azkar_evening.html", items=EVENING_AZKAR)


@app.route("/azkar/post-salah")
def azkar_post_salah():
    return render_template(
        "azkar_page.html",
        title="أذكار بعد الصلاة",
        items=POST_SALAH_AZKAR,
        storage_key="azkar_post_salah_v1",
    )


@app.route("/azkar/tasabeeh")
def azkar_tasabeeh():
    return render_template(
        "azkar_page.html",
        title="تسابيح وأذكار عظيمة",
        items=TASABEEH,
        storage_key="azkar_tasabeeh_v1",
    )


@app.route("/azkar/jawami")
def azkar_jawami():
    return render_template(
        "azkar_page.html",
        title="جوامع الدعاء",
        items=JAWAMI_DUA,
        storage_key="azkar_jawami_v1",
    )


@app.route("/azkar/prophet-duas")
def azkar_prophet_duas():
    return render_template(
        "azkar_page.html",
        title="أدعية النبي صلى الله عليه وسلم",
        items=PROPHET_DUAS,
        storage_key="azkar_prophet_duas_v1",
    )


@app.route("/azkar/quran-duas")
def azkar_quran_duas():
    return render_template(
        "azkar_page.html",
        title="الأدعية القرآنية",
        items=QURAN_DUAS,
        storage_key="azkar_quran_duas_v1",
    )


@app.route("/azkar/prophets-quran")
def azkar_prophets_quran():
    return render_template(
        "azkar_page.html",
        title="أدعية الأنبياء من القرآن الكريم",
        items=PROPHETS_QURAN_DUAS,
        storage_key="azkar_prophets_quran_v1",
    )


@app.route("/azkar/laylat-alqadr")
def azkar_laylat_alqadr():
    return render_template(
        "azkar_page.html",
        title="دعاء ليلة القدر",
        items=LAYLAT_ALQADR_DUAS,
        storage_key="azkar_laylat_alqadr_v1",
    )


@app.route("/tasbeeh")
def tasbeeh():
    return render_template("tasbeeh.html")


@app.route("/qibla")
def qibla():
    return render_template("qibla.html")


@app.route("/health")
def health():
    return "OK", 200


def keep_alive():
    """Ping the app every 10 minutes to prevent Render free-tier sleep."""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    url = f"{url}/health"
    while True:
        time.sleep(600)  # 10 minutes
        try:
            urlopen(url, timeout=10)
        except Exception:
            pass


if os.environ.get("RENDER"):
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()


if __name__ == "__main__":
    app.run(debug=True)
