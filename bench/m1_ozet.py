#!/usr/bin/env python3
"""Var olan M1 CSV dosyalarını yeniden özetler (ölçüm yapmaz, root gerekmez).

Kullanım:
    python3 bench/m1_ozet.py bench/sonuclar/m1_yerel_*.csv
    python3 bench/m1_ozet.py --ilk-tekrari-at bench/sonuclar/m1_ag_20261116_1128.csv

--ilk-tekrari-at: ısınma turu eklenmeden önceki ölçümlerde ilk tekrar
belirgin biçimde yavaştı; bu seçenek onu çıkararak "ısınma etkisi"ni gösterir.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from istatistik import ozet_metni  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="M1 CSV özetleyici")
    ap.add_argument("dosyalar", nargs="+")
    ap.add_argument("--ilk-tekrari-at", action="store_true")
    a = ap.parse_args()
    for yol in a.dosyalar:
        with open(yol, encoding="utf-8") as f:
            satirlar = list(csv.DictReader(f))
        if a.ilk_tekrari_at:
            satirlar = [r for r in satirlar if r["tekrar"] != "1"]
        print(f"== {os.path.basename(yol)}" + ("  (ilk tekrar hariç)" if a.ilk_tekrari_at else ""))
        print(ozet_metni(satirlar) + "\n")


if __name__ == "__main__":
    main()
