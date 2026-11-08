# Ortam

Bütün çalıştırma ve ölçümler kendi bilgisayarımdaki VirtualBox VM'inde yapılır.

| Bileşen | Değer |
|---|---|
| Sanallaştırma | VirtualBox |
| İşletim sistemi | Ubuntu 26.04.1 LTS (Desktop) |
| Çekirdek | `7.0.0-42-generic` |
| bcc | `bpfcc-tools`, `python3-bpfcc`, `libbpfcc` 0.35.0+ds-1ubuntu2 |
| LLVM / clang (bcc'nin içinde) | `libllvm21`, `libclang-cpp21` 1:21.1.8-6ubuntu1 |
| Python | 3.14.4 |

**Not:** Plan Ubuntu 24.04 idi. İndirme sayfasından güncel LTS sürümü (26.04.1) kuruldu; bunu sürümleri kontrol ederken fark ettim. 26.04 depolarında 24.04'ün 6.8 çekirdeği yok, bu yüzden 6.8'e dönmek mümkün olmadı. Sistem çalıştığı için 26.04 ile devam ediyorum.

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

**Neden:** bcc, eBPF programını VM'de clang ile derlerken çalışan çekirdeğin başlık dosyalarını (`linux-headers-$(uname -r)`) içeri alır. Ubuntu 26.04 kurulumum çekirdek 7.0 ile geldi. Bu çekirdeğin `fs.h` dosyasında `struct filename`, adı olmayan gömülü bir yapı (`struct __filename_head;`) içeriyor. Bu söz dizimi yalnızca `-fms-extensions` bayrağıyla geçerli. bcc bu bayrağı vermediği için clang alanı yok sayıyor ("declaration does not declare anything" uyarısı), yapının boyutu 64'ün katı çıkmıyor (kalan 40) ve başlıktaki `static_assert` derlemeyi durduruyor.

**Denenen ve olmayan çözüm:** Ubuntu 24.04'ün çekirdeği 6.8'e dönmek. 26.04 depolarında `linux-image-6.8.0-*-generic` paketi yok; `linux-image-generic` 7.0'a işaret ediyor.

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

**Kontrol deneyi:** Nedenin gerçekten bu bayrak olduğunu göstermek için `linux/fs.h`'yi içeren aynı programı iki kez, yalnızca bayrağı değiştirerek 5 saniye çalıştırdım:
```bash
sudo timeout -s INT 5 python3 ~/fs_bayrakli.py  2>&1 | grep -E "Calisiyor|Failed|error:"
sudo timeout -s INT 5 python3 ~/fs_bayraksiz.py 2>&1 | grep -E "Calisiyor|Failed|error:"
```

| Deneme | Sonuç |
|---|---|
| `linux/fs.h` + `-fms-extensions` | `Calisiyor!` (derlendi, çalıştı) |
| `linux/fs.h`, bayraksız | `error: static assertion failed ... sizeof(struct filename) % 64 == 0` → `Failed to compile BPF module` |

Tek değişken bayrak olduğu için neden doğrulandı.

**Sonuç:** Hazır `*-bpfcc` araçları (execsnoop, opensnoop, tcpconnect) bu çekirdekte kullanılamıyor. Collector bu yüzden baştan kendi bcc programımız olarak yazılacak ve hep `-fms-extensions` ile derlenecek. Esin kaynağı olarak bu araçların kaynak kodu okunmaya devam edecek.
