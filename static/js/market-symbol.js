/* ═══════════════════════════════════════════════════════════
   صفحة تحليل السهم — الشارت + البوابات + الدرجة + خطة التنفيذ.
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var M = window.Market;
  var State = M.State, Fmt = M.Fmt, el = M.el;

  var code = document.getElementById("mkQuote").dataset.code;
  var chart = null;
  var timeframe = null;
  var report = null;

  // ─────────────── التنبيهات ───────────────

  function renderAlerts(data) {
    var host = document.getElementById("mkAlerts");
    host.innerHTML = "";

    if (data.is_demo) {
      var demo = el("div", "mk-banner mk-banner--warn");
      demo.appendChild(el("span", "mk-banner__icon", "⚠️"));
      var body = el("span");
      body.innerHTML = "<strong>وضع تجريبي — ليست بيانات سوق حقيقية.</strong> " +
        "تعذّر الوصول إلى مزوّد البيانات، فتم توليد مسار سعري اصطناعي لتشغيل الواجهة. " +
        "كل الأرقام أدناه (السعر، الوقف، الأهداف، الدرجة) مبنية على هذه البيانات المولّدة — " +
        "<strong>لا تتخذ أي قرار بناءً عليها.</strong>";
      demo.appendChild(body);
      host.appendChild(demo);
    }

    if ((data.market || {}).state === "negative") {
      var warn = el("div", "mk-banner mk-banner--warn");
      warn.appendChild(el("span", "mk-banner__icon", "🔴"));
      warn.appendChild(el("span", "", "البوابة ② مغلقة: حالة السوق العامة سلبية — " +
        "الاستراتيجية تمنع أي شراء جديد بغض النظر عن قوة إشارة هذا السهم."));
      host.appendChild(warn);
    }
  }

  // ─────────────── رأس الصفحة ───────────────

  function renderQuote(data) {
    var host = document.getElementById("mkQuote");
    host.innerHTML = "";

    var title = el("div");
    title.style.display = "flex";
    title.style.alignItems = "center";
    title.style.gap = "10px";
    title.style.flexWrap = "wrap";

    var name = el("h1", "", data.name_ar || data.code);
    name.style.fontSize = "21px";
    name.style.margin = "0";
    title.appendChild(name);

    title.appendChild(el("span", "mk-badge mk-badge--ghost", data.code));
    if (data.sector) title.appendChild(el("span", "mk-badge mk-badge--ghost", data.sector));
    title.appendChild(M.signalBadge(data.signal));
    if (data.name_en && data.name_en !== data.name_ar) {
      var en = el("span", "mk-hint", data.name_en);
      en.style.direction = "ltr";
      title.appendChild(en);
    }
    host.appendChild(title);

    var priceRow = el("div");
    priceRow.style.display = "flex";
    priceRow.style.alignItems = "baseline";
    priceRow.style.gap = "14px";
    priceRow.style.flexWrap = "wrap";
    priceRow.style.marginTop = "8px";

    var price = el("span", "mk-num");
    price.style.fontSize = "32px";
    price.style.fontWeight = "700";
    price.textContent = Fmt.price(data.price);
    priceRow.appendChild(price);

    var change = el("span", "mk-num " + Fmt.dirClass(data.change_pct));
    change.style.fontSize = "16px";
    change.textContent = (data.change >= 0 ? "+" : "") + Fmt.price(data.change) +
                         " (" + Fmt.pct(data.change_pct, true) + ")";
    priceRow.appendChild(change);

    var prob = data.signal && data.signal.probability_up;
    if (prob !== null && prob !== undefined) {
      var probBadge = el("span", "mk-badge mk-badge--info");
      probBadge.textContent = "ميل صعودي تقديري " + prob.toFixed(0) + "٪";
      probBadge.title = "تقدير إحصائي مشتق من الدرجة المركّبة — ليس تنبؤًا ولا احتمالًا مُختبَرًا تاريخيًا.";
      priceRow.appendChild(probBadge);
    }
    host.appendChild(priceRow);

    var meta = el("div", "mk-hint");
    meta.style.marginTop = "8px";
    meta.style.display = "flex";
    meta.style.gap = "16px";
    meta.style.flexWrap = "wrap";
    var value = Fmt.moneyParts(data.value_traded);
    [
      ["افتتاح", Fmt.price(data.open), ""],
      ["أعلى", Fmt.price(data.high), ""],
      ["أدنى", Fmt.price(data.low), ""],
      ["الحجم", Fmt.int(data.volume), "سهم"],
      ["القيمة", value.num, (value.suffix + " ر.س").trim()],
      ["أعلى ٥٢ أسبوعًا", Fmt.price((data.week52 || {}).high), ""],
      ["أدنى ٥٢ أسبوعًا", Fmt.price((data.week52 || {}).low), ""]
    ].forEach(function (row) {
      var item = el("span");
      item.appendChild(el("span", "", row[0] + " "));
      item.appendChild(M.num(row[1]));
      // الوحدة العربية تبقى خارج الحقل الرقمي حتى لا يعكسها اتجاه LTR.
      if (row[2]) item.appendChild(el("span", "", " " + row[2]));
      meta.appendChild(item);
    });
    // عبارة عربية كاملة — لا تُوضع داخل حقل رقمي.
    meta.appendChild(el("span", "", "آخر تحديث " + Fmt.timeAgo(data.fetched_at)));
    host.appendChild(meta);
  }

  // ─────────────── الشارت ───────────────

  function renderChart(data) {
    var wrap = document.getElementById("mkChart");
    if (!chart) chart = new CandleChart(wrap, { initialBars: 130 });

    var levels = []
      .concat(((data.levels || {}).supports || []))
      .concat(((data.levels || {}).resistances || []));

    chart.setData({
      code: data.code,
      candles: data.candles || [],
      series: data.series || {},
      seriesMeta: data.series_meta || {},
      levels: levels,
      trendlines: data.trendlines || {},
      plan: data.plan || null
    });

    renderLegend(data);
  }

  function renderLegend(data) {
    var meta = data.series_meta || {};
    var host = document.getElementById("mkLegend");
    host.innerHTML = "";
    [
      ["#f0b90b", "متوسط " + (meta.ema_fast_period || "")],
      ["#3b82f6", "متوسط " + (meta.ema_mid_period || "")],
      ["#a855f7", "متوسط " + (meta.ema_slow_period || "")],
      ["#f0913b", "دعوم ومقاومات"],
      ["#4f9dfd", "خط اتجاه هابط"],
      ["#16c784", "خط اتجاه صاعد / أهداف"],
      ["#ea3943", "وقف الخسارة"]
    ].forEach(function (pair) {
      var item = el("span", "mk-legend__item");
      var swatch = el("span", "mk-legend__swatch");
      swatch.style.background = pair[0];
      item.appendChild(swatch);
      item.appendChild(el("span", "", pair[1]));
      host.appendChild(item);
    });
    host.appendChild(el("span", "mk-legend__item", "عجلة الفأرة = تكبير · السحب = تحريك"));
  }

  // ─────────────── قوائم الفحص ───────────────

  function checkRow(passed, name, detail, style) {
    var row = el("div", "mk-check");
    var kind = style || (passed ? "pass" : "fail");
    var mark = el("div", "mk-check__mark mk-check__mark--" + kind,
      kind === "pass" ? "✓" : kind === "fail" ? "✕" : kind === "warn" ? "!" : "·");
    row.appendChild(mark);
    var body = el("div", "mk-check__body");
    body.appendChild(el("div", "mk-check__name", name));
    if (detail) body.appendChild(el("div", "mk-check__detail", detail));
    row.appendChild(body);
    return row;
  }

  function renderGates(data) {
    var host = document.getElementById("mkGates");
    host.innerHTML = "";
    (data.gates || []).forEach(function (gate) {
      host.appendChild(checkRow(gate.passed, "البوابة " + gate.n + " — " + gate.name, gate.detail));
    });

    var passed = (data.gates || []).filter(function (g) { return g.passed; }).length;
    var summary = el("div", "mk-banner " +
      (passed === 5 ? "mk-banner--info" : "mk-banner--muted"));
    summary.style.marginTop = "12px";
    summary.style.marginBottom = "0";
    summary.appendChild(el("span", "mk-banner__icon", passed === 5 ? "🟢" : "⬜"));
    summary.appendChild(el("span", "", passed === 5
      ? "اجتاز السهم البوابات الخمس — الصفقة مؤهلة وفق الاستراتيجية، ويبقى القرار وحجم المخاطرة عليك."
      : "لم يجتز " + (5 - passed) + " من البوابات — الاستراتيجية لا تعتبره صفقة صالحة الآن."));
    host.appendChild(summary);
  }

  function renderSetups(data) {
    var host = document.getElementById("mkSetups");
    host.innerHTML = "";
    (data.setups || []).forEach(function (setup) {
      host.appendChild(checkRow(setup.triggered,
        setup.icon + " " + setup.name, setup.detail,
        setup.triggered ? "pass" : "idle"));
    });
  }

  function renderConfirmations(data) {
    var host = document.getElementById("mkConfirmations");
    host.innerHTML = "";
    var ok = 0;
    (data.confirmations || []).forEach(function (item) {
      if (item.ok) ok++;
      host.appendChild(checkRow(item.ok, item.name, item.detail, item.ok ? "pass" : "idle"));
    });
    var hint = document.getElementById("mkConfirmCount");
    hint.textContent = ok + "/" + (data.confirmations || []).length + " — يلزم ٢ على الأقل";
    hint.className = "mk-hint " + (ok >= 2 ? "up" : "");
  }

  function renderVetoes(data) {
    var host = document.getElementById("mkVetoes");
    host.innerHTML = "";
    var hits = 0;
    (data.vetoes || []).forEach(function (item) {
      if (item.hit) hits++;
      host.appendChild(checkRow(!item.hit, item.name, item.detail, item.hit ? "fail" : "pass"));
    });
    if (hits) {
      var note = el("div", "mk-banner mk-banner--warn");
      note.style.marginTop = "12px";
      note.style.marginBottom = "0";
      note.appendChild(el("span", "mk-banner__icon", "⛔"));
      note.appendChild(el("span", "", "تحقّق " + hits + " من شروط الفيتو — " +
        "إشارة الشراء ملغاة وسُقفت الدرجة، مهما بدت المؤشرات الأخرى إيجابية."));
      host.appendChild(note);
    }
  }

  function renderExits(data) {
    var host = document.getElementById("mkExits");
    host.innerHTML = "";
    (data.exits || []).forEach(function (item) {
      host.appendChild(checkRow(!item.hit, item.name, item.detail, item.hit ? "warn" : "idle"));
    });
  }

  // ─────────────── الدرجة ───────────────

  function renderScore(data) {
    var host = document.getElementById("mkScore");
    host.innerHTML = "";

    var score = (data.score || {}).total;
    var bar = el("div", "mk-score");
    var value = el("div", "mk-score__value " + Fmt.dirClass(score));
    value.textContent = score === null || score === undefined ? "—" : Number(score).toFixed(0);
    bar.appendChild(value);

    var track = el("div", "mk-score__track");
    var marker = el("div", "mk-score__marker");
    var pos = score === null || score === undefined ? 50 : (Number(score) + 100) / 2;
    marker.style.left = Math.max(0, Math.min(100, pos)) + "%";
    track.appendChild(marker);
    bar.appendChild(track);
    host.appendChild(bar);

    var badge = M.signalBadge(data.signal);
    badge.style.marginTop = "12px";
    host.appendChild(badge);

    var head = el("div", "mk-hint");
    head.style.margin = "12px 0 6px";
    head.textContent = "المكوّنات السبعة (القيمة × الوزن)";
    host.appendChild(head);

    ((data.score || {}).components || []).forEach(function (component) {
      var row = el("div", "mk-component");
      var label = el("div");
      label.appendChild(el("div", "", component.label));
      label.appendChild(el("div", "mk-component__weight", "وزن " + component.weight + "٪"));
      row.appendChild(label);

      row.appendChild(M.num(Number(component.value).toFixed(0), Fmt.dirClass(component.value)));

      var barWrap = el("div", "mk-component__bar");
      var fill = el("div", "mk-component__fill");
      var width = Math.min(Math.abs(component.value) / 2, 50);
      fill.style.width = width + "%";
      if (component.value >= 0) {
        fill.style.left = "50%";
        fill.style.background = "var(--mk-up)";
      } else {
        fill.style.left = (50 - width) + "%";
        fill.style.background = "var(--mk-down)";
      }
      barWrap.appendChild(fill);
      row.appendChild(barWrap);

      host.appendChild(row);
    });

    ((data.score || {}).adjustments || []).forEach(function (text) {
      var note = el("div", "mk-check__detail");
      note.style.marginTop = "8px";
      note.textContent = "↳ " + text;
      host.appendChild(note);
    });
  }

  // ─────────────── الخطة ───────────────

  /** ``isText`` للقيم التي تحوي كلمات عربية (ألف/مليون/ر.س) حتى لا يعكسها الاتجاه. */
  function planRow(label, value, accent, isText) {
    var row = el("div", "mk-plan-row" + (accent ? " mk-plan-row--accent" : ""));
    row.appendChild(el("span", "mk-plan-row__label", label));
    var node = el("span", "mk-plan-row__value" + (isText ? " mk-plan-row__value--text" : ""));
    if (value instanceof Node) node.appendChild(value); else node.textContent = value;
    row.appendChild(node);
    return row;
  }

  function renderPlan(data) {
    var host = document.getElementById("mkPlan");
    var plan = data.plan || {};
    host.innerHTML = "";

    var state = document.getElementById("mkPlanState");
    state.textContent = plan.acceptable ? "مقبولة" : "مرفوضة";
    state.className = "mk-hint " + (plan.acceptable ? "up" : "down");

    host.appendChild(planRow("سعر الدخول المرجعي", Fmt.price(plan.entry), true));

    var stop = el("span", "down");
    stop.textContent = Fmt.price(plan.stop) + "  (−" + Fmt.pct(plan.stop_pct) + ")";
    host.appendChild(planRow("وقف الخسارة", stop, true));

    var rr = el("span", plan.risk_reward >= 1.8 ? "up" : "down");
    rr.textContent = plan.risk_reward === null || plan.risk_reward === undefined
      ? "—" : Number(plan.risk_reward).toFixed(2);
    host.appendChild(planRow("العائد / المخاطرة", rr));

    host.appendChild(planRow("المخاطرة للسهم الواحد", Fmt.price(plan.risk_per_share, 3)));
    var riskText = Fmt.money(plan.risk_amount) + " ر.س";
    if (plan.risk_amount_base && plan.risk_amount_base !== plan.risk_amount) {
      riskText += " (من " + Fmt.money(plan.risk_amount_base) + ")";
    }
    host.appendChild(planRow("مبلغ المخاطرة", riskText, false, true));
    host.appendChild(planRow("عدد الأسهم", Fmt.int(plan.shares)));
    host.appendChild(planRow("قيمة المركز", Fmt.money(plan.position_value) + " ر.س", false, true));
    host.appendChild(planRow("أقصى خسارة متوقعة", Fmt.money(plan.max_loss) + " ر.س", false, true));

    if (plan.size_factor === 0) {
      host.appendChild(planRow("تعديل السوق", "لا شراء — سوق سلبي", false, true));
    } else if (plan.size_factor && plan.size_factor < 1) {
      host.appendChild(planRow("تعديل السوق",
        Math.round(plan.size_factor * 100) + "٪ من الحجم المعتاد", false, true));
    }

    var ladder = el("div", "mk-ladder");
    (plan.targets || []).forEach(function (target) {
      var item = el("div", "mk-ladder__item");
      var top = el("div", "mk-ladder__top");
      top.appendChild(el("span", "", target.label));
      var right = el("span", "mk-num up");
      right.textContent = Fmt.price(target.price) + "  (" +
        Fmt.pct(target.gain_pct, true) + " · " + target.r_multiple + "R)";
      top.appendChild(right);
      item.appendChild(top);
      item.appendChild(el("div", "mk-ladder__note", target.action));
      ladder.appendChild(item);
    });
    host.appendChild(ladder);

    if (plan.trail_rule) {
      var trail = el("div", "mk-check__detail");
      trail.style.marginTop = "10px";
      trail.textContent = "الوقف المتحرك: " + plan.trail_rule;
      host.appendChild(trail);
    }

    (plan.reasons || []).forEach(function (reason) {
      var note = el("div", "mk-check__detail down");
      note.style.marginTop = "6px";
      note.textContent = "⛔ " + reason;
      host.appendChild(note);
    });
  }

  function renderForecast(data) {
    var host = document.getElementById("mkForecast");
    var forecast = data.forecast || {};
    host.innerHTML = "";

    var range = el("div");
    range.style.fontSize = "19px";
    range.style.fontWeight = "700";
    range.style.direction = "ltr";
    range.style.textAlign = "center";
    range.style.margin = "4px 0 10px";
    range.className = "mk-num";
    range.textContent = Fmt.price(forecast.low) + " — " + Fmt.price(forecast.high);
    host.appendChild(range);

    host.appendChild(planRow("الأفق", forecast.horizon || "—", false, true));
    host.appendChild(planRow("حجم الحركة المحتمل", forecast.move_pct === null ||
      forecast.move_pct === undefined ? "—" : "±" + forecast.move_pct + "٪"));

    var note = el("div", "mk-check__detail");
    note.style.marginTop = "10px";
    note.textContent = forecast.note || "";
    host.appendChild(note);
  }

  function renderLevels(data) {
    var host = document.getElementById("mkLevels");
    var levels = data.levels || {};
    host.innerHTML = "";

    function block(title, rows, cls) {
      var head = el("div", "mk-hint");
      head.style.margin = "8px 0 4px";
      head.textContent = title;
      host.appendChild(head);
      if (!rows.length) {
        host.appendChild(el("div", "mk-check__detail", "لا توجد مستويات واضحة."));
        return;
      }
      rows.forEach(function (level) {
        var row = el("div", "mk-plan-row");
        var left = el("span", "mk-plan-row__label",
          level.touches + " لمسات · " + Fmt.pct(level.distance_pct, true));
        var right = el("span", "mk-plan-row__value " + cls, Fmt.price(level.price));
        row.appendChild(left);
        row.appendChild(right);
        host.appendChild(row);
      });
    }

    block("المقاومات (فوق السعر)", (levels.resistances || []).slice().reverse(), "down");
    block("الدعوم (تحت السعر)", levels.supports || [], "up");
  }

  function renderIndicators(data) {
    var host = document.getElementById("mkIndicators");
    var ind = data.indicators || {};
    host.innerHTML = "";

    var grid = el("div", "mk-grid mk-grid--3");
    [
      ["RSI (14)", ind.rsi, 1, "القوة النسبية — فوق ٧٠ تشبّع شرائي، تحت ٣٠ تشبّع بيعي"],
      ["ADX", ind.adx, 1, "قوة الاتجاه — فوق ٢٠ اتجاه حقيقي"],
      ["+DI", ind.plus_di, 1, "ضغط شرائي"],
      ["−DI", ind.minus_di, 1, "ضغط بيعي"],
      ["MACD هستوغرام", ind.macd_hist, 3, "الزخم — موجب ومتزايد = تسارع صاعد"],
      ["ATR", ind.atr, 2, "متوسط المدى الحقيقي — أساس حساب الوقف"],
      ["ATR كنسبة", ind.atr_pct, 2, "تذبذب السهم اليومي كنسبة من سعره"],
      ["نسبة الحجم", ind.volume_ratio, 2, "الحجم الحالي مقارنة بمتوسط ٢٠ فترة"],
      ["التذبذب السنوي", ind.volatility, 1, "الانحراف المعياري السنوي التقريبي"],
      ["ستوكاستك %K", ind.stoch_k, 1, "موقع الإغلاق داخل نطاق ١٤ فترة"],
      ["المتوسط السريع", ind.ema_fast, 2, "المتوسط الأقصر — مرجع الوقف المتحرك"],
      ["البُعد عن المتوسط", ind.distance_from_fast_pct, 2, "تمدّد السعر فوق/تحت المتوسط السريع"]
    ].forEach(function (row) {
      var card = el("div", "mk-stat");
      card.title = row[3];
      card.appendChild(el("div", "mk-stat__label", row[0]));
      var value = el("div", "mk-stat__value mk-num");
      value.style.fontSize = "18px";
      value.textContent = row[1] === null || row[1] === undefined
        ? "—" : Number(row[1]).toFixed(row[2]);
      card.appendChild(value);
      card.appendChild(el("div", "mk-stat__meta", row[3]));
      grid.appendChild(card);
    });
    host.appendChild(grid);

    if (data.divergence) {
      var note = el("div", "mk-banner mk-banner--" +
        (data.divergence === "bullish" ? "info" : "warn"));
      note.style.marginTop = "14px";
      note.style.marginBottom = "0";
      note.appendChild(el("span", "mk-banner__icon", data.divergence === "bullish" ? "🔵" : "🟠"));
      note.appendChild(el("span", "", data.divergence === "bullish"
        ? "دايفرجنس صاعد: قاع سعري أدنى مقابل قاع RSI أعلى — إشارة انعكاس محتملة للأعلى."
        : "دايفرجنس هابط: قمة سعرية أعلى مقابل قمة RSI أدنى — تحذير انعكاس، وهو أحد شروط الفيتو."));
      host.appendChild(note);
    }
  }

  // ─────────────── التحميل ───────────────

  function syncTimeframeButtons(active) {
    Array.prototype.forEach.call(
      document.getElementById("mkTimeframes").querySelectorAll("button"),
      function (btn) { btn.classList.toggle("is-active", btn.dataset.timeframe === active); }
    );
  }

  function load() {
    var extra = { timeframe: timeframe };
    M.fetchJson("/api/market/symbol/" + code + "?" + State.query(extra))
      .then(function (data) {
        if (data.error) throw new Error(data.error);
        report = data;
        timeframe = data.timeframe;
        syncTimeframeButtons(timeframe);
        renderAlerts(data);
        renderQuote(data);
        renderChart(data);
        renderGates(data);
        renderSetups(data);
        renderConfirmations(data);
        renderVetoes(data);
        renderExits(data);
        renderScore(data);
        renderPlan(data);
        renderForecast(data);
        renderLevels(data);
        renderIndicators(data);
      })
      .catch(function (error) {
        document.getElementById("mkQuote").innerHTML =
          '<div class="mk-empty">تعذّر تحميل التحليل: ' + error.message + "</div>";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("mkTimeframes").addEventListener("click", function (event) {
      var btn = event.target.closest("button[data-timeframe]");
      if (!btn || btn.dataset.timeframe === timeframe) return;
      timeframe = btn.dataset.timeframe;
      syncTimeframeButtons(timeframe);
      load();
    });

    document.querySelectorAll("input[data-layer]").forEach(function (input) {
      input.addEventListener("change", function () {
        if (chart) chart.setVisibility(input.dataset.layer, input.checked);
      });
    });

    State.onChange(function () {
      timeframe = null;  // كل نمط له إطاره الزمني الافتراضي
      load();
    });

    load();
    void report;
  });
})();
