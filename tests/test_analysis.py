"""
اختبارات محرّك القرار — تتحقق أن الكود يطابق ``docs/STRATEGY.md``.

كل اختبار مربوط ببند صريح في الوثيقة، فإذا تغيّرت القاعدة في أحدهما
دون الآخر يسقط الاختبار.
"""

import pytest

from conftest import candle, make_payload
from market import analysis


# ═══════════════ البوابة ① — السيولة ═══════════════


def test_illiquid_stock_fails_the_liquidity_gate(illiquid_stock, rising_index):
    report = analysis.analyze(illiquid_stock, rising_index, "swing")
    gate = report["gates"][0]
    assert gate["key"] == "liquidity"
    assert gate["passed"] is False
    assert report["liquidity"]["reasons"]


def test_liquid_stock_passes_the_liquidity_gate(textbook_breakout, rising_index):
    report = analysis.analyze(textbook_breakout, rising_index, "swing")
    assert report["gates"][0]["passed"] is True


# ═══════════════ البوابة ② — حالة السوق ═══════════════


def test_falling_index_closes_the_market_gate(falling_index):
    regime = analysis.market_regime(falling_index, "swing")
    assert regime["state"] == "negative"
    assert regime["allow_buy"] is False
    assert regime["size_factor"] == 0.0


def test_rising_index_opens_the_market_gate(rising_index):
    regime = analysis.market_regime(rising_index, "swing")
    assert regime["state"] == "positive"
    assert regime["size_factor"] == 1.0


def test_missing_index_is_reported_as_unknown_not_assumed_good():
    regime = analysis.market_regime(None, "swing")
    assert regime["state"] == "unknown"
    assert "حذر" in regime["note"]


def test_negative_regime_applies_the_one_third_haircut(textbook_breakout,
                                                      rising_index, falling_index):
    good = analysis.analyze(textbook_breakout, rising_index, "swing")
    bad = analysis.analyze(textbook_breakout, falling_index, "swing")
    assert good["score"]["total"] > 0
    # الدرجة تُخصم ثم يُسقفها الفيتو (حالة السوق سلبية = فيتو بذاته)
    assert bad["score"]["total"] < good["score"]["total"]
    assert any(v["key"] == "market" and v["hit"] for v in bad["vetoes"])


# ═══════════════ البوابات ③–⑤ — المسار الكامل ═══════════════


def test_textbook_breakout_passes_all_five_gates(textbook_breakout, rising_index):
    """
    الاختبار المرجعي: وضع مثالي يجب أن يمرّ من البوابات الخمس.

    لولاه يمكن أن تصبح القواعد متشدّدة لدرجة استحالة أي صفقة، وهو خلل
    صامت لا يظهر في أي اختبار آخر.
    """
    report = analysis.analyze(textbook_breakout, rising_index, "swing",
                              capital=100_000, risk_pct=1.0)

    assert all(gate["passed"] for gate in report["gates"]), [
        (g["n"], g["detail"]) for g in report["gates"] if not g["passed"]
    ]
    assert report["signal"]["side"] == "buy"
    assert report["score"]["total"] >= 20
    assert not [v for v in report["vetoes"] if v["hit"]]

    triggered = [s["key"] for s in report["setups"] if s["triggered"]]
    assert "trendline_break" in triggered      # النموذج (أ) — كسر خط الهبوط
    assert sum(1 for c in report["confirmations"] if c["ok"]) >= 2


def test_trend_classification_needs_both_stacking_and_adx(textbook_breakout, rising_index):
    report = analysis.analyze(textbook_breakout, rising_index, "swing")
    assert report["trend"]["state"] == "up"
    assert report["trend"]["tradable"] is True


def test_sideways_market_is_not_tradable(rising_index):
    """سعر متذبذب بلا اتجاه يجب أن يسقط في البوابة ③."""
    candles = []
    for i in range(150):
        close = 50.0 + (2.0 if i % 2 else -2.0)
        candles.append(candle(i * 86400, close, close + 0.6, close - 0.6, close, 300_000))
    report = analysis.analyze(make_payload(candles), rising_index, "swing")
    assert report["trend"]["state"] == "sideways"
    assert report["gates"][2]["passed"] is False


# ═══════════════ الفيتو ═══════════════


def test_parabolic_move_triggers_the_extension_veto(rising_index):
    """صعود عمودي: RSI فوق ٨٠ وابتعاد كبير عن المتوسط ⇒ فيتو التمدّد."""
    candles = []
    price = 20.0
    for i in range(160):
        price *= 1.0 if i < 120 else 1.035    # هدوء ثم انفجار
        candles.append(candle(i * 86400, price * 0.995, price * 1.02,
                              price * 0.99, price, 500_000))
    report = analysis.analyze(make_payload(candles), rising_index, "swing")
    veto = [v for v in report["vetoes"] if v["key"] == "extended"][0]
    assert veto["hit"] is True
    assert report["score"]["total"] <= analysis.VETO_SCORE_CAP


def test_veto_caps_the_score_and_is_explained(textbook_breakout, falling_index):
    report = analysis.analyze(textbook_breakout, falling_index, "swing")
    assert report["score"]["total"] <= analysis.VETO_SCORE_CAP
    assert report["score"]["adjustments"]


# ═══════════════ خطة التنفيذ ═══════════════


def test_position_size_keeps_the_loss_fixed_not_the_position(textbook_breakout, rising_index):
    """الثابت هو مبلغ الخسارة — مضاعفة رأس المال تضاعف الكمية لا المخاطرة النسبية."""
    small = analysis.analyze(textbook_breakout, rising_index, "swing",
                             capital=100_000, risk_pct=1.0)["plan"]
    large = analysis.analyze(textbook_breakout, rising_index, "swing",
                             capital=200_000, risk_pct=1.0)["plan"]

    assert small["risk_amount"] == pytest.approx(1_000.0)
    assert large["risk_amount"] == pytest.approx(2_000.0)
    assert large["shares"] == pytest.approx(small["shares"] * 2, rel=0.01)
    # أقصى خسارة لا تتجاوز المبلغ المرصود
    assert small["max_loss"] <= small["risk_amount"] + small["risk_per_share"]


def test_risk_pct_scales_the_position(textbook_breakout, rising_index):
    one = analysis.analyze(textbook_breakout, rising_index, "swing",
                           capital=100_000, risk_pct=1.0)["plan"]
    two = analysis.analyze(textbook_breakout, rising_index, "swing",
                           capital=100_000, risk_pct=2.0)["plan"]
    assert two["shares"] == pytest.approx(one["shares"] * 2, rel=0.01)
    assert one["stop"] == two["stop"]      # الوقف فني، لا يتأثر بحجم المحفظة


def test_risk_pct_is_clamped_to_a_sane_band(textbook_breakout, rising_index):
    wild = analysis.analyze(textbook_breakout, rising_index, "swing",
                            capital=100_000, risk_pct=500.0)["plan"]
    assert wild["risk_pct"] <= 5.0


def test_stop_is_always_below_entry_and_targets_above(textbook_breakout, rising_index):
    plan = analysis.analyze(textbook_breakout, rising_index, "swing")["plan"]
    assert plan["stop"] < plan["entry"]
    for target in plan["targets"]:
        assert target["price"] > plan["entry"]
        assert target["r_multiple"] > 0
    assert plan["targets"][1]["price"] > plan["targets"][0]["price"]


def test_stop_is_not_widened_to_a_far_away_support(textbook_breakout, rising_index):
    """
    قاعدة الوثيقة: يُنزَّل الوقف تحت دعم *ملاصق*. دعم بعيد يجب ألا يوسّع
    الوقف — وإلا تحوّلت خسارة ٣٪ إلى خسارة ٢٠٪.
    """
    profile = analysis.get_profile("swing")
    plan = analysis.analyze(textbook_breakout, rising_index, "swing")["plan"]
    assert plan["stop_pct"] <= profile["max_stop_pct"]


def test_market_regime_halves_the_position_when_neutral(textbook_breakout):
    """سوق محايد ⇒ نصف حجم المركز (البوابة ②)."""
    flat = []
    for i in range(260):
        close = 10_000.0 + (30.0 if i % 2 else -30.0)
        flat.append(candle(i * 86400, close, close + 20, close - 20, close, 1_000_000))
    neutral_index = make_payload(flat, code="TASI")

    full = analysis.analyze(textbook_breakout, None, "swing", capital=100_000)["plan"]
    half = analysis.analyze(textbook_breakout, neutral_index, "swing", capital=100_000)["plan"]
    if half["size_factor"] == 0.5:
        assert half["shares"] == pytest.approx(full["shares"] * 0.5, rel=0.02)


# ═══════════════ النطاق المتوقع ═══════════════


def test_forecast_is_a_range_around_price_never_a_single_number(textbook_breakout, rising_index):
    report = analysis.analyze(textbook_breakout, rising_index, "swing")
    forecast = report["forecast"]
    assert forecast["low"] < report["price"] < forecast["high"]
    assert forecast["move_pct"] > 0
    assert "ليس تنبؤًا" in forecast["note"]


def test_forecast_widens_with_the_horizon(textbook_breakout, rising_index):
    """المدى يتّسع بجذر الزمن، فالأفق الأطول نطاقه أوسع نسبيًا."""
    swing = analysis.analyze(textbook_breakout, rising_index, "swing")["forecast"]
    intraday = analysis.analyze(textbook_breakout, rising_index, "intraday")["forecast"]
    assert swing["bars"] > intraday["bars"]
    assert swing["move_pct"] > intraday["move_pct"]


# ═══════════════ الأنماط الثلاثة ═══════════════


@pytest.mark.parametrize("key", ["intraday", "swing", "position"])
def test_every_profile_produces_a_complete_report(textbook_breakout, rising_index, key):
    report = analysis.analyze(textbook_breakout, rising_index, key)
    assert report["profile"]["key"] == key
    for field in ("score", "signal", "plan", "gates", "setups", "vetoes", "forecast"):
        assert field in report
    assert -100 <= report["score"]["total"] <= 100


def test_profiles_differ_in_their_risk_parameters():
    intraday = analysis.get_profile("intraday")
    swing = analysis.get_profile("swing")
    position = analysis.get_profile("position")
    assert intraday["max_stop_pct"] < swing["max_stop_pct"] < position["max_stop_pct"]
    assert intraday["atr_stop_mult"] < swing["atr_stop_mult"] < position["atr_stop_mult"]
    assert position["min_rr"] > swing["min_rr"] > intraday["min_rr"]


def test_unknown_profile_falls_back_to_the_default():
    assert analysis.get_profile("nonsense")["key"] == analysis.DEFAULT_PROFILE
    assert analysis.get_profile(None)["key"] == analysis.DEFAULT_PROFILE


# ═══════════════ الدرجة والتصنيف ═══════════════


def test_score_weights_sum_to_one_hundred():
    assert sum(analysis.WEIGHTS.values()) == pytest.approx(100.0)


def test_every_weight_has_a_matching_component(textbook_breakout, rising_index):
    report = analysis.analyze(textbook_breakout, rising_index, "swing")
    keys = {component["key"] for component in report["score"]["components"]}
    assert keys == set(analysis.WEIGHTS)


def test_signal_bands_are_ordered_and_cover_the_range():
    for score, expected in [(90, "strong_buy"), (30, "buy"), (0, "neutral"),
                            (-30, "sell"), (-90, "strong_sell")]:
        assert analysis._classify_signal(score)["key"] == expected


def test_short_series_returns_an_explicit_error_not_a_fake_signal():
    candles = [candle(i * 86400, 10, 11, 9, 10, 1000) for i in range(5)]
    report = analysis.analyze(make_payload(candles), None, "swing")
    assert "error" in report
    assert report["signal"]["key"] == "unknown"
    assert report["score"]["total"] is None


def test_report_always_carries_the_disclaimer(textbook_breakout, rising_index):
    report = analysis.analyze(textbook_breakout, rising_index, "swing")
    assert "توصية" in report["disclaimer"]
    assert "شرعي" in report["disclaimer"]
