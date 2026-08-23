"""اختبارات المزوّد والماسح وواجهات HTTP (كلها في الوضع غير المتصل)."""

import json

import pytest

from market import providers, scanner
from market import symbols as sym


# ═══════════════ الرموز ═══════════════


def test_universe_codes_are_all_four_digit_and_unique():
    codes = sym.codes()
    assert len(codes) == len(set(codes))
    assert all(sym.is_valid_code(code) for code in codes)


def test_every_symbol_has_a_name_and_a_known_sector():
    for row in sym.UNIVERSE:
        assert row["name_ar"] and row["name_en"]
        assert row["sector"] in sym.SECTORS


def test_normalize_code_accepts_common_user_input():
    assert sym.normalize_code("2222") == "2222"
    assert sym.normalize_code("2222.SR") == "2222"
    assert sym.normalize_code(" 1120 ") == "1120"
    assert sym.normalize_code("abcd") is None
    assert sym.normalize_code("") is None
    assert sym.normalize_code("12345") is None


def test_search_matches_code_arabic_and_english():
    assert sym.search("1211")[0]["code"] == "1211"
    assert any(r["code"] == "1120" for r in sym.search("الراجحي"))
    assert any(r["code"] == "2222" for r in sym.search("aramco"))
    assert sym.search("") == []


# ═══════════════ المزوّد ═══════════════


def test_offline_mode_is_flagged_never_silently_faked():
    payload = providers.fetch_ohlcv("1211", "6mo")
    assert payload["is_demo"] is True          # لأن MARKET_OFFLINE=1
    assert providers.network_status()["offline"] is True


def test_demo_data_is_deterministic_per_symbol():
    providers.clear_cache()
    first = providers.fetch_ohlcv("2222", "6mo")["candles"]
    providers.clear_cache()
    second = providers.fetch_ohlcv("2222", "6mo")["candles"]
    assert first == second


def test_candles_are_internally_consistent():
    for candle in providers.fetch_ohlcv("1120", "6mo")["candles"]:
        assert candle["l"] <= candle["o"] <= candle["h"]
        assert candle["l"] <= candle["c"] <= candle["h"]
        assert candle["v"] >= 0


def test_invalid_symbol_returns_none():
    assert providers.fetch_ohlcv("abc") is None
    assert providers.fetch_ohlcv("99999") is None


def test_timeframes_resolve_with_a_safe_fallback():
    assert providers.resolve_timeframe("6mo")["interval"] == "1d"
    assert providers.resolve_timeframe("nonsense")["range"] == \
        providers.TIMEFRAMES[providers.DEFAULT_TIMEFRAME]["range"]


def test_fetch_many_returns_every_valid_code():
    result = providers.fetch_many(["2222", "1120", "7010"], "6mo")
    assert set(result) == {"2222", "1120", "7010"}


# ═══════════════ الماسح ═══════════════


@pytest.fixture(scope="module")
def scan_result():
    scanner.clear_cache()
    return scanner.scan("swing", capital=100_000, risk_pct=1.0, limit=10)


def test_scan_covers_the_whole_universe(scan_result):
    assert scan_result["analyzed"] > 100
    assert scan_result["universe_size"] == len(sym.codes())


def test_rising_list_only_contains_fully_qualified_trades(scan_result):
    """
    «مرشحة للصعود» يجب أن تعني صفقة اجتازت البوابات الخمس بلا فيتو.
    عرض صفقة مرفوضة تحت عنوان «شراء قوي» تضليل، لا اختصار.
    """
    for row in scan_result["lists"]["rising"]:
        assert row["all_gates_passed"] is True
        assert row["gates_passed"] == 5
        assert row["plan_ok"] is True
        assert not row["vetoes"]
        assert row["score"] >= scanner.RISING_MIN_SCORE
        assert row["signal"]["side"] == "buy"


def test_rising_list_is_sorted_by_score(scan_result):
    scores = [row["score"] for row in scan_result["lists"]["rising"]]
    assert scores == sorted(scores, reverse=True)


def test_falling_list_is_negative_and_ascending(scan_result):
    scores = [row["score"] for row in scan_result["lists"]["falling"]]
    assert all(score <= scanner.FALLING_MAX_SCORE for score in scores)
    assert scores == sorted(scores)


def test_losers_are_in_a_downtrend_near_the_bottom_of_their_range(scan_result):
    for row in scan_result["lists"]["losers"]:
        assert row["trend_state"] == "down"
        assert row["week52_position"] <= scanner.LOSER_RANGE_POSITION


def test_watchlist_never_overlaps_the_rising_list(scan_result):
    rising = {row["code"] for row in scan_result["lists"]["rising"]}
    watch = {row["code"] for row in scan_result["lists"]["watchlist"]}
    assert rising.isdisjoint(watch)


def test_daily_movers_are_ranked_by_change(scan_result):
    gainers = [row["change_pct"] for row in scan_result["lists"]["gainers_today"]]
    losers = [row["change_pct"] for row in scan_result["lists"]["losers_today"]]
    assert gainers == sorted(gainers, reverse=True)
    assert losers == sorted(losers)


def test_breadth_counts_add_up(scan_result):
    breadth = scan_result["breadth"]
    total = breadth["advancers"] + breadth["decliners"] + breadth["unchanged"]
    assert total <= scan_result["analyzed"]
    assert breadth["tradable_setups"] == len(scan_result["lists"]["rising"])


def test_sector_breakdown_covers_every_scanned_stock(scan_result):
    assert sum(sector["count"] for sector in scan_result["sectors"]) == scan_result["analyzed"]


def test_scan_marks_demo_data(scan_result):
    assert scan_result["is_demo"] is True


def test_scan_can_be_limited_to_one_sector():
    scanner.clear_cache()
    codes = [row["code"] for row in sym.by_sector("البنوك")]
    result = scanner.scan("swing", codes=codes, limit=5)
    assert result["analyzed"] == len(codes)


# ═══════════════ واجهات HTTP ═══════════════


@pytest.fixture(scope="module")
def client():
    import app as flask_app
    flask_app.app.config["TESTING"] = True
    return flask_app.app.test_client()


def test_pages_render(client):
    assert client.get("/market").status_code == 200
    assert client.get("/market/1211").status_code == 200


def test_unknown_symbol_page_is_404(client):
    assert client.get("/market/notacode").status_code == 404


def test_symbol_api_returns_a_full_report(client):
    payload = json.loads(client.get("/api/market/symbol/1211").data)
    for field in ("candles", "series", "score", "signal", "plan", "gates",
                  "setups", "confirmations", "vetoes", "forecast", "levels"):
        assert field in payload
    assert payload["code"] == "1211"


def test_symbol_api_rejects_a_bad_code(client):
    response = client.get("/api/market/symbol/xyz")
    assert response.status_code == 400
    assert "error" in json.loads(response.data)


def test_symbol_api_honours_capital_and_risk(client):
    plan = json.loads(
        client.get("/api/market/symbol/1211?capital=500000&risk=2").data
    )["plan"]
    assert plan["capital"] == 500_000
    assert plan["risk_pct"] == 2.0
    assert plan["risk_amount_base"] == pytest.approx(10_000.0)
    # المبلغ الفعلي = الأساس × معامل حجم السوق (نصف الحجم في سوق محايد)
    assert plan["risk_amount"] == pytest.approx(10_000.0 * plan["size_factor"])


def test_api_clamps_absurd_inputs(client):
    plan = json.loads(
        client.get("/api/market/symbol/1211?capital=-5&risk=9999").data
    )["plan"]
    assert plan["capital"] >= 1_000
    assert plan["risk_pct"] <= 5.0


def test_api_ignores_a_non_numeric_capital(client):
    plan = json.loads(
        client.get("/api/market/symbol/1211?capital=abc").data
    )["plan"]
    assert plan["capital"] == 100_000


def test_scan_api_shape(client):
    payload = json.loads(client.get("/api/market/scan?limit=5").data)
    assert set(payload["lists"]) >= {"rising", "falling", "losers", "watchlist"}
    assert all(len(rows) <= 5 for rows in payload["lists"].values())


def test_scan_api_limit_is_bounded(client):
    payload = json.loads(client.get("/api/market/scan?limit=9999").data)
    assert all(len(rows) <= 30 for rows in payload["lists"].values())


def test_overview_api_reports_regime_and_network(client):
    payload = json.loads(client.get("/api/market/overview").data)
    assert "regime" in payload
    assert payload["network"]["offline"] is True
    assert payload["index"]["is_demo"] is True


def test_search_api(client):
    results = json.loads(client.get("/api/market/search?q=معادن").data)["results"]
    assert results[0]["code"] == "1211"
    assert json.loads(client.get("/api/market/search?q=").data)["results"] == []


def test_profiles_api_exposes_all_three(client):
    payload = json.loads(client.get("/api/market/profiles").data)
    assert {p["key"] for p in payload["profiles"]} == {"intraday", "swing", "position"}
    assert payload["default"] == "swing"


def test_main_app_still_works(client):
    """قسم السوق مضاف بجانب التطبيق الأصلي، لا فوقه."""
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/azkar/morning").status_code == 200
