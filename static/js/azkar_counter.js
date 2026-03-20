(function () {
    const counters = {};
    const cards = document.querySelectorAll('.zikr-card');
    const totalItems = cards.length;

    function pad(n) {
        return String(n).padStart(2, '0');
    }

    function renderCard(card) {
        const idx = card.dataset.index;
        const target = parseInt(card.dataset.target);
        const remaining = counters[idx] !== undefined ? counters[idx] : target;
        const display = card.querySelector('#cv-' + idx);

        display.textContent = pad(remaining);

        if (remaining <= 0) {
            card.classList.add('zikr-card--done');
        } else {
            card.classList.remove('zikr-card--done');
        }
    }

    function updateGlobal() {
        let done = 0;
        cards.forEach(function (card) {
            const idx = card.dataset.index;
            const target = parseInt(card.dataset.target);
            const remaining = counters[idx] !== undefined ? counters[idx] : target;
            if (remaining <= 0) done++;
        });
        const el = document.getElementById('globalProgress');
        if (el) el.textContent = done + ' / ' + totalItems;
    }

    function renderAll() {
        cards.forEach(renderCard);
        updateGlobal();
    }

    // Counter click
    document.querySelectorAll('.counter-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const idx = this.dataset.index;
            const target = parseInt(document.getElementById('zikr-' + idx).dataset.target);
            let remaining = counters[idx] !== undefined ? counters[idx] : target;

            if (remaining > 0) {
                remaining--;
                counters[idx] = remaining;
                if (navigator.vibrate) navigator.vibrate(40);

                // Pulse animation
                this.classList.remove('is-pulsing');
                void this.offsetWidth;
                this.classList.add('is-pulsing');
            }

            renderAll();
        });
    });

    // Undo
    document.querySelectorAll('.undo-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const idx = this.dataset.index;
            const target = parseInt(document.getElementById('zikr-' + idx).dataset.target);
            let remaining = counters[idx] !== undefined ? counters[idx] : target;

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
            // Visual feedback
            resetBtn.classList.add('btn-success');
            setTimeout(function(){ resetBtn.classList.remove('btn-success'); }, 400);
            // Debug log
            console.log('Reset all clicked');
        });
    }

    renderAll();
})();
