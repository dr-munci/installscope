#!/usr/bin/env python3
"""installscope collector v1.

Bir kurulum komutunu kendisi başlatır ve o komutun process ağacında olan
execve, openat ve connect olaylarını eBPF ile yakalayıp JSONL dosyasına yazar.

Kullanım (VM'de, depo kökünden):
    sudo python3 collector/collector.py -o pip.jsonl -- ~/deneme/bin/pip install requests
    sudo python3 collector/collector.py --root -o apt.jsonl -- apt-get install -y cowsay

Çıktı: her satır bir JSON nesnesi
    {"ts_ns", "pid", "ppid", "comm", "type", "detail", ...}
İlk satır "start" (kök PID, komut, ayarlar), son satır "end" (çıkış kodu,
kayıp sayısı, kurulum süresi).

Ayarlar collector/ayar.json'dan okunur (başka dosya için --ayar).
Ctrl+C ya da SIGTERM gelirse izlenen komut da durdurulur ve "end" yine yazılır.
"""
import argparse
import json
import os
import pwd
import signal
import socket
import stat
import sys
import time

from bcc import BPF

BURASI = os.path.dirname(os.path.abspath(__file__))
TIPLER = {1: "exec", 2: "open", 3: "connect"}  # izleyici.c'deki TIP_* ile aynı

O_ACCMODE = 0o3   # openat bayraklarında okuma/yazma kipini tutan bitler
O_CREAT = 0o100   # "yoksa oluştur" bayrağı


def arguman_al():
    """Komut satırını okur: çıktı dosyası, --root ve '--' sonrasındaki komut."""
    ap = argparse.ArgumentParser(description="Kurulum komutunu eBPF ile izler")
    ap.add_argument("-o", "--cikti", required=True, help="JSONL çıktı dosyası")
    ap.add_argument("--ayar", default=os.path.join(BURASI, "ayar.json"),
                    help="ayar dosyası (varsayılan collector/ayar.json)")
    ap.add_argument("--root", action="store_true",
                    help="komutu root olarak çalıştır (apt için gerekli)")
    ap.add_argument("komut", nargs=argparse.REMAINDER, help="-- sonrasındaki komut")
    a = ap.parse_args()
    if a.komut and a.komut[0] == "--":
        a.komut = a.komut[1:]
    if not a.komut:
        ap.error("izlenecek komut yok; örnek: -- pip install requests")
    return a


def hata(mesaj, kod=3):
    """Anlamlı bir Türkçe hata mesajı yazıp programı verilen kodla bitirir."""
    print(f"HATA: {mesaj}", file=sys.stderr)
    sys.exit(kod)


def ayar_oku(yol):
    """Ayar dosyasını okur, doğrular ve sözlük olarak döndürür (KG5).

    Neden izin bitlerine kendimiz bakıyoruz: collector sudo ile, yani root
    olarak çalışır. Root, CAP_DAC_OVERRIDE yetkisi sayesinde 'chmod 000'
    yapılmış dosyayı bile okuyabilir; yani open() hata vermez. Dosya sahibinin
    "okuyamaz" dediği bir ayarı sessizce kullanmak yerine reddediyoruz.
    """
    try:
        bilgi = os.stat(yol)
    except FileNotFoundError:
        hata(f"Ayar dosyası bulunamadı: {yol}")
    if not bilgi.st_mode & stat.S_IRUSR:
        hata(f"Ayar dosyası okunamıyor: {yol} (izinler: "
             f"{stat.filemode(bilgi.st_mode)}). Düzeltmek için: chmod 644 {yol}")
    try:
        with open(yol, encoding="utf-8") as f:
            ayar = json.load(f)
    except PermissionError:
        hata(f"Ayar dosyasını açma izni yok: {yol}")
    except json.JSONDecodeError as e:
        hata(f"Ayar dosyası bozuk: {yol}, satır {e.lineno}: {e.msg}")

    olaylar = ayar.get("olaylar", list(TIPLER.values()))
    bilinmeyen = set(olaylar) - set(TIPLER.values())
    if bilinmeyen:
        hata(f"Ayar dosyasında bilinmeyen olay tipi: {', '.join(sorted(bilinmeyen))}"
             f" (geçerli olanlar: {', '.join(TIPLER.values())})")
    # perf buffer sayfa sayısı 2'nin kuvveti olmalı (çekirdek halka tamponu böyle ister)
    sayfa = ayar.get("perf_sayfa", 256)
    if not (isinstance(sayfa, int) and sayfa > 0 and sayfa & (sayfa - 1) == 0):
        hata(f"perf_sayfa 2'nin kuvveti olmalı (ör. 64, 256), verilen: {sayfa}")
    return {"olaylar": olaylar, "perf_sayfa": sayfa}


def kullaniciya_don():
    """Çocuk process'te: sudo'yu çağıran kullanıcının kimliğine geri döner.

    Neden: eBPF yüklemek root ister ama pip/npm'i root olarak çalıştırmak
    gerçek kullanımı yansıtmaz (dosyalar /root altına gider). sudo, asıl
    kullanıcıyı SUDO_UID/SUDO_GID değişkenlerinde saklar.
    """
    uid = os.environ.get("SUDO_UID")
    if uid is None:
        return  # sudo'suz çalıştırılmış; kimlik zaten doğru
    kisi = pwd.getpwuid(int(uid))
    os.initgroups(kisi.pw_name, kisi.pw_gid)  # ek grupları da geri yükle
    os.setgid(kisi.pw_gid)                    # önce grup, sonra kullanıcı:
    os.setuid(kisi.pw_uid)                    # setuid sonrası setgid yapılamaz
    os.environ["HOME"] = kisi.pw_dir
    os.environ["USER"] = kisi.pw_name


def komutu_hazirla(komut, root_kalsin):
    """Komutu fork eder ama exec'i bekletir; çocuğun PID'ini döndürür.

    Neden bekletiyoruz: Kökün PID'ini eBPF haritasına probe'lar yüklendikten
    SONRA ama komut çalışmaya başlamadan ÖNCE koymamız gerek. Yoksa ilk
    olaylar kaçar.

    İki boru (pipe) ile el sıkışma:
      1. çocuk kimliğini değiştirir (/etc/passwd okur) ve "hazırım" der,
      2. ebeveyn kökü ancak bundan SONRA izlemeye alır ve "başla" der,
      3. çocuk exec eder.
    Neden: kimlik değiştirmek için açılan dosyalar collector'ın kendi işi,
    kurulumun değil. Kök erken izlenirse bunlar yanlışlıkla kayda girer
    (ilk denemede /etc/passwd, /etc/nsswitch.conf böyle görünmüştü).
    """
    hazir_oku, hazir_yaz = os.pipe()  # çocuk → ebeveyn: "hazırım"
    basla_oku, basla_yaz = os.pipe()  # ebeveyn → çocuk: "başla"
    pid = os.fork()
    if pid == 0:  # --- çocuk ---
        os.close(hazir_oku)
        os.close(basla_yaz)
        if not root_kalsin:
            kullaniciya_don()
        os.write(hazir_yaz, b"h")
        os.close(hazir_yaz)
        os.read(basla_oku, 1)  # ebeveyn "başla" diyene kadar burada bloklanır
        os.close(basla_oku)
        try:
            os.execvp(komut[0], komut)
        except OSError as e:
            print(f"komut çalıştırılamadı: {e}", file=sys.stderr)
            os._exit(127)
    os.close(hazir_yaz)  # --- ebeveyn ---
    os.close(basla_oku)
    os.read(hazir_oku, 1)  # çocuk kimliğini değiştirene kadar bekle
    os.close(hazir_oku)
    return pid, basla_yaz


def cocugu_durdur(pid, bekle_s=5):
    """Ctrl+C ya da SIGTERM'de izlenen komutu da durdurur; çıkış durumunu döndürür.

    Önce SIGINT gönderiyoruz (Ctrl+C ile aynı; pip yarım kurulumu temizleyebilir).
    Komut bekle_s saniye içinde bitmezse SIGKILL ile zorla bitiriyoruz.
    Neden: collector ölüp komut arkada yaşamaya devam ederse ölçümler kirlenir.
    """
    try:
        os.kill(pid, signal.SIGINT)
    except ProcessLookupError:
        pass  # zaten bitmiş
    son = time.monotonic() + bekle_s
    while time.monotonic() < son:
        bitti, durum = os.waitpid(pid, os.WNOHANG)
        if bitti:
            return durum
        time.sleep(0.1)
    os.kill(pid, signal.SIGKILL)
    return os.waitpid(pid, 0)[1]


def sigterm_geldi(signum, cerceve):
    """SIGTERM'i Ctrl+C gibi ele almak için KeyboardInterrupt'a çevirir."""
    raise KeyboardInterrupt


def detay_olustur(ev):
    """Olayın 'detail' alanını üretir: dosya/program yolu ya da ip:port."""
    if ev.tip == 3:  # connect
        if ev.aile == socket.AF_INET:
            ip = socket.inet_ntop(socket.AF_INET, bytes(ev.adres[:4]))
            return f"{ip}:{socket.ntohs(ev.port)}"
        ip = socket.inet_ntop(socket.AF_INET6, bytes(ev.adres[:16]))
        return f"[{ip}]:{socket.ntohs(ev.port)}"
    return ev.detay.decode("utf-8", "replace")


def olay_sozlugu(ev):
    """Çekirdekten gelen ham kaydı JSON'a yazılacak sözlüğe çevirir."""
    d = {
        "ts_ns": ev.ts_ns,
        "pid": ev.pid,
        "ppid": ev.ppid,
        "comm": ev.comm.decode("utf-8", "replace"),
        "type": TIPLER.get(ev.tip, "?"),
        "detail": detay_olustur(ev),
    }
    if ev.tip == 2:  # open/openat: yazma amaçlı mı, başarılı mı?
        d["write"] = bool((ev.bayrak & O_ACCMODE) or (ev.bayrak & O_CREAT))
        d["ret"] = ev.sonuc  # ≥0: dosya tanımlayıcı, <0: -errno (ör. -2 = ENOENT)
    return d


class Yazici:
    """JSONL'ye satır satır yazar ve her satırdan sonra diske gönderir.

    Neden her satırda flush: collector kill -9 ile öldürülürse (KG1) Python'un
    tamponunda bekleyen satırlar kaybolur. flush ile her olay anında çekirdeğe
    (sayfa önbelleğine) geçer; en kötü ihtimalle yalnızca son satır yarım kalır.
    """

    def __init__(self, yol):
        self.f = open(yol, "w", encoding="utf-8")

    def yaz(self, sozluk):
        try:
            self.f.write(json.dumps(sozluk, ensure_ascii=False) + "\n")
            self.f.flush()
        except OSError as e:  # ör. disk dolu (KG2)
            print(f"HATA: çıktı dosyasına yazılamadı ({e.strerror}). "
                  "Disk dolu olabilir; izleme durduruluyor.", file=sys.stderr)
            sys.exit(2)


def main():
    a = arguman_al()
    if os.geteuid() != 0:
        hata("eBPF programı yüklemek için root gerekir: sudo ile çalıştırın.", 1)
    ayar = ayar_oku(a.ayar)  # BPF yüklemeden önce: hatalı ayarda hızlı çık

    yazici = Yazici(a.cikti)
    kayip = [0]  # perf buffer'da kaybolan olay sayısı (M3, KG4)

    # 1) eBPF programını derle ve yükle.
    # -fms-extensions: çekirdek 7.0 başlıkları için gerekli (docs/ortam.md).
    # -DIZLE_OPEN gibi tanımlar: ayardaki olay tiplerini açar; tanımlanmayan
    #  tipin probe'u derlenmez, yani hiç bağlanmaz (#ifdef, izleyici.c).
    t0 = time.monotonic()
    bayraklar = ["-fms-extensions"] + [f"-DIZLE_{t.upper()}" for t in ayar["olaylar"]]
    b = BPF(src_file=os.path.join(BURASI, "izleyici.c"), cflags=bayraklar)
    derleme_s = time.monotonic() - t0

    # 2) Komutu fork et (henüz exec etmedi) ve kökü izlenenlere ekle.
    kok, basla_borusu = komutu_hazirla(a.komut, a.root)
    b["izlenen"][b["izlenen"].Key(kok)] = b["izlenen"].Leaf(1)

    def olay_geldi(cpu, veri, boyut):
        yazici.yaz(olay_sozlugu(b["olaylar"].event(veri)))

    def olay_kayboldu(sayi):
        kayip[0] += sayi
        yazici.yaz({"type": "lost", "detail": sayi})

    # page_cnt: CPU başına tampon boyutu (sayfa). Büyük tampon = daha az kayıp.
    b["olaylar"].open_perf_buffer(olay_geldi, page_cnt=ayar["perf_sayfa"],
                                  lost_cb=olay_kayboldu)

    yazici.yaz({"type": "start", "pid": kok, "detail": " ".join(a.komut),
                "ayar": ayar, "derleme_s": round(derleme_s, 3)})

    # 3) Çocuğa "başla" de ve olayları komut bitene kadar oku.
    signal.signal(signal.SIGTERM, sigterm_geldi)
    durduruldu = False
    basla = time.monotonic()
    os.write(basla_borusu, b"x")
    os.close(basla_borusu)
    try:
        while True:
            b.perf_buffer_poll(timeout=100)  # en fazla 100 ms bekle
            bitti, durum = os.waitpid(kok, os.WNOHANG)
            if bitti:
                break
    except KeyboardInterrupt:
        # Temizlik sırasında ikinci bir Ctrl+C bizi yarıda kesmesin.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        durduruldu = True
        print("durduruluyor: izlenen komut da sonlandırılıyor...", file=sys.stderr)
        durum = cocugu_durdur(kok)
    sure_s = time.monotonic() - basla
    b.perf_buffer_poll(timeout=200)  # tamponda kalan son olayları da al

    kod = os.waitstatus_to_exitcode(durum)
    yazici.yaz({"type": "end", "pid": kok, "detail": kod, "lost": kayip[0],
                "sure_s": round(sure_s, 3), "durduruldu": durduruldu})
    print(f"bitti: çıkış kodu {kod}, süre {sure_s:.2f} s, kaybolan olay "
          f"{kayip[0]}, çıktı {a.cikti}" + (" (durduruldu)" if durduruldu else ""),
          file=sys.stderr)


if __name__ == "__main__":
    main()
