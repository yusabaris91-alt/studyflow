"""YKS müfredatı: TYT'nin tüm dersleri + AYT'nin Matematik ve Fen (Fizik, Kimya, Biyoloji) kısmı.

Veri tek yerde durur; ilk kurulumda (migration v3) veritabanına yüklenir. Sonrasında konular
uygulamadan eklenip silinebilir. Listeler ÖSYM/MEB kazanım dağılımına göre özetlenmiştir;
yıllık ÖSYM kılavuzuyla karşılaştırıp "Konular" sayfasından düzeltebilirsin.
"""
from __future__ import annotations

# (sınav, ders adı, [konular])
CURRICULUM: list[tuple[str, str, list[str]]] = [
    # ------------------------------------------------------------------ TYT
    ("TYT", "TYT Türkçe", [
        "Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Anlam (Ana Düşünce, Yapı, Anlatım Biçimleri)",
        "Ses Bilgisi", "Yazım Kuralları", "Noktalama İşaretleri", "Sözcükte Yapı (Kök ve Ekler)",
        "İsim (Ad), Sıfat, Zamir", "Zarf, Edat, Bağlaç, Ünlem", "Fiiller (Kip, Zaman, Ek Fiil)",
        "Fiilimsiler", "Fiilde Çatı", "Cümlenin Öğeleri", "Cümle Türleri", "Anlatım Bozuklukları",
    ]),
    ("TYT", "TYT Matematik", [
        "Temel Kavramlar", "Sayı Basamakları", "Bölme ve Bölünebilme", "EBOB – EKOK",
        "Rasyonel Sayılar", "Basit Eşitsizlikler", "Mutlak Değer", "Üslü Sayılar", "Köklü Sayılar",
        "Çarpanlara Ayırma", "Oran – Orantı", "Denklem Çözme", "Sayı ve Kesir Problemleri",
        "Yaş Problemleri", "Yüzde, Kâr – Zarar Problemleri", "Karışım Problemleri",
        "Hareket Problemleri", "İşçi – Havuz Problemleri", "Kümeler", "Kartezyen Çarpım", "Mantık",
        "Fonksiyonlar", "Polinomlar", "İkinci Dereceden Denklemler", "Permütasyon ve Kombinasyon",
        "Olasılık", "Veri, Tablo ve Grafikler",
    ]),
    ("TYT", "TYT Geometri", [
        "Doğruda ve Üçgende Açılar", "Dik Üçgen ve Özel Üçgenler", "İkizkenar ve Eşkenar Üçgen",
        "Açıortay", "Kenarortay", "Eşlik ve Benzerlik", "Üçgende Alan", "Açı – Kenar Bağıntıları",
        "Çokgenler", "Yamuk", "Paralelkenar, Eşkenar Dörtgen, Deltoid", "Dikdörtgen ve Kare",
        "Çember ve Daire", "Analitik Geometri", "Katı Cisimler",
    ]),
    ("TYT", "TYT Fizik", [
        "Fizik Bilimine Giriş", "Madde ve Özellikleri", "Hareket ve Kuvvet", "İş, Güç ve Enerji",
        "Isı, Sıcaklık ve Genleşme", "Basınç", "Kaldırma Kuvveti", "Elektrostatik",
        "Elektrik Akımı ve Devreler", "Manyetizma", "Dalgalar", "Optik (Aynalar, Kırılma, Mercekler)",
    ]),
    ("TYT", "TYT Kimya", [
        "Kimya Bilimi", "Atom ve Periyodik Sistem", "Kimyasal Türler Arası Etkileşimler",
        "Maddenin Halleri", "Doğa ve Kimya", "Kimyanın Temel Kanunları", "Mol Kavramı",
        "Kimyasal Hesaplamalar", "Karışımlar", "Asitler, Bazlar ve Tuzlar", "Kimya Her Yerde",
    ]),
    ("TYT", "TYT Biyoloji", [
        "Canlıların Ortak Özellikleri", "Canlıların Temel Bileşenleri", "Hücre ve Organeller",
        "Madde Geçişleri", "Canlıların Sınıflandırılması", "Hücre Bölünmeleri ve Üreme",
        "Kalıtımın Genel İlkeleri", "Ekosistem Ekolojisi", "Güncel Çevre Sorunları",
    ]),
    ("TYT", "TYT Tarih", [
        "Tarih ve Zaman", "İlk ve Orta Çağlarda Türk Dünyası", "İslam Medeniyetinin Doğuşu",
        "İlk Türk – İslam Devletleri", "Selçuklu Türkiyesi", "Beylikten Devlete Osmanlı",
        "Dünya Gücü Osmanlı", "Osmanlı Kültür ve Medeniyeti", "Değişen Dünya Dengeleri ve Osmanlı",
        "Değişim Çağı: Avrupa ve Osmanlı (XVIII–XIX. yy)", "XX. Yüzyıl Başlarında Osmanlı",
        "Milli Mücadele", "Atatürkçülük ve Türk İnkılabı", "İki Savaş Arası Türkiye ve Dünya",
        "II. Dünya Savaşı ve Soğuk Savaş", "Küreselleşen Dünya",
    ]),
    ("TYT", "TYT Coğrafya", [
        "Doğa ve İnsan", "Dünya'nın Şekli ve Hareketleri", "Coğrafi Konum", "Harita Bilgisi",
        "Atmosfer ve Sıcaklık", "İklimler", "Basınç ve Rüzgârlar", "Nem, Yağış ve Buharlaşma",
        "İç Kuvvetler ve Yer Şekilleri", "Dış Kuvvetler", "Su, Toprak ve Bitki Varlığı",
        "Nüfus ve Göç", "Yerleşme", "Türkiye'nin Yer Şekilleri", "Ekonomik Faaliyetler",
        "Bölgeler ve Ülkeler", "Doğal Afetler", "Çevre ve Toplum",
    ]),
    ("TYT", "TYT Felsefe", [
        "Felsefeyle Tanışma", "Bilgi Felsefesi", "Varlık Felsefesi", "Ahlak Felsefesi",
        "Sanat Felsefesi", "Din Felsefesi", "Siyaset Felsefesi", "Bilim Felsefesi",
    ]),
    ("TYT", "TYT Din Kültürü", [
        "Bilgi ve İnanç", "Din ve İslam", "İslam ve İbadet", "Gençlik ve Değerler",
        "Gönül Coğrafyamız", "Allah – İnsan İlişkisi", "Hz. Muhammed'in Hayatı",
        "Vahiy ve Akıl", "İslam Düşüncesinde Yorumlar", "Din, Kültür ve Medeniyet",
        "İslam ve Bilim", "Yaşayan Dinler",
    ]),
    # ------------------------------------------------------------------ AYT
    ("AYT", "AYT Matematik", [
        "Fonksiyonlar ve Uygulamaları", "Polinomlar", "İkinci Dereceden Denklemler ve Eşitsizlikler",
        "Parabol", "Trigonometri", "Logaritma", "Üstel Fonksiyonlar", "Diziler",
        "Limit ve Süreklilik", "Türev", "İntegral", "Permütasyon, Kombinasyon, Binom",
        "Olasılık", "Doğrunun Analitik İncelenmesi", "Dönüşümler",
        "Çemberin Analitik İncelenmesi", "Çember ve Daire (Geometri)", "Katı Cisimler (Geometri)",
    ]),
    ("AYT", "AYT Fizik", [
        "Vektörler", "Bağıl Hareket", "Newton'un Hareket Yasaları", "Bir Boyutta Sabit İvmeli Hareket",
        "İki Boyutta Hareket ve Atışlar", "Enerji ve Hareket", "İtme ve Çizgisel Momentum",
        "Tork ve Denge", "Kütle Merkezi", "Basit Makineler", "Elektriksel Kuvvet ve Alan",
        "Elektriksel Potansiyel ve Sığa", "Manyetizma ve Elektromanyetik İndüksiyon",
        "Alternatif Akım ve Transformatörler", "Düzgün Çembersel Hareket",
        "Dönme, Yuvarlanma ve Açısal Momentum", "Kütle Çekim ve Kepler Yasaları",
        "Basit Harmonik Hareket", "Dalga Mekaniği", "Atom Fiziğine Giriş ve Radyoaktivite",
        "Modern Fizik ve Uygulamaları",
    ]),
    ("AYT", "AYT Kimya", [
        "Modern Atom Teorisi", "Gazlar", "Sıvı Çözeltiler ve Çözünürlük",
        "Kimyasal Tepkimelerde Enerji", "Kimyasal Tepkimelerde Hız", "Kimyasal Tepkimelerde Denge",
        "Asit – Baz Dengesi", "Çözünürlük Dengesi", "Kimya ve Elektrik",
        "Karbon Kimyasına Giriş", "Organik Bileşikler", "Enerji Kaynakları ve Bilimsel Gelişmeler",
    ]),
    ("AYT", "AYT Biyoloji", [
        "Sinir Sistemi", "Endokrin Sistem", "Duyu Organları", "Destek ve Hareket Sistemi",
        "Sindirim Sistemi", "Dolaşım ve Bağışıklık Sistemi", "Solunum Sistemi", "Boşaltım Sistemi",
        "Üreme Sistemi ve Embriyonik Gelişim", "Komünite ve Popülasyon Ekolojisi",
        "Nükleik Asitler ve Protein Sentezi", "Genetik Mühendisliği ve Biyoteknoloji",
        "Canlılarda Enerji Dönüşümleri", "Fotosentez ve Kemosentez", "Hücresel Solunum",
        "Bitki Biyolojisi",
    ]),
]
