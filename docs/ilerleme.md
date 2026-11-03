# İlerleme ve commit takibi

Haftalar **ISO takvim haftasıdır** (Pazartesi–Pazar). Ders kuralı 5 gereği commit geçmişi en az 5 farklı haftaya yayılmalı.
Güncel durumu görmek için:

```bash
python3 tools/takip.py --ref origin/main
```

| ISO hafta | Tarih | Plan | İş | Teslim | Durum |
|---|---|---|---|---|---|
| W45 | 02.11 – 08.11 | H1 | Repo iskeleti, README (YZ beyanı), K1 önerisi | | tamam |
| W46 | 09.11 – 15.11 | H1/H2 | VM'de bcc kurulumu, K1 son okuma; collector başlangıcı | **K1 · 12.11** | |
| W47 | 16.11 – 22.11 | H2 | Collector v0: execve + openat + connect tek JSONL | | |
| W48 | 23.11 – 29.11 | H3 | M1 ölçümü (5+5 tekrar, CSV) | **K2 · 26.11** | |
| W49 | 30.11 – 06.12 | H4 | Process ağacı (büküm), orphan işaretleme | | |
| W50 | 07.12 – 13.12 | H5 | Pano v0.5, video, ara rapor, `v0.5` etiketi | **K3 · 10.12** | |
| W51 | 14.12 – 20.12 | H6 | M2 (npm/pip/apt), strace ve /proc kanıtı | | |
| W52 | 21.12 – 27.12 | H7 | M3, kırılma testleri (KG1, KG4, KG5) | | |
| W53 | 28.12 – 03.01 | H8 | Final rapor, savunma hazırlığı | K4–K5 (tarih?) | |

## Alt ajanlar (`.claude/agents/`)

| Ajan | Hafta | Görev |
|---|---|---|
| `collector-gelistirici` | W46–W47 | bcc collector, JSONL |
| `olcum-yurutucu` | W48, W51–W52 | M1–M3 betikleri, strace ve /proc kanıtı |
| `agac-kurucu` | W49 | Process ağacı (büküm) |
| `pano-gelistirici` | W50 | `dashboard/index.html` |
| `rapor-yazari` | W50, W53 (+ her hafta YZ beyanı) | Ara rapor, video senaryosu, final rapor |
| `kirilma-testcisi` | W52 | KG1–KG6 |
| `savunma-denetcisi` | her commit öncesi | Açıklanabilirlik denetimi, savunma soruları |
| `takvim-takipcisi` | her hafta | Commit ve teslim takibi |

Alt ajanlar commit atmaz; commit'ler ana oturumdan, işin yapıldığı hafta içinde atılır.
