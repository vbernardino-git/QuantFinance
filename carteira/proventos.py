# -*- coding: utf-8 -*-
"""Baixa os proventos ANUNCIADOS de cada acao da carteira (StatusInvest, gratis).
Gera dados/proventos.json. Rodar antes do montar_portifolio.py quando quiser atualizar."""
import urllib.request, json, datetime as dt, os

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}
TICKERS = ["ITSA4", "VIVT3", "TOTS3", "CPLE3", "EQTL3", "BRSR6", "PSSA3"]
DEST = os.path.join(os.path.dirname(__file__), "dados", "proventos.json")


def _d(s):
    if not s or s == "-":
        return None
    d, m, y = s.split("/")
    return "%s-%s-%s" % (y, m, d)


tudo = []
hist = []
for t in TICKERS:
    u = ("https://statusinvest.com.br/acao/companytickerprovents"
         "?ticker=%s&chartProventsType=2" % t)
    d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
    n = 0
    for e in d.get("assetEarningsModels", []):
        ed, pd_ = _d(e.get("ed")), _d(e.get("pd"))
        hist.append({"ativo": t, "data_com": ed, "pagamento": pd_,
                     "tipo": e.get("et"), "valor_acao": float(e["v"])})
        # so o que interessa: data-com OU pagamento em 2026/2027
        if not ((ed and ed >= "2026-01-01") or (pd_ and pd_ >= "2026-01-01")):
            continue
        tudo.append({"ativo": t, "data_com": ed, "pagamento": pd_,
                     "tipo": e.get("et"), "valor_acao": float(e["v"])})
        n += 1
    print("%-6s %d eventos" % (t, n))

tudo.sort(key=lambda x: (x["pagamento"] or "9999", x["ativo"]))
hist.sort(key=lambda x: (x["pagamento"] or "0000", x["ativo"]))
json.dump({"baixado_em": dt.date.today().isoformat(), "eventos": tudo, "historico": hist},
          open(DEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("SALVO:", DEST, len(tudo), "eventos")
