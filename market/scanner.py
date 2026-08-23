"""
ماسح السوق — ranks the whole TASI universe with the strategy engine.

يجلب المؤشر العام مرة واحدة، ثم يحلّل كل سهم بنفس البوابات والدرجة
المستخدمة في صفحة السهم المفردة، ويقسّم النتائج إلى قوائم جاهزة للعرض:

* ``rising``      : مرشحة للصعود — اجتازت البوابات ودرجتها موجبة.
* ``falling``     : مرشحة للهبوط — درجتها سالبة واتجاهها هابط.
* ``losers``      : الأسهم الخاسرة فعليًا (أداء ضعيف قرب قاع السنة).
* ``gainers_today``/``losers_today`` : الأعلى ارتفاعًا/انخفاضًا في الجلسة.
* ``most_active`` : الأعلى قيمة تداول.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from . import analysis, providers
from . import symbols as sym

SCAN_TTL = 300  # ثوانٍ

_scan_cache: Dict[str, Any] = {}
_scan_lock = threading.Lock()

# عتبات إدراج السهم في القوائم — مشتقة من جدول التصنيف في وثيقة الاستراتيجية.
RISING_MIN_SCORE = 20.0
FALLING_MAX_SCORE = -20.0
LOSER_RANGE_POSITION = 25.0  # ضمن أدنى ٢٥٪ من نطاق ٥٢ أسبوعًا


def _row(report: Dict[str, Any]) -> Dict[str, Any]:
    """يختصر تقرير التحليل إلى صف جدول خفيف."""
    plan = report.get("plan") or {}
    triggered = [s["name"] for s in report.get("setups", []) if s["triggered"]]
    hit_vetoes = [v["name"] for v in report.get("vetoes", []) if v["hit"]]
    gates = {g["key"]: bool(g["passed"]) for g in report.get("gates", [])}
    passed_gates = sum(1 for value in gates.values() if value)

    return {
        "code": report.get("code"),
        "name_ar": report.get("name_ar"),
        "name_en": report.get("name_en"),
        "sector": report.get("sector"),
        "price": report.get("price"),
        "change_pct": report.get("change_pct"),
        "volume": report.get("volume"),
        "value_traded": report.get("value_traded"),
        "score": (report.get("score") or {}).get("total"),
        "signal": report.get("signal"),
        "trend": (report.get("trend") or {}).get("label"),
        "trend_state": (report.get("trend") or {}).get("state"),
        "rsi": (report.get("indicators") or {}).get("rsi"),
        "adx": (report.get("indicators") or {}).get("adx"),
        "atr_pct": (report.get("indicators") or {}).get("atr_pct"),
        "volume_ratio": (report.get("indicators") or {}).get("volume_ratio"),
        "week52_position": (report.get("week52") or {}).get("position_pct"),
        "setups": triggered,
        "vetoes": hit_vetoes,
        "gates": gates,
        "gates_passed": passed_gates,
        "all_gates_passed": bool(gates) and all(gates.values()),
        "entry": plan.get("entry"),
        "stop": plan.get("stop"),
        "target": (plan.get("targets") or [{}])[0].get("price"),
        "risk_reward": plan.get("risk_reward"),
        "shares": plan.get("shares"),
        "plan_ok": plan.get("acceptable"),
        "probability_up": (report.get("signal") or {}).get("probability_up"),
        "is_demo": report.get("is_demo"),
        "liquidity_ok": (report.get("liquidity") or {}).get("passed", False),
    }


def scan(
    profile_key: str = analysis.DEFAULT_PROFILE,
    capital: float = 100_000.0,
    risk_pct: float = 1.0,
    codes: Optional[List[str]] = None,
    limit: int = 12,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    يمسح السوق ويُعيد القوائم المرتّبة مع ملخّص حالة السوق.

    النتيجة تُخزَّن مؤقتًا حسب (النمط، الرموز) لأن المسح مكلف؛ أما حجم
    المركز فيُعاد حسابه دائمًا لأنه يعتمد على مدخلات المستخدم.
    """
    profile = analysis.get_profile(profile_key)
    universe = codes or sym.codes()
    cache_key = f"scan:{profile['key']}:{len(universe)}:{hash(tuple(universe))}"

    cached = None
    if use_cache:
        with _scan_lock:
            entry = _scan_cache.get(cache_key)
            if entry and entry["expires"] > time.time():
                cached = entry["value"]

    if cached is None:
        index_payload = providers.fetch_index(profile["timeframe"])
        payloads = providers.fetch_many(universe, profile["timeframe"])

        reports = []
        for code in universe:
            payload = payloads.get(code)
            if not payload:
                continue
            report = analysis.analyze(
                payload, index_payload, profile["key"],
                capital=capital, risk_pct=risk_pct, include_series=False,
            )
            if report.get("error"):
                continue
            reports.append(report)

        cached = {
            "reports": reports,
            "index": _index_summary(index_payload, profile["key"]),
            "scanned_at": int(time.time()),
            "is_demo": bool(index_payload and index_payload.get("is_demo")),
        }
        with _scan_lock:
            _scan_cache[cache_key] = {"value": cached, "expires": time.time() + SCAN_TTL}

    reports = cached["reports"]

    # إعادة حساب حجم المركز بمدخلات المستخدم الحالية (رخيص، بلا شبكة).
    rows = []
    for report in reports:
        row = _row(report)
        entry, stop = row.get("entry"), row.get("stop")
        if entry and stop and entry > stop and capital:
            risk_amount = capital * max(0.05, min(risk_pct, 5.0)) / 100.0
            row["shares"] = int(risk_amount / (entry - stop))
        rows.append(row)

    tradable = [r for r in rows if r["liquidity_ok"]]

    # «مرشحة للصعود» = اجتاز البوابات الخمس كلها بلا فيتو، لا مجرد درجة عالية.
    # قائمة تعرض صفقة عائدها/مخاطرتها ٠٫٧٨ تحت عنوان «شراء قوي» تكذب على المستخدم.
    rising = sorted(
        [
            r for r in tradable
            if r["all_gates_passed"]
            and (r["score"] or 0) >= RISING_MIN_SCORE
            and r["signal"]["side"] == "buy"
            and not r["vetoes"]
        ],
        key=lambda r: r["score"] or 0,
        reverse=True,
    )
    falling = sorted(
        [r for r in tradable if (r["score"] or 0) <= FALLING_MAX_SCORE],
        key=lambda r: r["score"] or 0,
    )
    losers = sorted(
        [
            r for r in tradable
            if r["trend_state"] == "down"
            and (r["week52_position"] is not None and r["week52_position"] <= LOSER_RANGE_POSITION)
        ],
        key=lambda r: r["week52_position"] or 0,
    )
    # «تحت المراقبة» = الدرجة إيجابية لكن بوابة سقطت أو تحقّق فيتو —
    # إشارة واعدة لم تنضج بعد، وليست دعوة للدخول.
    watchlist = sorted(
        [
            r for r in tradable
            if r["signal"]["side"] == "buy"
            and (r["score"] or 0) > 0
            and not (r["all_gates_passed"] and not r["vetoes"])
        ],
        key=lambda r: r["score"] or 0,
        reverse=True,
    )

    by_change = [r for r in rows if r["change_pct"] is not None]
    gainers_today = sorted(by_change, key=lambda r: r["change_pct"], reverse=True)
    losers_today = sorted(by_change, key=lambda r: r["change_pct"])
    most_active = sorted(
        [r for r in rows if r["value_traded"] is not None],
        key=lambda r: r["value_traded"],
        reverse=True,
    )

    advancers = sum(1 for r in by_change if r["change_pct"] > 0)
    decliners = sum(1 for r in by_change if r["change_pct"] < 0)

    return {
        "profile": {
            "key": profile["key"], "label": profile["label"],
            "icon": profile["icon"], "horizon": profile["horizon_label"],
        },
        "index": cached["index"],
        "scanned_at": cached["scanned_at"],
        "is_demo": cached["is_demo"] or any(r["is_demo"] for r in rows),
        "universe_size": len(universe),
        "analyzed": len(rows),
        "tradable": len(tradable),
        "breadth": {
            "tradable_setups": len(rising),
            "advancers": advancers,
            "decliners": decliners,
            "unchanged": len(by_change) - advancers - decliners,
            "buy_signals": sum(1 for r in rows if r["signal"]["side"] == "buy"),
            "sell_signals": sum(1 for r in rows if r["signal"]["side"] == "sell"),
            "avg_score": round(
                sum(r["score"] or 0 for r in rows) / len(rows), 1
            ) if rows else None,
        },
        "lists": {
            "rising": rising[:limit],
            "falling": falling[:limit],
            "losers": losers[:limit],
            "watchlist": watchlist[:limit],
            "gainers_today": gainers_today[:limit],
            "losers_today": losers_today[:limit],
            "most_active": most_active[:limit],
        },
        "sectors": _sector_breakdown(rows),
        "disclaimer": analysis.DISCLAIMER,
    }


def _index_summary(index_payload, profile_key: str) -> Dict[str, Any]:
    """ملخّص المؤشر العام مع حالة السوق."""
    regime = analysis.market_regime(index_payload, profile_key)
    if not index_payload or not index_payload.get("candles"):
        return {"available": False, "regime": regime}

    candles = index_payload["candles"]
    price = candles[-1]["c"]
    prev = index_payload.get("previous_close") or (candles[-2]["c"] if len(candles) > 1 else price)
    return {
        "available": True,
        "name": index_payload.get("name_ar"),
        "price": round(price, 2),
        "change": round(price - prev, 2),
        "change_pct": round((price - prev) / prev * 100.0, 2) if prev else 0.0,
        "is_demo": bool(index_payload.get("is_demo")),
        "regime": regime,
        "candles": candles[-120:],
    }


def _sector_breakdown(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """متوسط الدرجة والأداء لكل قطاع — لمعرفة أين يتحرك المال."""
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(row["sector"] or "غير مصنّف", []).append(row)

    out = []
    for sector, members in buckets.items():
        scores = [m["score"] for m in members if m["score"] is not None]
        changes = [m["change_pct"] for m in members if m["change_pct"] is not None]
        out.append({
            "sector": sector,
            "count": len(members),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
            "avg_change_pct": round(sum(changes) / len(changes), 2) if changes else None,
            "buy_signals": sum(1 for m in members if m["signal"]["side"] == "buy"),
        })
    return sorted(out, key=lambda s: s["avg_score"] if s["avg_score"] is not None else -999, reverse=True)


def clear_cache() -> None:
    with _scan_lock:
        _scan_cache.clear()
