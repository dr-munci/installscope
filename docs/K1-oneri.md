# K1: Proje Önerisi

**Proje:** 010 · eBPF Gözlem Panosu: Bir Kurulum Sisteme Ne Yapar?
**Ders:** BMU1301 İşletim Sistemleri (ilgili haftalar: H2, H12–H13)
**Depo:** https://github.com/dr-munci/installscope
**Teslim:** 12.11

---

## 1. Heilmeier soruları

### 1.1 Ne yapmaya çalışıyorsun? (jargonsuz)
Bir programı kurduğumuzda (`pip install requests` gibi) bilgisayarda arka planda çok şey olur: başka programlar çalışır, yüzlerce dosya açılır, internete bağlanılır. Bunların hepsini kaydedip **kim neyi yaptı** sorusunu cevaplayan bir pano yapıyorum. Her olay, onu yapan programa ve o programı başlatan programa kadar geriye izlenebilecek.

### 1.2 Bugün nasıl yapılıyor, sınırları ne?
- **`strace -f`**: Bütün sistem çağrılarını görür ama `ptrace` ile her çağrıda process'i durdurur. Bu yüzden yavaştır ve çıktısı binlerce satırlık düz metindir.
- **bcc araçları (`execsnoop`, `opensnoop`, `tcpconnect`)**: Hızlıdır (eBPF, çekirdek içinde çalışır), ama her araç **ayrı** çalışır ve **bütün sistemi** gösterir. Olayları tek bir kuruluma ve onun process ağacına bağlamaz.
- **Paket yöneticisinin kendi logu**: Yalnızca paket yöneticisinin anlatmak istediğini gösterir. Kurulum betiklerinin (`postinstall`, `setup.py`) yaptıkları görünmez.

### 1.3 Yaklaşımında yeni olan ne?
Üç olay tipini **tek bir zaman damgalı akışta** toplamak ve **process ağacıyla ilişkilendirmek** (büküm). Collector hedef komutu kendisi başlattığı için kökün PID'i baştan bilinir; ağaç pid → ppid bağlarıyla kurulur. Ebeveyni görülmeden kaybolan kısa ömürlü process'ler "orphan" olarak işaretlenir ve gizlenmez.

### 1.4 Kimin umurunda? Başarılı olursa ne değişir?
- **Güvenlik:** Tedarik zinciri saldırıları çoğu zaman kurulum betiklerinde saklanır (beklenmedik bir `curl`, `~/.ssh` okuması). Pano bunu gözle görülür kılar.
- **Geliştirici:** Kurulum neden yavaş? Hangi alt process zaman yiyor?
- **Ders açısından:** `fork/execve`, process ağacı, sistem çağrıları, dosya tanımlayıcıları ve soketler gibi kavramlar gerçek bir iş yükü üzerinde gösterilir.

### 1.5 Riskler neler?
| Risk | Olasılık | Etki | Önlem |
|---|---|---|---|
| bcc / çekirdek başlığı uyumsuzluğu (Ubuntu 24.04) | orta | yüksek | H1'de ortamı kurup `execsnoop` ile doğrulamak |
| Perf buffer'da olay kaybı | orta | orta | Buffer boyutunu büyütmek, kayıpları saymak ve panoda göstermek (M3, KG4) |
| Kısa ömürlü process'lerin ppid'inin kaçırılması | yüksek | orta | ppid'i çekirdek tarafında `task->real_parent`'tan okumak, yine de kaçanları orphan saymak |
| Ağaç kurulumunun uzaması | orta | yüksek | B planı (aşağıda) |
| Olay hacmi panoyu yavaşlatır (npm binlerce `openat`) | orta | düşük | Panoda olayları process bazında gruplamak ve filtrelemek |

**B planı:** Ağaç zamanında bitmezse kapsam **olay sayıları ve düz zaman çizelgesine** (ağaçsız) indirilir. Collector ve ölçümler bundan etkilenmez; Seviye 1 ve 2 korunur.

### 1.6 Maliyeti ne?
Ek donanım ya da para gerekmez. Kendi bilgisayarımda bir Ubuntu 24.04 VM'i ve açık kaynak araçlar (bcc, Python 3, tarayıcı) yeter. Asıl maliyet zaman: haftada yaklaşık 6–8 saat, toplam 7–8 hafta.

### 1.7 Ne kadar sürer?
Aşağıdaki haftalık plana göre K3'te (10.12) çalışan çekirdek, ardından ölçümler ve kırılma testleriyle final.

### 1.8 Başarıyı nasıl ölçeceksin? (ara ve final sınavları)
| Kontrol noktası | Başarı ölçütü |
|---|---|
| K2 (26.11) | Collector üç olay tipini yakalıyor; M1 ölçümü 5 tekrarla CSV'de |
| K3 (10.12) | `pip install` için ağaç + zaman çizelgesi panoda görünüyor; 3 dakikalık video; `v0.5` etiketi |
| Final | M1 ve M2 tamam; eBPF sayıları `strace -f -c` ile karşılaştırılmış; ağaç `/proc/<pid>/status` PPid ile doğrulanmış; en az bir kırılma testi geçiyor |

---

## 2. Ölçüm planı

| Kod | Büyüklük | Kontrollü karşılaştırma | Tekrar |
|---|---|---|---|
| **M1** | Kurulum süresi (s) → izleme maliyeti (%) | Aynı paket, önbellek temizlenmiş; izleme **kapalı** vs **açık** | 5 + 5 |
| **M2** | process, dosya, bağlantı sayısı; ağaç derinliği | npm vs pip vs apt (benzer boyutta paketler) | her biri 5 |
| **M3** (ops.) | Kaybolan olay sayısı | Artan yük (paralel kurulum / `stress-ng`) | her seviye 5 |

**İşletim sistemi kanıtı:**
- `strace -f -c` ile sayılan `execve`/`openat`/`connect` sayıları ile eBPF sayılarının karşılaştırılması.
- Kurulum sürerken `/proc/<pid>/status` içindeki `PPid` değerlerinin örneklenip ağaçla tutarlılığının kontrolü.

Sonuçlar ortalama ve standart sapmayla raporlanır.

## 3. Kırılma testleri (planlanan)
KG1 (`kill -9` → yarım veri yok, bozuk son satır tolere edilir) öncelikli. Ardından KG4 (`CPUQuota=20%` → kayıp sayımı panoda) ve KG5 (`chmod 000` yapılandırma → anlamlı hata). KG2, KG3, KG6 zaman kalırsa yapılacak.

## 4. Haftalık plan

| Hafta | Tarih | İş | Çıktı |
|---|---|---|---|
| H1 | → 12.11 | Repo iskeleti, README (YZ beyanı), bu öneri; VM'de bcc kurulumu | **K1** |
| H2 | 13.11 – 19.11 | Collector v0: `execve` + `openat` + `connect` tek JSONL akışında | `collector/` |
| H3 | 20.11 – 26.11 | M1 ölçüm betiği, 5 tekrar, CSV | **K2** |
| H4 | 27.11 – 03.12 | Process ağacı (büküm), orphan işaretleme | `tree/` |
| H5 | 04.12 – 10.12 | Pano v0.5, video, ara rapor | **K3**, `v0.5` |
| H6 | 11.12 – 17.12 | M2 (npm/pip/apt), strace ve /proc kanıtı | `bench/` |
| H7 | 18.12 – 24.12 | M3, kırılma testleri (KG1, KG4, KG5) | |
| H8 | 25.12 → | Final rapor, savunma hazırlığı | **K4–K5** |

## 5. Güvenlik ve etik
İzleme yalnızca kendi VM'imde yapılır. Okul ağı, başka sistemler ya da internetteki sunucular izlenmez. Toplanan JSONL dosyaları yerel kalır; repoya yalnızca küçük, kişisel bilgi içermeyen örnekler konur.
