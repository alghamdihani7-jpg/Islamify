// Prayer Notifications System
class PrayerNotificationSystem {
  constructor() {
    this.settings = this.loadSettings();
    this.prayerTimes = {};
    this.notificationCheckInterval = null;
    this.init();
  }

  init() {
    this.registerServiceWorker();
    this.setupEventListeners();
    this.requestNotificationPermission();
    this.startNotificationChecker();
  }

  registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/static/js/service-worker.js')
        .then(registration => {
          console.log('Service Worker registered:', registration);
        })
        .catch(error => {
          console.log('Service Worker registration failed:', error);
        });
    }
  }

  requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
          console.log('Notification permission granted');
        }
      });
    }
  }

  setupEventListeners() {
    const saveButton = document.getElementById('saveSettingsButton');
    const resetButton = document.getElementById('resetSettingsButton');
    const testSoundButton = document.getElementById('testSoundButton');
    const volumeControl = document.getElementById('soundVolume');

    if (saveButton) saveButton.addEventListener('click', () => this.saveSettings());
    if (resetButton) resetButton.addEventListener('click', () => this.resetSettings());
    if (testSoundButton) testSoundButton.addEventListener('click', () => this.testSound());
    if (volumeControl) {
      volumeControl.addEventListener('input', (e) => {
        document.getElementById('volumePercent').textContent = e.target.value + '%';
      });
    }

    // Prayer toggles
    ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha'].forEach(prayer => {
      const checkbox = document.getElementById(`notify-${prayer}`);
      if (checkbox) {
        checkbox.addEventListener('change', (e) => {
          this.settings.prayer_notifications[prayer] = e.target.checked;
        });
      }
    });

    // Master toggle
    const enableNotifications = document.getElementById('enableNotifications');
    if (enableNotifications) {
      enableNotifications.addEventListener('change', (e) => {
        this.settings.enabled = e.target.checked;
      });
    }

    // Other toggles
    const enableSound = document.getElementById('enableSound');
    if (enableSound) {
      enableSound.addEventListener('change', (e) => {
        this.settings.sound_enabled = e.target.checked;
      });
    }

    const enableWudu = document.getElementById('enableWuduReminder');
    if (enableWudu) {
      enableWudu.addEventListener('change', (e) => {
        this.settings.wudu_reminder_enabled = e.target.checked;
      });
    }

    // Selects
    const notifyBefore = document.getElementById('notifyBefore');
    if (notifyBefore) {
      notifyBefore.addEventListener('change', (e) => {
        this.settings.notify_before_minutes = parseInt(e.target.value);
      });
    }

    const snoozeDuration = document.getElementById('snoozeDuration');
    if (snoozeDuration) {
      snoozeDuration.addEventListener('change', (e) => {
        this.settings.snooze_duration_minutes = parseInt(e.target.value);
      });
    }

    const wuduReminderTime = document.getElementById('wuduReminderTime');
    if (wuduReminderTime) {
      wuduReminderTime.addEventListener('change', (e) => {
        this.settings.wudu_reminder_minutes = parseInt(e.target.value);
      });
    }
  }

  loadSettings() {
    const saved = localStorage.getItem('prayer_notification_settings');
    if (saved) {
      return JSON.parse(saved);
    }
    return {
      enabled: true,
      sound_enabled: true,
      sound_volume: 80,
      notify_before_minutes: -5,
      snooze_duration_minutes: 10,
      wudu_reminder_enabled: true,
      wudu_reminder_minutes: 15,
      prayer_notifications: {
        fajr: true,
        dhuhr: true,
        asr: true,
        maghrib: true,
        isha: true
      },
      notify_offset_per_prayer: {
        fajr: -10,
        dhuhr: -5,
        asr: 0,
        maghrib: -5,
        isha: -10
      }
    };
  }

  saveSettings() {
    localStorage.setItem('prayer_notification_settings', JSON.stringify(this.settings));
    const messageDiv = document.getElementById('settingsSaveMessage');
    if (messageDiv) {
      messageDiv.textContent = 'تم حفظ الإعدادات بنجاح ✓';
      messageDiv.className = 'save-message success';
      setTimeout(() => {
        messageDiv.className = 'save-message';
      }, 3000);
    }
  }

  resetSettings() {
    if (confirm('هل تريد إعادة تعيين جميع الإعدادات إلى الافتراضية؟')) {
      this.settings = this.loadSettings();
      this.updateUI();
      this.saveSettings();
    }
  }

  updateUI() {
    document.getElementById('enableNotifications').checked = this.settings.enabled;
    document.getElementById('enableSound').checked = this.settings.sound_enabled;
    document.getElementById('soundVolume').value = this.settings.sound_volume;
    document.getElementById('volumePercent').textContent = this.settings.sound_volume + '%';
    document.getElementById('notifyBefore').value = this.settings.notify_before_minutes;
    document.getElementById('snoozeDuration').value = this.settings.snooze_duration_minutes;
    document.getElementById('enableWuduReminder').checked = this.settings.wudu_reminder_enabled;
    document.getElementById('wuduReminderTime').value = this.settings.wudu_reminder_minutes;

    ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha'].forEach(prayer => {
      const checkbox = document.getElementById(`notify-${prayer}`);
      if (checkbox) {
        checkbox.checked = this.settings.prayer_notifications[prayer];
      }
    });
  }

  testSound() {
    const audio = new Audio('/static/sounds/notification.mp3');
    audio.volume = this.settings.sound_volume / 100;
    audio.play().catch(error => {
      console.log('Sound playback failed:', error);
    });
  }

  setPrayerTimes(times) {
    this.prayerTimes = times;
  }

  startNotificationChecker() {
    // Check every minute
    this.notificationCheckInterval = setInterval(() => {
      this.checkPrayerNotifications();
    }, 60000);

    // Also check immediately
    this.checkPrayerNotifications();
  }

  checkPrayerNotifications() {
    if (!this.settings.enabled || !this.prayerTimes) {
      return;
    }

    const now = new Date();
    const prayers = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha'];

    prayers.forEach(prayer => {
      if (!this.settings.prayer_notifications[prayer]) {
        return;
      }

      const prayerTimeStr = this.prayerTimes[prayer];
      if (!prayerTimeStr) return;

      const [hours, minutes] = prayerTimeStr.split(':').map(Number);
      const prayerTime = new Date();
      prayerTime.setHours(hours, minutes, 0);

      const offset = this.settings.notify_offset_per_prayer[prayer] || this.settings.notify_before_minutes;
      const notifyTime = new Date(prayerTime.getTime() + offset * 60000);

      // Check if within 1 minute of notification time
      const timeDiff = Math.abs(now - notifyTime);
      if (timeDiff < 60000) {
        this.showNotification(prayer, prayerTimeStr);
      }

      // Wudu reminder
      if (this.settings.wudu_reminder_enabled) {
        const wuduTime = new Date(prayerTime.getTime() - this.settings.wudu_reminder_minutes * 60000);
        const wuduDiff = Math.abs(now - wuduTime);
        if (wuduDiff < 60000) {
          this.showWuduReminder(prayer, prayerTimeStr);
        }
      }
    });
  }

  showNotification(prayer, prayerTime) {
    const messages = {
      fajr: { ar: 'حان وقت صلاة الفجر', en: 'Fajr Prayer Time' },
      dhuhr: { ar: 'حان وقت صلاة الظهر', en: 'Dhuhr Prayer Time' },
      asr: { ar: 'حان وقت صلاة العصر', en: 'Asr Prayer Time' },
      maghrib: { ar: 'حان وقت صلاة المغرب', en: 'Maghrib Prayer Time' },
      isha: { ar: 'حان وقت صلاة العشاء', en: 'Isha Prayer Time' }
    };

    const message = messages[prayer] || { ar: 'وقت الصلاة', en: 'Prayer Time' };

    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(message.ar, {
        body: `الوقت: ${prayerTime}`,
        icon: '/static/img/icon-192x192.png',
        badge: '/static/img/badge-72x72.png',
        tag: `prayer-${prayer}`,
        requireInteraction: true,
        actions: [
          { action: 'mark-done', title: 'تم صلاتها' },
          { action: 'snooze', title: 'اذكرني لاحقاً' }
        ]
      });
    }

    // Play sound if enabled
    if (this.settings.sound_enabled) {
      this.testSound();
    }
  }

  showWuduReminder(prayer, prayerTime) {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('تذكير الوضوء', {
        body: `تذكير: الوضوء قريباً قبل صلاة ${['الفجر', 'الظهر', 'العصر', 'المغرب', 'العشاء'][['fajr', 'dhuhr', 'asr', 'maghrib', 'isha'].indexOf(prayer)]}`,
        icon: '/static/img/icon-192x192.png',
        tag: `wudu-${prayer}`
      });
    }
  }

  destroy() {
    if (this.notificationCheckInterval) {
      clearInterval(this.notificationCheckInterval);
    }
  }
}

// Initialize notifications system on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.prayerNotifications = new PrayerNotificationSystem();
  });
} else {
  window.prayerNotifications = new PrayerNotificationSystem();
}
