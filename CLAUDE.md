# CLAUDE.md — BMU1301 Dönem Projesi

## Proje
**010 · eBPF Gözlem Panosu: Bir Kurulum Sisteme Ne Yapar?**
İşletim Sistemleri (BMU1301) dersi için bireysel dönem projesi. Konunun işlendiği haftalar: H2, H12–H13.

Bir paket kurulumu (`npm install`, `pip install`, `apt install`) sırasında sistemde olan her şeyi eBPF ile yakalayıp zaman çizelgesine dökmek:
- hangi process'ler doğdu (execve)
- hangi dosyalar açıldı ya da yazıldı (openat)
- hangi ağ bağlantıları açıldı (connect)

**Büküm (zorunlu):** Olaylar process ağacıyla ilişkilendirilecek. Kök, kurulum komutu olacak; her olay ağaçta hangi process'e ait olduğuyla gösterilecek.

Esin kaynağı: bcc araçları (`execsnoop`, `opensnoop`, `tcpconnect`).

## Ortam
- Geliştirme bu repoda yapılır. Çalıştırma, ölçüm ve video **öğrencinin kendi Ubuntu 24.04 VM'inde** yapılır.
- Kurulum: `sudo apt install bpfcc-tools python3-bpfcc linux-headers-$(uname -r)`
- Dil: Python 3 ve bcc. Pano tek bir HTML dosyası olacak (vanilla JS ya da hafif bir kütüphane). Grafana isteğe bağlı.

## Mimari (hedef)
```
collector/   bcc ile execve + openat + connect izleme → JSONL olay akışı
             her olay: ts_ns, pid, ppid, comm, type, detail (dosya yolu / ip:port)
             izleme, hedef komutu kendisi başlatır (kökün PID'i bilinsin)
tree/        JSONL → process ağacı (pid/ppid), olayları düğümlere bağla
             kısa ömürlü ve ebeveyni kaçan process'leri "orphan" olarak işaretle
dashboard/   index.html: solda process ağacı, sağda zaman çizelgesi (şeritler)
             filtre: olay tipi, process; özet: process/dosya/bağlantı sayıları
bench/       ölçüm betikleri (5 tekrar), sonuçlar CSV
docs/        öneri, ara rapor, final rapor
```

## Ders kuralları (bunlara uy)
1. Proje bireyseldir.
2. **Seviye 1:** Gösterilecek ve ölçülecek şeyler çalışır; K3'te videoyla gösterilir.
3. **Seviye 2:** En az 2 ölçülebilir büyüklük, her biri en az 5 tekrar, kontrollü karşılaştırma ve işletim sistemi kanıtı (strace, perf ya da /proc).
4. **Seviye 3:** Büküm eksiksiz; proje hata altında da denenir.
5. **Commit geçmişi en az 5 farklı haftaya yayılmalı.** Her şeyi tek seferde yazıp commit'leme; işi haftalara böl.
6. Üretken YZ kullanımı serbest, ama README'de beyan edilmeli. **Açıklanamayan kod öğrencinin sayılmaz**, puan da savunma katsayısıyla çarpılır. Bu yüzden:
   - kodu küçük, okunur parçalar hâlinde yaz; gereksiz soyutlama yapma
   - her önemli fonksiyona ne yaptığını ve neden öyle yaptığını anlatan kısa bir Türkçe yorum ekle
   - her adımın sonunda öğrenciye 3–5 maddelik "bunu savunmada nasıl anlatırsın" özeti ver

## Takvim ve puanlama
| Aşama | Tarih | İçerik | Puan |
|---|---|---|---|
| K1 | 12.11 | Öneri: Heilmeier soruları, haftalık plan, risk ve B planı, açık GitHub deposu | 10 |
| K2 | 26.11 | Ortam ve ilk ölçüm (5 tekrar) | 10 |
| K3 | 10.12 | Çalışan çekirdek: en fazla 3 dakikalık video, v0.5 etiketi, ara rapor | 15 |
| K4–K5 | — | F1 çalışırlık ve büküm 20, F2 İS derinliği 15, F3 ölçüm 10, F4 tekrar üretilebilirlik 10, F5 demo ve kırılma testi 10 | 55 |

Notlar:
- K1 teslim edilmezse proje iptal olur.
- K3'te Seviye 1 çalışmıyorsa tavan puan 60'tır.
- Gecikme cezası: K1–K3'te gün başına aşama puanının %20'si, K4'te gün başına 10 puan. 3 günden sonra teslim kabul edilmez.

## Ölçüm planı
- **M1 – İzleme maliyeti:** Aynı kurulumun süresi; izleme yokken ve izleme açıkken (5'er tekrar, önbellek temizlenmiş, aynı paket).
- **M2 – Kurulum karşılaştırması:** npm, pip ve apt için process, dosya ve bağlantı sayıları ile ağaç derinliği.
- **M3 (opsiyonel) – Olay kaybı:** Yük arttıkça perf buffer'da kaybolan olay sayısı.
- **İS kanıtı:** `strace -f -c` sayımlarını eBPF sayımlarıyla karşılaştır; `/proc/<pid>/status` içindeki PPid değerinin ağaçla tutarlılığını kontrol et.

## Kırılma testleri (savunmada biri uygulanır)
- **KG1** `kill -9` collector'a: veri yarım kalmasın. JSONL satır satır flush edilsin; ağaç kurucu bozuk son satırı tolere etsin.
- **KG2** Disk dolu: yazma hatası yakalansın, anlamlı bir mesaj verilsin.
- **KG3** `MemoryMax=64M`: collector'ın davranışı ölçülsün.
- **KG4** `CPUQuota=20%`: kaybolan olaylar sayılsın ve panoda gösterilsin.
- **KG5** Yapılandırma dosyasına `chmod 000`: anlamlı bir hata verilsin.
- **KG6** `renice 19` ve ek yük: gecikme ve kayıp ölçülsün.

## Haftalık plan
- **H1 (→12.11):** Repo iskeleti, README (YZ beyanı dahil), docs/K1-oneri.md (Heilmeier soruları, plan, risk ve B planı)
- **H2:** Collector v0: üç olay tipi tek JSONL akışında
- **H3 (→26.11):** bench/ altında M1 ölçümleri, 5 tekrar (K2)
- **H4:** Process ağacı (büküm)
- **H5 (→10.12):** Pano v0.5, video, ara rapor (K3)
- **H6+:** M2 ve M3, kırılma testleri, final rapor

**Risk:** Ağaç kurulumu uzarsa ya da olay kaybı yüksek çıkarsa.
**B planı:** Kapsamı olay sayıları ve düz zaman çizelgesine indirmek (ağaçsız).

## Güvenlik
Yalnızca öğrencinin kendi VM'i üzerinde çalış. Başka sistemleri, okul ağını ya da internetteki sunucuları izleme.
