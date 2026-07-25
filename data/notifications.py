# Prayer Notification Settings & Configuration

DEFAULT_NOTIFICATION_SETTINGS = {
    "enabled": True,
    "sound_enabled": True,
    "sound_volume": 80,
    "notify_before_minutes": -5,
    "snooze_duration_minutes": 10,
    "wudu_reminder_enabled": True,
    "wudu_reminder_minutes": 15,
    "prayer_notifications": {
        "fajr": True,
        "dhuhr": True,
        "asr": True,
        "maghrib": True,
        "isha": True
    },
    "notify_offset_per_prayer": {
        "fajr": -10,
        "dhuhr": -5,
        "asr": 0,
        "maghrib": -5,
        "isha": -10
    }
}

PRAYER_TIMES = [
    {"id": "fajr", "name": "الفجر", "nameEn": "Fajr", "icon": "bi-sunrise"},
    {"id": "dhuhr", "name": "الظهر", "nameEn": "Dhuhr", "icon": "bi-sun"},
    {"id": "asr", "name": "العصر", "nameEn": "Asr", "icon": "bi-cloud-sun"},
    {"id": "maghrib", "name": "المغرب", "nameEn": "Maghrib", "icon": "bi-sunset"},
    {"id": "isha", "name": "العشاء", "nameEn": "Isha", "icon": "bi-moon-stars"}
]

NOTIFICATION_MESSAGES = {
    "fajr": {
        "ar": "حان وقت صلاة الفجر",
        "en": "It's time for Fajr prayer"
    },
    "dhuhr": {
        "ar": "حان وقت صلاة الظهر",
        "en": "It's time for Dhuhr prayer"
    },
    "asr": {
        "ar": "حان وقت صلاة العصر",
        "en": "It's time for Asr prayer"
    },
    "maghrib": {
        "ar": "حان وقت صلاة المغرب",
        "en": "It's time for Maghrib prayer"
    },
    "isha": {
        "ar": "حان وقت صلاة العشاء",
        "en": "It's time for Isha prayer"
    }
}

WUDU_REMINDER_MESSAGE = {
    "ar": "تذكير: الوضوء قريباً",
    "en": "Reminder: Prepare for Wudu soon"
}
