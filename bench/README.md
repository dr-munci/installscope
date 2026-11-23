# bench/

Ölçüm betikleri ve sonuçları (CSV). Her ölçüm en az 5 tekrar.

| Betik | Ölçüm |
|---|---|
| `m1_maliyet.py` | **M1** İzleme maliyeti: aynı kurulum, izleme kapalı / açık |
| `m1_ozet.py` | Var olan M1 CSV'lerini yeniden özetler (root gerekmez) |
| `istatistik.py` | Medyan, Welch t-testi, p değeri (yalnızca standart kütüphane) |
| (H6) | **M2** npm, pip, apt karşılaştırması: process, dosya, bağlantı sayısı ve ağaç derinliği |
| (H7) | **M3** (opsiyonel) yük altında olay kaybı |

## M1 – İzleme maliyeti

```bash
sudo python3 bench/m1_maliyet.py                 # PyPI'den indirerek, 1 ısınma + 10+10 tekrar
sudo python3 bench/m1_maliyet.py --kaynak yerel  # önceden indirilmiş wheel'lerden
```

**Kontrollü karşılaştırma:** iki mod arasında değişen tek şey izlemenin açık olması.
- Her ölçümden önce **temiz venv** (H2'de `.pyc` önbelleğinin open sayısını 657 → 466 değiştirdiğini gördük).
- Her ölçümden önce **sayfa önbelleği boşaltılır** (`sync; echo 3 > /proc/sys/vm/drop_caches`).
- pip'in önbelleği kapalı (`--no-cache-dir`), sürüm denetimi kapalı (`--disable-pip-version-check`; fazladan ağ isteği).
- Kapalı/açık **sırası her tekrarda yer değiştirir** (K-A, A-K, ...): sıra etkisi ortalamaya karışmasın.
- Ölçümden önce **kaydedilmeyen bir ısınma turu** (bir kapalı + bir açık). 16.11 ölçümlerinde ilk tekrar tutarlı biçimde yavaştı: yerel/kapalı ilk tekrar 4,0 s, sonrakiler ~2,9 s.
- Her iki modda da pip, sudo'yu çağıran kullanıcı olarak çalışır.
- Açık modda süre, collector'ın `end` satırındaki `sure_s` (komutun başla→bitir süresi). eBPF derleme süresi `derleme_s` sütununda ayrıca raporlanır, maliyete katılmaz.

**İki kaynak, iki soru:**
- `ag`: gerçekçi kurulum; süreye ağ gecikmesi de girer, değişkenlik yüksek olabilir.
- `yerel`: paketler önceden `~/.installscope_m1/wheelhouse`'a indirilir; ağ gürültüsü yok, izleme maliyeti daha net görünür (connect olayı olmaz).

**İstatistik (`istatistik.py`):** mod başına ortalama, medyan, std; maliyet hem ortalama hem medyan üzerinden; iki modun farkı için **Welch t-testi** (varyansların eşit olduğunu varsaymaz) ve iki yönlü **p değeri** (t dağılımının yoğunluğu Simpson kuralıyla integre edilir; tablo değerleriyle doğrulandı: t=2,101, df=18 → p=0,050).

**16.11 ölçümlerinin yeniden analizi** (`python3 bench/m1_ozet.py [--ilk-tekrari-at] ...`):

| Ölçüm | Maliyet (ort. / medyan) | p | İlk tekrar hariç: maliyet / p |
|---|---|---|---|
| yerel, 5+5 | %6,6 / %7,3 | 0,473 | %11,6 / 0,119 |
| ağ, 5+5 | %17,6 / %16,1 | 0,073 | %12,0 / 0,043 |

Isınma etkisi gerçek: ilk tekrar çıkarılınca iki kaynakta da maliyet ~%11–12'ye yaklaşıyor. 5 tekrar, farkı gürültüden ayırmaya yetmiyor; bu yüzden tekrar 10'a çıkarıldı ve ısınma turu eklendi.

**Bilinen geçerlilik tehditleri:** açık modda eBPF derlemesi ölçümden hemen önce çalışır ve bazı dosyaları önbelleğe alabilir; ağ modunda PyPI/CDN gecikmesi tekrarlar arasında değişir.

Çıktı: `sonuclar/m1_<kaynak>_<tarih>.csv` (ham), `_ozet.txt` (ortalama, std, maliyet %), `_ortam.txt` (çekirdek, bcc, Python, CPU, ayar).
