# collector/

bcc ile `execve`, `openat` ve `connect` olaylarını yakalayıp tek bir JSONL akışına yazar.

- Hedef komutu (ör. `pip install requests`) collector **kendisi başlatır**; böylece kökün PID'i baştan bilinir.
- Her satır bir olaydır: `ts_ns, pid, ppid, comm, type, detail`
- Satırlar tek tek flush edilir (KG1: `kill -9` sonrası veri yarım kalmasın).

- Çekirdek 7.0 başlıkları yüzünden her bcc programı `cflags=["-fms-extensions"]` ile derlenir (bkz. [docs/ortam.md](../docs/ortam.md)).

Durum: H1'de `deneme_exec.py` ile ortam doğrulandı. Collector **H2'de yazılacak.**
