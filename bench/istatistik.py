"""M1 için küçük istatistik yardımcıları (yalnızca standart kütüphane).

Neden scipy değil: VM'e ek paket kurmadan çalışsın ve her satırı savunmada
anlatılabilsin. Burada yalnızca üç şey var: medyan/ortalama özeti,
Welch t-testi ve onun p değeri.
"""
import math
import statistics


def welch(a, b):
    """Welch t-testi: iki grubun ortalaması farklı mı?

    Neden Welch (Student değil): kapalı ve açık modun standart sapmaları
    farklı çıkabiliyor (ilk ölçümde 0,53 ve 0,31). Welch varyansların eşit
    olduğunu varsaymaz. Serbestlik derecesi Welch–Satterthwaite formülüyle.
    Döner: (t, serbestlik derecesi)
    """
    va, vb = statistics.variance(a) / len(a), statistics.variance(b) / len(b)
    t = (statistics.mean(b) - statistics.mean(a)) / math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    return t, df


def t_p_degeri(t, df, adim=2000):
    """İki yönlü p değeri: |T| ≥ |t| olma olasılığı (T, df serbestlikli t dağılımı).

    t dağılımının yoğunluk fonksiyonunu 0'dan |t|'ye kadar Simpson kuralıyla
    sayısal olarak integre ediyoruz; p = 1 − 2 × (bu alan).
    """
    c = math.gamma((df + 1) / 2) / (math.sqrt(df * math.pi) * math.gamma(df / 2))
    def f(x):
        return c * (1 + x * x / df) ** (-(df + 1) / 2)
    h = abs(t) / adim
    alan = f(0) + f(abs(t))
    for i in range(1, adim):
        alan += (4 if i % 2 else 2) * f(i * h)
    alan *= h / 3
    return max(0.0, 1 - 2 * alan)


def ozet_metni(satirlar):
    """Mod başına özet ve izleme maliyeti. satirlar: CSV satırları (sözlük).

    Yalnızca çıkış kodu 0 olan ölçümler sayılır (başarısız kurulumun süresi
    anlamsız). Maliyeti hem ortalama hem medyan üzerinden veriyoruz: medyan,
    tek bir yavaş ölçümden (ör. ağda takılma) daha az etkilenir.
    """
    def sureler(mod):
        return [float(r["sure_s"]) for r in satirlar
                if r["mod"] == mod and int(r["cikis_kodu"]) == 0]
    k, a = sureler("kapali"), sureler("acik")
    metin = []
    for ad, x in (("kapalı", k), ("açık", a)):
        if len(x) >= 2:
            metin.append(f"{ad:6}: n={len(x)}  ortalama={statistics.mean(x):.3f} s  "
                         f"medyan={statistics.median(x):.3f} s  std={statistics.stdev(x):.3f} s  "
                         f"min={min(x):.3f}  max={max(x):.3f}")
    if len(k) >= 2 and len(a) >= 2:
        ort = (statistics.mean(a) / statistics.mean(k) - 1) * 100
        med = (statistics.median(a) / statistics.median(k) - 1) * 100
        t, df = welch(k, a)
        p = t_p_degeri(t, df)
        metin.append(f"izleme maliyeti: ortalamaya göre %{ort:.1f}, medyana göre %{med:.1f}")
        metin.append(f"Welch t = {t:.2f}, serbestlik = {df:.1f}, p = {p:.3f} → "
                     + ("fark istatistiksel olarak anlamlı (p < 0,05)" if p < 0.05
                        else "fark gürültüden ayırt edilemiyor (p ≥ 0,05)"))
    return "\n".join(metin)
