/* ═══════════════════════════════════════════════════════════
   لوحة السوق — يجلب المسح ويعرض القوائم والقطاعات.
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var M = window.Market;
  var State = M.State, Fmt = M.Fmt, el = M.el;

  var activeList = "rising";
  var lastScan = null;
  var indexChart = null;

  var LIST_HINTS = {
    rising: "اجتازت البوابات الخمس كاملة (٥/٥) ودرجتها ≥ ٢٠ بلا أي فيتو — هذه وحدها صفقات قابلة للتنفيذ.",
    watchlist: "درجتها إيجابية لكن سقطت بوابة أو تحقّق فيتو — راقبها ولا تدخل بعد.",
    falling: "درجتها ≤ −٢٠ — ضعف واضح، تجنّب الشراء.",
    losers: "اتجاه هابط وضمن أدنى ٢٥٪ من نطاق ٥٢ أسبوعًا — رخيص لأنه ضعيف، لا لأنه فرصة.",
    gainers_today: "الأعلى ارتفاعًا في الجلسة — ارتفاع اليوم ليس إشارة دخول بذاته.",
    losers_today: "الأعلى انخفاضًا في الجلسة.",
    most_active: "الأعلى قيمة تداول — حيث السيولة الحقيقية."
  };

  // ─────────────── التنبيهات ───────────────

  function renderAlerts(data) {
    var host = document.getElementById("mkAlerts");
    host.innerHTML = "";

    if (data.is_demo) {
      var demo = el("div", "mk-banner mk-banner--warn");
      demo.appendChild(el("span", "mk-banner__icon", "⚠️"));
      var body = el("span");
      body.innerHTML = "<strong>وضع تجريبي — الأرقام المعروضة ليست بيانات سوق حقيقية.</strong> " +
        "تعذّر الوصول إلى مزوّد البيانات من هذه البيئة، فتم توليد مسار سعري اصطناعي " +
        "لتشغيل الواجهة فقط. شغّل التطبيق في بيئة تتيح الاتصال بالإنترنت لتظهر بيانات تداول الفعلية. " +
        "<strong>لا تبنِ أي قرار على هذه الشاشة الآن.</strong>";
      demo.appendChild(body);
      host.appendChild(demo);
    }

    var regime = (data.index || {}).regime;
    if (regime && regime.state === "negative") {
      var warn = el("div", "mk-banner mk-banner--warn");
      warn.appendChild(el("span", "mk-banner__icon", "🔴"));
      warn.appendChild(el("span", "",
        "حالة السوق سلبية (البوابة ②): لا صفقات شراء جديدة وفق الاستراتيجية. " +
        "قائمة «مرشحة للصعود» ستكون فارغة أو مقيّدة عمدًا — وهذا سلوك مقصود لا خلل."));
      host.appendChild(warn);
    } else if (regime && regime.state === "neutral") {
      var info = el("div", "mk-banner mk-banner--info");
      info.appendChild(el("span", "mk-banner__icon", "🟡"));
      info.appendChild(el("span", "",
        "حالة السوق محايدة: أحجام المراكز المحسوبة نصف الحجم المعتاد، وأفضل الإشارات فقط."));
      host.appendChild(info);
    }
  }

  // ─────────────── المؤشر ───────────────

  function renderIndex(data) {
    var index = data.index || {};
    var body = document.getElementById("mkIndexBody");
    body.innerHTML = "";

    if (!index.available && index.price === undefined) {
      body.appendChild(el("div", "mk-empty", "تعذّر جلب بيانات المؤشر."));
      return;
    }

    var row = el("div");
    row.style.display = "flex";
    row.style.alignItems = "baseline";
    row.style.gap = "12px";
    row.style.flexWrap = "wrap";

    var price = el("span", "mk-num");
    price.style.fontSize = "28px";
    price.style.fontWeight = "700";
    price.textContent = Fmt.price(index.price);
    row.appendChild(price);

    var change = el("span", "mk-num " + Fmt.dirClass(index.change_pct));
    change.style.fontSize = "15px";
    change.textContent = (index.change >= 0 ? "+" : "") + Fmt.price(index.change) +
                         " (" + Fmt.pct(index.change_pct, true) + ")";
    row.appendChild(change);

    var regime = index.regime || {};
    var badge = el("span", "mk-badge mk-badge--" +
      (regime.state === "positive" ? "buy" : regime.state === "negative" ? "sell" : "hold"));
    badge.textContent = (regime.icon || "") + " سوق " + (regime.label || "—");
    row.appendChild(badge);

    body.appendChild(row);

    document.getElementById("mkIndexUpdated").textContent =
      "آخر مسح " + Fmt.timeAgo(data.scanned_at);

    if (index.candles && index.candles.length > 2) {
      var wrap = document.getElementById("mkIndexChart");
      if (!indexChart) {
        indexChart = new CandleChart(wrap, { initialBars: 90 });
        indexChart.setVisibility("volume", false);
        indexChart.setVisibility("levels", false);
        indexChart.setVisibility("plan", false);
        indexChart.setVisibility("trendlines", false);
        indexChart.setVisibility("ema", false);
      }
      indexChart.setData({ code: "TASI", candles: index.candles, series: {}, levels: [] });
    }
  }

  function renderRegime(data) {
    var regime = (data.index || {}).regime || {};
    var body = document.getElementById("mkRegimeBody");
    body.innerHTML = "";

    var head = el("div");
    head.style.fontSize = "20px";
    head.style.fontWeight = "700";
    head.style.marginBottom = "6px";
    head.textContent = (regime.icon || "") + " " + (regime.label || "—");
    body.appendChild(head);

    body.appendChild(el("p", "mk-check__detail", regime.note || ""));

    var rows = [
      ["الأسهم الممسوحة", Fmt.int(data.analyzed) + " / " + Fmt.int(data.universe_size), false],
      ["اجتازت فلتر السيولة", Fmt.int(data.tradable), false],
      ["حجم المركز المسموح من المعتاد", regime.size_factor === 0 ? "لا شراء" :
        (Math.round((regime.size_factor === undefined ? 1 : regime.size_factor) * 100) + "%"),
        regime.size_factor === 0],
      ["النمط", (data.profile || {}).label, true]
    ];
    rows.forEach(function (pair) {
      var line = el("div", "mk-plan-row");
      line.appendChild(el("span", "mk-plan-row__label", pair[0]));
      // النصوص العربية تحتاج اتجاهها الطبيعي، والأرقام تبقى LTR.
      line.appendChild(el("span",
        "mk-plan-row__value" + (pair[2] ? " mk-plan-row__value--text" : ""), pair[1]));
      body.appendChild(line);
    });
  }

  function renderStats(data) {
    var breadth = data.breadth || {};
    var node = document.getElementById("mkBreadth");
    node.innerHTML = "";
    node.appendChild(M.num("▲ " + Fmt.int(breadth.advancers), "up"));
    node.appendChild(el("span", "", "\u00a0 "));
    node.appendChild(M.num("▼ " + Fmt.int(breadth.decliners), "down"));

    document.getElementById("mkBuyCount").textContent = Fmt.int(breadth.buy_signals);
    document.getElementById("mkSellCount").textContent = Fmt.int(breadth.sell_signals);

    var avg = document.getElementById("mkAvgScore");
    avg.textContent = breadth.avg_score === null || breadth.avg_score === undefined
      ? "—" : Number(breadth.avg_score).toFixed(0);
    avg.className = "mk-stat__value " + Fmt.dirClass(breadth.avg_score);

    document.getElementById("mkScanMeta").textContent =
      "من " + Fmt.int(data.analyzed) + " سهمًا · " + Fmt.timeAgo(data.scanned_at);
  }

  // ─────────────── الجداول ───────────────

  function renderList(key) {
    activeList = key;
    var rows = ((lastScan || {}).lists || {})[key] || [];
    var body = document.getElementById("mkListBody");
    body.innerHTML = "";

    document.getElementById("mkListHint").textContent = LIST_HINTS[key] || "";

    Array.prototype.forEach.call(
      document.getElementById("mkListTabs").querySelectorAll("button"),
      function (btn) { btn.classList.toggle("is-active", btn.dataset.list === key); }
    );

    if (!rows.length) {
      // ملاحظة: لا تسمِّ متغيّرًا محليًا cell هنا — سيظلّل الدالة cell للنطاق كله.
      var emptyRow = el("tr");
      var emptyCell = el("td", "mk-empty",
        key === "rising"
          ? "لا يوجد سهم يجتاز البوابات الخمس حاليًا — والانتظار قرار، لا فشل."
          : "لا نتائج في هذه القائمة.");
      emptyCell.colSpan = 15;
      emptyRow.appendChild(emptyCell);
      body.appendChild(emptyRow);
      return;
    }

    rows.forEach(function (row) {
      var tr = el("tr");
      tr.addEventListener("click", function () {
        location.href = "/market/" + row.code + "?" + State.query();
      });

      var symCell = el("td");
      var sym = el("div", "mk-sym");
      sym.appendChild(el("span", "mk-sym__name", row.name_ar));
      sym.appendChild(el("span", "mk-sym__code", row.code + " · " + (row.sector || "")));
      symCell.appendChild(sym);
      tr.appendChild(symCell);

      tr.appendChild(cell(M.num(Fmt.price(row.price))));
      tr.appendChild(cell(M.num(Fmt.pct(row.change_pct, true), Fmt.dirClass(row.change_pct))));
      tr.appendChild(cell(M.scoreCell(row.score)));
      tr.appendChild(cell(M.signalBadge(row.signal)));
      tr.appendChild(cell(el("span", "", row.trend || "—")));
      tr.appendChild(cell(M.num(row.rsi === null || row.rsi === undefined ? "—" : row.rsi.toFixed(0))));
      tr.appendChild(cell(M.num(row.adx === null || row.adx === undefined ? "—" : row.adx.toFixed(0))));

      var gates = el("span", "mk-badge mk-badge--" +
        (row.gates_passed === 5 ? "buy" : row.gates_passed >= 3 ? "warn" : "ghost"));
      gates.textContent = row.gates_passed + "/5";
      tr.appendChild(cell(gates));

      tr.appendChild(cell(M.num(Fmt.price(row.entry))));
      tr.appendChild(cell(M.num(Fmt.price(row.stop), "down")));
      tr.appendChild(cell(M.num(Fmt.price(row.target), "up")));

      var rr = row.risk_reward;
      tr.appendChild(cell(M.num(rr === null || rr === undefined ? "—" : rr.toFixed(2),
        rr && rr >= 1.8 ? "up" : "flat")));

      tr.appendChild(cell(M.num(Fmt.int(row.shares))));

      var setups = el("span", "mk-check__detail");
      setups.textContent = row.setups && row.setups.length
        ? row.setups.join(" · ")
        : (row.vetoes && row.vetoes.length ? "⛔ " + row.vetoes[0] : "—");
      tr.appendChild(cell(setups));

      body.appendChild(tr);
    });
  }

  function cell(node) {
    var td = el("td");
    td.appendChild(node);
    return td;
  }

  function renderSectors(data) {
    var body = document.getElementById("mkSectorBody");
    body.innerHTML = "";
    var sectors = data.sectors || [];
    if (!sectors.length) {
      var tr = el("tr");
      var td = el("td", "mk-empty", "—");
      td.colSpan = 5;
      tr.appendChild(td);
      body.appendChild(tr);
      return;
    }
    sectors.forEach(function (sector) {
      var tr = el("tr");
      tr.appendChild(cell(el("span", "", sector.sector)));
      tr.appendChild(cell(M.num(Fmt.int(sector.count))));
      tr.appendChild(cell(M.num(
        sector.avg_score === null ? "—" : Number(sector.avg_score).toFixed(0),
        Fmt.dirClass(sector.avg_score))));
      tr.appendChild(cell(M.num(Fmt.pct(sector.avg_change_pct, true), Fmt.dirClass(sector.avg_change_pct))));
      tr.appendChild(cell(M.num(Fmt.int(sector.buy_signals), sector.buy_signals ? "up" : "flat")));
      body.appendChild(tr);
    });
  }

  // ─────────────── التحميل ───────────────

  function load() {
    var body = document.getElementById("mkListBody");
    body.innerHTML = '<tr><td colspan="15" class="mk-empty">جارٍ مسح السوق… ' +
                     '<span class="mk-spinner"></span></td></tr>';

    M.fetchJson("/api/market/scan?" + State.query({ limit: 20 }))
      .then(function (data) {
        lastScan = data;
        renderAlerts(data);
        renderIndex(data);
        renderRegime(data);
        renderStats(data);
        renderSectors(data);
        renderList(activeList);
      })
      .catch(function (error) {
        body.innerHTML = "";
        var tr = el("tr");
        var td = el("td", "mk-empty", "تعذّر مسح السوق: " + error.message);
        td.colSpan = 15;
        tr.appendChild(td);
        body.appendChild(tr);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("mkListTabs").addEventListener("click", function (event) {
      var btn = event.target.closest("button[data-list]");
      if (btn) renderList(btn.dataset.list);
    });

    State.onChange(load);
    load();
  });
})();
