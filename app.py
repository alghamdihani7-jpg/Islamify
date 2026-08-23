import os
import secrets
import threading
import time
from datetime import datetime
from urllib.request import urlopen

from flask import Flask, render_template, request, g, jsonify, session, redirect, url_for
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from data.content import FEATURE_CARDS, TRUST_NOTES, ARAFAT_DUAS
from data.morning_azkar import MORNING_AZKAR
from data.evening_azkar import EVENING_AZKAR
from data.post_salah_azkar import POST_SALAH_AZKAR
from data.tasabeeh import TASABEEH
from data.jawami_dua import JAWAMI_DUA
from data.prophet_duas import PROPHET_DUAS
from data.quran_duas import QURAN_DUAS
from data.prophets_quran_duas import PROPHETS_QURAN_DUAS
from data.laylat_alqadr import LAYLAT_ALQADR_DUAS
from data.night_prayer_duas import NIGHT_PRAYER_DUAS
from data.translations import get_text, get_all_languages, TRANSLATIONS
from auth_service import verify_credentials, generate_otp, store_otp, verify_otp as check_otp, send_otp_email, get_masked_email
from market.routes import market_bp

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
    "connect-src": "'self' https://api.aladhan.com https://nominatim.openstreetmap.org",
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


# ── قسم تحليل السوق السعودي (تاسي) ──
# المسح يجلب عشرات الرموز من مزوّد خارجي، فله حد أشد من بقية المسارات.
app.register_blueprint(market_bp)
limiter.limit("60 per minute")(app.view_functions["market.market_dashboard"])
limiter.limit("60 per minute")(app.view_functions["market.market_symbol"])
limiter.limit("20 per minute")(app.view_functions["market.api_scan"])
limiter.limit("60 per minute")(app.view_functions["market.api_symbol"])
limiter.limit("60 per minute")(app.view_functions["market.api_overview"])
limiter.limit("120 per minute")(app.view_functions["market.api_search"])


# ── Language Support ──
def get_current_language():
    """Get current language from cookie or request args, default to 'ar'"""
    lang = request.args.get("lang") or request.cookies.get("language", "ar")
    return lang if lang in TRANSLATIONS else "ar"


# ── Nonce for inline scripts ──
@app.context_processor
def inject_globals():
    current_lang = get_current_language()
    return {
        "current_year": datetime.now().year,
        "csp_nonce": getattr(g, "_csp_nonce", ""),
        "current_language": current_lang,
        "all_languages": TRANSLATIONS,
        "get_text": lambda key: get_text(key, current_lang),
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


@app.route("/azkar/arafah")
def azkar_arafah():
    return render_template(
        "azkar_page.html",
        title="دعاء يوم عرفة",
        items=ARAFAT_DUAS,
        storage_key="azkar_arafah_v1",
    )



@app.route("/azkar/night-prayer")
def azkar_night_prayer():
    return render_template(
        "azkar_page.html",
        title="دعاء قيام الليل",
        items=NIGHT_PRAYER_DUAS,
        storage_key="azkar_night_prayer_v1",
    )

@app.route("/prayer-times")
def prayer_times():
    return render_template("prayer_times.html")


@app.route("/tasbeeh")
def tasbeeh():
    return render_template("tasbeeh.html")


@app.route("/qibla")
def qibla():
    return render_template("qibla.html")


@app.route("/health")
def health():
    return "OK", 200


@app.route("/api/set-language/<language>")
def set_language(language):
    """Set user's language preference"""
    if language not in TRANSLATIONS:
        language = "ar"
    response = jsonify({"success": True, "language": language})
    response.set_cookie(
        "language",
        language,
        max_age=31536000,
        secure=True,
        httponly=True,
        samesite="Lax"
    )
    return response


# ── Dashboard Authentication ──

def is_logged_in():
    """Check if user is logged in"""
    return 'dashboard_user' in session


def login_required(f):
    """Decorator to require login"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for('dashboard_login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/dashboard/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def dashboard_login():
    """Dashboard login page"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if verify_credentials(username, password):
            # Generate and send OTP
            otp = generate_otp()
            store_otp("alghamdihani7@gmail.com", otp)
            send_otp_email("alghamdihani7@gmail.com", otp)

            # Store temp session data
            session['temp_username'] = username
            session['temp_email'] = "alghamdihani7@gmail.com"
            session.modified = True

            return redirect(url_for('verify_otp_page'))
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


@app.route("/dashboard/verify-otp", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def verify_otp_page():
    """OTP verification page"""
    if 'temp_username' not in session:
        return redirect(url_for('dashboard_login'))

    email = session.get('temp_email', '')
    masked_email = get_masked_email(email)

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()

        success, message = check_otp(email, otp)
        if success:
            # Set authenticated session
            username = session.pop('temp_username')
            session.pop('temp_email', None)
            session['dashboard_user'] = username
            session.modified = True

            return redirect(url_for('dashboard'))
        else:
            return render_template("otp_verify.html", masked_email=masked_email, error=message)

    return render_template("otp_verify.html", masked_email=masked_email)


@app.route("/dashboard/resend-otp")
@limiter.limit("5 per minute")
def resend_otp():
    """Resend OTP"""
    if 'temp_email' not in session:
        return redirect(url_for('dashboard_login'))

    email = session.get('temp_email', '')
    otp = generate_otp()
    store_otp(email, otp)
    send_otp_email(email, otp)

    masked_email = get_masked_email(email)
    return render_template("otp_verify.html", masked_email=masked_email, success_message="OTP resent successfully!")


@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard page"""
    username = session.get('dashboard_user', 'User')
    return render_template("dashboard.html", username=username)


@app.route("/dashboard/logout")
def logout():
    """Logout from dashboard"""
    session.pop('dashboard_user', None)
    session.modified = True
    return redirect(url_for('dashboard_login'))


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


def _lan_ip():
    """عنوان الجهاز على الشبكة المحلية — لطباعة رابط يعمل من الجوال."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # لا يُرسل أي شيء فعليًا؛ فقط يسأل النظام أي واجهة سيستخدم للخروج.
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


if __name__ == "__main__":
    # HOST=0.0.0.0 يجعل الخادم يستمع لكل واجهات الشبكة، فيصبح قابلًا
    # للفتح من الجوال عبر عنوان الكمبيوتر على شبكة الواي فاي.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))

    # مصحّح Werkzeug يسمح بتنفيذ كود عن بُعد، فلا يُفتح على الشبكة أبدًا.
    loopback = host in ("127.0.0.1", "localhost", "::1")
    debug = os.environ.get("FLASK_DEBUG", "1") == "1" and loopback

    if not loopback:
        ip = _lan_ip()
        print("\n" + "═" * 58)
        print("  الخادم يستمع لكل واجهات الشبكة (المصحّح مُعطَّل للأمان).")
        if ip:
            print(f"  من هذا الجهاز :  http://127.0.0.1:{port}/market")
            print(f"  من الجوال     :  http://{ip}:{port}/market")
            print("  اربط الجوال بنفس شبكة الواي فاي.")
        else:
            print(f"  تعذّر تحديد عنوان الشبكة — جرّب ipconfig أو ifconfig. المنفذ {port}.")
        print("═" * 58 + "\n")

    app.run(host=host, port=port, debug=debug)
