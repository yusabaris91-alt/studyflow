"""Uygulama ayarları. Yollar ortam değişkenleriyle değiştirilebilir."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("STUDYFLOW_DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "studyflow.db"
# Yedekleri iCloud/OneDrive/Dropbox gibi senkron bir klasöre yönlendirmek için:
BACKUP_DIR = Path(os.environ.get("STUDYFLOW_BACKUP_DIR", DATA_DIR / "backups"))
KEEP_AUTO_BACKUPS = 14

STUDY_TYPES = [
    "Konu çalışması",
    "Soru çözümü",
    "Deneme sınavı",
    "Tekrar",
    "Yanlış analizi",
    "Video / Ders",
]

DEFAULT_SUBJECTS = [
    "Türkçe", "Matematik", "Geometri", "Fizik", "Kimya", "Biyoloji",
    "Edebiyat", "Tarih", "Coğrafya", "Felsefe",
]

# Soru sayısının anlamlı olduğu çalışma türleri (diğerlerinde alan hiç gösterilmez).
QUESTION_TYPES = {"Soru çözümü", "Deneme sınavı", "Yanlış analizi"}
