# collector/

bcc ile `execve`, `openat` ve `connect` olaylarını yakalayıp tek bir JSONL akışına yazar.

| Dosya | Ne |
|---|---|
| `izleyici.c` | Çekirdekte çalışan eBPF programı. Yalnızca kurulum ağacındaki process'lerin olaylarını gönderir. |
| `collector.py` | eBPF'i yükler, komutu başlatır, olayları JSONL'ye yazar. |
| `deneme_exec.py` | H1 ortam denemesi (bkz. [docs/ortam.md](../docs/ortam.md)). |

## Kullanım (VM'de, depo kökünden)

```bash
sudo python3 collector/collector.py -o pip.jsonl -- ~/deneme/bin/pip install requests
sudo python3 collector/collector.py --root -o apt.jsonl -- apt-get install -y cowsay
```

- Komut, `sudo`'yu çağıran kullanıcı olarak çalışır. `--root` verilirse root kalır (apt için).
- `head -3 pip.jsonl` ile ilk satırlara bakılabilir.

## Nasıl çalışır

1. `izleyici.c` derlenip çekirdeğe yüklenir (`cflags=["-fms-extensions"]`, çekirdek 7.0 için).
2. Komut `fork` edilir ama `exec` etmeden bir boruyu (pipe) okuyarak bekler. Böylece kökün PID'i probe'lar hazır olmadan önce bilinir ve hiçbir olay kaçmaz.
3. Kök PID `izlenen` eBPF haritasına yazılır. `sched_process_fork` her yeni çocuğu bu haritaya ekler, `sched_process_exit` çıkanı siler. Ağaç dışındaki olaylar çekirdekte elenir.
4. Çocuğa "başla" denir. Olaylar perf buffer üzerinden gelir ve her satır yazıldıktan sonra `flush` edilir (KG1).

## Çıktı biçimi (JSONL)

```json
{"type": "start", "pid": 4501, "detail": "/home/u/deneme/bin/pip install requests"}
{"ts_ns": 123, "pid": 4501, "ppid": 4500, "comm": "pip", "type": "exec", "detail": "/home/u/deneme/bin/pip"}
{"ts_ns": 456, "pid": 4501, "ppid": 4500, "comm": "pip", "type": "open", "detail": "/etc/hosts", "write": false}
{"ts_ns": 789, "pid": 4501, "ppid": 4500, "comm": "pip", "type": "connect", "detail": "151.101.0.223:443"}
{"type": "lost", "detail": 12}
{"type": "end", "pid": 4501, "detail": 0, "lost": 12}
```

## v0 sınırları (bilerek)

- `openat` girişte yakalanır; açma başarısız olduysa da kaydedilir (dönüş değeri v1'de).
- `open`, `openat2`, `creat` gibi diğer dosya çağrıları ve UNIX soketleri yok.
- Collector Ctrl+C ile durdurulursa çalışan komut kendi başına devam eder.

Durum: **v0 yazıldı (H2).** VM'de ilk deneme bekleniyor.
