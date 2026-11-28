# K2: Ortam ve İlk Ölçüm

**Proje:** 010 · eBPF Gözlem Panosu: Bir Kurulum Sisteme Ne Yapar?
**Teslim:** 26.11
**Depo:** https://github.com/dr-munci/installscope

## 1. Özet

- Ortam kuruldu: VirtualBox üzerinde Ubuntu 26.04.1, çekirdek 7.0, bcc 0.35.
- Collector üç olay tipini (`execve`, `openat`, `connect`) tek bir JSONL akışına yazıyor. Kurulum komutunu kendisi başlatıyor ve yalnızca onun process ağacını izliyor.
- Collector'ın sayıları **strace ile doğrulandı**: aynı Python komutunda ikisi de 99 `openat` saydı.
- **M1 – İzleme maliyeti:** Ağ etkisi çıkarılmış ölçümde (10 + 10 tekrar) izleme, bir `pip install requests` kurulumunu **ortalamada %11,5, medyanda %8,3** yavaşlattı. Fark anlamlı: Welch t = 3,44, p = 0,005.
- Yol boyunca çekirdek 7.0'dan kaynaklanan iki sorun bulundu, nedenleri gösterildi ve çözüldü (bölüm 4).

## 2. Ortam

| Bileşen | Değer |
|---|---|
| Sanallaştırma | VirtualBox, 4 CPU |
| İşletim sistemi | Ubuntu 26.04.1 LTS |
| Çekirdek | 7.0.0-43-generic (21.11 ölçümleri); ilk kurulum 7.0.0-42 |
| bcc | 0.35.0+ds-1ubuntu2 |
| LLVM / clang | 21.1.8 |
| Python | 3.14.4 |
| Ölçülen kurulum | `pip install requests` (requests 2.34.2 + 4 bağımlılık) |

Plan Ubuntu 24.04 idi. İndirme sayfasının önerdiği güncel LTS (26.04.1) kuruldu. 24.04'ün 6.8 çekirdeği bu sürümün depolarında olmadığı için 26.04 ile devam edildi. Ayrıntılar: [ortam.md](ortam.md).

## 3. M1 – İzleme maliyeti

**Soru:** eBPF ile izlemek, izlenen kurulumu ne kadar yavaşlatır?

### Yöntem (kontrollü karşılaştırma)
İki mod arasında değişen tek şey izlemenin açık olması: kapalı modda `pip install` doğrudan, açık modda collector altında çalışır. Her ölçümden önce:
- **temiz bir venv** kurulur (önceki kurulumun `.pyc` önbelleği sayıları değiştiriyordu),
- **sayfa önbelleği boşaltılır** (`sync; echo 3 > /proc/sys/vm/drop_caches`),
- pip'in kendi önbelleği ve sürüm denetimi kapalıdır (`--no-cache-dir`, `--disable-pip-version-check`).

Kapalı/açık sırası her tekrarda yer değiştirir (K-A, A-K, …). Ölçümden önce kaydedilmeyen bir **ısınma turu** yapılır. Açık modda süre, komutun başlatıldığı andan bitişine kadar ölçülür. eBPF derlemesi (3,1–5,4 s) bu süreye katılmaz, ayrı raporlanır.

İki kaynakla ölçüldü:
- **yerel:** paketler önceden indirilir, ağ gürültüsü yoktur. Asıl sonuç bu kaynaktan.
- **ağ:** paketler PyPI'den indirilir. Gerçekçidir ama gürültülüdür.

Betik: [`bench/m1_maliyet.py`](../bench/m1_maliyet.py). İstatistik: [`bench/istatistik.py`](../bench/istatistik.py).

### Sonuçlar (21.11, 1 ısınma + 10 + 10 tekrar)

| Kaynak | Kapalı medyan | Açık medyan | Maliyet (ort. / medyan) | Welch t | p |
|---|---|---|---|---|---|
| **yerel** | 2,982 s | 3,229 s | **%11,5 / %8,3** | 3,44 | **0,005** |
| ağ | 5,784 s | 6,272 s | %−12,8 / %8,5 | −0,61 | 0,555 |
| ağ, aykırı değer hariç | 5,727 s | 6,272 s | %10,0 / %9,5 | 2,40 | 0,033 |

Olay sayıları tekrarlar arasında sabit:
- yerel: 9 `exec`, 1062 `open`, 0 `connect`, 0 kayıp
- ağ: 9 `exec`, 1130 `open`, 20 `connect`, 0 kayıp

Ham veri: `bench/sonuclar/m1_yerel_20261121_1927.csv`, `bench/sonuclar/m1_ag_20261121_1932.csv`

### Yorum
- **İzleme maliyeti yaklaşık %8–12.** Ağ gürültüsünün olmadığı yerel ölçümde fark istatistiksel olarak anlamlı (p = 0,005).
- **Ağ ölçümünde tek bir aykırı değer var:** 7. tekrarda izleme *kapalıyken* kurulum 21,2 s sürdü, diğerleri ~5,8 s. Bu, ağ ya da PyPI'deki bir takılma. Ortalamayı tersine çeviriyor (%−12,8), medyan ise yerel sonuçla tutarlı (%8,5). Aykırı değer veriden silinmedi, iki hâliyle de raporlandı. Medyanın neden ayrıca verildiğini bu örnek gösteriyor.
- **Maliyet nereden geliyor:** `openat` olayları `raw_syscalls` tracepoint'leriyle yakalanıyor (bölüm 4.2). Bu tracepoint sistemdeki her sistem çağrısında tetikleniyor. İlk satırda çağrı numarasına bakıp hemen dönülüyor, ama bu iş her çağrıda yapılıyor.

### Ölçüm yönteminin gelişimi
| Tarih | Ölçüm | Sorun | Değişiklik |
|---|---|---|---|
| 16.11 | ağ, 5 + 5 | `open` sayısı 42–886 arasında değişiyor; maliyet %−6,3 | collector hatası bulundu (4.2) |
| 16.11 | yerel ve ağ, 5 + 5 | sayılar sabit, ama p = 0,47 ve 0,07; ilk tekrarlar hep yavaş | ısınma turu, 10 tekrar, Welch t-testi |
| 21.11 | yerel ve ağ, 10 + 10 | yerelde anlamlı sonuç (p = 0,005) | — |

16.11 ölçümleri, ilk tekrar çıkarılarak yeniden analiz edildiğinde de maliyet %11–12 civarında çıkıyor (`python3 bench/m1_ozet.py --ilk-tekrari-at ...`).

## 4. İşletim sistemi kanıtı ve karşılaşılan sorunlar

### 4.1 Hazır bcc araçları derlenmiyor
`execsnoop-bpfcc`, çekirdek 7.0 başlıklarında `static_assert(sizeof(struct filename) % 64 == 0)` hatasıyla derlenmedi. Neden: `struct filename` içindeki adsız gömülü yapı (`struct __filename_head;`) ancak `-fms-extensions` bayrağıyla geçerli. Bu bayrak verilmeyince alan yok sayılıyor ve yapı küçük çıkıyor.

**Kontrol deneyi:** `linux/fs.h`'yi içeren aynı program bayrakla çalıştı, bayraksız aynı hatayı verdi. Collector bu yüzden her zaman `cflags=["-fms-extensions"]` ile derleniyor.

### 4.2 `sys_enter_openat` olayları gelmiyor → strace ile yakalandı
16.11 ölçümünde `open` sayısının tutarsız olması üzerine collector strace ile karşılaştırıldı:

| Araç | `openat` (aynı Python komutu) |
|---|---|
| `strace -f -e trace=openat` | 99 |
| collector, `syscalls:sys_enter_openat` | 0 |
| `bpftrace`, aynı tracepoint | olayları görüyor |
| **collector, `raw_syscalls` (düzeltme sonrası)** | **99** |

Çekirdek 7.0'da `sys_enter_openat` formatına yeni bir alan eklenmiş: `__data_loc char[] __filename_val`. Çekirdek artık dosya adını olayın içine kendisi kopyalıyor ve bizim bcc programımız bu tracepoint'ten olay alamadı. Çözüm olarak `openat`, `raw_syscalls:sys_enter` ve `sys_exit` ile yakalanıyor. Girişte dosya adının adresi saklanıyor, çıkışta o adresten okunuyor. Yan kazanç: açmanın dönüş değeri (`ret`) de kaydediliyor.

Bu karşılaştırma aynı zamanda ölçüm aracının doğrulamasıdır: perf buffer "0 kayıp" demesine rağmen olaylar eksikti. Aracın kendi raporu yetmedi, bağımsız bir araçla (strace) karşılaştırmak gerekti.

## 5. Kırılma testleri (şimdiye kadar)
| Kart | Durum |
|---|---|
| KG1 `kill -9` | Her JSONL satırından sonra `flush` yapılıyor. Test W52'de. |
| KG5 `chmod 000` ayar dosyası | ✅ Denendi: anlamlı hata, çıkış kodu 3. Root, `CAP_DAC_OVERRIDE` ile izni atladığı için izin bitleri `os.stat` ile ayrıca denetleniyor. |
| Ctrl+C / SIGTERM | ✅ İzlenen komut da durduruluyor (önce SIGINT, 5 s sonra SIGKILL); `end` satırı `"durduruldu": true` ile yazılıyor. |

## 6. Plana göre durum ve sonraki adımlar
Plana göre yaklaşık bir hafta öndeyim: collector (H2) W46'da, M1 betiği W47'de bitti.

| Hafta | İş |
|---|---|
| W49 | Process ağacı (büküm): JSONL'den ağaç, orphan işaretleme, `exec` etmeyen fork'lar |
| W50 | Pano v0.5, 3 dakikalık video, ara rapor (**K3 · 10.12**) |
| W51 | M2 (npm/pip/apt karşılaştırması), strace ve `/proc` kanıtı |
| W52 | M3 ve kırılma testleri (KG1, KG2, KG3, KG4, KG6) |

## 7. Üretken YZ kullanımı
Kod ve belge taslakları YZ desteğiyle (Claude) hazırlandı. Ölçümleri kendi VM'imde çalıştırdım, sonuçları okuyup hataları bulmada kullandım ve her değişikliği kendi adımla commit'ledim. Ayrıntılı beyan: [README](../README.md#üretken-yapay-zekâ-kullanım-beyanı).
