#!/usr/bin/env python3
"""installscope collector v0.

Bir kurulum komutunu kendisi başlatır ve o komutun process ağacında olan
execve, openat ve connect olaylarını eBPF ile yakalayıp JSONL dosyasına yazar.

Kullanım (VM'de, depo kökünden):
    sudo python3 collector/collector.py -o pip.jsonl -- ~/deneme/bin/pip install requests
    sudo python3 collector/collector.py --root -o apt.jsonl -- apt-get install -y cowsay

Çıktı: her satır bir JSON nesnesi
    {"ts_ns", "pid", "ppid", "comm", "type", "detail", ...}
İlk satır "start" (kök PID ve komut), son satır "end" (çıkış kodu, kayıp sayısı).
"""
import argparse
import json
import os
import pwd
import socket
import sys

from bcc import BPF

BURASI = os.path.dirname(os.path.abspath(__file__))
TIPLER = {1: "exec", 2: "open", 3: "connect"}  # izleyici.c'deki TIP_* ile aynı

O_ACCMODE = 0o3   # openat bayraklarında okuma/yazma kipini tutan bitler
O_CREAT = 0o100   # "yoksa oluştur" bayrağı


def arguman_al():
    """Komut satırını okur: çıktı dosyası, --root ve '--' sonrasındaki komut."""
    ap = argparse.ArgumentParser(description="Kurulum komutunu eBPF ile izler")
    ap.add_argument("-o", "--cikti", required=True, help="JSONL çıktı dosyası")
    ap.add_argument("--root", action="store_true",
                    help="komutu root olarak çalıştır (apt için gerekli)")
    ap.add_argument("komut", nargs=argparse.REMAINDER, help="-- sonrasındaki komut")
    a = ap.parse_args()
    if a.komut and a.komut[0] == "--":
        a.komut = a.komut[1:]
    if not a.komut:
        ap.error("izlenecek komut yok; örnek: -- pip install requests")
    return a


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
    olaylar kaçar. Çocuk bir boruyu (pipe) okuyarak bekler; ebeveyn hazır
    olunca boruya bir bayt yazar ve çocuk exec eder.
    """
    oku, yaz = os.pipe()
    pid = os.fork()
    if pid == 0:  # --- çocuk ---
        os.close(yaz)
        os.read(oku, 1)  # ebeveyn "başla" diyene kadar burada bloklanır
        os.close(oku)
        if not root_kalsin:
            kullaniciya_don()
        try:
            os.execvp(komut[0], komut)
        except OSError as e:
            print(f"komut çalıştırılamadı: {e}", file=sys.stderr)
            os._exit(127)
    os.close(oku)  # --- ebeveyn ---
    return pid, yaz


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
    if ev.tip == 2:  # openat: yazma amaçlı mı açıldı?
        d["write"] = bool((ev.bayrak & O_ACCMODE) or (ev.bayrak & O_CREAT))
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
        sys.exit("eBPF programı yüklemek için root gerekir: sudo ile çalıştırın.")

    yazici = Yazici(a.cikti)
    kayip = [0]  # perf buffer'da kaybolan olay sayısı (M3, KG4)

    # 1) eBPF programını derle ve yükle.
    # -fms-extensions: çekirdek 7.0 başlıkları için gerekli (docs/ortam.md).
    b = BPF(src_file=os.path.join(BURASI, "izleyici.c"),
            cflags=["-fms-extensions"])

    # 2) Komutu fork et (henüz exec etmedi) ve kökü izlenenlere ekle.
    kok, basla_borusu = komutu_hazirla(a.komut, a.root)
    b["izlenen"][b["izlenen"].Key(kok)] = b["izlenen"].Leaf(1)

    def olay_geldi(cpu, veri, boyut):
        yazici.yaz(olay_sozlugu(b["olaylar"].event(veri)))

    def olay_kayboldu(sayi):
        kayip[0] += sayi
        yazici.yaz({"type": "lost", "detail": sayi})

    # page_cnt: CPU başına tampon boyutu (sayfa). Büyük tampon = daha az kayıp.
    b["olaylar"].open_perf_buffer(olay_geldi, page_cnt=256, lost_cb=olay_kayboldu)

    yazici.yaz({"type": "start", "pid": kok, "detail": " ".join(a.komut)})

    # 3) Çocuğa "başla" de ve olayları komut bitene kadar oku.
    os.write(basla_borusu, b"x")
    os.close(basla_borusu)
    while True:
        b.perf_buffer_poll(timeout=100)  # en fazla 100 ms bekle
        bitti, durum = os.waitpid(kok, os.WNOHANG)
        if bitti:
            break
    b.perf_buffer_poll(timeout=200)  # tamponda kalan son olayları da al

    kod = os.waitstatus_to_exitcode(durum)
    yazici.yaz({"type": "end", "pid": kok, "detail": kod, "lost": kayip[0]})
    print(f"bitti: çıkış kodu {kod}, kaybolan olay {kayip[0]}, çıktı {a.cikti}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
