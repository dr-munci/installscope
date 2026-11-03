# tree/

JSONL olay akışından process ağacını kurar (pid → ppid) ve her olayı ait olduğu düğüme bağlar.

- Kök: kurulum komutunun process'i.
- Ebeveyni görülmeden kaybolan kısa ömürlü process'ler `orphan` olarak işaretlenir.
- Bozuk son satır tolere edilir (KG1).

Durum: **H4'te yazılacak.**
