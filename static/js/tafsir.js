// Tafsir Integration Module
class TafsirViewer {
  constructor() {
    this.currentSurah = 1;
    this.currentAyah = 1;
    this.selectedSource = 'ibn_kathir';
    this.tafsirCache = {};
    this.tafsirSources = [
      { id: 'ibn_kathir', name: 'تفسير ابن كثير', nameEn: 'Ibn Kathir' },
      { id: 'tabari', name: 'تفسير الطبري', nameEn: 'Al-Tabari' },
      { id: 'qurtubi', name: 'تفسير القرطبي', nameEn: 'Al-Qurtubi' },
      { id: 'muyassar', name: 'التفسير الميسر', nameEn: 'Al-Muyassar' }
    ];

    this.init();
  }

  init() {
    this.createModal();
    this.setupEventListeners();
  }

  createModal() {
    const modalHTML = `
      <div id="tafsirModal" class="tafsir-modal" style="display: none;">
        <div class="tafsir-modal-overlay"></div>
        <div class="tafsir-modal-content">
          <div class="tafsir-modal-header">
            <h2 id="tafsirTitle">تفسير الآية</h2>
            <button class="tafsir-close-btn" id="tafsirCloseBtn">
              <i class="bi bi-x"></i>
            </button>
          </div>

          <div class="tafsir-modal-body">
            <!-- Ayah Text -->
            <div class="tafsir-ayah-section">
              <h3>الآية</h3>
              <p id="tafsirAyahText" class="ayah-text"></p>
              <p id="tafsirAyahRef" class="ayah-reference"></p>
            </div>

            <!-- Tafsir Source Selector -->
            <div class="tafsir-source-selector">
              <label>اختر المصدر</label>
              <select id="tafsirSourceSelect" class="tafsir-select">
                <option value="ibn_kathir">تفسير ابن كثير</option>
                <option value="tabari">تفسير الطبري</option>
                <option value="qurtubi">تفسير القرطبي</option>
                <option value="muyassar">التفسير الميسر</option>
              </select>
            </div>

            <!-- Tafsir Content -->
            <div class="tafsir-content-section">
              <h3>التفسير</h3>
              <div id="tafsirContent" class="tafsir-text">
                <p class="loading">جاري التحميل...</p>
              </div>
            </div>

            <!-- Loading Indicator -->
            <div id="tafsirLoading" class="tafsir-loading" style="display: none;">
              <div class="spinner"></div>
              <p>جاري التحميل...</p>
            </div>

            <!-- Navigation -->
            <div class="tafsir-nav">
              <button id="tafsirPrevAyah" class="tafsir-nav-btn">
                <i class="bi bi-chevron-right"></i> الآية السابقة
              </button>
              <span id="tafsirAyahCounter" class="ayah-counter"></span>
              <button id="tafsirNextAyah" class="tafsir-nav-btn">
                الآية التالية <i class="bi bi-chevron-left"></i>
              </button>
            </div>
          </div>

          <div class="tafsir-modal-footer">
            <button id="tafsirCopyBtn" class="tafsir-btn tafsir-btn-secondary">
              <i class="bi bi-clipboard"></i> نسخ
            </button>
            <button id="tafsirShareBtn" class="tafsir-btn tafsir-btn-secondary">
              <i class="bi bi-share"></i> شارك
            </button>
            <button id="tafsirCloseFooterBtn" class="tafsir-btn tafsir-btn-primary">
              <i class="bi bi-check-circle"></i> إغلاق
            </button>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);
  }

  setupEventListeners() {
    const closeBtn = document.getElementById('tafsirCloseBtn');
    const closeFooterBtn = document.getElementById('tafsirCloseFooterBtn');
    const overlay = document.querySelector('.tafsir-modal-overlay');
    const sourceSelect = document.getElementById('tafsirSourceSelect');
    const prevBtn = document.getElementById('tafsirPrevAyah');
    const nextBtn = document.getElementById('tafsirNextAyah');
    const copyBtn = document.getElementById('tafsirCopyBtn');
    const shareBtn = document.getElementById('tafsirShareBtn');

    if (closeBtn) closeBtn.addEventListener('click', () => this.closeModal());
    if (closeFooterBtn) closeFooterBtn.addEventListener('click', () => this.closeModal());
    if (overlay) overlay.addEventListener('click', () => this.closeModal());
    if (sourceSelect) sourceSelect.addEventListener('change', (e) => this.changeSource(e.target.value));
    if (prevBtn) prevBtn.addEventListener('click', () => this.previousAyah());
    if (nextBtn) nextBtn.addEventListener('click', () => this.nextAyah());
    if (copyBtn) copyBtn.addEventListener('click', () => this.copyTafsir());
    if (shareBtn) shareBtn.addEventListener('click', () => this.shareTafsir());

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen()) {
        this.closeModal();
      }
    });
  }

  openModal(surah, ayah) {
    console.log('Opening tafsir modal for Surah:', surah, 'Ayah:', ayah);
    this.currentSurah = surah;
    this.currentAyah = ayah;
    this.selectedSource = 'ibn_kathir';

    const modal = document.getElementById('tafsirModal');
    if (!modal) {
      console.error('Tafsir modal element not found in DOM');
      return;
    }

    // Use class instead of inline style for better control
    modal.style.display = 'flex';
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';

    console.log('✅ Tafsir modal opened');
    this.loadTafsir();
  }

  closeModal() {
    const modal = document.getElementById('tafsirModal');
    if (modal) {
      modal.style.display = 'none';
      modal.classList.remove('show');
      document.body.style.overflow = 'auto';
      console.log('✅ Tafsir modal closed');
    }
  }

  isOpen() {
    const modal = document.getElementById('tafsirModal');
    return modal && (modal.style.display === 'flex' || modal.classList.contains('show'));
  }

  loadTafsir() {
    const cacheKey = `${this.currentSurah}_${this.currentAyah}`;

    // Load from cache
    if (this.tafsirCache[cacheKey]) {
      this.displayTafsir(this.tafsirCache[cacheKey]);
      return;
    }

    this.showLoading(true);

    // Fetch from API (currently just shows placeholder)
    fetch(`/api/tafsir/${this.currentSurah}/${this.currentAyah}`)
      .then(res => res.json())
      .then(data => {
        // For now, show a placeholder
        const placeholder = {
          ayah_text: `آية من سورة ${(window.SURAHS || []).find(s => s.number === this.currentSurah)?.name || ''}`,
          tafsirs: {
            ibn_kathir: {
              name: 'تفسير ابن كثير',
              text: 'جاري جلب التفسير من المصادر الخارجية. يمكن دمج Quran.com API لتحميل النصوص الكاملة.'
            }
          }
        };

        this.tafsirCache[cacheKey] = placeholder;
        this.displayTafsir(placeholder);
      })
      .catch(error => {
        console.error('Error loading tafsir:', error);
        this.showLoading(false);
        document.getElementById('tafsirContent').innerHTML = `
          <p class="error">حدث خطأ في تحميل التفسير. حاول مجدداً.</p>
        `;
      });
  }

  displayTafsir(data) {
    this.showLoading(false);

    // Get SURAHS from window if available
    const surahs = window.SURAHS || [];
    const surah = surahs.find(s => s.number === this.currentSurah);

    if (!surah) {
      console.warn(`Surah ${this.currentSurah} not found`);
    }

    document.getElementById('tafsirTitle').textContent = `تفسير سورة ${surah?.name || 'غير محدد'} الآية ${this.currentAyah}`;
    document.getElementById('tafsirAyahText').textContent = data.ayah_text || 'آية من القرآن الكريم';
    document.getElementById('tafsirAyahRef').textContent = `${surah?.number || this.currentSurah}:${this.currentAyah}`;
    document.getElementById('tafsirAyahCounter').textContent = `الآية ${this.currentAyah} من ${surah?.verses || '؟'}`;

    const sourceSelect = document.getElementById('tafsirSourceSelect');
    sourceSelect.innerHTML = '';

    Object.keys(data.tafsirs || {}).forEach(sourceId => {
      const option = document.createElement('option');
      option.value = sourceId;
      option.textContent = data.tafsirs[sourceId].name || sourceId;
      sourceSelect.appendChild(option);
    });

    // Display first available tafsir
    if (Object.keys(data.tafsirs).length > 0) {
      this.selectedSource = Object.keys(data.tafsirs)[0];
      sourceSelect.value = this.selectedSource;
      this.displaySelectedTafsir(data.tafsirs[this.selectedSource]);
    } else {
      document.getElementById('tafsirContent').innerHTML = `
        <p class="no-data">التفسير غير متاح حالياً</p>
      `;
    }
  }

  displaySelectedTafsir(tafsirData) {
    const content = document.getElementById('tafsirContent');
    if (tafsirData && tafsirData.text) {
      content.innerHTML = `<p>${tafsirData.text}</p>`;
    } else {
      content.innerHTML = '<p class="no-data">التفسير غير متاح</p>';
    }
  }

  changeSource(sourceId) {
    this.selectedSource = sourceId;
    const cacheKey = `${this.currentSurah}_${this.currentAyah}`;
    const tafsirData = this.tafsirCache[cacheKey];

    if (tafsirData && tafsirData.tafsirs[sourceId]) {
      this.displaySelectedTafsir(tafsirData.tafsirs[sourceId]);
    }
  }

  previousAyah() {
    const surahs = window.SURAHS || [];
    const surah = surahs.find(s => s.number === this.currentSurah);
    if (this.currentAyah > 1) {
      this.currentAyah--;
      this.loadTafsir();
    } else if (this.currentSurah > 1) {
      const prevSurah = surahs.find(s => s.number === this.currentSurah - 1);
      this.currentSurah--;
      this.currentAyah = prevSurah?.verses || 1;
      this.loadTafsir();
    }
  }

  nextAyah() {
    const surahs = window.SURAHS || [];
    const surah = surahs.find(s => s.number === this.currentSurah);
    if (surah && this.currentAyah < surah.verses) {
      this.currentAyah++;
      this.loadTafsir();
    } else if (this.currentSurah < 114) {
      this.currentSurah++;
      this.currentAyah = 1;
      this.loadTafsir();
    }
  }

  copyTafsir() {
    const content = document.getElementById('tafsirContent').textContent;
    navigator.clipboard.writeText(content).then(() => {
      alert('تم نسخ التفسير');
    }).catch(() => {
      alert('فشل النسخ');
    });
  }

  shareTafsir() {
    const surahs = window.SURAHS || [];
    const surah = surahs.find(s => s.number === this.currentSurah);
    const text = `${surah?.name}:${this.currentAyah} - ${this.currentSurah}:${this.currentAyah}`;

    if (navigator.share) {
      navigator.share({
        title: 'Islamify',
        text: `تفسير الآية: ${text}`
      }).catch(err => console.log('Share failed:', err));
    } else {
      alert('المشاركة غير مدعومة في المتصفح الحالي');
    }
  }

  showLoading(show) {
    const loading = document.getElementById('tafsirLoading');
    const content = document.getElementById('tafsirContent');

    if (show) {
      loading.style.display = 'flex';
      content.style.display = 'none';
    } else {
      loading.style.display = 'none';
      content.style.display = 'block';
    }
  }
}

// Initialize Tafsir Viewer
let tafsirViewer = null;
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    tafsirViewer = new TafsirViewer();
  });
} else {
  tafsirViewer = new TafsirViewer();
}
