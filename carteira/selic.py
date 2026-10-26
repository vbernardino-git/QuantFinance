import json, os, datetime as dt
from calendar import monthrange

# Selic mensal (BCB SGS 4390): https://api.bcb.gov.br/dados/serie/bcdata.sgs.4390/dados?formato=json
raw = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "selic_mensal.json"),
                     encoding="utf-8-sig"))
S = {}
for r in raw:
    d = dt.datetime.strptime(r["data"], "%d/%m/%Y").date()
    S[(d.year, d.month)] = float(str(r["valor"]).replace(",", ".")) / 100.0

def selic_acum(ini, fim):
    """fator acumulado da Selic entre duas datas, pro-rata por dias corridos nos meses parciais"""
    f = 1.0
    y, m = ini.year, ini.month
    while (y, m) <= (fim.year, fim.month):
        taxa = S.get((y, m))
        if taxa is None:
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            continue
        nd = monthrange(y, m)[1]
        d0 = ini.day if (y, m) == (ini.year, ini.month) else 1
        d1 = fim.day if (y, m) == (fim.year, fim.month) else nd
        dias = max(0, d1 - d0 + 1)
        f *= (1 + taxa) ** (dias / nd)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f

if __name__ == "__main__":
    hoje = dt.date(2026, 8, 21)
    for nome, d in [("CPLE3", dt.date(2026,5,16)), ("VIVT3", dt.date(2026,6,6)),
                    ("BBAS3", dt.date(2026,6,6)), ("TOTS3", dt.date(2026,6,10)),
                    ("ITSA4", dt.date(2026,6,10))]:
        print(nome, d, "->", round((selic_acum(d, hoje)-1)*100, 3), "%")
    print("2020->hoje:", round((selic_acum(dt.date(2020,1,1), hoje)-1)*100, 2), "%")
