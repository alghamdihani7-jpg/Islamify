"""
محرّك الإشارات — the decision engine described in ``docs/STRATEGY.md``.

كل ثابت هنا يقابل رقمًا في وثيقة الاستراتيجية. تعديل السلوك يتم من
``PROFILES`` في الأعلى، لا من داخل الدوال.

التسلسل: خمس بوابات (سيولة ← حالة السوق ← اتجاه السهم ← إشارة دخول ←
مخاطرة مقبولة)، ثم درجة مركّبة من −١٠٠ إلى +١٠٠، ثم خطة تنفيذ كاملة
(دخول/وقف/أهداف/حجم مركز).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from . import indicators as ta

Num = Optional[float]


# ═══════════════════════ معاملات الأنماط الثلاثة ═══════════════════════

PROFILES: Dict[str, Dict[str, Any]] = {
    "intraday": {
        "key": "intraday",
        "label": "مضاربة يومية",
        "icon": "⚡",
        "timeframe": "5d",
        "horizon_bars": 12,
        "horizon_label": "خلال يوم إلى يومين",
        "ema_fast": 9, "ema_mid": 21, "ema_slow": 50,
        "rsi_period": 14, "atr_period": 14, "adx_period": 14,
        "adx_min": 22.0, "adx_veto": 18.0,
        "atr_stop_mult": 1.2, "atr_trail_mult": 1.8,
        "vol_breakout_mult": 1.8,
        "rsi_strong": (50.0, 72.0), "rsi_pullback": (42.0, 56.0),
        "rsi_veto": 82.0, "extension_veto_pct": 6.0,
        "min_rr": 1.5, "max_stop_pct": 3.0,
        "chase_limit_pct": 2.0, "min_headroom_pct": 1.2,
        "min_liquidity_sar": 5_000_000.0,
        "swing_span": 2,
    },
    "swing": {
        "key": "swing",
        "label": "مضاربة متأرجحة",
        "icon": "📈",
        "timeframe": "6mo",
        "horizon_bars": 20,
        "horizon_label": "خلال ٥ أيام إلى ٨ أسابيع",
        "ema_fast": 20, "ema_mid": 50, "ema_slow": 200,
        "rsi_period": 14, "atr_period": 14, "adx_period": 14,
        "adx_min": 20.0, "adx_veto": 15.0,
        "atr_stop_mult": 1.8, "atr_trail_mult": 2.5,
        "vol_breakout_mult": 1.5,
        "rsi_strong": (50.0, 70.0), "rsi_pullback": (40.0, 55.0),
        "rsi_veto": 80.0, "extension_veto_pct": 12.0,
        "min_rr": 1.8, "max_stop_pct": 8.0,
        "chase_limit_pct": 4.0, "min_headroom_pct": 2.0,
        "min_liquidity_sar": 2_000_000.0,
        "swing_span": 3,
    },
    "position": {
        "key": "position",
        "label": "استثمار طويل",
        "icon": "🏛",
        "timeframe": "5y",
        "horizon_bars": 13,
        "horizon_label": "خلال ٣ إلى ١٢ شهرًا",
        "ema_fast": 13, "ema_mid": 26, "ema_slow": 52,
        "rsi_period": 14, "atr_period": 14, "adx_period": 14,
        "adx_min": 18.0, "adx_veto": 12.0,
        "atr_stop_mult": 2.5, "atr_trail_mult": 3.5,
        "vol_breakout_mult": 1.3,
        "rsi_strong": (50.0, 72.0), "rsi_pullback": (38.0, 55.0),
        "rsi_veto": 85.0, "extension_veto_pct": 20.0,
        "min_rr": 2.5, "max_stop_pct": 15.0,
        "chase_limit_pct": 6.0, "min_headroom_pct": 3.0,
        "min_liquidity_sar": 1_000_000.0,
        "swing_span": 3,
    },
}
DEFAULT_PROFILE = "swing"

# أوزان الدرجة المركّبة (المجموع = ١٠٠) — القسم ٦ من وثيقة الاستراتيجية.
WEIGHTS = {
    "trend": 25.0,
    "relative_strength": 15.0,
    "momentum": 15.0,
    "trend_strength": 13.0,
    "rsi": 12.0,
    "liquidity_flow": 10.0,
    "structure": 10.0,
}

# حدود التصنيف النهائي.
SIGNAL_BANDS = [
    (45.0, "strong_buy", "شراء قوي", "🟢", "buy"),
    (20.0, "buy", "شراء", "🟩", "buy"),
    (-20.0, "neutral", "حياد / انتظار", "⬜", "hold"),
    (-45.0, "sell", "بيع / تخفيف", "🟧", "sell"),
    (-101.0, "strong_sell", "بيع قوي", "🔴", "sell"),
]

NEGATIVE_REGIME_HAIRCUT = 2.0 / 3.0   # خصم الثلث عند سوق سلبي
VETO_SCORE_CAP = 15.0                 # سقف الدرجة عند وجود فيتو
LIQUIDITY_LOOKBACK = 20
MIN_CANDLES = 60
MAX_DEAD_SESSIONS = 3

DISCLAIMER = (
    "هذا تحليل فني آلي لأغراض تعليمية ولا يُعد توصية استثمارية أو حكمًا شرعيًا. "
    "قرار الشراء أو البيع مسؤوليتك وحدك، ولا توجد استراتيجية تضمن الربح."
)


def get_profile(key: Optional[str]) -> Dict[str, Any]:
    return PROFILES.get(key or DEFAULT_PROFILE, PROFILES[DEFAULT_PROFILE])


# ═══════════════════════ أدوات صغيرة ═══════════════════════


def _clamp(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _interp(x: float, anchors: Sequence[tuple]) -> float:
    """استيفاء خطي بين نقاط مرتّبة — يُستخدم لتحويل RSI إلى درجة."""
    if x <= anchors[0][0]:
        return anchors[0][1]
    if x >= anchors[-1][0]:
        return anchors[-1][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y1
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return 0.0


def _round(value: Num, digits: int = 2) -> Num:
    return None if value is None else round(float(value), digits)


# ═══════════════════════ حالة السوق (البوابة ②) ═══════════════════════


def market_regime(index_payload: Optional[Dict[str, Any]], profile_key: str = DEFAULT_PROFILE) -> Dict[str, Any]:
    """
    يصنّف حالة تاسي إلى إيجابية / محايدة / سلبية.

    تُستخدم النتيجة لتقييد إشارات الشراء وتقليص أحجام المراكز.
    """
    unknown = {
        "state": "unknown",
        "label": "غير معروفة",
        "icon": "❔",
        "allow_buy": True,
        "size_factor": 1.0,
        "note": "تعذّر تحديد حالة المؤشر العام — تعامل بحذر إضافي.",
    }
    if not index_payload or not index_payload.get("candles"):
        return unknown

    profile = get_profile(profile_key)
    closes = [c["c"] for c in index_payload["candles"]]
    if len(closes) < profile["ema_mid"] + 5:
        return unknown

    ema_mid = ta.last_valid(ta.ema(closes, profile["ema_mid"]))
    ema_slow = ta.last_valid(ta.ema(closes, profile["ema_slow"]))
    price = closes[-1]
    highs = [c["h"] for c in index_payload["candles"]]
    lows = [c["l"] for c in index_payload["candles"]]
    adx_now = ta.last_valid(ta.adx(highs, lows, closes, profile["adx_period"])["adx"]) or 0.0

    if ema_mid is None:
        return unknown

    above_mid = price > ema_mid
    stacked_up = ema_slow is not None and ema_mid > ema_slow
    stacked_down = ema_slow is not None and ema_mid < ema_slow

    if above_mid and (stacked_up or ema_slow is None) and adx_now >= 18:
        return {
            "state": "positive", "label": "إيجابية", "icon": "🟢",
            "allow_buy": True, "size_factor": 1.0,
            "note": "تاسي فوق متوسطه — إشارات الشراء مفعّلة بالكامل.",
            "price": price, "ema_mid": ema_mid, "ema_slow": ema_slow, "adx": adx_now,
        }
    if (not above_mid) and stacked_down:
        return {
            "state": "negative", "label": "سلبية", "icon": "🔴",
            "allow_buy": False, "size_factor": 0.0,
            "note": "تاسي تحت متوسطه والمتوسطات هابطة — لا صفقات شراء جديدة.",
            "price": price, "ema_mid": ema_mid, "ema_slow": ema_slow, "adx": adx_now,
        }
    return {
        "state": "neutral", "label": "محايدة", "icon": "🟡",
        "allow_buy": True, "size_factor": 0.5,
        "note": "سوق متذبذب — نصف حجم المركز وأفضل الإشارات فقط.",
        "price": price, "ema_mid": ema_mid, "ema_slow": ema_slow, "adx": adx_now,
    }


# ═══════════════════════ التحليل الكامل ═══════════════════════


def analyze(
    payload: Dict[str, Any],
    index_payload: Optional[Dict[str, Any]] = None,
    profile_key: str = DEFAULT_PROFILE,
    capital: float = 100_000.0,
    risk_pct: float = 1.0,
    include_series: bool = True,
) -> Dict[str, Any]:
    """
    يحلّل سهمًا واحدًا ويُعيد تقريرًا كاملًا: بوابات، درجة، إشارة، خطة.

    ``payload`` من ``providers.fetch_ohlcv``؛ ``index_payload`` من
    ``providers.fetch_index`` (اختياري لكنه مطلوب للبوابة ② والقوة النسبية).
    """
    profile = get_profile(profile_key)
    candles = payload.get("candles") or []

    if len(candles) < 20:
        return _insufficient(payload, profile, "عدد الشموع المتاحة غير كافٍ للتحليل.")

    opens = [c["o"] for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    closes = [c["c"] for c in candles]
    volumes = [c["v"] for c in candles]

    price = closes[-1]
    prev_close = payload.get("previous_close") or (closes[-2] if len(closes) > 1 else price)
    change = price - prev_close
    change_pct = (change / prev_close * 100.0) if prev_close else 0.0

    # ── المؤشرات ──
    ema_fast = ta.ema(closes, profile["ema_fast"])
    ema_mid = ta.ema(closes, profile["ema_mid"])
    ema_slow = ta.ema(closes, profile["ema_slow"])
    rsi_series = ta.rsi(closes, profile["rsi_period"])
    macd_pack = ta.macd(closes)
    atr_series = ta.atr(highs, lows, closes, profile["atr_period"])
    adx_pack = ta.adx(highs, lows, closes, profile["adx_period"])
    bb = ta.bollinger(closes, 20, 2.0)
    stoch = ta.stochastic(highs, lows, closes)
    obv_series = ta.obv(closes, volumes)
    vol_ma = ta.sma(volumes, LIQUIDITY_LOOKBACK)

    ind = {
        "ema_fast": ta.last_valid(ema_fast),
        "ema_mid": ta.last_valid(ema_mid),
        "ema_slow": ta.last_valid(ema_slow),
        "rsi": ta.last_valid(rsi_series),
        "macd": ta.last_valid(macd_pack["macd"]),
        "macd_signal": ta.last_valid(macd_pack["signal"]),
        "macd_hist": ta.last_valid(macd_pack["hist"]),
        "atr": ta.last_valid(atr_series),
        "adx": ta.last_valid(adx_pack["adx"]),
        "plus_di": ta.last_valid(adx_pack["plus_di"]),
        "minus_di": ta.last_valid(adx_pack["minus_di"]),
        "bb_upper": ta.last_valid(bb["upper"]),
        "bb_lower": ta.last_valid(bb["lower"]),
        "bb_width": ta.last_valid(bb["width"]),
        "stoch_k": ta.last_valid(stoch["k"]),
        "stoch_d": ta.last_valid(stoch["d"]),
        "volume": volumes[-1],
        "volume_ma": ta.last_valid(vol_ma),
        "volatility": ta.historical_volatility(closes, 20),
    }
    ind["atr_pct"] = (ind["atr"] / price * 100.0) if ind["atr"] and price else None
    ind["volume_ratio"] = (
        volumes[-1] / ind["volume_ma"] if ind["volume_ma"] else None
    )
    ind["obv_slope"] = ta.slope(obv_series, 20)
    ind["ema_fast_slope"] = ta.slope(ema_fast, 10)
    ind["distance_from_fast_pct"] = (
        (price - ind["ema_fast"]) / ind["ema_fast"] * 100.0 if ind["ema_fast"] else None
    )

    # ── البنية السعرية ──
    span = profile["swing_span"]
    swings = ta.swing_points(highs, lows, span)
    levels = ta.support_resistance(highs, lows, closes, span)
    last_index = len(closes) - 1
    down_line = ta.trendline(swings["tops"], last_index)
    up_line = ta.trendline(swings["bottoms"], last_index)
    rng = ta.range_position(closes, 252)
    divergence = ta.rsi_divergence(closes, rsi_series)

    # ── البوابات ──
    liquidity = _gate_liquidity(closes, volumes, profile)
    regime = market_regime(index_payload, profile["key"])
    trend = _classify_trend(price, ind, profile)
    setups = _detect_setups(
        closes, highs, lows, volumes, opens, ind, levels, down_line, up_line,
        rsi_series, ema_fast, ema_mid, ema_slow, profile, trend,
    )
    confirmations = _confirmations(ind, macd_pack, closes, index_payload, rng, profile)
    vetoes = _vetoes(ind, price, divergence, levels, regime, profile)

    # ── الدرجة المركّبة ──
    components = _score_components(
        price, ind, closes, index_payload, rng, down_line, up_line, levels,
        macd_pack, trend, profile,
    )
    raw_total = sum(c["contribution"] for c in components)

    total = raw_total
    adjustments: List[str] = []
    if regime["state"] == "negative" and total > 0:
        total *= NEGATIVE_REGIME_HAIRCUT
        adjustments.append("خُصم الثلث من الدرجة لأن حالة السوق العامة سلبية.")
    hit_vetoes = [v for v in vetoes if v["hit"]]
    if hit_vetoes and total > VETO_SCORE_CAP:
        total = VETO_SCORE_CAP
        adjustments.append("سُقفت الدرجة عند ١٥ بسبب تحقق فيتو واحد على الأقل.")
    total = _clamp(total)

    signal = _classify_signal(total)
    probability_up = 1.0 / (1.0 + math.exp(-total / 28.0)) * 100.0

    # ── خطة التنفيذ ──
    plan = build_plan(
        price=price, ind=ind, lows=lows, levels=levels, profile=profile,
        regime=regime, capital=capital, risk_pct=risk_pct,
    )

    gates = _gates_summary(liquidity, regime, trend, setups, plan, profile, signal)
    forecast = _forecast(price, ind["atr"], profile)
    exits = _exit_signals(price, ind, closes, lows, macd_pack, divergence, levels, profile)

    report: Dict[str, Any] = {
        "code": payload.get("code"),
        "name_ar": payload.get("name_ar"),
        "name_en": payload.get("name_en"),
        "sector": payload.get("sector"),
        "currency": payload.get("currency", "SAR"),
        "is_demo": bool(payload.get("is_demo")),
        "fetched_at": payload.get("fetched_at"),
        "timeframe": payload.get("timeframe"),
        "interval": payload.get("interval"),
        "profile": {
            "key": profile["key"],
            "label": profile["label"],
            "icon": profile["icon"],
            "horizon": profile["horizon_label"],
        },
        "price": _round(price, 2),
        "prev_close": _round(prev_close, 2),
        "change": _round(change, 2),
        "change_pct": _round(change_pct, 2),
        "open": _round(opens[-1], 2),
        "high": _round(highs[-1], 2),
        "low": _round(lows[-1], 2),
        "volume": int(volumes[-1]),
        "value_traded": _round(price * volumes[-1], 0),
        "week52": {
            "high": _round(rng["high"], 2),
            "low": _round(rng["low"], 2),
            "position_pct": _round(rng["position_pct"], 1),
        },
        "indicators": {k: _round(v, 4) for k, v in ind.items()},
        "trend": trend,
        "market": regime,
        "liquidity": liquidity,
        "levels": {
            "supports": [
                {"price": _round(lv["price"], 2), "touches": lv["touches"],
                 "distance_pct": _round(lv["distance_pct"], 2)}
                for lv in levels["supports"]
            ],
            "resistances": [
                {"price": _round(lv["price"], 2), "touches": lv["touches"],
                 "distance_pct": _round(lv["distance_pct"], 2)}
                for lv in levels["resistances"]
            ],
        },
        "trendlines": {
            "down": _serialize_line(down_line),
            "up": _serialize_line(up_line),
        },
        "divergence": divergence,
        "setups": setups,
        "confirmations": confirmations,
        "vetoes": vetoes,
        "gates": gates,
        "score": {
            "total": _round(total, 1),
            "raw": _round(raw_total, 1),
            "components": components,
            "adjustments": adjustments,
        },
        "signal": {**signal, "probability_up": _round(probability_up, 1)},
        "plan": plan,
        "forecast": forecast,
        "exits": exits,
        "disclaimer": DISCLAIMER,
    }

    if include_series:
        report["candles"] = candles
        report["series"] = {
            "ema_fast": ema_fast,
            "ema_mid": ema_mid,
            "ema_slow": ema_slow,
            "rsi": rsi_series,
            "macd": macd_pack["macd"],
            "macd_signal": macd_pack["signal"],
            "macd_hist": macd_pack["hist"],
            "bb_upper": bb["upper"],
            "bb_lower": bb["lower"],
            "volume_ma": vol_ma,
        }
        report["series_meta"] = {
            "ema_fast_period": profile["ema_fast"],
            "ema_mid_period": profile["ema_mid"],
            "ema_slow_period": profile["ema_slow"],
        }

    return report


# ═══════════════════════ البوابات ═══════════════════════


def _gate_liquidity(closes, volumes, profile) -> Dict[str, Any]:
    """البوابة ① — استبعاد الأسهم قليلة السيولة قبل أي تحليل."""
    window = min(LIQUIDITY_LOOKBACK, len(closes))
    values = [closes[-i] * volumes[-i] for i in range(1, window + 1)]
    avg_value = sum(values) / len(values) if values else 0.0
    dead_sessions = sum(1 for i in range(1, window + 1) if volumes[-i] <= 0)
    price = closes[-1]

    reasons: List[str] = []
    if avg_value < profile["min_liquidity_sar"]:
        reasons.append(
            f"متوسط قيمة التداول {avg_value/1_000_000:.2f} مليون ريال — "
            f"أقل من الحد ({profile['min_liquidity_sar']/1_000_000:.0f} مليون)."
        )
    if price < 1.0:
        reasons.append("سعر السهم أقل من ريال واحد.")
    if len(closes) < MIN_CANDLES:
        reasons.append(f"عدد الشموع {len(closes)} — أقل من {MIN_CANDLES}.")
    if dead_sessions > MAX_DEAD_SESSIONS:
        reasons.append(f"{dead_sessions} جلسات بلا تداول خلال آخر {window}.")

    return {
        "passed": not reasons,
        "avg_value_traded": _round(avg_value, 0),
        "avg_value_millions": _round(avg_value / 1_000_000, 2),
        "dead_sessions": dead_sessions,
        "reasons": reasons,
    }


def _classify_trend(price: float, ind: Dict[str, Num], profile) -> Dict[str, Any]:
    """البوابة ③ — صاعد / هابط / عرضي."""
    fast, mid, slow = ind["ema_fast"], ind["ema_mid"], ind["ema_slow"]
    adx_now = ind["adx"] or 0.0
    pdi, mdi = ind["plus_di"] or 0.0, ind["minus_di"] or 0.0

    if fast is None or mid is None:
        return {"state": "unknown", "label": "غير محدّد", "icon": "❔",
                "tradable": False, "note": "بيانات غير كافية لتحديد الاتجاه."}

    up_stack = price > fast and fast > mid and (slow is None or mid > slow)
    down_stack = price < fast and fast < mid and (slow is None or mid < slow)

    if adx_now < profile["adx_min"] or (not up_stack and not down_stack):
        if adx_now < profile["adx_min"]:
            reason = (
                f"قوة الاتجاه ضعيفة: ADX = {adx_now:.1f} دون الحد "
                f"{profile['adx_min']:.0f}."
            )
        else:
            reason = (
                f"المتوسطات متشابكة رغم ADX = {adx_now:.1f} — "
                "السعر والمتوسطات غير مرتّبة في اتجاه واحد."
            )
        return {
            "state": "sideways", "label": "عرضي", "icon": "↔️", "tradable": False,
            "note": reason + " لا صفقة اتجاهية.",
            "adx": _round(adx_now, 1),
        }
    if up_stack and pdi > mdi:
        return {
            "state": "up", "label": "صاعد", "icon": "⬆️", "tradable": True,
            "note": "ترتيب المتوسطات صاعد و +DI أعلى من −DI.",
            "adx": _round(adx_now, 1),
        }
    if down_stack and mdi > pdi:
        return {
            "state": "down", "label": "هابط", "icon": "⬇️", "tradable": True,
            "note": "ترتيب المتوسطات هابط و −DI أعلى من +DI.",
            "adx": _round(adx_now, 1),
        }
    return {
        "state": "sideways", "label": "عرضي", "icon": "↔️", "tradable": False,
        "note": "الاتجاه ومؤشر DI غير متوافقين.", "adx": _round(adx_now, 1),
    }


def _detect_setups(
    closes, highs, lows, volumes, opens, ind, levels, down_line, up_line,
    rsi_series, ema_fast, ema_mid, ema_slow, profile, trend,
) -> List[Dict[str, Any]]:
    """البوابة ④ — النماذج الأربعة."""
    price = closes[-1]
    vol_ratio = ind["volume_ratio"] or 0.0
    vol_ok = vol_ratio >= profile["vol_breakout_mult"]
    fast = ind["ema_fast"]
    rsi_now = ind["rsi"]

    setups: List[Dict[str, Any]] = []

    # (أ) كسر خط الاتجاه الهابط — النموذج المعروض في الصورة المرجعية
    a_hit, a_detail = False, "لا يوجد خط اتجاه هابط صالح."
    if down_line and down_line["slope"] < 0:
        line_now = down_line["value_now"]
        above_now = price > line_now
        prev_line = down_line["slope"] * (len(closes) - 2) + down_line["intercept"]
        was_below = closes[-2] < prev_line
        above_fast = fast is not None and price > fast
        if above_now and above_fast and vol_ok:
            a_hit = True
            a_detail = (
                f"إغلاق {price:.2f} فوق خط الهبوط ({line_now:.2f}) وفوق المتوسط "
                f"({fast:.2f}) بحجم {vol_ratio:.1f}× المتوسط."
            )
        elif above_now and above_fast:
            a_detail = f"كسر الخط لكن الحجم {vol_ratio:.1f}× دون الحد ({profile['vol_breakout_mult']}×)."
        elif above_now and was_below:
            a_detail = "كسر الخط لكن الإغلاق ما زال تحت المتوسط السريع."
        else:
            a_detail = f"السعر ما زال تحت خط الهبوط ({line_now:.2f})."
    setups.append({
        "key": "trendline_break", "name": "كسر خط الاتجاه الهابط",
        "icon": "📐", "triggered": a_hit, "detail": a_detail,
    })

    # (ب) اختراق مقاومة أفقية
    b_hit, b_detail = False, "لا توجد مقاومة مخترقة."
    broken = [
        lv for lv in ta.cluster_levels(
            ta.swing_points(highs, lows, profile["swing_span"])["tops"], 1.5
        )
        if lv["touches"] >= 2 and lv["price"] < price
    ]
    if broken:
        nearest = max(broken, key=lambda lv: lv["price"])
        over_pct = (price - nearest["price"]) / nearest["price"] * 100.0
        if vol_ok and over_pct <= profile["chase_limit_pct"]:
            b_hit = True
            b_detail = (
                f"إغلاق فوق مقاومة {nearest['price']:.2f} ({nearest['touches']} لمسات) "
                f"بفارق {over_pct:.1f}٪ وحجم {vol_ratio:.1f}×."
            )
        elif over_pct > profile["chase_limit_pct"]:
            b_detail = f"ابتعد {over_pct:.1f}٪ فوق المقاومة — مطاردة، لا دخول."
        else:
            b_detail = f"اخترق المقاومة لكن بحجم {vol_ratio:.1f}× فقط."
    setups.append({
        "key": "resistance_breakout", "name": "اختراق مقاومة",
        "icon": "🚀", "triggered": b_hit, "detail": b_detail,
    })

    # (ج) ارتداد ضمن اتجاه صاعد
    c_hit, c_detail = False, "الاتجاه ليس صاعدًا — النموذج غير قابل للتطبيق."
    if trend["state"] == "up" and rsi_now is not None:
        low_band, high_band = profile["rsi_pullback"]
        near_ema = False
        for level in (ind["ema_fast"], ind["ema_mid"]):
            if level and abs(price - level) / level * 100.0 <= 3.0:
                near_ema = True
        rsi_prev = rsi_series[-2] if len(rsi_series) > 1 else None
        turning_up = rsi_prev is not None and rsi_now > rsi_prev
        in_band = low_band <= rsi_now <= high_band
        if near_ema and in_band and turning_up:
            c_hit = True
            c_detail = (
                f"تصحيح إلى منطقة المتوسط و RSI {rsi_now:.0f} داخل نطاق "
                f"{low_band:.0f}-{high_band:.0f} وبدأ يرتفع."
            )
        elif near_ema and in_band:
            c_detail = f"السعر عند المتوسط و RSI {rsi_now:.0f} لكنه لم ينعطف صعودًا بعد."
        elif in_band:
            c_detail = f"RSI {rsi_now:.0f} في نطاق الارتداد لكن السعر بعيد عن المتوسطات."
        else:
            c_detail = f"RSI {rsi_now:.0f} خارج نطاق الارتداد ({low_band:.0f}-{high_band:.0f})."
    setups.append({
        "key": "uptrend_pullback", "name": "ارتداد ضمن اتجاه صاعد",
        "icon": "🎯", "triggered": c_hit, "detail": c_detail,
    })

    # (د) التقاطع الذهبي
    d_hit, d_detail = False, "لا يتوفر متوسط بطيء كافٍ."
    if ind["ema_mid"] is not None and ind["ema_slow"] is not None:
        cross_index = None
        for i in range(len(closes) - 1, max(len(closes) - 30, 1), -1):
            m0, m1 = ema_mid[i - 1], ema_mid[i]
            s0, s1 = ema_slow[i - 1], ema_slow[i]
            if None in (m0, m1, s0, s1):
                continue
            if m0 <= s0 and m1 > s1:
                cross_index = i
                break
        if cross_index is not None and price > ind["ema_mid"] and (ind["adx"] or 0) >= profile["adx_min"]:
            d_hit = True
            d_detail = (
                f"تقاطع ذهبي قبل {len(closes) - 1 - cross_index} شمعة، "
                f"والسعر فوق المتوسطين و ADX = {ind['adx']:.0f}."
            )
        elif ind["ema_mid"] > ind["ema_slow"]:
            d_detail = "المتوسط المتوسط فوق البطيء لكن لا تقاطع حديث."
        else:
            d_detail = "المتوسط المتوسط ما زال تحت البطيء."
    setups.append({
        "key": "golden_cross", "name": "التقاطع الذهبي",
        "icon": "✨", "triggered": d_hit, "detail": d_detail,
    })

    return setups


def _confirmations(ind, macd_pack, closes, index_payload, rng, profile) -> List[Dict[str, Any]]:
    """قائمة التأكيد — يلزم اثنان على الأقل."""
    hist = macd_pack["hist"]
    hist_now = ind["macd_hist"]
    hist_prev = hist[-2] if len(hist) > 1 else None
    rising = hist_now is not None and hist_prev is not None and hist_now > hist_prev

    low_band, high_band = profile["rsi_strong"]
    rsi_now = ind["rsi"]

    rel = _relative_strength(closes, index_payload)

    items = [
        {
            "key": "macd", "name": "هستوغرام MACD موجب ومتزايد",
            "ok": bool(hist_now is not None and hist_now > 0 and rising),
            "detail": f"القيمة {hist_now:.3f}" if hist_now is not None else "غير متاح",
        },
        {
            "key": "rsi", "name": f"RSI بين {low_band:.0f} و {high_band:.0f}",
            "ok": bool(rsi_now is not None and low_band <= rsi_now <= high_band),
            "detail": f"RSI = {rsi_now:.1f}" if rsi_now is not None else "غير متاح",
        },
        {
            "key": "obv", "name": "تدفق السيولة (OBV) صاعد",
            "ok": bool(ind["obv_slope"] is not None and ind["obv_slope"] > 0),
            "detail": "تجميع" if (ind["obv_slope"] or 0) > 0 else "توزيع أو محايد",
        },
        {
            "key": "di", "name": "‎+DI أعلى من −DI مع ADX كافٍ",
            "ok": bool(
                ind["plus_di"] is not None and ind["minus_di"] is not None
                and ind["plus_di"] > ind["minus_di"]
                and (ind["adx"] or 0) >= profile["adx_min"]
            ),
            "detail": (
                f"+DI {ind['plus_di']:.0f} / −DI {ind['minus_di']:.0f}"
                if ind["plus_di"] is not None and ind["minus_di"] is not None else "غير متاح"
            ),
        },
        {
            "key": "relative", "name": "أقوى من المؤشر العام",
            "ok": bool(rel is not None and rel > 0),
            "detail": f"فارق الأداء {rel:+.1f}٪" if rel is not None else "المؤشر غير متاح",
        },
        {
            "key": "range", "name": "في النصف الأعلى من نطاق ٥٢ أسبوعًا",
            "ok": bool(rng["position_pct"] is not None and rng["position_pct"] >= 50),
            "detail": (
                f"الموقع {rng['position_pct']:.0f}٪" if rng["position_pct"] is not None else "غير متاح"
            ),
        },
    ]
    return items


def _vetoes(ind, price, divergence, levels, regime, profile) -> List[Dict[str, Any]]:
    """قائمة الفيتو — أي واحدة تُلغي إشارة الشراء."""
    rsi_now = ind["rsi"]
    extension = ind["distance_from_fast_pct"]
    vol_ratio = ind["volume_ratio"]
    adx_now = ind["adx"]

    nearest_res = levels["resistances"][0] if levels["resistances"] else None
    headroom = nearest_res["distance_pct"] if nearest_res else None

    return [
        {
            "key": "extended", "name": "تمدّد حاد فوق المتوسط",
            "hit": bool(
                rsi_now is not None and extension is not None
                and rsi_now > profile["rsi_veto"] and extension > profile["extension_veto_pct"]
            ),
            "detail": (
                f"RSI {rsi_now:.0f} والابتعاد {extension:+.1f}٪ عن المتوسط السريع"
                if rsi_now is not None and extension is not None else "غير متاح"
            ),
        },
        {
            "key": "divergence", "name": "دايفرجنس هابط بين السعر و RSI",
            "hit": divergence == "bearish",
            "detail": "قمة سعرية أعلى مقابل قمة RSI أدنى" if divergence == "bearish" else "لا يوجد",
        },
        {
            "key": "choppy", "name": "سوق عشوائي بلا اتجاه",
            "hit": bool(adx_now is not None and adx_now < profile["adx_veto"]),
            "detail": f"ADX = {adx_now:.1f}" if adx_now is not None else "غير متاح",
        },
        {
            "key": "weak_volume", "name": "حجم دون المتوسط في يوم الإشارة",
            "hit": bool(vol_ratio is not None and vol_ratio < 1.0),
            "detail": f"الحجم {vol_ratio:.2f}× المتوسط" if vol_ratio is not None else "غير متاح",
        },
        {
            "key": "no_headroom", "name": "مقاومة قريبة تخنق الهدف",
            "hit": bool(headroom is not None and headroom < profile["min_headroom_pct"]),
            "detail": (
                f"أقرب مقاومة على بعد {headroom:.1f}٪ فقط"
                if headroom is not None else "لا توجد مقاومة قريبة"
            ),
        },
        {
            "key": "market", "name": "حالة السوق العامة سلبية",
            "hit": regime["state"] == "negative",
            "detail": regime["note"],
        },
    ]


# ═══════════════════════ الدرجة المركّبة ═══════════════════════


def _relative_strength(closes: Sequence[float], index_payload) -> Num:
    """فارق أداء السهم عن المؤشر خلال ٢٠ شمعة (نقاط مئوية)."""
    if not index_payload or not index_payload.get("candles"):
        return None
    idx_closes = [c["c"] for c in index_payload["candles"]]
    if len(closes) < 21 or len(idx_closes) < 21:
        return None
    stock = ta.pct_change(closes[-1], closes[-21])
    market = ta.pct_change(idx_closes[-1], idx_closes[-21])
    if stock is None or market is None:
        return None
    return stock - market


_RSI_ANCHORS = (
    (0.0, -25.0), (25.0, -60.0), (40.0, -35.0), (48.0, -5.0), (52.0, 10.0),
    (58.0, 45.0), (66.0, 80.0), (72.0, 85.0), (80.0, 35.0), (88.0, -35.0), (100.0, -70.0),
)


def _score_components(
    price, ind, closes, index_payload, rng, down_line, up_line, levels,
    macd_pack, trend, profile,
) -> List[Dict[str, Any]]:
    """يحسب المكوّنات السبعة، كل منها من −١٠٠ إلى +١٠٠، ثم يزنها."""
    fast, mid, slow = ind["ema_fast"], ind["ema_mid"], ind["ema_slow"]

    # ① الاتجاه
    terms = []
    if fast is not None:
        terms.append((price > fast, 30.0))
    if fast is not None and mid is not None:
        terms.append((fast > mid, 25.0))
    if mid is not None and slow is not None:
        terms.append((mid > slow, 25.0))
    if slow is not None:
        terms.append((price > slow, 20.0))
    weight_sum = sum(w for _, w in terms) or 1.0
    trend_score = sum((w if ok else -w) for ok, w in terms) / weight_sum * 100.0

    # ② القوة النسبية
    rel = _relative_strength(closes, index_payload)
    rel_score = _clamp(rel * 8.0) if rel is not None else 0.0

    # ③ الزخم — MACD
    hist_now = ind["macd_hist"]
    hist = macd_pack["hist"]
    hist_prev = hist[-2] if len(hist) > 1 else None
    if hist_now is None or not price:
        momentum_score = 0.0
    else:
        normalized = hist_now / price * 100.0
        momentum_score = _clamp(normalized * 45.0, -60.0, 60.0)
        if hist_prev is not None:
            momentum_score += 20.0 if hist_now > hist_prev else -20.0
        if ind["macd"] is not None and ind["macd_signal"] is not None:
            momentum_score += 20.0 if ind["macd"] > ind["macd_signal"] else -20.0
        momentum_score = _clamp(momentum_score)

    # ④ قوة الاتجاه — ADX / DI
    adx_now, pdi, mdi = ind["adx"], ind["plus_di"], ind["minus_di"]
    if adx_now is None or pdi is None or mdi is None or (pdi + mdi) == 0:
        strength_score = 0.0
    elif adx_now < profile["adx_veto"]:
        strength_score = 0.0
    else:
        spread = (pdi - mdi) / (pdi + mdi)
        conviction = _clamp((adx_now - profile["adx_veto"]) / 35.0, 0.0, 1.0)
        strength_score = _clamp(spread * 100.0 * (0.45 + 0.55 * conviction))

    # ⑤ RSI
    rsi_score = _interp(ind["rsi"], _RSI_ANCHORS) if ind["rsi"] is not None else 0.0

    # ⑥ تدفق السيولة
    flow_score = 0.0
    avg_vol = ind["volume_ma"]
    if ind["obv_slope"] is not None and avg_vol:
        flow_score += _clamp(ind["obv_slope"] / avg_vol * 160.0, -70.0, 70.0)
    ratio = ind["volume_ratio"]
    if ratio is not None and len(closes) > 1:
        direction = 1.0 if closes[-1] >= closes[-2] else -1.0
        if ratio >= 1.3:
            flow_score += 30.0 * direction
        elif ratio < 0.7:
            flow_score -= 15.0
    flow_score = _clamp(flow_score)

    # ⑦ البنية السعرية
    structure_score = 0.0
    if rng["position_pct"] is not None:
        structure_score += _clamp((rng["position_pct"] - 50.0) * 1.2, -60.0, 60.0)
    if down_line and down_line["slope"] < 0 and price > down_line["value_now"]:
        structure_score += 25.0
    if up_line and up_line["slope"] > 0 and price < up_line["value_now"]:
        structure_score -= 25.0
    if levels["supports"] and abs(levels["supports"][0]["distance_pct"]) <= 2.0 and trend["state"] == "up":
        structure_score += 15.0
    if levels["resistances"] and levels["resistances"][0]["distance_pct"] <= 2.0:
        structure_score -= 15.0
    structure_score = _clamp(structure_score)

    raw = [
        ("trend", "الاتجاه", trend_score),
        ("relative_strength", "القوة النسبية مقابل تاسي", rel_score),
        ("momentum", "الزخم (MACD)", momentum_score),
        ("trend_strength", "قوة الاتجاه (ADX/DI)", strength_score),
        ("rsi", "القوة النسبية RSI", rsi_score),
        ("liquidity_flow", "تدفق السيولة", flow_score),
        ("structure", "البنية السعرية", structure_score),
    ]

    return [
        {
            "key": key,
            "label": label,
            "weight": WEIGHTS[key],
            "value": _round(value, 1),
            "contribution": _round(value * WEIGHTS[key] / 100.0, 2),
        }
        for key, label, value in raw
    ]


def _classify_signal(total: float) -> Dict[str, Any]:
    for threshold, key, label, icon, side in SIGNAL_BANDS:
        if total >= threshold:
            return {"key": key, "label": label, "icon": icon, "side": side}
    return {"key": "neutral", "label": "حياد / انتظار", "icon": "⬜", "side": "hold"}


# ═══════════════════════ خطة التنفيذ ═══════════════════════


def build_plan(price, ind, lows, levels, profile, regime, capital, risk_pct) -> Dict[str, Any]:
    """
    وقف الخسارة والأهداف وحجم المركز — القسم ٣ من وثيقة الاستراتيجية.

    الثابت هو **مبلغ الخسارة** لا حجم المركز.
    """
    atr_value = ind["atr"]
    entry = price

    swing_low = min(lows[-10:]) if len(lows) >= 10 else min(lows)
    candidates = [swing_low * 0.997]
    if atr_value:
        candidates.append(entry - profile["atr_stop_mult"] * atr_value)
    stop = max(candidates)  # الأقرب للسعر = الأقل خسارة

    # نزّل الوقف تحت الدعم فقط إذا كان الدعم *ملاصقًا* للوقف المرشّح، حتى
    # لا يُصاد الأمر عند اختبار طبيعي للدعم. أما دعم بعيد بعدة نسب مئوية
    # فلا يُوسَّع إليه الوقف — التوسيع يحوّل خسارة منضبطة إلى خسارة كبيرة.
    hug_band = (atr_value or entry * 0.01) * 0.6
    for level in levels["supports"]:
        support = level["price"]
        if support < stop and (stop - support) <= hug_band:
            stop = support * 0.995
            break

    stop = max(0.01, min(stop, entry * 0.999))
    risk_per_share = entry - stop
    stop_pct = risk_per_share / entry * 100.0 if entry else 0.0

    # الأهداف: أقرب مقاومتين، وإلا مضاعفات R.
    resistances = [lv["price"] for lv in levels["resistances"]]
    t1 = resistances[0] if resistances else entry + 2.0 * risk_per_share
    t2 = resistances[1] if len(resistances) > 1 else entry + 3.0 * risk_per_share
    if t1 <= entry:
        t1 = entry + 2.0 * risk_per_share
    if t2 <= t1:
        t2 = max(t1 * 1.01, entry + 3.0 * risk_per_share)

    def _target(label, target_price, portion):
        reward = target_price - entry
        return {
            "label": label,
            "price": _round(target_price, 2),
            "gain_pct": _round(reward / entry * 100.0, 2) if entry else None,
            "r_multiple": _round(reward / risk_per_share, 2) if risk_per_share > 0 else None,
            "action": portion,
        }

    targets = [
        _target("الهدف الأول", t1, "بيع ثلث المركز ونقل الوقف إلى التعادل"),
        _target("الهدف الثاني", t2, "بيع ثلث آخر"),
    ]
    rr = (t1 - entry) / risk_per_share if risk_per_share > 0 else None

    # حجم المركز
    risk_pct = max(0.05, min(float(risk_pct or 1.0), 5.0))
    capital = max(0.0, float(capital or 0.0))
    size_factor = regime.get("size_factor", 1.0)
    risk_amount_base = capital * risk_pct / 100.0
    # سوق محايد ⇒ نصف الحجم. نُبقي المبلغ الأصلي ظاهرًا حتى يفهم المستخدم
    # لماذا اختلف المبلغ عمّا أدخله بدل أن يبدو الرقم خطأً.
    risk_amount = risk_amount_base * (size_factor if size_factor > 0 else 1.0)
    shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
    position_value = shares * entry

    checks = {
        "rr_ok": bool(rr is not None and rr >= profile["min_rr"]),
        "stop_ok": stop_pct <= profile["max_stop_pct"],
    }
    reasons = []
    if not checks["rr_ok"]:
        reasons.append(
            f"العائد/المخاطرة {rr:.2f} أقل من الحد المطلوب {profile['min_rr']}."
            if rr is not None else "تعذّر حساب العائد/المخاطرة."
        )
    if not checks["stop_ok"]:
        reasons.append(
            f"بُعد وقف الخسارة {stop_pct:.1f}٪ يتجاوز الحد {profile['max_stop_pct']}٪."
        )

    trail = None
    if atr_value:
        trail = entry - profile["atr_trail_mult"] * atr_value

    return {
        "entry": _round(entry, 2),
        "stop": _round(stop, 2),
        "stop_pct": _round(stop_pct, 2),
        "risk_per_share": _round(risk_per_share, 3),
        "targets": targets,
        "risk_reward": _round(rr, 2),
        "trail_stop": _round(trail, 2),
        "trail_rule": (
            f"بعد تحقق ١R انقل الوقف للتعادل، ثم تابع بـ {profile['atr_trail_mult']}× ATR "
            "أو تحت المتوسط السريع على أساس إغلاق."
        ),
        "capital": _round(capital, 2),
        "risk_pct": _round(risk_pct, 2),
        "risk_amount": _round(risk_amount, 2),
        "risk_amount_base": _round(risk_amount_base, 2),
        "size_factor": size_factor,
        "shares": shares,
        "position_value": _round(position_value, 2),
        "position_pct_of_capital": _round(position_value / capital * 100.0, 1) if capital else None,
        "max_loss": _round(shares * risk_per_share, 2),
        "checks": checks,
        "reasons": reasons,
        "acceptable": all(checks.values()),
    }


def _gates_summary(liquidity, regime, trend, setups, plan, profile, signal) -> List[Dict[str, Any]]:
    triggered = [s for s in setups if s["triggered"]]
    return [
        {
            "n": 1, "key": "liquidity", "name": "السيولة",
            "passed": liquidity["passed"],
            "detail": " · ".join(liquidity["reasons"]) if liquidity["reasons"]
            else f"متوسط قيمة التداول {liquidity['avg_value_millions']} مليون ريال.",
        },
        {
            "n": 2, "key": "market", "name": "حالة السوق (تاسي)",
            "passed": regime["state"] in ("positive", "neutral", "unknown"),
            "detail": f"{regime['label']} — {regime['note']}",
        },
        {
            "n": 3, "key": "trend", "name": "اتجاه السهم",
            "passed": trend["tradable"],
            "detail": f"{trend['label']} — {trend['note']}",
        },
        {
            "n": 4, "key": "setup", "name": "إشارة دخول",
            "passed": bool(triggered),
            "detail": " · ".join(s["name"] for s in triggered) if triggered
            else "لم يتحقق أي من النماذج الأربعة.",
        },
        {
            "n": 5, "key": "risk", "name": "مخاطرة مقبولة",
            "passed": plan["acceptable"],
            "detail": " · ".join(plan["reasons"]) if plan["reasons"]
            else f"العائد/المخاطرة {plan['risk_reward']} ووقف على بعد {plan['stop_pct']}٪.",
        },
    ]


def _forecast(price: float, atr_value: Num, profile) -> Dict[str, Any]:
    """نطاق الحركة المتوقع — لا سعر مفرد."""
    bars = profile["horizon_bars"]
    if not atr_value:
        return {
            "bars": bars, "horizon": profile["horizon_label"],
            "low": None, "high": None, "move_pct": None,
            "note": "تعذّر حساب النطاق لعدم توفر ATR.",
        }
    move = atr_value * math.sqrt(bars)
    return {
        "bars": bars,
        "horizon": profile["horizon_label"],
        "low": _round(max(0.0, price - move), 2),
        "high": _round(price + move, 2),
        "move_pct": _round(move / price * 100.0, 1) if price else None,
        "note": (
            "نطاق إحصائي مشتق من تذبذب السهم (ATR×√المدة) — يصف حجم الحركة "
            "المحتملة لا اتجاهها، وليس تنبؤًا بالسعر."
        ),
    }


def _exit_signals(price, ind, closes, lows, macd_pack, divergence, levels, profile) -> List[Dict[str, Any]]:
    """إشارات الخروج — القسم ٤ من وثيقة الاستراتيجية."""
    fast, mid, slow = ind["ema_fast"], ind["ema_mid"], ind["ema_slow"]
    hist_now = ind["macd_hist"]
    swing_low = min(lows[-10:]) if len(lows) >= 10 else min(lows)
    extension = ind["distance_from_fast_pct"]
    rsi_now = ind["rsi"]

    items = [
        {
            "name": "إغلاق تحت المتوسط السريع مع زخم سالب",
            "hit": bool(fast is not None and price < fast and (hist_now or 0) < 0),
            "detail": f"السعر {price:.2f} مقابل المتوسط {fast:.2f}" if fast else "غير متاح",
        },
        {
            "name": "كسر آخر قاع محوري",
            "hit": bool(price < swing_low),
            "detail": f"آخر قاع محوري {swing_low:.2f}",
        },
        {
            "name": "تقاطع الموت أو −DI يتفوّق",
            "hit": bool(
                (mid is not None and slow is not None and mid < slow)
                or (
                    ind["minus_di"] is not None and ind["plus_di"] is not None
                    and ind["minus_di"] > ind["plus_di"] and (ind["adx"] or 0) > 25
                )
            ),
            "detail": "ترتيب هابط للمتوسطات أو ضغط بيعي مؤكد بـ ADX",
        },
        {
            "name": "دايفرجنس هابط",
            "hit": divergence == "bearish",
            "detail": "قمة سعرية أعلى مقابل قمة RSI أدنى" if divergence == "bearish" else "لا يوجد",
        },
        {
            "name": "تمدّد حاد يستدعي جني أرباح جزئي",
            "hit": bool(
                rsi_now is not None and extension is not None
                and rsi_now > 85 and extension > profile["extension_veto_pct"] * 1.25
            ),
            "detail": (
                f"RSI {rsi_now:.0f} والابتعاد {extension:+.1f}٪"
                if rsi_now is not None and extension is not None else "غير متاح"
            ),
        },
    ]
    return items


def _serialize_line(line) -> Optional[Dict[str, Any]]:
    if not line:
        return None
    return {
        "slope": _round(line["slope"], 5),
        "slope_pct": _round(line["slope_pct"], 3),
        "value_now": _round(line["value_now"], 2),
        "start_index": line["start_index"],
        "start_value": _round(line["start_value"], 2),
        "points": line["points"],
        "direction": "down" if line["slope"] < 0 else "up",
    }


def _insufficient(payload, profile, reason) -> Dict[str, Any]:
    return {
        "code": payload.get("code"),
        "name_ar": payload.get("name_ar"),
        "name_en": payload.get("name_en"),
        "sector": payload.get("sector"),
        "is_demo": bool(payload.get("is_demo")),
        "profile": {"key": profile["key"], "label": profile["label"], "icon": profile["icon"],
                    "horizon": profile["horizon_label"]},
        "error": reason,
        "signal": {"key": "unknown", "label": "غير كافٍ", "icon": "❔", "side": "hold",
                   "probability_up": None},
        "score": {"total": None, "components": [], "adjustments": []},
        "disclaimer": DISCLAIMER,
    }
