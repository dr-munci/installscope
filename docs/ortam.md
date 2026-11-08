# Ortam

Bütün çalıştırma ve ölçümler kendi bilgisayarımdaki VirtualBox VM'inde yapılır.

| Bileşen | Değer |
|---|---|
| Sanallaştırma | VirtualBox |
| İşletim sistemi | Ubuntu 24.04 (Desktop) |
| Çekirdek | `7.0.0-42-generic` (HWE) |
| bcc paketi | `bpfcc-tools`, `python3-bpfcc` (Ubuntu deposundan); sürüm: [doldurulacak] |
| clang / LLVM | [doldurulacak] |
| Python | [doldurulacak] |

Kurulum:
```bash
sudo apt update
sudo apt install -y git curl bpfcc-tools python3-bpfcc python3-venv linux-headers-$(uname -r)
```

## Karşılaşılan sorun: hazır bcc araçları derlenmiyor

**Belirti:** `sudo execsnoop-bpfcc` çalışmadı:
```
include/linux/fs.h:2428:2: warning: declaration does not declare anything
        struct __filename_head;
include/linux/fs.h:2432:15: error: static assertion failed due to requirement
      'sizeof(struct filename) % 64 == 0'
Exception: Failed to compile BPF module <text>
```

**Neden:** bcc, eBPF programını VM'de clang ile derlerken çalışan çekirdeğin başlık dosyalarını (`linux-headers-$(uname -r)`) içeri alır. Ubuntu 24.04 kurulumum çekirdek 7.0 ile geldi. Bu çekirdeğin `fs.h` dosyasında `struct filename`, adı olmayan gömülü bir yapı (`struct __filename_head;`) içeriyor. Bu söz dizimi yalnızca `-fms-extensions` bayrağıyla geçerli. bcc bu bayrağı vermediği için clang alanı yok sayıyor ("declaration does not declare anything" uyarısı), yapının boyutu 64'ün katı çıkmıyor (kalan 40) ve başlıktaki `static_assert` derlemeyi durduruyor.

**Denenen ve olmayan çözüm:** Ubuntu 24.04'ün ilk çekirdeği 6.8'e dönmek. Bu kurulumun depolarında `linux-image-6.8.0-*-generic` paketi bulunamadı; `linux-image-generic` da 7.0'a işaret ediyor.

**Çözüm:** Kendi bcc programımızda derleyiciye bayrağı vermek:
```python
b = BPF(text=PROG, cflags=["-fms-extensions"])
```
Deneme: [`collector/deneme_exec.py`](../collector/deneme_exec.py). `sudo python3 collector/deneme_exec.py` çalışırken başka terminalde `ls` yazınca:
```
bash-32856  ...  exec pid=32856 ppid=5623
  ls-32879  ...  exec pid=32879 ppid=32856
```
`ls`'in ebeveyni (`ppid=32856`) gerçekten onu başlatan `bash`. Yani hem eBPF derleniyor hem de process ağacı için gereken pid/ppid bilgisi çekirdekten okunabiliyor.

**Kontrol deneyi:** Aynı programı `cflags` olmadan çalıştırıp aynı hatanın çıktığını görmek, nedenin gerçekten bu bayrak olduğunu kanıtlar. Sonuç: [doldurulacak]

**Sonuç:** Hazır `*-bpfcc` araçları (execsnoop, opensnoop, tcpconnect) bu çekirdekte kullanılamıyor. Collector bu yüzden baştan kendi bcc programımız olarak yazılacak ve hep `-fms-extensions` ile derlenecek. Esin kaynağı olarak bu araçların kaynak kodu okunmaya devam edecek.
