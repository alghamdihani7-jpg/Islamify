(function () {
    var counters = {};
    var cards = document.querySelectorAll('.zikr-card');
    var totalItems = cards.length;

    function pad(n) {
        return String(n).padStart(2, '0');
    }

    function renderCard(card) {
        var idx = card.dataset.index;
        var target = parseInt(card.dataset.target);
        var remaining = counters[idx] !== undefined ? counters[idx] : target;
        var display = card.querySelector('#cv-' + idx);

        if (remaining >= 100) {
            display.textContent = String(remaining);
        } else {
            display.textContent = pad(remaining);
        }

        if (remaining <= 0) {
            card.classList.add('zikr-card--done');
        } else {
            card.classList.remove('zikr-card--done');
        }
    }

    function updateGlobal() {
        var done = 0;
        cards.forEach(function (card) {
            var idx = card.dataset.index;
            var target = parseInt(card.dataset.target);
            var remaining = counters[idx] !== undefined ? counters[idx] : target;
            if (remaining <= 0) done++;
        });
        var el = document.getElementById('globalProgress');
        if (el) el.textContent = done + ' / ' + totalItems;
    }

    function renderAll() {
        cards.forEach(renderCard);
        updateGlobal();
    }

    // Counter click
    document.querySelectorAll('.counter-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var idx = this.dataset.index;
            var target = parseInt(document.getElementById('zikr-' + idx).dataset.target);
            var remaining = counters[idx] !== undefined ? counters[idx] : target;

            if (remaining > 0) {
                remaining--;
                counters[idx] = remaining;
                if (navigator.vibrate) navigator.vibrate(15);
            }

            renderAll();
        });
    });

    // Undo
    document.querySelectorAll('.undo-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var idx = this.dataset.index;
            var target = parseInt(document.getElementById('zikr-' + idx).dataset.target);
            var remaining = counters[idx] !== undefined ? counters[idx] : target;

            if (remaining < target) {
                remaining++;
                counters[idx] = remaining;
            }

            renderAll();
        });
    });

    // Reset all
    var resetBtn = document.getElementById('resetAllBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            cards.forEach(function (card) {
                delete counters[card.dataset.index];
            });
            renderAll();
        });
    }

    renderAll();
})();
