/* ═══════════════════════════════════════════════════════════
   وظائف مشتركة بين صفحات السوق: حالة المستخدم (النمط، رأس المال،
   المخاطرة)، البحث، وأدوات بناء العناصر.
   ═══════════════════════════════════════════════════════════ */
(function (global) {
  "use strict";

  var STORAGE_KEY = "mk_prefs_v1";

  var State = {
    profile: document.body.dataset.profile || "swing",
    capital: parseFloat(document.body.dataset.capital) || 100000,
    risk: parseFloat(document.body.dataset.risk) || 1,
    listeners: []
  };

  function loadPrefs() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      var saved = JSON.parse(raw);
      // الاستعلام في الرابط له الأولوية على ما هو محفوظ محليًا.
      var params = new URLSearchParams(location.search);
      if (!params.has("profile") && saved.profile) State.profile = saved.profile;
      if (!params.has("capital") && saved.capital) State.capital = saved.capital;
      if (!params.has("risk") && saved.risk) State.risk = saved.risk;
    } catch (err) { /* تخزين محلي غير متاح — نكمل بالقيم الافتراضية */ }
  }

  function savePrefs() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        profile: State.profile, capital: State.capital, risk: State.risk
      }));
    } catch (err) { /* تجاهل */ }
  }

  State.onChange = function (fn) { State.listeners.push(fn); };

  State.emit = function () {
    savePrefs();
    State.listeners.forEach(function (fn) {
      try { fn(State); } catch (err) { console.error(err); }
    });
  };

  State.query = function (extra) {
    var params = new URLSearchParams();
    params.set("profile", State.profile);
    params.set("capital", String(State.capital));
    params.set("risk", String(State.risk));
    Object.keys(extra || {}).forEach(function (key) {
      if (extra[key] !== null && extra[key] !== undefined) params.set(key, extra[key]);
    });
    return params.toString();
  };

  // ─────────────── أدوات تنسيق ───────────────

  var Fmt = {
    price: function (value, digits) {
      if (value === null || value === undefined || isNaN(value)) return "—";
      return Number(value).toLocaleString("en-US", {
        minimumFractionDigits: digits === undefined ? 2 : digits,
        maximumFractionDigits: digits === undefined ? 2 : digits
      });
    },
    pct: function (value, withSign) {
      if (value === null || value === undefined || isNaN(value)) return "—";
      var sign = withSign && value > 0 ? "+" : "";
      return sign + Number(value).toFixed(2) + "%";
    },
    int: function (value) {
      if (value === null || value === undefined || isNaN(value)) return "—";
      return Number(value).toLocaleString("en-US", { maximumFractionDigits: 0 });
    },
    /** يُعيد {num, suffix} — الرقم لاتيني و اللاحقة عربية، كلٌّ في عنصره. */
    moneyParts: function (value) {
      if (value === null || value === undefined || isNaN(value)) return { num: "—", suffix: "" };
      if (Math.abs(value) >= 1e9) return { num: (value / 1e9).toFixed(2), suffix: "مليار" };
      if (Math.abs(value) >= 1e6) return { num: (value / 1e6).toFixed(2), suffix: "مليون" };
      if (Math.abs(value) >= 1e3) return { num: (value / 1e3).toFixed(1), suffix: "ألف" };
      return { num: Number(value).toFixed(0), suffix: "" };
    },
    money: function (value) {
      var parts = Fmt.moneyParts(value);
      return parts.suffix ? parts.num + " " + parts.suffix : parts.num;
    },
    dirClass: function (value) {
      if (value === null || value === undefined || isNaN(value) || value === 0) return "flat";
      return value > 0 ? "up" : "down";
    },
    timeAgo: function (seconds) {
      if (!seconds) return "—";
      var diff = Math.max(0, Math.floor(Date.now() / 1000 - seconds));
      if (diff < 60) return "قبل لحظات";
      if (diff < 3600) return "قبل " + Math.floor(diff / 60) + " دقيقة";
      if (diff < 86400) return "قبل " + Math.floor(diff / 3600) + " ساعة";
      return "قبل " + Math.floor(diff / 86400) + " يوم";
    }
  };

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function num(value, className) {
    var node = el("span", "mk-num" + (className ? " " + className : ""));
    node.textContent = value;
    return node;
  }

  function signalBadge(signal) {
    if (!signal) return el("span", "mk-badge mk-badge--hold", "—");
    var side = signal.side || "hold";
    var node = el("span", "mk-badge mk-badge--" + side);
    node.textContent = (signal.icon ? signal.icon + " " : "") + (signal.label || "—");
    return node;
  }

  function scoreCell(score) {
    var wrap = el("span", "mk-num " + Fmt.dirClass(score));
    wrap.textContent = score === null || score === undefined ? "—" : Number(score).toFixed(0);
    return wrap;
  }

  function fetchJson(url) {
    return fetch(url, { headers: { "Accept": "application/json" } }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  // ─────────────── البحث ───────────────

  function initSearch() {
    var input = document.getElementById("mkSearch");
    var results = document.getElementById("mkSearchResults");
    if (!input || !results) return;

    var timer = null;
    var items = [];
    var cursor = -1;

    function close() { results.innerHTML = ""; items = []; cursor = -1; }

    function go(code) {
      location.href = "/market/" + code + "?" + State.query();
    }

    function render(rows) {
      results.innerHTML = "";
      items = rows;
      cursor = -1;
      rows.forEach(function (row, i) {
        var item = el("div", "mk-search__item");
        item.setAttribute("role", "option");
        item.appendChild(el("span", "mk-search__code", row.code));
        item.appendChild(el("span", "", row.name_ar));
        item.appendChild(el("span", "mk-search__sector", row.sector));
        item.addEventListener("mousedown", function (event) {
          event.preventDefault();
          go(row.code);
        });
        item.dataset.index = String(i);
        results.appendChild(item);
      });
    }

    function highlight() {
      Array.prototype.forEach.call(results.children, function (child, i) {
        child.classList.toggle("is-active", i === cursor);
      });
    }

    input.addEventListener("input", function () {
      clearTimeout(timer);
      var query = input.value.trim();
      if (query.length < 1) { close(); return; }
      timer = setTimeout(function () {
        fetchJson("/api/market/search?q=" + encodeURIComponent(query))
          .then(function (data) { render(data.results || []); })
          .catch(function () { close(); });
      }, 180);
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown" && items.length) {
        event.preventDefault();
        cursor = (cursor + 1) % items.length;
        highlight();
      } else if (event.key === "ArrowUp" && items.length) {
        event.preventDefault();
        cursor = (cursor - 1 + items.length) % items.length;
        highlight();
      } else if (event.key === "Enter") {
        if (cursor >= 0 && items[cursor]) { go(items[cursor].code); return; }
        var direct = input.value.trim().replace(/\D/g, "");
        if (direct.length === 4) go(direct);
      } else if (event.key === "Escape") {
        close();
        input.blur();
      }
    });

    input.addEventListener("blur", function () { setTimeout(close, 120); });
  }

  // ─────────────── أدوات التحكم العلوية ───────────────

  function initControls() {
    var switcher = document.getElementById("mkProfileSwitch");
    var capitalInput = document.getElementById("mkCapital");
    var riskInput = document.getElementById("mkRisk");
    var hint = document.getElementById("mkProfileHint");

    function syncInputs() {
      if (capitalInput) capitalInput.value = String(Math.round(State.capital));
      if (riskInput) riskInput.value = String(State.risk);
      if (switcher) {
        Array.prototype.forEach.call(switcher.querySelectorAll("button"), function (btn) {
          var active = btn.dataset.profile === State.profile;
          btn.classList.toggle("is-active", active);
          btn.setAttribute("aria-selected", active ? "true" : "false");
        });
      }
    }

    if (switcher) {
      switcher.addEventListener("click", function (event) {
        var btn = event.target.closest("button[data-profile]");
        if (!btn || btn.dataset.profile === State.profile) return;
        State.profile = btn.dataset.profile;
        syncInputs();
        State.emit();
      });
    }

    function bindNumber(input, key, min, max) {
      if (!input) return;
      var debounce = null;
      input.addEventListener("input", function () {
        clearTimeout(debounce);
        debounce = setTimeout(function () {
          var value = parseFloat(input.value);
          if (isNaN(value)) return;
          State[key] = Math.max(min, Math.min(max, value));
          State.emit();
        }, 450);
      });
      input.addEventListener("blur", function () {
        var value = parseFloat(input.value);
        if (isNaN(value)) { input.value = String(State[key]); return; }
        input.value = String(Math.max(min, Math.min(max, value)));
      });
    }

    bindNumber(capitalInput, "capital", 1000, 1e9);
    bindNumber(riskInput, "risk", 0.05, 5);

    syncInputs();

    fetchJson("/api/market/profiles").then(function (data) {
      global.MarketProfiles = data;
      function updateHint() {
        if (!hint) return;
        var current = (data.profiles || []).filter(function (p) {
          return p.key === State.profile;
        })[0];
        if (!current) { hint.textContent = ""; return; }
        hint.textContent = current.horizon +
          " · متوسطات " + current.emas.join("/") +
          " · أدنى عائد/مخاطرة " + current.min_rr;
      }
      updateHint();
      State.onChange(updateHint);
    }).catch(function () { /* التلميح اختياري */ });
  }

  loadPrefs();

  global.Market = {
    State: State,
    Fmt: Fmt,
    el: el,
    num: num,
    signalBadge: signalBadge,
    scoreCell: scoreCell,
    fetchJson: fetchJson
  };

  document.addEventListener("DOMContentLoaded", function () {
    initSearch();
    initControls();
  });
})(window);
