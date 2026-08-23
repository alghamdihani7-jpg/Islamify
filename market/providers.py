"""
مزوّد بيانات السوق — market data access layer.

المصدر الأساسي هو واجهة الرسوم البيانية العامة من Yahoo Finance، وهي
تغطي أسهم السوق السعودي (تداول) باللاحقة ``.SR`` ولا تحتاج مفتاحًا.

* ``fetch_ohlcv("2222")``  → شموع أرامكو السعودية.
* ``fetch_index()``        → شموع المؤشر العام (تاسي).

إذا تعذّر الوصول للشبكة (بيئة مغلقة، أو ``MARKET_OFFLINE=1``) يتحوّل
المزوّد إلى **وضع تجريبي** يولّد بيانات اصطناعية ثابتة لكل رمز، ويضع
العلم ``is_demo=True`` كي تعرض الواجهة تنبيهًا صريحًا بأن الأرقام ليست
حقيقية. لا يُخلط الوضعان أبدًا بصمت.
"""

from __future__ import annotations

import math
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import requests

from . import symbols as sym

# ─────────────────────────── الإعدادات ───────────────────────────

PROVIDER_HOSTS = [
    os.environ.get("MARKET_PROVIDER_HOST", "query1.finance.yahoo.com"),
    "query2.finance.yahoo.com",
]
USER_AGENT = os.environ.get(
    "MARKET_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
)
REQUEST_TIMEOUT = float(os.environ.get("MARKET_TIMEOUT", "12"))
MAX_WORKERS = int(os.environ.get("MARKET_MAX_WORKERS", "8"))

# مدد التخزين المؤقت بالثواني — أقصر للأطر الزمنية القصيرة.
CACHE_TTL = {
    "intraday": int(os.environ.get("MARKET_TTL_INTRADAY", "180")),
    "daily": int(os.environ.get("MARKET_TTL_DAILY", "900")),
}

# الأطر الزمنية المدعومة في الواجهة: المفتاح -> (range, interval, تسمية)
TIMEFRAMES: Dict[str, Dict[str, str]] = {
    "1d":  {"range": "1d",  "interval": "5m",  "label": "يوم",     "kind": "intraday"},
    "5d":  {"range": "5d",  "interval": "30m", "label": "5 أيام",  "kind": "intraday"},
    "1mo": {"range": "1mo", "interval": "1d",  "label": "شهر",     "kind": "daily"},
    "3mo": {"range": "3mo", "interval": "1d",  "label": "3 أشهر",  "kind": "daily"},
    "6mo": {"range": "6mo", "interval": "1d",  "label": "6 أشهر",  "kind": "daily"},
    "1y":  {"range": "1y",  "interval": "1d",  "label": "سنة",     "kind": "daily"},
    "2y":  {"range": "2y",  "interval": "1wk", "label": "سنتان",   "kind": "daily"},
    "5y":  {"range": "5y",  "interval": "1wk", "label": "5 سنوات", "kind": "daily"},
}
DEFAULT_TIMEFRAME = "6mo"

_OFFLINE_ENV = os.environ.get("MARKET_OFFLINE", "").strip().lower() in ("1", "true", "yes")

# ─────────────────────────── التخزين المؤقت ───────────────────────────

_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()

# حالة الشبكة: إذا فشل الاتصال نتوقف عن المحاولة لفترة قصيرة بدل إبطاء كل طلب.
_network_state = {"failed_until": 0.0, "last_error": ""}


def _cache_get(key: str) -> Optional[Any]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry and entry["expires"] > time.time():
            return entry["value"]
        if entry:
            _cache.pop(key, None)
    return None


def _cache_set(key: str, value: Any, ttl: int) -> None:
    with _cache_lock:
        _cache[key] = {"value": value, "expires": time.time() + ttl}
        # حد أعلى بسيط لحجم الذاكرة المؤقتة.
        if len(_cache) > 800:
            now = time.time()
            for k in [k for k, v in _cache.items() if v["expires"] <= now][:400]:
                _cache.pop(k, None)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def network_status() -> Dict[str, Any]:
    """حالة الاتصال بمزوّد البيانات كما تُعرض في الواجهة."""
    offline = _OFFLINE_ENV or _network_state["failed_until"] > time.time()
    return {
        "offline": offline,
        "forced_offline": _OFFLINE_ENV,
        "last_error": _network_state["last_error"],
    }


# ─────────────────────────── الجلب الفعلي ───────────────────────────

_session_local = threading.local()


def _session() -> requests.Session:
    session = getattr(_session_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        _session_local.session = session
    return session


def _provider_symbol(code: str) -> str:
    """رمز تداول بصيغة المزوّد."""
    return code if code.startswith("^") else f"{code}.SR"


def _http_chart(provider_symbol: str, range_: str, interval: str) -> Optional[Dict[str, Any]]:
    """طلب الشموع من المزوّد؛ يُعيد ``None`` عند الفشل."""
    if _OFFLINE_ENV or _network_state["failed_until"] > time.time():
        return None

    params = {
        "range": range_,
        "interval": interval,
        "includePrePost": "false",
        "events": "div,split",
    }
    last_error = ""
    for host in PROVIDER_HOSTS:
        url = f"https://{host}/v8/finance/chart/{provider_symbol}"
        try:
            response = _session().get(url, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code == 404:
                return None  # رمز غير موجود لدى المزوّد — لا فائدة من إعادة المحاولة.
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue

    # فشل كل المضيفين — نعتبر الشبكة معطّلة لدقيقة.
    _network_state["failed_until"] = time.time() + 60
    _network_state["last_error"] = last_error
    return None


def _parse_chart(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """يحوّل استجابة المزوّد إلى شموع نظيفة."""
    try:
        result = payload["chart"]["result"][0]
        stamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError):
        return None

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    candles: List[Dict[str, float]] = []
    for i, ts in enumerate(stamps):
        try:
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            v = volumes[i]
        except IndexError:
            continue
        if None in (o, h, l, c):
            continue  # جلسة بلا تداول
        candles.append(
            {
                "t": int(ts),
                "o": float(o),
                "h": float(h),
                "l": float(l),
                "c": float(c),
                "v": float(v or 0),
            }
        )

    if len(candles) < 2:
        return None

    meta = result.get("meta", {}) or {}
    return {
        "candles": candles,
        "provider_name": meta.get("longName") or meta.get("shortName") or "",
        "currency": meta.get("currency") or "SAR",
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName") or "",
        "previous_close": meta.get("chartPreviousClose") or meta.get("previousClose"),
        "market_price": meta.get("regularMarketPrice"),
        "market_time": meta.get("regularMarketTime"),
    }


# ─────────────────────────── الوضع التجريبي ───────────────────────────


def _demo_candles(code: str, count: int, step_seconds: int) -> List[Dict[str, float]]:
    """
    مسار سعري اصطناعي ثابت لكل رمز.

    ليس توقعًا ولا بيانات سوق — الغرض منه فقط تشغيل الواجهة والاختبارات
    حين لا يتوفّر اتصال. البذرة مشتقّة من الرمز فيبقى الرسم ثابتًا.
    """
    rng = random.Random(int("".join(ch for ch in code if ch.isdigit()) or "1"))
    price = 15.0 + rng.random() * 120.0
    drift = (rng.random() - 0.45) * 0.0022
    vol = 0.010 + rng.random() * 0.014
    base_volume = 200_000 + rng.random() * 2_500_000

    # نبدأ من الماضي وننتهي عند آخر فترة مكتملة.
    end = int(time.time()) - (int(time.time()) % step_seconds)
    start = end - step_seconds * (count - 1)

    candles: List[Dict[str, float]] = []
    for i in range(count):
        # دورة بطيئة تعطي موجات صعود وهبوط بدل مسار عشوائي بحت.
        wave = math.sin(i / 22.0 + rng.random() * 0.01) * vol * 0.6
        shock = rng.gauss(0, vol)
        change = drift + wave * 0.35 + shock
        open_price = price
        close_price = max(0.5, price * (1 + change))
        span = abs(close_price - open_price) + price * vol * rng.uniform(0.2, 0.9)
        high = max(open_price, close_price) + span * rng.uniform(0.1, 0.6)
        low = max(0.4, min(open_price, close_price) - span * rng.uniform(0.1, 0.6))
        volume = base_volume * rng.uniform(0.4, 2.1) * (1 + abs(change) * 12)
        candles.append(
            {
                "t": start + i * step_seconds,
                "o": round(open_price, 2),
                "h": round(high, 2),
                "l": round(low, 2),
                "c": round(close_price, 2),
                "v": float(int(volume)),
            }
        )
        price = close_price
    return candles


_STEP_SECONDS = {
    "5m": 300, "15m": 900, "30m": 1800, "60m": 3600, "1h": 3600,
    "1d": 86400, "1wk": 604800, "1mo": 2592000,
}
_DEMO_COUNT = {"intraday": 78, "daily": 260}


def _demo_payload(code: str, timeframe: Dict[str, str]) -> Dict[str, Any]:
    step = _STEP_SECONDS.get(timeframe["interval"], 86400)
    count = _DEMO_COUNT["intraday" if timeframe["kind"] == "intraday" else "daily"]
    candles = _demo_candles(code, count, step)
    return {
        "candles": candles,
        "provider_name": "",
        "currency": "SAR",
        "exchange": "Saudi Exchange (وضع تجريبي)",
        "previous_close": candles[-2]["c"],
        "market_price": candles[-1]["c"],
        "market_time": candles[-1]["t"],
    }


# ─────────────────────────── الواجهة العامة ───────────────────────────


def resolve_timeframe(key: Optional[str]) -> Dict[str, str]:
    return TIMEFRAMES.get(key or DEFAULT_TIMEFRAME, TIMEFRAMES[DEFAULT_TIMEFRAME])


def fetch_ohlcv(code: str, timeframe: str = DEFAULT_TIMEFRAME) -> Optional[Dict[str, Any]]:
    """
    شموع سهم واحد مع بيانات وصفية.

    يُعيد ``None`` فقط إذا كان الرمز غير صالح؛ وإلا فإنه يُعيد بيانات
    حيّة أو — عند تعذّر الشبكة — بيانات تجريبية مُعلَّمة بـ ``is_demo``.
    """
    code = str(code).strip()
    if not (sym.is_valid_code(code) or code.startswith("^")):
        return None

    tf = resolve_timeframe(timeframe)
    cache_key = f"ohlcv:{code}:{tf['range']}:{tf['interval']}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    raw = _http_chart(_provider_symbol(code), tf["range"], tf["interval"])
    parsed = _parse_chart(raw) if raw else None
    is_demo = parsed is None

    if is_demo:
        parsed = _demo_payload(code, tf)

    info = sym.get(code) or {}
    payload = {
        "code": code,
        "name_ar": info.get("name_ar") or parsed["provider_name"] or code,
        "name_en": parsed["provider_name"] or info.get("name_en") or code,
        "sector": info.get("sector") or "غير مصنّف",
        "timeframe": timeframe if timeframe in TIMEFRAMES else DEFAULT_TIMEFRAME,
        "interval": tf["interval"],
        "is_demo": is_demo,
        "fetched_at": int(time.time()),
        **parsed,
    }

    ttl = CACHE_TTL["intraday" if tf["kind"] == "intraday" else "daily"]
    _cache_set(cache_key, payload, ttl if not is_demo else min(ttl, 120))
    return payload


def fetch_index(timeframe: str = DEFAULT_TIMEFRAME) -> Optional[Dict[str, Any]]:
    """شموع المؤشر العام (تاسي) — يجرّب صيغ الرمز المعروفة بالترتيب."""
    tf = resolve_timeframe(timeframe)
    cache_key = f"index:{tf['range']}:{tf['interval']}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    parsed = None
    for candidate in sym.INDEX_SYMBOL_CANDIDATES:
        raw = _http_chart(candidate, tf["range"], tf["interval"])
        parsed = _parse_chart(raw) if raw else None
        if parsed:
            break

    is_demo = parsed is None
    if is_demo:
        parsed = _demo_payload("9999", tf)

    payload = {
        "code": "TASI",
        "name_ar": sym.INDEX_NAME_AR,
        "name_en": sym.INDEX_NAME_EN,
        "sector": "مؤشر",
        "timeframe": timeframe if timeframe in TIMEFRAMES else DEFAULT_TIMEFRAME,
        "interval": tf["interval"],
        "is_demo": is_demo,
        "fetched_at": int(time.time()),
        **parsed,
    }
    ttl = CACHE_TTL["intraday" if tf["kind"] == "intraday" else "daily"]
    _cache_set(cache_key, payload, ttl if not is_demo else min(ttl, 120))
    return payload


def fetch_many(codes: List[str], timeframe: str = DEFAULT_TIMEFRAME) -> Dict[str, Dict[str, Any]]:
    """جلب متوازٍ لعدة أسهم — يتجاهل الرموز التي تفشل."""
    results: Dict[str, Dict[str, Any]] = {}
    if not codes:
        return results

    workers = max(1, min(MAX_WORKERS, len(codes)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for code, payload in zip(codes, pool.map(lambda c: fetch_ohlcv(c, timeframe), codes)):
            if payload:
                results[code] = payload
    return results
