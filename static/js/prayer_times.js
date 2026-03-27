(function () {
    'use strict';

    /* ════════ lookup data ════════ */
    var PRAYER_NAMES = {
        Fajr:    'الفجر',
        Sunrise: 'الشروق',
        Dhuhr:   'الظهر',
        Asr:     'العصر',
        Maghrib: 'المغرب',
        Isha:    'العشاء'
    };
    var PRAYER_ICONS = {
        Fajr:    'bi-sunrise',
        Sunrise: 'bi-sun',
        Dhuhr:   'bi-sun-fill',
        Asr:     'bi-cloud-sun',
        Maghrib: 'bi-sunset',
        Isha:    'bi-moon-stars-fill'
    };
    var PRAYER_ORDER = ['Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];
    var ADHAN_URL     = '/static/files/adhan_mecca.mp3';

    /* ════════ element helper ════════ */
    function g(id) { return document.getElementById(id); }

    /* ════════ state ════════ */
    var countdownInterval = null;
    var prevNextKey       = null;   // used to detect when a prayer time hits
    var lastFiredKey      = null;   // "Key|DateString" prevents double-fire
    var adhanEnabled      = localStorage.getItem('adhanNotify') === '1';
    var audioCtx          = null;
    var adhanAudio        = null;   // HTML5 Audio element for Mecca adhan MP3
    var reqId             = 0;      // incremented on every new async request;
                                    // callbacks check their own copy and bail
                                    // if a newer request has started (race-condition fix)

    /* ════════════════════════════════════════════
       UI STATE MACHINE
       All state changes go through these helpers.
    ════════════════════════════════════════════ */

    function showLoading(label) {
        g('loading-state').style.display    = '';
        g('loading-label').textContent      = label || 'جارٍ تحديد موقعك تلقائياً…';
        g('prayer-card').style.display      = 'none';
        g('search-section').style.display   = 'none';
        g('error-msg').style.display        = 'none';
    }

    /* Called after prayer data successfully renders */
    function showData() {
        g('loading-state').style.display    = 'none';
        g('prayer-card').style.display      = '';
        g('error-msg').style.display        = 'none';
        g('search-section').style.display   = '';
        g('change-city-wrap').style.display = '';       // compact toggle visible
        g('search-form-wrap').style.display = 'none';   // form collapsed
    }

    /* Called when geo fails or there is no data yet — shows search prominently */
    function showSearchOnly() {
        g('loading-state').style.display    = 'none';
        g('search-section').style.display   = '';
        g('change-city-wrap').style.display = 'none';   // no compact toggle
        g('search-form-wrap').style.display = '';       // form visible
    }

    function showError(msg) {
        g('error-msg').textContent   = msg;
        g('error-msg').style.display = '';
    }

    function hideError() { g('error-msg').style.display = 'none'; }

    function setSearchLoading(on) {
        var btn = g('search-btn');
        if (on) {
            btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
            btn.disabled  = true;
        } else {
            btn.innerHTML = 'بحث';
            btn.disabled  = false;
        }
    }

    /* ════════════════════════════════════════════
       ADHAN AUDIO + VIBRATION
    ════════════════════════════════════════════ */

    function initAudio() {
        if (!audioCtx) {
            var AC = window.AudioContext || window.webkitAudioContext;
            if (AC) audioCtx = new AC();
        }
        if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
        return audioCtx;
    }

    /**
     * Synthesise a sequence of sine-wave notes.
     * @param {Array}  notes  — [[frequency_hz, start_offset_s, duration_s], …]
     * @param {number} vol    — peak gain (0–1)
     */
    function playSynthNotes(notes, vol) {
        var ctx = initAudio();
        if (!ctx) return;
        vol = vol || 0.16;
        var base = ctx.currentTime + 0.08;
        notes.forEach(function (n) {
            var freq = n[0], offset = n[1], dur = n[2];
            var osc  = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type            = 'sine';
            osc.frequency.value = freq;
            var t = base + offset;
            gain.gain.setValueAtTime(0, t);
            gain.gain.linearRampToValueAtTime(vol, t + 0.07);
            gain.gain.setValueAtTime(vol, t + dur - 0.09);
            gain.gain.linearRampToValueAtTime(0, t + dur);
            osc.start(t);
            osc.stop(t + dur + 0.02);
        });
    }

    /* Short 3-note preview — plays the first moment the user enables the toggle */
    function playPreview() {
        playSynthNotes([
            [392.00, 0.00, 0.38],   // G4
            [523.25, 0.44, 0.38],   // C5
            [783.99, 0.88, 0.60],   // G5
        ], 0.13);
    }

    /* Full Mecca adhan — plays the MP3 file */
    function playAdhanMelody() {
        try {
            if (!adhanAudio) {
                adhanAudio = new Audio(ADHAN_URL);
                adhanAudio.preload = 'auto';
            }
            adhanAudio.currentTime = 0;
            adhanAudio.volume = 0.95;
            adhanAudio.play().catch(function () {});
        } catch (e) {}
    }

    function triggerAdhan() {
        // Vibrate — long pattern for mobile
        if (navigator.vibrate) {
            navigator.vibrate([700, 300, 700, 300, 700, 300, 1000, 400, 700]);
        }
        playAdhanMelody();

        // Brief visual flash on the countdown box
        var cd = g('countdown');
        if (cd) {
            cd.classList.add('pt-adhan-flash');
            setTimeout(function () { cd.classList.remove('pt-adhan-flash'); }, 1800);
        }
    }

    function updateBellBtn() {
        var btn = g('adhan-notify-btn');
        if (!btn) return;
        if (adhanEnabled) {
            btn.innerHTML = '<i class="bi bi-bell-fill"></i> تنبيه الأذان: مفعّل';
            btn.className = 'btn btn-sm rounded-pill px-3 btn-success';
        } else {
            btn.innerHTML = '<i class="bi bi-bell-slash"></i> تنبيه الأذان';
            btn.className = 'btn btn-sm rounded-pill px-3 btn-outline-secondary';
        }
    }

    /* ════════════════════════════════════════════
       API HELPERS
    ════════════════════════════════════════════ */

    function fetchByCoords(lat, lng) {
        var d   = new Date();
        var url = 'https://api.aladhan.com/v1/timings/' +
            d.getDate() + '-' + (d.getMonth() + 1) + '-' + d.getFullYear() +
            '?latitude=' + lat + '&longitude=' + lng + '&method=4';
        return fetch(url).then(function (r) {
            if (!r.ok) throw new Error('api');
            return r.json();
        });
    }

    function reverseGeocode(lat, lng) {
        var url = 'https://nominatim.openstreetmap.org/reverse' +
            '?lat=' + lat + '&lon=' + lng + '&format=json&accept-language=ar';
        return fetch(url, { headers: { Accept: 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var a = data.address || {};
                return a.city || a.town || a.village || a.state || '';
            })
            .catch(function () { return ''; });
    }

    function forwardGeocode(city) {
        var url = 'https://nominatim.openstreetmap.org/search' +
            '?q=' + encodeURIComponent(city) + '&format=json&limit=1&accept-language=ar';
        return fetch(url, { headers: { Accept: 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (results) {
                if (!results || !results.length) throw new Error('notfound');
                return {
                    lat:  parseFloat(results[0].lat),
                    lng:  parseFloat(results[0].lon),
                    name: results[0].display_name.split(',')[0]
                };
            });
    }

    /* ════════════════════════════════════════════
       RENDER
    ════════════════════════════════════════════ */

    function render(data, cityName) {
        var t = data.data.timings;
        var d = data.data.date;

        g('city-name').textContent  = cityName || '';
        g('date-info').textContent  = d.readable;
        g('hijri-date').textContent = d.hijri.day + ' ' + d.hijri.month.ar + ' ' + d.hijri.year;

        var grid = g('timings-grid');
        grid.innerHTML = '';
        PRAYER_ORDER.forEach(function (key) {
            var time24 = t[key].split(' ')[0];
            var col    = document.createElement('div');
            col.className = 'col-6 col-md-4 col-lg-2';
            col.innerHTML =
                '<div class="timing-box text-center" id="box-' + key + '">' +
                '  <i class="bi ' + PRAYER_ICONS[key] + ' d-block mb-1 timing-box__icon"></i>' +
                '  <strong class="d-block">' + PRAYER_NAMES[key] + '</strong>' +
                '  <span class="timing-time">' + time24 + '</span>' +
                '</div>';
            grid.appendChild(col);
        });

        showData();
        updateBellBtn();

        // Reset adhan fire state for the new city / new load
        prevNextKey  = null;
        lastFiredKey = null;
        if (countdownInterval) clearInterval(countdownInterval);
        startCountdown(t);
    }

    /* ════════════════════════════════════════════
       COUNTDOWN + ADHAN MOMENT DETECTION
    ════════════════════════════════════════════ */

    function startCountdown(timings) {
        function tick() {
            var now     = new Date();
            var next    = null;
            var nextKey = null;

            for (var i = 0; i < PRAYER_ORDER.length; i++) {
                var key   = PRAYER_ORDER[i];
                if (key === 'Sunrise') continue;
                var parts = timings[key].split(' ')[0].split(':');
                var pt    = new Date(now);
                pt.setHours(+parts[0], +parts[1], 0, 0);
                if (pt > now) { next = pt; nextKey = key; break; }
            }

            if (!next) {
                // All prayers passed — next is tomorrow's Fajr
                nextKey     = 'Fajr';
                var fp      = timings.Fajr.split(' ')[0].split(':');
                next        = new Date(now);
                next.setDate(next.getDate() + 1);
                next.setHours(+fp[0], +fp[1], 0, 0);
            }

            /* ── Adhan moment detection ──────────────────────────────
               When nextKey changes, the previous "next prayer" just
               arrived (its countdown hit zero).  We fire adhan once
               per prayer per day by keying on "PrayerName|DateString".
            ─────────────────────────────────────────────────────── */
            if (adhanEnabled && prevNextKey && prevNextKey !== nextKey) {
                var fireKey = prevNextKey + '|' + now.toDateString();
                if (lastFiredKey !== fireKey) {
                    lastFiredKey = fireKey;
                    triggerAdhan();
                }
            }
            prevNextKey = nextKey;

            /* ── Countdown display ── */
            var diff = next - now;
            var hrs  = Math.floor(diff / 3600000);
            var mins = Math.floor((diff % 3600000) / 60000);
            var secs = Math.floor((diff % 60000) / 1000);

            g('next-prayer-name').textContent = PRAYER_NAMES[nextKey] || '';
            g('countdown').textContent =
                String(hrs).padStart(2, '0') + ':' +
                String(mins).padStart(2, '0') + ':' +
                String(secs).padStart(2, '0');

            /* ── Highlight the upcoming prayer box ── */
            PRAYER_ORDER.forEach(function (k) {
                var box = document.getElementById('box-' + k);
                if (!box) return;
                if (k === nextKey) {
                    box.classList.add('timing-box--next');
                } else {
                    box.classList.remove('timing-box--next');
                }
            });
        }

        tick();
        countdownInterval = setInterval(tick, 1000);
    }

    /* ════════════════════════════════════════════
       GEO AUTO-DETECT
    ════════════════════════════════════════════ */

    function startGeoDetect() {
        if (!navigator.geolocation) {
            showSearchOnly();
            return;
        }

        showLoading();
        var myReq = ++reqId;

        navigator.geolocation.getCurrentPosition(
            function (pos) {
                if (myReq !== reqId) return; // superseded by a newer request
                var lat = pos.coords.latitude;
                var lng = pos.coords.longitude;

                Promise.all([fetchByCoords(lat, lng), reverseGeocode(lat, lng)])
                    .then(function (res) {
                        if (myReq !== reqId) return;
                        var data = res[0];
                        var city = res[1] || data.data.meta.timezone
                            .replace(/_/g, ' ').split('/').pop();
                        render(data, city);
                    })
                    .catch(function () {
                        if (myReq !== reqId) return;
                        showSearchOnly();
                        showError('تعذّر جلب أوقات الصلاة. ابحث عن مدينتك يدوياً.');
                    });
            },
            function () {
                // User denied location or timed out
                if (myReq !== reqId) return;
                showSearchOnly();
            },
            { timeout: 8000 }
        );
    }

    /* ════════════════════════════════════════════
       MANUAL CITY SEARCH
    ════════════════════════════════════════════ */

    function doSearch() {
        var city = g('city-input').value.trim();
        if (!city) { g('city-input').focus(); return; }

        var myReq = ++reqId; // cancels any pending geo callback
        hideError();
        setSearchLoading(true);

        forwardGeocode(city)
            .then(function (geo) {
                return fetchByCoords(geo.lat, geo.lng).then(function (data) {
                    if (myReq !== reqId) return;
                    render(data, geo.name);
                    setSearchLoading(false);
                });
            })
            .catch(function () {
                if (myReq !== reqId) return;
                setSearchLoading(false);
                showError('لم يُعثر على المدينة. تأكد من الاسم وحاول مجدداً.');
            });
    }

    /* ════════════════════════════════════════════
       EVENT LISTENERS
    ════════════════════════════════════════════ */

    g('search-btn').addEventListener('click', doSearch);

    g('city-input').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') doSearch();
    });

    g('adhan-notify-btn').addEventListener('click', function () {
        initAudio(); // must happen inside a user-gesture handler
        adhanEnabled = !adhanEnabled;
        localStorage.setItem('adhanNotify', adhanEnabled ? '1' : '0');
        updateBellBtn();
        if (adhanEnabled) {
            // preload the audio file and play a short 3-second preview
            if (!adhanAudio) {
                adhanAudio = new Audio(ADHAN_URL);
                adhanAudio.preload = 'auto';
            }
            adhanAudio.currentTime = 0;
            adhanAudio.volume = 0.95;
            adhanAudio.play().catch(function () { playPreview(); });
            // stop preview after 3 seconds
            setTimeout(function () {
                if (adhanAudio && !adhanAudio.paused) {
                    adhanAudio.pause();
                    adhanAudio.currentTime = 0;
                }
            }, 3000);
        } else {
            // stop if currently playing
            if (adhanAudio && !adhanAudio.paused) {
                adhanAudio.pause();
                adhanAudio.currentTime = 0;
            }
        }
    });

    g('change-city-btn').addEventListener('click', function () {
        var form     = g('search-form-wrap');
        var isHidden = form.style.display === 'none';
        form.style.display = isHidden ? '' : 'none';
        if (isHidden) g('city-input').focus();
    });

    /* ════════ init ════════ */
    startGeoDetect();
})();
