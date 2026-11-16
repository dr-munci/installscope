#!/usr/bin/env python3
"""M1 – İzleme maliyeti: aynı kurulum, izleme kapalı ve açık.

Her tekrarda:
  1. temiz bir venv kurulur (önceki kurulumun izi kalmasın),
  2. sayfa önbelleği boşaltılır (diskten okuma koşulları aynı olsun),
  3. paket ya izlemesiz ya da collector altında kurulur ve süre ölçülür.
Kapalı/açık sırası her tekrarda yer değiştirir (K-A, A-K, ...) ki
"önce çalışan hep dezavantajlı" gibi bir sıra etkisi ortalamaya karışmasın.

Kullanım (VM'de, depo kökünden):
    sudo python3 bench/m1_maliyet.py                 # PyPI'den, 5+5 tekrar
    sudo python3 bench/m1_maliyet.py --kaynak yerel  # önceden indirilmiş paketlerden

Çıktı: bench/sonuclar/m1_<kaynak>_<tarih>.csv, aynı adla _ortam.txt ve _ozet.txt
"""
import argparse
import csv
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time

DEPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(DEPO, "collector"))
import collector  # noqa: E402  (kullaniciya_don'u yeniden kullanmak için)

COLLECTOR = os.path.join(DEPO, "collector", "collector.py")


def arguman_al():
    ap = argparse.ArgumentParser(description="M1: izleme maliyeti ölçümü")
    ap.add_argument("--tekrar", type=int, default=5, help="her mod için tekrar (≥5)")
    ap.add_argument("--paket", default="requests")
    ap.add_argument("--kaynak", choices=["ag", "yerel"], default="ag",
                    help="ag: PyPI'den indir; yerel: önceden indirilmiş wheel'lerden")
    ap.add_argument("--ayar", default=os.path.join(DEPO, "collector", "ayar.json"))
    ap.add_argument("--cikti-dizin", default=os.path.join(DEPO, "bench", "sonuclar"))
    return ap.parse_args()


def kullanici_olarak(komut, **kw):
    """Komutu sudo'yu çağıran kullanıcı olarak çalıştırır (pip root olmasın)."""
    return subprocess.run(komut, preexec_fn=collector.kullaniciya_don, **kw)


def calisma_dizini():
    """Geçici venv'ler için kullanıcının ev dizininde bir klasör hazırlar."""
    ev = os.path.expanduser(f"~{os.environ.get('SUDO_USER', '')}")
    yol = os.path.join(ev, ".installscope_m1")
    os.makedirs(yol, exist_ok=True)
    sahibi_yap(yol)
    return yol


def sahibi_yap(yol):
    """Root olarak oluşturulan dosyayı kullanıcıya devreder (git add edebilsin)."""
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if uid and gid:
        os.chown(yol, int(uid), int(gid))


def sayfa_onbellegini_bosalt():
    """Çekirdeğin sayfa önbelleğini boşaltır.

    Neden: Bir önceki kurulumun okuduğu dosyalar (Python kütüphaneleri,
    wheel'ler) RAM'de kalırsa sonraki kurulum diske gitmeden hızlı biter.
    sync önce kirli sayfaları diske yazar; '3' sayfa önbelleğini ve
    dentry/inode önbelleklerini bırakır.
    """
    os.sync()
    with open("/proc/sys/vm/drop_caches", "w") as f:
        f.write("3")


def temiz_venv(dizin):
    """Her ölçümden önce sıfırdan bir venv kurar ve pip yolunu döndürür."""
    venv = os.path.join(dizin, "venv")
    shutil.rmtree(venv, ignore_errors=True)
    kullanici_olarak([sys.executable, "-m", "venv", venv], check=True)
    return os.path.join(venv, "bin", "pip")


def pip_komutu(pip, a, tekerlek_dizini):
    """Ölçülecek pip komutunu kurar. --no-cache-dir: pip'in kendi önbelleği kapalı."""
    k = [pip, "install", "--no-cache-dir", "--disable-pip-version-check", "-q"]
    if a.kaynak == "yerel":
        k += ["--no-index", "--find-links", tekerlek_dizini]
    return k + [a.paket]


def olcum_kapali(komut):
    """İzlemesiz kurulum: yalnızca süre ve çıkış kodu."""
    t = time.monotonic()
    s = kullanici_olarak(komut, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return {"sure_s": round(time.monotonic() - t, 3), "cikis_kodu": s.returncode,
            "hata": s.stderr.strip()[-300:]}


def olcum_acik(komut, a, jsonl):
    """Collector altında kurulum. Süreyi collector'ın 'end' satırından alıyoruz.

    Neden dışarıdan ölçmüyoruz: collector'ın toplam süresine eBPF derleme
    (birkaç saniye) da girer. M1'in sorusu "izleme kurulumu ne kadar
    yavaşlatıyor?" olduğu için yalnızca komutun başla→bitir süresini
    karşılaştırıyoruz; derleme süresini ayrı sütunda raporluyoruz.
    """
    s = subprocess.run([sys.executable, COLLECTOR, "--ayar", a.ayar, "-o", jsonl, "--"] + komut,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    sayac = {"exec": 0, "open": 0, "connect": 0}
    son = {}
    bas = {}
    with open(jsonl, encoding="utf-8") as f:
        for satir in f:
            o = json.loads(satir)
            if o["type"] in sayac:
                sayac[o["type"]] += 1
            elif o["type"] == "end":
                son = o
            elif o["type"] == "start":
                bas = o
    return {"sure_s": son.get("sure_s"), "cikis_kodu": son.get("detail", s.returncode),
            "kayip": son.get("lost"), "derleme_s": bas.get("derleme_s"),
            "hata": s.stderr.strip()[-300:] if s.returncode else "", **sayac}


def ortam_yaz(yol, a):
    """Tekrar üretilebilirlik (F4) için ölçüm ortamını kaydeder."""
    def komut(k):
        try:
            return subprocess.run(k, capture_output=True, text=True).stdout.strip()
        except OSError:
            return "?"
    with open(yol, "w", encoding="utf-8") as f:
        f.write(f"tarih: {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"cekirdek: {platform.release()}\n")
        f.write(f"isletim_sistemi: {komut(['lsb_release', '-ds'])}\n")
        f.write(f"python: {platform.python_version()}\n")
        f.write(f"bcc: {komut(['dpkg-query', '-W', '-f=${Version}', 'python3-bpfcc'])}\n")
        f.write(f"cpu_sayisi: {os.cpu_count()}\n")
        f.write(f"paket: {a.paket}, kaynak: {a.kaynak}, tekrar: {a.tekrar}\n")
        f.write(f"ayar: {json.dumps(collector.ayar_oku(a.ayar), ensure_ascii=False)}\n")
    sahibi_yap(yol)


def ozet(satirlar):
    """Mod başına ortalama, standart sapma ve izleme maliyetini (%) hesaplar."""
    def sureler(mod):
        return [r["sure_s"] for r in satirlar if r["mod"] == mod and r["cikis_kodu"] == 0]
    k, a = sureler("kapali"), sureler("acik")
    metin = []
    for ad, x in (("kapalı", k), ("açık", a)):
        if len(x) >= 2:
            metin.append(f"{ad:6}: n={len(x)}  ortalama={statistics.mean(x):.3f} s  "
                         f"std={statistics.stdev(x):.3f} s  min={min(x):.3f}  max={max(x):.3f}")
    if len(k) >= 2 and len(a) >= 2:
        fark = (statistics.mean(a) - statistics.mean(k)) / statistics.mean(k) * 100
        metin.append(f"izleme maliyeti: %{fark:.1f} (açık ortalaması / kapalı ortalaması − 1)")
    return "\n".join(metin)


def main():
    a = arguman_al()
    if os.geteuid() != 0:
        collector.hata("Ölçüm root ister (eBPF ve önbellek boşaltma): sudo ile çalıştırın.", 1)
    if a.tekrar < 5:
        print("UYARI: ders kuralı her ölçüm için en az 5 tekrar ister.", file=sys.stderr)
    collector.ayar_oku(a.ayar)  # ayar bozuksa ölçüme hiç başlama

    dizin = calisma_dizini()
    tekerlek = os.path.join(dizin, "wheelhouse")
    if a.kaynak == "yerel" and not os.path.isdir(tekerlek):
        print(f"[hazırlık] {a.paket} ve bağımlılıkları {tekerlek} içine indiriliyor...")
        # Ubuntu'nun sistem Python'unda pip yok; indirmeyi geçici bir venv'in pip'i yapar.
        kullanici_olarak([temiz_venv(dizin), "download", "-q", "-d", tekerlek, a.paket],
                         check=True)

    os.makedirs(a.cikti_dizin, exist_ok=True)
    sahibi_yap(a.cikti_dizin)
    kok = os.path.join(a.cikti_dizin, f"m1_{a.kaynak}_{time.strftime('%Y%m%d_%H%M')}")
    ortam_yaz(kok + "_ortam.txt", a)

    satirlar = []
    sira = 0
    for i in range(1, a.tekrar + 1):
        # Tek tekrarlarda önce kapalı, çift tekrarlarda önce açık (sıra etkisini dengeler)
        modlar = ["kapali", "acik"] if i % 2 else ["acik", "kapali"]
        for mod in modlar:
            sira += 1
            komut = pip_komutu(temiz_venv(dizin), a, tekerlek)
            sayfa_onbellegini_bosalt()
            if mod == "kapali":
                r = olcum_kapali(komut)
            else:
                r = olcum_acik(komut, a, os.path.join(dizin, f"olay_{i}.jsonl"))
            r.update({"tekrar": i, "sira": sira, "mod": mod, "kaynak": a.kaynak, "paket": a.paket})
            satirlar.append(r)
            print(f"[{sira:2}/{2 * a.tekrar}] tekrar {i} {mod:6} {r['sure_s']} s"
                  + (f"  exec={r['exec']} open={r['open']} connect={r['connect']} kayıp={r['kayip']}"
                     if mod == "acik" else "")
                  + (f"  ÇIKIŞ KODU {r['cikis_kodu']}: {r['hata']}" if r["cikis_kodu"] else ""))

    alanlar = ["tekrar", "sira", "mod", "kaynak", "paket", "sure_s", "cikis_kodu",
               "exec", "open", "connect", "kayip", "derleme_s"]
    with open(kok + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=alanlar, extrasaction="ignore")
        w.writeheader()
        w.writerows(satirlar)
    sahibi_yap(kok + ".csv")

    metin = ozet(satirlar)
    with open(kok + "_ozet.txt", "w", encoding="utf-8") as f:
        f.write(metin + "\n")
    sahibi_yap(kok + "_ozet.txt")
    print("\n" + metin + f"\n\nsonuçlar: {kok}.csv")


if __name__ == "__main__":
    main()
