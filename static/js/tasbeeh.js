(function () {
    var toast = document.getElementById('tasbeehToast');
    var toastMsg = document.getElementById('toastMsg');
    var canvas = document.getElementById('confettiCanvas');

    var counters = {};

    /* -------- toast -------- */
    function showToast(msg) {
        toastMsg.textContent = msg;
        toast.classList.add('show');
        setTimeout(function () { toast.classList.remove('show'); }, 3000);
    }

    /* -------- confetti -------- */
    function launchConfetti() {
        var ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        var particles = [];
        var colors = ['#1e7a73','#28a745','#ffc107','#e91e63','#2196f3','#ff5722','#9c27b0'];
        for (var i = 0; i < 80; i++) {
            particles.push({
                x: canvas.width * 0.5 + (Math.random() - 0.5) * 300,
                y: canvas.height * 0.35,
                vx: (Math.random() - 0.5) * 12,
                vy: -Math.random() * 14 - 4,
                size: Math.random() * 7 + 3,
                color: colors[Math.floor(Math.random() * colors.length)],
                rotation: Math.random() * 360,
                rotSpeed: (Math.random() - 0.5) * 10,
                life: 1,
            });
        }
        var frame;
        function animate() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            var alive = false;
            for (var i = 0; i < particles.length; i++) {
                var p = particles[i];
                if (p.life <= 0) continue;
                alive = true;
                p.x += p.vx; p.vy += 0.35; p.y += p.vy;
                p.rotation += p.rotSpeed; p.life -= 0.013;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rotation * Math.PI / 180);
                ctx.globalAlpha = Math.max(0, p.life);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
                ctx.restore();
            }
            if (alive) { frame = requestAnimationFrame(animate); }
            else { ctx.clearRect(0, 0, canvas.width, canvas.height); }
        }
        animate();
    }

    /* -------- init each card -------- */
    var cards = document.querySelectorAll('.misbaha-card');

    cards.forEach(function (card) {
        var id = card.getAttribute('data-id');
        var digits = card.querySelector('.misbaha-digits');
        var countBtn = card.querySelector('.misbaha-btn-count');
        var resetBtn = card.querySelector('.misbaha-btn-reset');
        var clickArea = card.querySelector('.misbaha-click-area');
        var device = card.querySelector('.misbaha-device');
        var zikrEl = card.querySelector('.misbaha-zikr');

        if (!counters[id]) counters[id] = 0;
        digits.textContent = counters[id];

        function increment() {
            counters[id]++;
            digits.textContent = counters[id];

            // Pulse animation
            device.classList.add('misbaha-pulse');
            setTimeout(function () { device.classList.remove('misbaha-pulse'); }, 200);

            // Vibrate
            if (navigator.vibrate) navigator.vibrate(40);

            // Milestones: 33, 100, 500, 1000
            var v = counters[id];
            if (v === 33 || v === 100 || v === 500 || v === 1000) {
                var zikr = zikrEl.textContent.substring(0, 30);
                if (zikrEl.textContent.length > 30) zikr += '...';
                showToast('ما شاء الله! ' + v + ' × ' + zikr + ' 🎉');
                launchConfetti();
                if (navigator.vibrate) navigator.vibrate([80, 50, 80, 50, 120]);
            }
        }

        function reset() {
            counters[id] = 0;
            digits.textContent = 0;
        }

        countBtn.addEventListener('click', increment);
        clickArea.addEventListener('click', increment);
        resetBtn.addEventListener('click', reset);
    });
})();
