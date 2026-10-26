# -*- coding: utf-8 -*-
"""Agenda de proventos + preco ex + decisao de captura (arbitragem de provento).

1. Le os proventos ANUNCIADOS (StatusInvest) e marca NOVO o que nao tinha visto antes.
2. Calcula o preco teorico depois da data-com (B3 desconta o valor BRUTO do preco de referencia)
   e o preco esperado pelo HISTORICO do papel (quanto ele cai de verdade no dia ex).
3. Compara rendimento da captura x DY do provento:
      DY liquido      = provento liquido / preco
      queda esperada  = razao historica (queda no dia ex / provento bruto) x provento bruto
      arbitragem      = DY liquido - queda esperada - custos
   Se arbitragem > 0 (o papel costuma cair MENOS que o provento): COMPRA pra capturar.
   Se < 0: NAO COMPRA - voce paga no preco o que recebe no provento.
Tudo gratis (StatusInvest + Yahoo + Google News RSS). Uso:
   python agenda_proventos.py            -> carteira (carteira/dados/carteira.json)
   python agenda_proventos.py BBAS3 TAEE11 -> carteira + esses
"""
import urllib.request, urllib.parse, json, datetime as dt, os, sys, statistics as st
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
AQUI = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}
IR_JCP = 0.175          # retido na fonte
CUSTO = 0.0006          # emolumentos B3 ida+volta (~0,03% cada lado), corretagem zero
CARTEIRA = os.path.join(AQUI, "..", "carteira", "dados", "carteira.json")
VISTOS = os.path.join(AQUI, "agenda_proventos_vistos.json")
HOJE = dt.date.today()


def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()


def carteira():
    """{ticker: qtd} das posicoes que ele ainda tem"""
    d = json.load(open(CARTEIRA, encoding="utf-8"))
    return {p["ticker"]: (p["qtd"], dt.date.fromisoformat(p["data_entrada"]) if p.get("data_entrada") else None)
            for p in d["posicoes"] if "VENDIDO" not in (p.get("obs") or "")}


def proventos(t):
    """eventos agrupados por data-com: {data_com: {bruto, liquido, tipos, pagamento}}"""
    d = json.loads(get("https://statusinvest.com.br/acao/companytickerprovents"
                       "?ticker=%s&chartProventsType=2" % t))
    ev = {}
    for e in d.get("assetEarningsModels", []):
        if not e.get("ed") or e["ed"] == "-":
            continue
        dc = dt.datetime.strptime(e["ed"], "%d/%m/%Y").date()
        v = float(e["v"])
        liq = v * (1 - IR_JCP) if e.get("et") == "JCP" else v
        x = ev.setdefault(dc, {"bruto": 0, "liquido": 0, "tipos": set(), "pagamento": e.get("pd")})
        x["bruto"] += v
        x["liquido"] += liq
        x["tipos"].add(e.get("et"))
    return ev


def precos(sym):
    """{data: (abertura, fechamento)} de 5 anos, sem ajuste por provento"""
    r = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/%s"
                       "?range=5y&interval=1d" % urllib.parse.quote(sym)))["chart"]["result"][0]
    off = r["meta"].get("gmtoffset", -10800)
    q = r["indicators"]["quote"][0]
    out = {}
    for ts, o, c in zip(r["timestamp"], q["open"], q["close"]):
        if o and c:
            out[dt.datetime.utcfromtimestamp(ts + off).date()] = (o, c)
    return out, r["meta"].get("regularMarketPrice")


def razao_historica(ev, px, ibov):
    """quanto o papel caiu no dia ex (fech. data-com -> abertura do dia seguinte),
    descontado o gap do Ibovespa, em fracao do provento bruto"""
    dias = sorted(px)
    rs = []
    for dc, x in ev.items():
        if dc >= HOJE or dc not in px:
            continue
        i = dias.index(dc)
        if i + 1 >= len(dias):
            continue
        dex = dias[i + 1]
        fech, abre = px[dc][1], px[dex][0]
        gap_mkt = (ibov[dex][0] / ibov[dc][1] - 1) if dc in ibov and dex in ibov else 0
        queda = fech - abre * (1 - gap_mkt)     # queda em R$, ja tirando o mercado
        rs.append({"data_com": dc, "razao": queda / x["bruto"],
                   "ganho": (x["liquido"] - queda) / fech - CUSTO})
    return rs


def noticias(t):
    q = urllib.parse.quote('%s (dividendos OR JCP OR "juros sobre capital") when:14d' % t)
    try:
        root = ET.fromstring(get("https://news.google.com/rss/search?q=%s&hl=pt-BR&gl=BR&ceid=BR:pt-419" % q))
    except Exception:
        return []
    return [(i.findtext("pubDate")[5:16], i.findtext("title")) for i in root.iter("item")][:3]


def main():
    qtds = carteira()
    tickers = list(dict.fromkeys(list(qtds) + [a.upper() for a in sys.argv[1:]]))
    a_receber = []
    vistos = set(json.load(open(VISTOS))) if os.path.exists(VISTOS) else set()
    ibov, _ = precos("^BVSP")
    print("AGENDA DE PROVENTOS - %s\n" % HOJE.strftime("%d/%m/%Y"))
    for t in tickers:
        try:
            ev = proventos(t)
            px, preco = precos(t + ".SA")
        except Exception as e:
            print("%s: erro ao baixar (%s)\n" % (t, e))
            continue
        hist = razao_historica(ev, px, ibov)
        futuros = sorted(dc for dc in ev if dc >= HOJE)
        print("=" * 78)
        print("%s  cotacao R$ %.2f" % (t, preco))
        if hist:
            razao = st.median(h["razao"] for h in hist)
            pos = sum(h["ganho"] > 0 for h in hist) / len(hist)
            print("  historico: %d datas-com; no dia ex cai em media %.0f%% do provento bruto; "
                  "captura deu lucro em %.0f%% das vezes" % (len(hist), razao * 100, pos * 100))
        else:
            razao = 1.0
            print("  sem historico suficiente - assumindo queda = 100% do provento")
        if not futuros:
            print("  nenhum provento anunciado com data-com pela frente")
        for dc in futuros:
            x = ev[dc]
            chave = "%s|%s|%.8f" % (t, dc, x["bruto"])
            novo = "  [NOVO]" if chave not in vistos else ""
            vistos.add(chave)
            dy = x["liquido"] / preco
            queda = razao * x["bruto"]
            arb = (x["liquido"] - queda) / preco - CUSTO
            print("\n  %s R$ %.4f bruto / R$ %.4f liquido - data-com %s, paga %s%s"
                  % ("+".join(sorted(x["tipos"])), x["bruto"], x["liquido"],
                     dc.strftime("%d/%m/%Y"), x["pagamento"], novo))
            print("    preco ex teorico (B3):   R$ %.2f   (%.2f - %.4f)" % (preco - x["bruto"], preco, x["bruto"]))
            print("    preco ex pelo historico: R$ %.2f" % (preco - queda))
            print("    DY do provento: %.2f%%  x  arbitragem: %+.2f%%  -> %s"
                  % (dy * 100, arb * 100,
                     "COMPRA pra capturar (cai menos que o provento)" if arb > 0 else
                     "NAO COMPRA pra capturar (a queda come o provento)"))
            if dc == HOJE:
                print("    >>> HOJE e o ultimo dia pra ter direito: precisa estar com a acao no fechamento")
        for dc, x in ev.items():
            pg = dt.datetime.strptime(x["pagamento"], "%d/%m/%Y").date() if x["pagamento"] not in (None, "-") else None
            if t in qtds and dc < HOJE and pg and pg >= HOJE:
                q, entrada = qtds[t]
                if entrada is None or dc >= entrada:   # sem data de entrada: conta, mas avisa
                    a_receber.append((pg, t, q, x["liquido"], "" if entrada else "  (sem data de entrada - conferir)"))
        for data, tit in noticias(t):
            print("  noticia %s: %s" % (data, tit))
        print()
    if a_receber:
        print("=" * 78)
        print("A RECEBER (data-com ja passou, voce tinha a acao):")
        for pg, t, q, liq, obs in sorted(a_receber):
            print("  %s  %-6s %4d x R$ %.4f = R$ %8.2f%s" % (pg.strftime("%d/%m/%Y"), t, q, liq, q * liq, obs))
        print("  TOTAL R$ %.2f" % sum(r[2] * r[3] for r in a_receber))
    json.dump(sorted(vistos), open(VISTOS, "w"), indent=0)


if __name__ == "__main__":
    main()
