(function(){
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
    var PRAYER_ORDER = ['Fajr','Sunrise','Dhuhr','Asr','Maghrib','Isha'];

    function $(id) { return document.getElementById(id); }
    var countdownInterval;

    /* ── helpers ── */
    function setStatus(html) {
        var el = $('location-status');
        if (html) {
            el.innerHTML = html;
            el.style.display = '';
        } else {
            el.style.display = 'none';
        }
    }

    function fetchByCoords(lat, lng) {
        var today = new Date();
        var dd = today.getDate(), mm = today.getMonth()+1, yyyy = today.getFullYear();
        var url = 'https://api.aladhan.com/v1/timings/'+dd+'-'+mm+'-'+yyyy+'?latitude='+lat+'&longitude='+lng+'&method=4';
        return fetch(url).then(function(res) {
            if (!res.ok) throw new Error('API error');
            return res.json();
        });
    }

    function reverseGeocode(lat, lng) {
        var url = 'https://nominatim.openstreetmap.org/reverse?lat='+lat+'&lon='+lng+'&format=json&accept-language=ar';
        return fetch(url, {headers:{'Accept':'application/json'}}).then(function(res) {
            return res.json();
        }).then(function(data) {
            var addr = data.address || {};
            return addr.city || addr.town || addr.village || addr.state || '';
        }).catch(function() { return ''; });
    }

    function forwardGeocode(query) {
        var url = 'https://nominatim.openstreetmap.org/search?q='+encodeURIComponent(query)+'&format=json&limit=1&accept-language=ar';
        return fetch(url, {headers:{'Accept':'application/json'}}).then(function(res) {
            return res.json();
        }).then(function(results) {
            if (!results || results.length === 0) throw new Error('Not found');
            return {
                lat: parseFloat(results[0].lat),
                lng: parseFloat(results[0].lon),
                name: results[0].display_name.split(',')[0]
            };
        });
    }

    /* ── render ── */
    function render(data, cityName) {
        var t = data.data.timings;
        var d = data.data.date;

        $('city-name').textContent = cityName || '';
        $('date-info').textContent = d.readable;
        $('hijri-date').textContent = d.hijri.day + ' ' + d.hijri.month.ar + ' ' + d.hijri.year;

        var grid = $('timings-grid');
        grid.innerHTML = '';
        PRAYER_ORDER.forEach(function(key) {
            var time24 = t[key].split(' ')[0];
            var col = document.createElement('div');
            col.className = 'col-6 col-md-4 col-lg-2';
            col.innerHTML =
                '<div class="timing-box p-3 rounded-3 text-center" id="box-' + key + '">' +
                '<i class="bi ' + PRAYER_ICONS[key] + ' d-block mb-1" style="font-size:1.3rem;color:var(--teal,#0d7377);"></i>' +
                '<strong class="d-block">' + PRAYER_NAMES[key] + '</strong>' +
                '<span>' + time24 + '</span></div>';
            grid.appendChild(col);
        });

        // show results, hide spinner
        $('prayer-card').style.display = '';
        setStatus(null);
        $('error-msg').style.display = 'none';
        $('manual-search').style.display = '';
        startCountdown(t);
    }

    /* ── countdown ── */
    function startCountdown(timings) {
        if (countdownInterval) clearInterval(countdownInterval);

        function tick() {
            var now = new Date();
            var next = null, nextKey = null;

            for (var i = 0; i < PRAYER_ORDER.length; i++) {
                var key = PRAYER_ORDER[i];
                if (key === 'Sunrise') continue;
                var parts = timings[key].split(' ')[0].split(':');
                var prayerTime = new Date(now);
                prayerTime.setHours(parseInt(parts[0]), parseInt(parts[1]), 0, 0);
                if (prayerTime > now) {
                    next = prayerTime;
                    nextKey = key;
                    break;
                }
            }

            if (!next) {
                nextKey = 'Fajr';
                var fp = timings.Fajr.split(' ')[0].split(':');
                next = new Date(now);
                next.setDate(next.getDate() + 1);
                next.setHours(parseInt(fp[0]), parseInt(fp[1]), 0, 0);
            }

            var diff = next - now;
            var hrs = Math.floor(diff / 3600000);
            var mins = Math.floor((diff % 3600000) / 60000);
            var secs = Math.floor((diff % 60000) / 1000);

            $('next-prayer-name').textContent = PRAYER_NAMES[nextKey];
            $('countdown').textContent =
                String(hrs).padStart(2,'0') + ':' +
                String(mins).padStart(2,'0') + ':' +
                String(secs).padStart(2,'0');

            PRAYER_ORDER.forEach(function(k) {
                var box = document.getElementById('box-' + k);
                if (box) {
                    box.style.border = k === nextKey ? '2px solid var(--teal,#0d7377)' : '';
                    box.style.boxShadow = k === nextKey ? '0 0 12px rgba(13,115,119,0.3)' : '';
                }
            });
        }

        tick();
        countdownInterval = setInterval(tick, 1000);
    }

    function showError(msg) {
        $('error-msg').textContent = msg;
        $('error-msg').style.display = '';
        setStatus(null);
        $('manual-search').style.display = '';
    }

    /* ── geolocation auto-detect ── */
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(pos) {
                var lat = pos.coords.latitude;
                var lng = pos.coords.longitude;
                Promise.all([
                    fetchByCoords(lat, lng),
                    reverseGeocode(lat, lng)
                ]).then(function(results) {
                    var data = results[0];
                    var cityName = results[1] || data.data.meta.timezone.replace(/_/g,' ').split('/').pop();
                    render(data, cityName);
                }).catch(function() {
                    showError('تعذر جلب المواقيت. حاول البحث يدويًا.');
                });
            },
            function() {
                setStatus('<i class="bi bi-geo-alt"></i> <span>لم يتم السماح بتحديد الموقع. ابحث يدويًا:</span>');
                $('manual-search').style.display = '';
            },
            { timeout: 8000 }
        );
    } else {
        setStatus('<i class="bi bi-geo-alt"></i> <span>المتصفح لا يدعم تحديد الموقع. ابحث يدويًا:</span>');
        $('manual-search').style.display = '';
    }

    /* ── manual search ── */
    $('search-btn').addEventListener('click', function() {
        var city = $('city-input').value.trim();
        var country = $('country-input').value.trim();
        if (!city) return;

        $('error-msg').style.display = 'none';
        $('prayer-card').style.display = 'none';
        setStatus('<div class="spinner-border spinner-border-sm" role="status"></div> <span>جارٍ البحث...</span>');

        var query = country ? city + ' ' + country : city;
        forwardGeocode(query)
            .then(function(geo) {
                return fetchByCoords(geo.lat, geo.lng).then(function(data) {
                    render(data, geo.name);
                });
            })
            .catch(function() {
                showError('لم يتم العثور على المدينة. تأكد من الاسم وحاول مجددًا.');
            });
    });

    // Enter key on inputs
    ['city-input','country-input'].forEach(function(id) {
        $(id).addEventListener('keydown', function(e) {
            if (e.key === 'Enter') $('search-btn').click();
        });
    });
})();
