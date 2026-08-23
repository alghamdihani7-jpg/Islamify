"""
واجهات التطبيق — Flask blueprint for the TASI analysis module.

الصفحات:
    ``/market``           لوحة السوق (المؤشر، القوائم المرشحة، القطاعات).
    ``/market/<code>``    صفحة تحليل السهم مع الشارت والخطة.

الواجهات البرمجية (JSON):
    ``/api/market/profiles``       أنماط التداول المتاحة.
    ``/api/market/overview``       المؤشر العام وحالة السوق.
    ``/api/market/scan``           مسح السوق وترتيب الأسهم.
    ``/api/market/symbol/<code>``  تحليل كامل لسهم واحد.
    ``/api/market/search``         بحث بالرمز أو الاسم.
"""

from __future__ import annotations

from typing import Tuple

from flask import Blueprint, jsonify, render_template, request

from . import analysis, providers, scanner
from . import symbols as sym

market_bp = Blueprint("market", __name__)

DEFAULT_CAPITAL = 100_000.0
DEFAULT_RISK_PCT = 1.0
MAX_SCAN_LIMIT = 30


def _float_arg(name: str, default: float, low: float, high: float) -> float:
    """يقرأ رقمًا من الاستعلام ضمن حدود آمنة."""
    try:
        value = float(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    if value != value or value in (float("inf"), float("-inf")):  # NaN / inf
        return default
    return max(low, min(value, high))


def _int_arg(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(low, min(value, high))


def _user_inputs() -> Tuple[str, float, float]:
    profile = request.args.get("profile") or analysis.DEFAULT_PROFILE
    if profile not in analysis.PROFILES:
        profile = analysis.DEFAULT_PROFILE
    capital = _float_arg("capital", DEFAULT_CAPITAL, 1_000.0, 1_000_000_000.0)
    risk = _float_arg("risk", DEFAULT_RISK_PCT, 0.05, 5.0)
    return profile, capital, risk


# ─────────────────────────── الصفحات ───────────────────────────


@market_bp.route("/market")
def market_dashboard():
    profile_key, capital, risk = _user_inputs()
    return render_template(
        "market/dashboard.html",
        profiles=analysis.PROFILES,
        active_profile=profile_key,
        capital=capital,
        risk_pct=risk,
        sectors=sym.SECTORS,
        disclaimer=analysis.DISCLAIMER,
    )


@market_bp.route("/market/<code>")
def market_symbol(code: str):
    normalized = sym.normalize_code(code)
    if not normalized:
        return render_template("404.html"), 404

    profile_key, capital, risk = _user_inputs()
    info = sym.get(normalized) or {}
    return render_template(
        "market/symbol.html",
        code=normalized,
        info=info,
        profiles=analysis.PROFILES,
        active_profile=profile_key,
        timeframes=providers.TIMEFRAMES,
        capital=capital,
        risk_pct=risk,
        disclaimer=analysis.DISCLAIMER,
    )


# ─────────────────────────── الواجهات البرمجية ───────────────────────────


@market_bp.route("/api/market/profiles")
def api_profiles():
    return jsonify({
        "profiles": [
            {
                "key": p["key"], "label": p["label"], "icon": p["icon"],
                "horizon": p["horizon_label"], "timeframe": p["timeframe"],
                "min_rr": p["min_rr"], "max_stop_pct": p["max_stop_pct"],
                "adx_min": p["adx_min"], "vol_breakout_mult": p["vol_breakout_mult"],
                "emas": [p["ema_fast"], p["ema_mid"], p["ema_slow"]],
            }
            for p in analysis.PROFILES.values()
        ],
        "default": analysis.DEFAULT_PROFILE,
        "timeframes": providers.TIMEFRAMES,
        "weights": analysis.WEIGHTS,
    })


@market_bp.route("/api/market/overview")
def api_overview():
    profile_key, _, _ = _user_inputs()
    profile = analysis.get_profile(profile_key)
    index_payload = providers.fetch_index(profile["timeframe"])
    regime = analysis.market_regime(index_payload, profile_key)

    candles = (index_payload or {}).get("candles") or []
    price = candles[-1]["c"] if candles else None
    prev = (index_payload or {}).get("previous_close") or (
        candles[-2]["c"] if len(candles) > 1 else price
    )

    return jsonify({
        "index": {
            "name": (index_payload or {}).get("name_ar"),
            "price": round(price, 2) if price else None,
            "change": round(price - prev, 2) if price and prev else None,
            "change_pct": round((price - prev) / prev * 100.0, 2) if price and prev else None,
            "candles": candles[-140:],
            "is_demo": bool((index_payload or {}).get("is_demo")),
        },
        "regime": regime,
        "network": providers.network_status(),
        "disclaimer": analysis.DISCLAIMER,
    })


@market_bp.route("/api/market/scan")
def api_scan():
    profile_key, capital, risk = _user_inputs()
    limit = _int_arg("limit", 12, 3, MAX_SCAN_LIMIT)

    sector = request.args.get("sector")
    codes = None
    if sector and sector in sym.SECTORS:
        codes = [row["code"] for row in sym.by_sector(sector)]

    result = scanner.scan(
        profile_key=profile_key, capital=capital, risk_pct=risk,
        codes=codes, limit=limit,
    )
    result["network"] = providers.network_status()
    result["filter_sector"] = sector if codes else None
    return jsonify(result)


@market_bp.route("/api/market/symbol/<code>")
def api_symbol(code: str):
    normalized = sym.normalize_code(code)
    if not normalized:
        return jsonify({"error": "رمز غير صالح — يجب أن يكون أربعة أرقام."}), 400

    profile_key, capital, risk = _user_inputs()
    profile = analysis.get_profile(profile_key)
    timeframe = request.args.get("timeframe") or profile["timeframe"]
    if timeframe not in providers.TIMEFRAMES:
        timeframe = profile["timeframe"]

    payload = providers.fetch_ohlcv(normalized, timeframe)
    if not payload:
        return jsonify({"error": "تعذّر جلب بيانات هذا الرمز."}), 404

    index_payload = providers.fetch_index(timeframe)
    report = analysis.analyze(
        payload, index_payload, profile_key, capital=capital, risk_pct=risk,
    )
    report["network"] = providers.network_status()
    report["available_timeframes"] = providers.TIMEFRAMES
    return jsonify(report)


@market_bp.route("/api/market/search")
def api_search():
    query = request.args.get("q", "")
    return jsonify({"results": sym.search(query, limit=12)})
