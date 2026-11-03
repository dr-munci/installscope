# installscope

**eBPF Gözlem Panosu: Bir Kurulum Sisteme Ne Yapar?**
BMU1301 İşletim Sistemleri dersinin bireysel dönem projesi (konu 010).

`npm install`, `pip install` ya da `apt install` çalışırken sistemde olanları eBPF ile yakalar:

| Olay | Sistem çağrısı | Ne gösterir |
|---|---|---|
| process doğumu | `execve` | kurulum hangi programları çalıştırdı |
| dosya erişimi | `openat` | hangi dosyalar okundu ya da yazıldı |
| ağ bağlantısı | `connect` | hangi adreslere (ip:port) bağlanıldı |

**Büküm:** Olaylar düz bir liste olarak kalmaz. Kökü kurulum komutu olan bir **process ağacına** bağlanır, böylece her olayın hangi process'ten geldiği görülür.

Esin kaynağı: bcc araçları `execsnoop`, `opensnoop`, `tcpconnect`.

## Mimari

```
kurulum komutu ──► collector/ (bcc, eBPF) ──► olaylar.jsonl ──► tree/ ──► ağaç.json ──► dashboard/index.html
```

| Klasör | Görev |
|---|---|
| `collector/` | eBPF ile 3 olay tipini yakalar, JSONL yazar. Hedef komutu kendisi başlatır. |
| `tree/` | pid/ppid ile ağacı kurar, olayları düğümlere bağlar, yetim (orphan) process'leri işaretler. |
| `dashboard/` | Solda ağaç, sağda zaman çizelgesi; filtre ve özet sayılar. |
| `bench/` | Ölçüm betikleri (5 tekrar) ve CSV sonuçları. |
| `docs/` | Öneri (K1), ara rapor (K3), final rapor. |

## Ortam

Proje, kendi **Ubuntu 24.04** sanal makinemde çalıştırılır ve ölçülür.

```bash
sudo apt install bpfcc-tools python3-bpfcc linux-headers-$(uname -r)
```

eBPF programı yüklemek root yetkisi istediği için collector `sudo` ile çalıştırılır. Yalnızca kendi VM'imi izlerim.

## Durum

| Aşama | Tarih | Durum |
|---|---|---|
| K1: Öneri | 12.11 | [docs/K1-oneri.md](docs/K1-oneri.md) |
| K2: Ortam ve ilk ölçüm | 26.11 | yapılacak |
| K3: Çalışan çekirdek (v0.5) | 10.12 | yapılacak |
| K4–K5: Final | — | yapılacak |

## Üretken yapay zekâ kullanım beyanı

Bu projede üretken yapay zekâ (Anthropic Claude, Claude Code aracılığıyla) kullanılmaktadır. Ders kuralları gereği bu kullanımı açıkça beyan ediyorum.

- **Nerede kullanıldı:** repo iskeleti, belge taslakları ve kod taslakları. Her aşamada hangi dosyalarda kullanıldığı aşağıdaki tabloya eklenecek.
- **Nasıl kullanıldı:** YZ'nin ürettiği her parçayı okuyup anladım, kendi VM'imde çalıştırıp test ettim ve gerektiğinde değiştirdim. Kod, savunmada satır satır anlatılabilecek kadar küçük parçalar hâlinde ve Türkçe yorumlu tutuldu.
- **Neyi YZ yapmadı:** ölçümler, VM üzerindeki çalıştırmalar, video ve sonuçların yorumu bana aittir.

| Hafta | Dosya / iş | YZ'nin katkısı |
|---|---|---|
| H1 | README, klasör iskeleti, `docs/K1-oneri.md` | taslak metin; içerik ve plan tarafımdan gözden geçirildi |
