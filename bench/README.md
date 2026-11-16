# bench/

Ölçüm betikleri ve sonuçları (CSV). Her ölçüm en az 5 tekrar.

| Betik | Ölçüm |
|---|---|
| `m1_maliyet.py` | **M1** İzleme maliyeti: aynı kurulum, izleme kapalı / açık |
| (H6) | **M2** npm, pip, apt karşılaştırması: process, dosya, bağlantı sayısı ve ağaç derinliği |
| (H7) | **M3** (opsiyonel) yük altında olay kaybı |

## M1 – İzleme maliyeti

```bash
sudo python3 bench/m1_maliyet.py                 # PyPI'den indirerek, 5+5 tekrar
sudo python3 bench/m1_maliyet.py --kaynak yerel  # önceden indirilmiş wheel'lerden
```

**Kontrollü karşılaştırma:** iki mod arasında değişen tek şey izlemenin açık olması.
- Her ölçümden önce **temiz venv** (H2'de `.pyc` önbelleğinin open sayısını 657 → 466 değiştirdiğini gördük).
- Her ölçümden önce **sayfa önbelleği boşaltılır** (`sync; echo 3 > /proc/sys/vm/drop_caches`).
- pip'in önbelleği kapalı (`--no-cache-dir`), sürüm denetimi kapalı (`--disable-pip-version-check`; fazladan ağ isteği).
- Kapalı/açık **sırası her tekrarda yer değiştirir** (K-A, A-K, ...): sıra etkisi ortalamaya karışmasın.
- Her iki modda da pip, sudo'yu çağıran kullanıcı olarak çalışır.
- Açık modda süre, collector'ın `end` satırındaki `sure_s` (komutun başla→bitir süresi). eBPF derleme süresi `derleme_s` sütununda ayrıca raporlanır, maliyete katılmaz.

**İki kaynak, iki soru:**
- `ag`: gerçekçi kurulum; süreye ağ gecikmesi de girer, değişkenlik yüksek olabilir.
- `yerel`: paketler önceden `~/.installscope_m1/wheelhouse`'a indirilir; ağ gürültüsü yok, izleme maliyeti daha net görünür (connect olayı olmaz).

**Bilinen geçerlilik tehditleri:** açık modda eBPF derlemesi ölçümden hemen önce çalışır ve bazı dosyaları önbelleğe alabilir; ağ modunda PyPI/CDN gecikmesi tekrarlar arasında değişir.

Çıktı: `sonuclar/m1_<kaynak>_<tarih>.csv` (ham), `_ozet.txt` (ortalama, std, maliyet %), `_ortam.txt` (çekirdek, bcc, Python, CPU, ayar).
