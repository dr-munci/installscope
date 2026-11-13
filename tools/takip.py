#!/usr/bin/env python3
"""Zaman ve commit takibi.

git log'daki commit'leri ISO haftalarına göre gruplar, haftalık planla
karşılaştırır ve en yakın teslim tarihine kalan günü yazar.

Kullanım:
    python3 tools/takip.py                 # HEAD üzerinden
    python3 tools/takip.py --ref origin/main
    python3 tools/takip.py --bugun 2026-11-24   # başka bir günü taklit et
"""
import argparse
import subprocess
from collections import Counter
from datetime import date

# Haftalık plan: (ISO yılı, ISO haftası, plan kodu, iş).
# ISO haftası Pazartesi başlar, Pazar biter. Ders kuralı "en az 5 farklı
# hafta" dediği için takvim haftasını kullanmak en savunulabilir seçim.
PLAN = [
    (2026, 45, "H1", "Repo iskeleti, README (YZ beyanı), K1 önerisi"),
    (2026, 46, "H1/H2", "K1 teslimi (12.11); VM'de bcc kurulumu; collector başlangıcı"),
    (2026, 47, "H2", "Collector v0: execve + openat + connect tek JSONL"),
    (2026, 48, "H3", "M1 ölçümü (5+5 tekrar, CSV); K2 teslimi (26.11)"),
    (2026, 49, "H4", "Process ağacı (büküm), orphan işaretleme"),
    (2026, 50, "H5", "Pano v0.5, video, ara rapor; K3 teslimi (10.12)"),
    (2026, 51, "H6", "M2 (npm/pip/apt), strace ve /proc kanıtı"),
    (2026, 52, "H7", "M3, kırılma testleri (KG1, KG4, KG5)"),
    (2026, 53, "H8", "Final rapor, savunma hazırlığı"),
]

# Teslim tarihleri (CLAUDE.md'deki takvimden).
TESLIMLER = [
    ("K1", date(2026, 11, 12)),
    ("K2", date(2026, 11, 26)),
    ("K3", date(2026, 12, 10)),
]

HEDEF_HAFTA = 5  # Kural 5: commit geçmişi en az 5 farklı haftaya yayılmalı


YZ_YAZARI = "Claude"  # YZ'nin attığı commit'lerin yazar adı


def commitler(ref):
    """git log'dan her commit için (yazar tarihi, yazar adı) döndürür.

    GitHub'ın commit listesinde gösterdiği tarih yazar tarihidir; hoca da
    büyük ihtimalle ona bakacağı için onu sayıyoruz. Yazar adını da alıyoruz,
    çünkü savunma katsayısı Git geçmişine bakıyor ve öğrencinin kendi
    commit'leri ayrıca görünmeli.
    """
    cikti = subprocess.run(
        ["git", "log", ref, "--format=%ad|%an", "--date=short"],
        capture_output=True, text=True, check=True,
    ).stdout
    sonuc = []
    for satir in cikti.splitlines():
        tarih, yazar = satir.split("|", 1)
        sonuc.append((date.fromisoformat(tarih), yazar))
    return sonuc


def haftalara_say(liste):
    """Her (yıl, hafta) çiftinde kaç commit olduğunu sayar."""
    return Counter(t.isocalendar()[:2] for t, _ in liste)


def main():
    ap = argparse.ArgumentParser(description="Commit ve takvim takibi")
    ap.add_argument("--ref", default="HEAD", help="sayılacak dal (varsayılan HEAD)")
    ap.add_argument("--bugun", type=date.fromisoformat, default=date.today())
    args = ap.parse_args()

    hepsi = commitler(args.ref)
    sayac = haftalara_say(hepsi)
    ogrenci = haftalara_say([c for c in hepsi if c[1] != YZ_YAZARI])
    bu_hafta = args.bugun.isocalendar()[:2]

    print(f"Bugün: {args.bugun}  (ISO hafta {bu_hafta[1]})\n")
    print(f"{'Hafta':<6} {'Plan':<6} {'Commit':>6} {'Senin':>5}  Durum      İş")
    for yil, hafta, kod, is_ in PLAN:
        n = sayac.get((yil, hafta), 0)
        if (yil, hafta) == bu_hafta:
            durum = "← BU HAFTA"
        elif (yil, hafta) > bu_hafta:
            durum = "ileride"
        else:
            durum = "tamam" if n else "BOŞ!"
        m = ogrenci.get((yil, hafta), 0)
        print(f"W{hafta:<5} {kod:<6} {n:>6} {m:>5}  {durum:<10} {is_}")

    farkli = len(sayac)
    print(f"\nCommit'li farklı hafta: {farkli} / hedef {HEDEF_HAFTA}"
          + ("  ✓" if farkli >= HEDEF_HAFTA else ""))

    print(f"Senin commit'lerinin olduğu hafta: {len(ogrenci)}")

    if sayac.get(bu_hafta, 0) == 0:
        print("UYARI: Bu hafta henüz commit yok. Hafta Pazar akşamı kapanıyor.")
    elif ogrenci.get(bu_hafta, 0) == 0:
        print("NOT: Bu haftaki commit'lerin yazarı sen değilsin; VM'den kendi adınla commit'le.")

    # Henüz geçmemiş ilk teslimi bul
    for ad, gun in TESLIMLER:
        kalan = (gun - args.bugun).days
        if kalan >= 0:
            print(f"Sıradaki teslim: {ad} ({gun:%d.%m}), {kalan} gün kaldı.")
            break
    else:
        print("K1–K3 teslimleri geçti; final (K4–K5) tarihini CLAUDE.md'ye ekle.")


if __name__ == "__main__":
    main()
