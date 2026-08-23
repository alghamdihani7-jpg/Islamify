/* ═══════════════════════════════════════════════════════════════
   شارت الشموع — dependency-free candlestick chart on <canvas>.

   يرسم: الشموع، المتوسطات المتحركة، مستويات الدعم والمقاومة،
   خطوط الاتجاه، الحجم مع متوسطه، ومستويات خطة التنفيذ
   (الدخول / وقف الخسارة / الأهداف)، مع مؤشر تقاطع وتلميح.

   لا يعتمد على أي مكتبة خارجية — كل شيء رسم يدوي على 2D context.
   ═══════════════════════════════════════════════════════════════ */
(function (global) {
  "use strict";

  var MONTHS_AR = ["ينا", "فبر", "مار", "أبر", "مايو", "يون",
                   "يول", "أغس", "سبت", "أكت", "نوف", "ديس"];

  var COLORS = {
    up: "#16c784",
    down: "#ea3943",
    upWick: "#0f9d6b",
    downWick: "#c02832",
    grid: "rgba(255,255,255,.05)",
    axis: "#5b6b7e",
    text: "#8496ab",
    emaFast: "#f0b90b",
    emaMid: "#3b82f6",
    emaSlow: "#a855f7",
    level: "#f0913b",
    trendDown: "#4f9dfd",
    trendUp: "#16c784",
    volMa: "#f0b90b",
    crosshair: "rgba(255,255,255,.28)",
    entry: "#e6edf5",
    stop: "#ea3943",
    target: "#16c784"
  };

  function fmtPrice(value, digits) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    var d = digits === undefined ? (Math.abs(value) >= 100 ? 1 : 2) : digits;
    return value.toFixed(d);
  }

  function fmtVolume(value) {
    if (!value && value !== 0) return "—";
    if (value >= 1e9) return (value / 1e9).toFixed(2) + "B";
    if (value >= 1e6) return (value / 1e6).toFixed(2) + "M";
    if (value >= 1e3) return (value / 1e3).toFixed(1) + "K";
    return String(Math.round(value));
  }

  function fmtDate(seconds, withTime) {
    var d = new Date(seconds * 1000);
    var label = d.getDate() + " " + MONTHS_AR[d.getMonth()];
    if (d.getFullYear() !== new Date().getFullYear()) label += " " + d.getFullYear();
    if (withTime) {
      label += " " + String(d.getHours()).padStart(2, "0") +
               ":" + String(d.getMinutes()).padStart(2, "0");
    }
    return label;
  }

  /** خطوة سعرية "مريحة" (1/2/5 × 10^n) قريبة من المطلوب. */
  function niceStep(raw) {
    if (!(raw > 0)) return 1;
    var exp = Math.floor(Math.log(raw) / Math.LN10);
    var base = Math.pow(10, exp);
    var norm = raw / base;
    var step = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
    return step * base;
  }

  function CandleChart(wrapEl, options) {
    this.wrap = wrapEl;
    this.options = options || {};
    this.canvas = document.createElement("canvas");
    this.wrap.appendChild(this.canvas);
    this.ctx = this.canvas.getContext("2d");

    this.tooltip = document.createElement("div");
    this.tooltip.className = "mk-chart-tooltip";
    this.wrap.appendChild(this.tooltip);

    this.data = null;
    this.view = { start: 0, count: 0 };
    this.hover = null;
    this.drag = null;
    this.visible = {
      ema: true,
      levels: true,
      trendlines: true,
      plan: true,
      volume: true
    };

    this._bind();
    this._resizeObserver();
  }

  CandleChart.prototype._bind = function () {
    var self = this;

    this.canvas.addEventListener("mousemove", function (event) {
      var rect = self.canvas.getBoundingClientRect();
      var x = event.clientX - rect.left;
      var y = event.clientY - rect.top;

      if (self.drag) {
        var shift = Math.round((self.drag.x - x) / Math.max(self._barWidth(), 0.5));
        self._setStart(self.drag.start + shift);
        self.render();
        return;
      }
      self.hover = { x: x, y: y };
      self.render();
    });

    this.canvas.addEventListener("mouseleave", function () {
      self.hover = null;
      self.drag = null;
      self.tooltip.classList.remove("is-visible");
      self.render();
    });

    this.canvas.addEventListener("mousedown", function (event) {
      var rect = self.canvas.getBoundingClientRect();
      self.drag = { x: event.clientX - rect.left, start: self.view.start };
      self.canvas.style.cursor = "grabbing";
    });

    window.addEventListener("mouseup", function () {
      if (!self.drag) return;
      self.drag = null;
      self.canvas.style.cursor = "crosshair";
    });

    this.canvas.addEventListener("wheel", function (event) {
      if (!self.data) return;
      event.preventDefault();
      var factor = event.deltaY > 0 ? 1.15 : 0.87;
      var total = self.data.candles.length;
      var next = Math.round(self.view.count * factor);
      next = Math.max(20, Math.min(total, next));

      // تكبير حول موضع المؤشر بدل بداية النطاق.
      var rect = self.canvas.getBoundingClientRect();
      var ratio = (event.clientX - rect.left - self._padLeft()) /
                  Math.max(self._plotWidth(), 1);
      ratio = Math.max(0, Math.min(1, ratio));
      var anchor = self.view.start + ratio * self.view.count;

      self.view.count = next;
      self._setStart(Math.round(anchor - ratio * next));
      self.render();
    }, { passive: false });
  };

  CandleChart.prototype._resizeObserver = function () {
    var self = this;
    if (typeof ResizeObserver === "function") {
      this._ro = new ResizeObserver(function () { self.render(); });
      this._ro.observe(this.wrap);
    } else {
      window.addEventListener("resize", function () { self.render(); });
    }
  };

  CandleChart.prototype._setStart = function (start) {
    var total = this.data ? this.data.candles.length : 0;
    var max = Math.max(0, total - this.view.count);
    this.view.start = Math.max(0, Math.min(max, start));
  };

  CandleChart.prototype._padLeft = function () { return 8; };
  CandleChart.prototype._padRight = function () { return 64; };
  CandleChart.prototype._plotWidth = function () {
    return Math.max(10, this.width - this._padLeft() - this._padRight());
  };
  CandleChart.prototype._barWidth = function () {
    return this._plotWidth() / Math.max(this.view.count, 1);
  };

  CandleChart.prototype.setVisibility = function (key, value) {
    this.visible[key] = !!value;
    this.render();
  };

  CandleChart.prototype.setData = function (data) {
    var keepView = this.data &&
                   data.candles.length === this.data.candles.length &&
                   data.code === this.data.code;
    this.data = data;
    if (!keepView) {
      var total = data.candles.length;
      var initial = Math.min(total, this.options.initialBars || 130);
      this.view = { start: Math.max(0, total - initial), count: initial };
    }
    this.render();
  };

  CandleChart.prototype.render = function () {
    if (!this.data || !this.data.candles || !this.data.candles.length) return;

    var dpr = window.devicePixelRatio || 1;
    var rect = this.wrap.getBoundingClientRect();
    this.width = Math.max(rect.width, 320);
    this.height = Math.max(rect.height, 220);

    this.canvas.width = Math.round(this.width * dpr);
    this.canvas.height = Math.round(this.height * dpr);
    var ctx = this.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, this.width, this.height);

    var axisH = 24;
    var gap = 8;
    var volH = this.visible.volume ? Math.round((this.height - axisH) * 0.2) : 0;
    var priceH = this.height - axisH - volH - (volH ? gap : 0);

    this.geo = {
      priceTop: 6,
      priceBottom: priceH,
      volTop: priceH + gap,
      volBottom: priceH + gap + volH,
      axisY: this.height - axisH,
      left: this._padLeft(),
      right: this.width - this._padRight()
    };

    var slice = this._slice();
    this._computeScale(slice);
    this._computeTags();
    this._drawGrid(slice);
    // الخطة قبل المستويات: بطاقات الدخول/الوقف/الأهداف لها أولوية على المحور.
    if (this.visible.plan) this._drawPlan();
    if (this.visible.levels) this._drawLevels();
    if (this.visible.trendlines) this._drawTrendlines();
    this._drawCandles(slice);
    if (this.visible.ema) this._drawEmas();
    if (volH) this._drawVolume(slice);
    this._drawAxes(slice);
    this._drawCrosshair(slice);
  };

  CandleChart.prototype._slice = function () {
    var start = this.view.start;
    var end = Math.min(this.data.candles.length, start + this.view.count);
    return { start: start, end: end, items: this.data.candles.slice(start, end) };
  };

  CandleChart.prototype._computeScale = function (slice) {
    var min = Infinity, max = -Infinity;

    slice.items.forEach(function (candle) {
      if (candle.l < min) min = candle.l;
      if (candle.h > max) max = candle.h;
    });

    var series = this.data.series || {};
    var self = this;
    if (this.visible.ema) {
      ["ema_fast", "ema_mid", "ema_slow"].forEach(function (key) {
        var arr = series[key];
        if (!arr) return;
        for (var i = slice.start; i < slice.end; i++) {
          var v = arr[i];
          if (v === null || v === undefined) continue;
          if (v < min) min = v;
          if (v > max) max = v;
        }
      });
    }

    // ضمّ المستويات القريبة فقط، حتى لا يسحق مستوى بعيد مقياس الرسم.
    var extras = [];
    if (this.visible.levels) {
      (this.data.levels || []).forEach(function (lv) { extras.push(lv.price); });
    }
    if (this.visible.plan && this.data.plan) {
      var plan = this.data.plan;
      [plan.entry, plan.stop].forEach(function (v) { if (v) extras.push(v); });
      (plan.targets || []).forEach(function (t) { if (t.price) extras.push(t.price); });
    }
    var span = max - min || 1;
    extras.forEach(function (value) {
      if (value === null || value === undefined) return;
      if (value >= min - span * 0.55 && value <= max + span * 0.55) {
        if (value < min) min = value;
        if (value > max) max = value;
      }
    });

    if (!isFinite(min) || !isFinite(max)) { min = 0; max = 1; }
    if (max === min) { max = min + 1; }

    var pad = (max - min) * 0.07;
    this.scale = { min: min - pad, max: max + pad };
    void self;
  };

  /**
   * يحجز مواضع بطاقات الأسعار على المحور الأيمن بترتيب أولوية،
   * ويسقط أي بطاقة تتراكب مع بطاقة أعلى أولوية. بدون هذا تتكدّس
   * بطاقات الدعوم والمقاومات وخطة التنفيذ فوق بعضها فتصبح غير مقروءة.
   */
  CandleChart.prototype._computeTags = function () {
    var wanted = [];

    if (this.visible.plan && this.data.plan) {
      var plan = this.data.plan;
      if (plan.entry) {
        wanted.push({ price: plan.entry, label: "دخول", color: COLORS.entry, owner: "plan" });
      }
      if (plan.stop) {
        wanted.push({ price: plan.stop, label: "وقف", color: COLORS.stop, owner: "plan" });
      }
      (plan.targets || []).forEach(function (target, i) {
        if (target.price) {
          wanted.push({
            price: target.price, label: "هدف " + (i + 1),
            color: COLORS.target, owner: "plan"
          });
        }
      });
    }
    if (this.visible.levels) {
      (this.data.levels || []).forEach(function (level) {
        wanted.push({
          price: level.price, label: fmtPrice(level.price),
          color: COLORS.level, owner: "level"
        });
      });
    }

    var taken = [];
    var self = this;
    var minGap = 15;

    wanted.forEach(function (tag) {
      var y = self._yPrice(tag.price);
      if (y < self.geo.priceTop || y > self.geo.priceBottom) return;
      for (var i = 0; i < taken.length; i++) {
        if (Math.abs(taken[i].y - y) < minGap) return;   // متراكبة — تُسقط بطاقتها
      }
      tag.y = y;
      taken.push(tag);
    });

    this.tags = taken;
  };

  CandleChart.prototype._tagFor = function (price, owner) {
    var tags = this.tags || [];
    for (var i = 0; i < tags.length; i++) {
      if (tags[i].owner === owner && Math.abs(tags[i].price - price) < 1e-9) return tags[i];
    }
    return null;
  };

  CandleChart.prototype._yPrice = function (price) {
    var g = this.geo, s = this.scale;
    var ratio = (price - s.min) / (s.max - s.min);
    return g.priceBottom - ratio * (g.priceBottom - g.priceTop);
  };

  CandleChart.prototype._xIndex = function (index) {
    return this.geo.left + (index - this.view.start + 0.5) * this._barWidth();
  };

  CandleChart.prototype._indexAtX = function (x) {
    var i = Math.floor((x - this.geo.left) / this._barWidth()) + this.view.start;
    return Math.max(this.view.start, Math.min(this.view.start + this.view.count - 1, i));
  };

  CandleChart.prototype._drawGrid = function (slice) {
    var ctx = this.ctx, g = this.geo, s = this.scale;
    var target = Math.max(3, Math.round((g.priceBottom - g.priceTop) / 58));
    var step = niceStep((s.max - s.min) / target);
    var first = Math.ceil(s.min / step) * step;

    ctx.save();
    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = COLORS.text;
    ctx.font = "11px " + (this.options.monoFont || "ui-monospace, Menlo, monospace");
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";

    for (var price = first; price <= s.max; price += step) {
      var y = Math.round(this._yPrice(price)) + 0.5;
      if (y < g.priceTop || y > g.priceBottom) continue;
      ctx.beginPath();
      ctx.moveTo(g.left, y);
      ctx.lineTo(g.right, y);
      ctx.stroke();

      var blocked = (this.tags || []).some(function (tag) {
        return Math.abs(tag.y - y) < 13;
      });
      if (!blocked) ctx.fillText(fmtPrice(price), g.right + 7, y);
    }

    // شبكة رأسية عند علامات الوقت
    var ticks = this._timeTicks(slice);
    ctx.beginPath();
    for (var t = 0; t < ticks.length; t++) {
      var x = Math.round(this._xIndex(ticks[t].index)) + 0.5;
      ctx.moveTo(x, g.priceTop);
      ctx.lineTo(x, g.axisY);
    }
    ctx.stroke();
    ctx.restore();
  };

  CandleChart.prototype._timeTicks = function (slice) {
    var maxTicks = Math.max(2, Math.floor(this._plotWidth() / 88));
    var stride = Math.max(1, Math.ceil(slice.items.length / maxTicks));
    var ticks = [];
    for (var i = slice.items.length - 1; i >= 0; i -= stride) {
      ticks.push({ index: slice.start + i, time: slice.items[i].t });
    }
    return ticks.reverse();
  };

  CandleChart.prototype._drawCandles = function (slice) {
    var ctx = this.ctx;
    var bw = this._barWidth();
    var body = Math.max(1, Math.min(bw * 0.66, 16));
    var self = this;

    slice.items.forEach(function (candle, offset) {
      var index = slice.start + offset;
      var x = self._xIndex(index);
      var rising = candle.c >= candle.o;

      ctx.strokeStyle = rising ? COLORS.upWick : COLORS.downWick;
      ctx.lineWidth = Math.max(1, Math.min(bw * 0.12, 1.6));
      ctx.beginPath();
      ctx.moveTo(Math.round(x) + 0.5, self._yPrice(candle.h));
      ctx.lineTo(Math.round(x) + 0.5, self._yPrice(candle.l));
      ctx.stroke();

      var yOpen = self._yPrice(candle.o);
      var yClose = self._yPrice(candle.c);
      var top = Math.min(yOpen, yClose);
      var height = Math.max(Math.abs(yClose - yOpen), 1);

      ctx.fillStyle = rising ? COLORS.up : COLORS.down;
      ctx.fillRect(Math.round(x - body / 2), Math.round(top), Math.round(body), Math.round(height));
    });
  };

  CandleChart.prototype._drawSeriesLine = function (values, color, width) {
    if (!values) return;
    var ctx = this.ctx, g = this.geo;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = width || 1.4;
    ctx.lineJoin = "round";
    ctx.beginPath();

    var started = false;
    for (var i = this.view.start; i < this.view.start + this.view.count; i++) {
      var value = values[i];
      if (value === null || value === undefined) { started = false; continue; }
      var x = this._xIndex(i);
      var y = this._yPrice(value);
      if (y < g.priceTop - 40 || y > g.priceBottom + 40) { started = false; continue; }
      if (!started) { ctx.moveTo(x, y); started = true; }
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  };

  CandleChart.prototype._drawEmas = function () {
    var series = this.data.series || {};
    this._drawSeriesLine(series.ema_slow, COLORS.emaSlow, 1.3);
    this._drawSeriesLine(series.ema_mid, COLORS.emaMid, 1.4);
    this._drawSeriesLine(series.ema_fast, COLORS.emaFast, 1.7);
  };

  CandleChart.prototype._drawHLine = function (price, color, label, dash, owner) {
    var ctx = this.ctx, g = this.geo;
    var y = this._yPrice(price);
    if (y < g.priceTop || y > g.priceBottom) return;

    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.setLineDash(dash || [5, 4]);
    ctx.beginPath();
    ctx.moveTo(g.left, Math.round(y) + 0.5);
    ctx.lineTo(g.right, Math.round(y) + 0.5);
    ctx.stroke();
    ctx.setLineDash([]);

    if (label && this._tagFor(price, owner)) {
      ctx.font = "10.5px " + (this.options.monoFont || "ui-monospace, Menlo, monospace");
      var text = label;
      var w = ctx.measureText(text).width + 10;
      ctx.fillStyle = color;
      ctx.fillRect(g.right + 2, y - 8, Math.min(w, this._padRight() - 4), 16);
      ctx.fillStyle = "#0b0f14";
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";
      ctx.fillText(text, g.right + 7, y);
    }
    ctx.restore();
  };

  CandleChart.prototype._drawLevels = function () {
    var self = this;
    (this.data.levels || []).forEach(function (level) {
      self._drawHLine(level.price, COLORS.level, fmtPrice(level.price), [5, 4], "level");
    });
  };

  CandleChart.prototype._drawPlan = function () {
    var plan = this.data.plan;
    if (!plan) return;
    if (plan.entry) this._drawHLine(plan.entry, COLORS.entry, "دخول", [2, 3], "plan");
    if (plan.stop) this._drawHLine(plan.stop, COLORS.stop, "وقف", [6, 3], "plan");
    var self = this;
    (plan.targets || []).forEach(function (target, i) {
      if (target.price) {
        self._drawHLine(target.price, COLORS.target, "هدف " + (i + 1), [6, 3], "plan");
      }
    });
  };

  CandleChart.prototype._drawTrendlines = function () {
    var lines = this.data.trendlines || {};
    var self = this;
    var lastIndex = this.data.candles.length - 1;

    ["down", "up"].forEach(function (key) {
      var line = lines[key];
      if (!line) return;
      // اللون حسب ميل الخط الفعلي، لا حسب مصدره: خط دعم هابط يجب ألا يظهر أخضر.
      var color = line.direction === "down" ? COLORS.trendDown : COLORS.trendUp;
      var startIndex = Math.max(line.start_index, self.view.start);
      var endIndex = lastIndex;
      if (endIndex <= startIndex) return;

      var y1 = line.slope * startIndex + (line.value_now - line.slope * lastIndex);
      var y2 = line.value_now;

      var ctx = self.ctx, g = self.geo;
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.7;
      ctx.beginPath();
      ctx.moveTo(self._xIndex(startIndex), self._yPrice(y1));
      ctx.lineTo(self._xIndex(endIndex), self._yPrice(y2));
      ctx.stroke();
      ctx.restore();
      void g;
    });
  };

  CandleChart.prototype._drawVolume = function (slice) {
    var ctx = this.ctx, g = this.geo;
    var maxVol = 0;
    slice.items.forEach(function (c) { if (c.v > maxVol) maxVol = c.v; });
    if (!maxVol) return;

    var bw = this._barWidth();
    var body = Math.max(1, Math.min(bw * 0.66, 16));
    var height = g.volBottom - g.volTop;
    var self = this;

    slice.items.forEach(function (candle, offset) {
      var index = slice.start + offset;
      var x = self._xIndex(index);
      var h = Math.max(1, candle.v / maxVol * height);
      ctx.fillStyle = candle.c >= candle.o ? "rgba(22,199,132,.5)" : "rgba(234,57,67,.5)";
      ctx.fillRect(Math.round(x - body / 2), Math.round(g.volBottom - h), Math.round(body), Math.round(h));
    });

    var volMa = (this.data.series || {}).volume_ma;
    if (volMa) {
      ctx.save();
      ctx.strokeStyle = COLORS.volMa;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      var started = false;
      for (var i = slice.start; i < slice.end; i++) {
        var value = volMa[i];
        if (value === null || value === undefined) { started = false; continue; }
        var y = g.volBottom - Math.min(value / maxVol, 1.2) * height;
        var x = self._xIndex(i);
        if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.restore();
    }

    ctx.save();
    ctx.fillStyle = COLORS.text;
    ctx.font = "10px " + (this.options.monoFont || "ui-monospace, Menlo, monospace");
    ctx.textBaseline = "top";
    ctx.textAlign = "left";
    ctx.fillText("الحجم " + fmtVolume(maxVol), g.right + 7, g.volTop + 2);
    ctx.restore();
  };

  CandleChart.prototype._drawAxes = function (slice) {
    var ctx = this.ctx, g = this.geo;
    ctx.save();
    ctx.strokeStyle = "rgba(255,255,255,.08)";
    ctx.beginPath();
    ctx.moveTo(g.left, Math.round(g.axisY) + 0.5);
    ctx.lineTo(g.right, Math.round(g.axisY) + 0.5);
    ctx.stroke();

    ctx.fillStyle = COLORS.text;
    ctx.font = "10.5px sans-serif";
    ctx.textBaseline = "top";
    ctx.textAlign = "center";

    var withTime = this._isIntraday();
    var ticks = this._timeTicks(slice);
    for (var i = 0; i < ticks.length; i++) {
      var x = this._xIndex(ticks[i].index);
      if (x < g.left + 20 || x > g.right - 20) continue;
      ctx.fillText(fmtDate(ticks[i].time, withTime), x, g.axisY + 6);
    }
    ctx.restore();
  };

  CandleChart.prototype._isIntraday = function () {
    var candles = this.data.candles;
    if (candles.length < 3) return false;
    return (candles[1].t - candles[0].t) < 86400;
  };

  CandleChart.prototype._drawCrosshair = function (slice) {
    if (!this.hover) { this.tooltip.classList.remove("is-visible"); return; }
    var ctx = this.ctx, g = this.geo;
    var x = this.hover.x, y = this.hover.y;
    if (x < g.left || x > g.right || y < g.priceTop || y > g.axisY) {
      this.tooltip.classList.remove("is-visible");
      return;
    }

    var index = this._indexAtX(x);
    var candle = this.data.candles[index];
    if (!candle) return;
    var snapX = this._xIndex(index);

    ctx.save();
    ctx.strokeStyle = COLORS.crosshair;
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(Math.round(snapX) + 0.5, g.priceTop);
    ctx.lineTo(Math.round(snapX) + 0.5, g.axisY);
    ctx.moveTo(g.left, Math.round(y) + 0.5);
    ctx.lineTo(g.right, Math.round(y) + 0.5);
    ctx.stroke();
    ctx.setLineDash([]);

    if (y <= g.priceBottom) {
      var ratio = (g.priceBottom - y) / (g.priceBottom - g.priceTop);
      var price = this.scale.min + ratio * (this.scale.max - this.scale.min);
      ctx.fillStyle = "#2b3a4d";
      ctx.fillRect(g.right + 2, y - 9, this._padRight() - 6, 18);
      ctx.fillStyle = "#e6edf5";
      ctx.font = "11px " + (this.options.monoFont || "ui-monospace, Menlo, monospace");
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";
      ctx.fillText(fmtPrice(price), g.right + 7, y);
    }
    ctx.restore();

    this._renderTooltip(candle, index, snapX, y);
    void slice;
  };

  CandleChart.prototype._renderTooltip = function (candle, index, x, y) {
    var series = this.data.series || {};
    var meta = this.data.seriesMeta || {};
    var changePct = null;
    if (index > 0) {
      var prev = this.data.candles[index - 1].c;
      if (prev) changePct = (candle.c - prev) / prev * 100;
    }

    var rows = [
      ["افتتاح", fmtPrice(candle.o)],
      ["أعلى", fmtPrice(candle.h)],
      ["أدنى", fmtPrice(candle.l)],
      ["إغلاق", fmtPrice(candle.c)],
      ["التغير", changePct === null ? "—" : (changePct >= 0 ? "+" : "") + changePct.toFixed(2) + "%"],
      ["الحجم", fmtVolume(candle.v)]
    ];

    if (this.visible.ema) {
      [["ema_fast", meta.ema_fast_period], ["ema_mid", meta.ema_mid_period],
       ["ema_slow", meta.ema_slow_period]].forEach(function (pair) {
        var arr = series[pair[0]];
        if (arr && arr[index] !== null && arr[index] !== undefined) {
          rows.push(["متوسط " + (pair[1] || ""), fmtPrice(arr[index])]);
        }
      });
    }
    if (series.rsi && series.rsi[index] !== null && series.rsi[index] !== undefined) {
      rows.push(["RSI", series.rsi[index].toFixed(1)]);
    }

    var html = '<div class="mk-chart-tooltip__date">' +
               fmtDate(candle.t, this._isIntraday()) + "</div><dl>";
    rows.forEach(function (row) {
      html += "<dt>" + row[0] + "</dt><dd>" + row[1] + "</dd>";
    });
    html += "</dl>";

    this.tooltip.innerHTML = html;
    this.tooltip.classList.add("is-visible");

    var tw = this.tooltip.offsetWidth || 170;
    var th = this.tooltip.offsetHeight || 150;
    var left = x + 16;
    if (left + tw > this.width - 6) left = x - tw - 16;
    if (left < 4) left = 4;
    var top = Math.min(Math.max(y - th / 2, 4), this.height - th - 4);

    this.tooltip.style.left = left + "px";
    this.tooltip.style.top = top + "px";
  };

  global.CandleChart = CandleChart;
  global.MarketFormat = { price: fmtPrice, volume: fmtVolume, date: fmtDate };
})(window);
