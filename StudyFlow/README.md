# StudyFlow – YKS çalışma planlayıcı

**Haftalık şablon → akşamdan yarının planı → bugünün esnek icrası → rapor.**

## Kurulum (VS Code terminali)
```bash
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
streamlit run app.py --server.address 0.0.0.0
```
Bilgisayarda: http://localhost:8501 · Aynı Wi‑Fi'deki telefon/iPad'de: `http://<bilgisayar-IP>:8501`
Testler: `pytest -q`

## Akış (üstteki sayfa seçici)
1. **📅 Şablon** (bir kez): Pazartesi–Pazar için o gün çalışılacak dersleri seç (ör. Pzt: AYT Matematik, TYT Fizik).
   Saatli program değil, günün **ders havuzu**; her derse isteğe bağlı hedef süre (dk) verilir.
   Günü başka günlere kopyalayabilirsin. Haftalık hedefler (ders başına) şablon toplamından otomatik oluşur.
2. **🌙 Yarın** (akşamdan): Yarının (ya da sonraki 7 günün) şablon dersleri kart kart gelir.
   Her derste tek dokunuşla **➕ sıradaki konu** eklenir ya da "Konu seç / serbest" ile netleştirilir.
   Şablon dışı ders de eklenebilir.
3. **☀️ Bugün** (icra):
   - **✅ Tamamla**: süre (önceden dolu) + çözülen soru + "konuyu bitirdim" → çalışma günlüğüne işlenir.
   - **🔄 Değiştir**: "AYT Fizik" yazıyordu ama "AYT Kimya" çalıştın → tek adımda derse/konuya çevir
     (kart "🔄 AYT Fizik yerine" rozetini taşır; kayıt gerçek çalışılan derse yazılır).
   - **➕ Plan dışı / ekstra çalışma**: planda olmayan çalışmayı doğrudan kaydet.
   - **➡ Yarına aktar**: tek görev ya da "Kalan N görevi yarına aktar". Geçmişten kalanlar "⏳ Bekleyen"de durur.
   - **👀 Yarın ve sonraki günler**: kapalı bir bölümde önünü gör.
   - Şablonda dersi olan ama planı hazırlanmamış gün için **📋 Bugünün taslağını hazırla**.
4. **📊 Rapor**: toplam süre, ders dağılımı (pasta / çubuk), **hedef ↔ gerçekleşen**,
   TYT/AYT **müfredat ilerlemesi** (biten konu / toplam), günlere ve türe göre dağılım, çalışma kayıtları.
5. **📚 Konular**: YKS konu listesi; bitenleri işaretle, kendi konunu ekle/sil.
   TYT'nin tüm dersleri + AYT'nin Matematik, Fizik, Kimya, Biyoloji konuları ilk açılışta yüklenir.
   Listeler özet niteliğindedir; güncel ÖSYM kılavuzuyla karşılaştırıp düzenle.
6. **⚙️ Ayar**: dersler (silinmez, arşivlenir), yedekleme/geri yükleme.

## Veri güvenliği (değişmedi)
- Tek dosya SQLite: `data/studyflow.db` (WAL, `synchronous=FULL`, foreign key zorunlu).
- Günde bir otomatik yedek (son 14), `data/backups/`. Her yedek `integrity_check` ile doğrulanır.
- Geri yüklemeden önce mevcut hâl `pre-restore` olarak saklanır. Manuel yedekler asla silinmez.
- **Önemli**: yedekler aynı diskte. Bulut klasörüne yönlendir:
  `STUDYFLOW_BACKUP_DIR=C:\Users\...\OneDrive\StudyFlowBackups` (veya Ayar'dan indir).

## Eski sürümden geçiş
Açılışta şema otomatik **v3**'e yükselir (mevcut görev ve kayıtlar korunur). Eski varsayılan dersler
(Matematik, Fizik…) daha önce kullanıldıysa **arşive** alınır (geçmiş raporlar bozulmaz, Ayar'dan geri getirilebilir),
kullanılmadıysa kaldırılır; yerine TYT/AYT dersleri gelir. Eski "haftalık havuz" görevleri Bugün'de
"Güne atanmamış görevler" altında görünmeye devam eder.

## Mimari
```
app.py                  giriş, sayfa seçici, açılışta DB hazırlama + günlük yedek
studyflow/config.py     yollar, çalışma türleri
studyflow/curriculum.py YKS müfredat verisi (TYT tümü + AYT Mat/Fen)
studyflow/models.py     Subject / Topic / TemplateEntry / Task / StudyLog
studyflow/db.py         bağlantı, migrations (PRAGMA user_version), yedekleme, müfredat yükleme
studyflow/repository.py TÜM SQL burada
studyflow/services.py   rapor hesapları, müfredat ilerlemesi, koçluk mesajı (UI'dan bağımsız)
studyflow/ui/           common (stil, bileşenler) · cards (görev kartları) · today · plan (yarın)
                        template · topics · reports · logs · settings
```
Şema değişikliği: `db.MIGRATIONS` listesine yeni fonksiyon ekle; açılışta otomatik uygulanır.

## Senkronizasyona geçiş (sonraki aşama)
Hazırlık yapıldı: UUID anahtarlar, her satırda `updated_at`, SQL tek katmanda. `Repository` ile aynı
metotlara sahip bir Postgres/Supabase uygulaması yazıp `app.py > get_repo()` içinde değiştirmek yeterli.
