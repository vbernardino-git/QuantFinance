# -*- coding: utf-8 -*-
"""Modelo estatistico de ponto de compra.

Ideia: uma acao esta "boa pra comprar" quando ela esta barata CONTRA ELA MESMA -
nao contra o mercado, nem contra um preco-alvo de analista. Tres eixos, todos
medidos em desvios-padrao da propria historia do papel:

  1. PRECO x MEDIA        - quantos desvios abaixo da media movel de 200 pregoes
  2. PERCENTIL            - onde o preco esta na faixa dos ultimos 3 anos
  3. DIVIDEND YIELD       - o DY de hoje contra a media do DY historico do papel
                            (DY alto = preco baixo em relacao ao que a empresa paga)
  4. QUEDA DA MAXIMA      - drawdown contra a maxima de 52 semanas

Cada eixo vira um z-score, a media dos z vira um SCORE de 0 a 100, e o script
faz o BACKTEST: em toda a historia, quando o score esteve em cada faixa, qual
foi o retorno de fato nos 6 e 12 meses seguintes (preco + dividendos)? Se o
retorno nao cresce com o score, o modelo nao presta e o proprio relatorio diz.

Uso:  python modelo_preco.py ABCB4 [OUTRO ...]
"""
import sys, json, math, urllib.request, datetime as dt, statistics as st

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}
DIA = 86400


def _get(u, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=timeout).read()


def historico(tic):
    """serie diaria (data, fechamento, fechamento ajustado) desde sempre"""
    u = ("https://query1.finance.yahoo.com/v8/finance/chart/%s.SA"
         "?range=15y&interval=1d&events=div" % tic)
    d = json.loads(_get(u))["chart"]["result"][0]
    ts = d["timestamp"]
    close = d["indicators"]["quote"][0]["close"]
    adj = d["indicators"].get("adjclose", [{}])[0].get("adjclose", close)
    out = []
    for i, t in enumerate(ts):
        if close[i] is None:
            continue
        out.append((dt.date.fromtimestamp(t), float(close[i]),
                    float(adj[i]) if adj[i] is not None else float(close[i])))
    return out


def proventos(tic):
    """[(data_com, valor_por_acao)] - fonte StatusInvest"""
    u = ("https://statusinvest.com.br/acao/companytickerprovents"
         "?ticker=%s&chartProventsType=2" % tic)
    try:
        d = json.loads(_get(u))
    except Exception:
        return []
    if not isinstance(d, dict):
        return []
    out = []
    for e in d.get("assetEarningsModels", []):
        ed = e.get("ed")
        if not ed or ed == "-":
            continue
        dd, mm, yy = ed.split("/")
        out.append((dt.date(int(yy), int(mm), int(dd)), float(e["v"])))
    out.sort()
    return out


def z(v, serie):
    """z-score de v contra a serie (desvios-padrao)"""
    serie = [x for x in serie if x is not None]
    if len(serie) < 30:
        return None
    m = sum(serie) / len(serie)
    s = st.pstdev(serie)
    return None if s == 0 else (v - m) / s


def analisa(tic, verbose=True):
    hist = historico(tic)
    prov = proventos(tic)
    if len(hist) < 800:
        print("%s: historico curto demais (%d pregoes)" % (tic, len(hist)))
        return None
    datas = [h[0] for h in hist]
    px = [h[1] for h in hist]
    adj = [h[2] for h in hist]
    n = len(hist)

    # ---- DPA acumulado dos ultimos 12 meses, em cada data
    dpa12 = []
    for i, d0 in enumerate(datas):
        ini = d0 - dt.timedelta(days=365)
        dpa12.append(sum(v for dd, v in prov if ini < dd <= d0))
    dy = [(dpa12[i] / px[i]) if px[i] else 0.0 for i in range(n)]

    # ---- indicadores
    MA = 200
    JAN = 756          # 3 anos de pregao
    ma = [None] * n
    sd = [None] * n
    for i in range(n):
        if i >= MA:
            jan = px[i - MA:i]
            ma[i] = sum(jan) / MA
            sd[i] = st.pstdev(jan)

    reg = []           # (i, z_ma, pct, z_dy, dd52, score)
    for i in range(n):
        if ma[i] is None or sd[i] in (None, 0):
            continue
        z_ma = -(px[i] - ma[i]) / sd[i]                      # abaixo da media = positivo
        jan = px[max(0, i - JAN):i + 1]
        pct = sum(1 for v in jan if v > px[i]) / len(jan)    # 1 = na minima da janela
        jan_dy = dy[max(0, i - JAN):i + 1]
        z_dy = z(dy[i], jan_dy) or 0.0                       # DY alto = positivo
        alta52 = max(px[max(0, i - 252):i + 1])
        dd = (alta52 - px[i]) / alta52                       # queda da maxima
        # normaliza tudo pra mesma escala e soma
        comp = [max(-2.5, min(2.5, z_ma)),
                (pct - 0.5) * 4,
                max(-2.5, min(2.5, z_dy)),
                (dd - 0.15) * 6]
        score = 50 + 10 * (sum(comp) / len(comp))
        score = max(0, min(100, score))
        reg.append((i, z_ma, pct, z_dy, dd, score))

    # ---- backtest: retorno total 6m e 12m depois de cada leitura
    def fwd(i, meses):
        alvo = datas[i] + dt.timedelta(days=int(30.44 * meses))
        j = None
        for k in range(i + 1, n):
            if datas[k] >= alvo:
                j = k
                break
        if j is None:
            return None
        return adj[j] / adj[i] - 1        # ajustado ja inclui dividendo

    faixas = [(0, 40), (40, 55), (55, 70), (70, 100)]
    tabela = []
    for lo, hi in faixas:
        r6 = [fwd(i, 6) for i, *_ , sc in reg if lo <= sc < hi]
        r12 = [fwd(i, 12) for i, *_, sc in reg if lo <= sc < hi]
        r6 = [x for x in r6 if x is not None]
        r12 = [x for x in r12 if x is not None]
        if not r12:
            continue
        tabela.append({
            "faixa": "%d a %d" % (lo, hi), "n": len(r12),
            "med6": st.median(r6) * 100 if r6 else 0,
            "med12": st.median(r12) * 100,
            "media12": sum(r12) / len(r12) * 100,
            "pos12": sum(1 for x in r12 if x > 0) / len(r12) * 100,
            "pior12": min(r12) * 100, "melhor12": max(r12) * 100,
        })

    todos12 = [fwd(i, 12) for i, *_ in reg]
    todos12 = [x for x in todos12 if x is not None]
    base12 = {"n": len(todos12), "med": st.median(todos12) * 100,
              "media": sum(todos12) / len(todos12) * 100,
              "pos": sum(1 for x in todos12 if x > 0) / len(todos12) * 100}

    i = reg[-1][0]
    _, z_ma, pct, z_dy, dd, score = reg[-1]
    # preco que levaria o score a 70 (mexendo so no preco, tudo mais constante)
    def score_em(p):
        zm = -(p - ma[i]) / sd[i]
        jan = px[max(0, i - JAN):i + 1]
        pc = sum(1 for v in jan if v > p) / len(jan)
        d2 = (dpa12[i] / p) if p else 0
        jan_dy = dy[max(0, i - JAN):i + 1]
        zd = z(d2, jan_dy) or 0.0
        alta52 = max(px[max(0, i - 252):i + 1])
        ddx = (alta52 - p) / alta52
        comp = [max(-2.5, min(2.5, zm)), (pc - .5) * 4,
                max(-2.5, min(2.5, zd)), (ddx - .15) * 6]
        return max(0, min(100, 50 + 10 * (sum(comp) / len(comp))))

    alvos = {}
    for meta in (55, 65, 70):
        lo, hi = 0.2 * px[i], px[i] * 1.5
        if score_em(lo) < meta:
            alvos[meta] = None          # inalcancavel so mexendo no preco
            continue
        for _ in range(60):
            mid = (lo + hi) / 2
            if score_em(mid) >= meta:
                lo = mid
            else:
                hi = mid
        alvos[meta] = lo

    res = dict(ticker=tic, base12=base12, data=datas[i], preco=px[i], ma200=ma[i], sd200=sd[i],
               z_ma=z_ma, pct=pct, dy=dy[i], dpa12=dpa12[i], z_dy=z_dy, dd52=dd,
               score=score, backtest=tabela, alvos=alvos,
               dy_medio=sum(dy[max(0, i - JAN):i + 1]) / len(dy[max(0, i - JAN):i + 1]),
               min52=min(px[max(0, i - 252):i + 1]), max52=max(px[max(0, i - 252):i + 1]),
               pregoes=n, primeiro=datas[0])

    if verbose:
        print("=" * 92)
        print("%s - leitura de %s   (base: %d pregoes desde %s)" % (
            tic, res["data"].strftime("%d/%m/%Y"), n, res["primeiro"].strftime("%d/%m/%Y")))
        print("=" * 92)
        print("  Preco                      R$ %8.2f" % px[i])
        print("  Media movel 200 pregoes    R$ %8.2f   (desvio-padrao R$ %.2f)" % (ma[i], sd[i]))
        print("  Distancia da media         %+8.1f%%  = %+.2f desvios %s" % (
            (px[i] / ma[i] - 1) * 100, -z_ma, "ABAIXO" if z_ma > 0 else "ACIMA"))
        print("  Percentil em 3 anos        %8.0f%%  (100%% = na minima do periodo)" % (pct * 100))
        print("  Minima/maxima 52 semanas   R$ %.2f / R$ %.2f   queda da maxima %.1f%%" % (
            res["min52"], res["max52"], dd * 100))
        print("  DY 12 meses                %8.2f%%  (media de 3 anos: %.2f%%, z = %+.2f)" % (
            dy[i] * 100, res["dy_medio"] * 100, z_dy))
        print("  DPA 12 meses               R$ %8.4f" % dpa12[i])
        print()
        print("  SCORE DE COMPRA            %8.0f / 100" % score)
        print()
        print("  BACKTEST - o que aconteceu depois, em toda a historia do papel")
        print("  %-10s %6s %10s %10s %10s %10s %10s" % (
            "SCORE", "casos", "med 6m", "med 12m", "media 12m", "% positivo", "pior 12m"))
        for L in tabela:
            print("  %-10s %6d %9.1f%% %9.1f%% %9.1f%% %9.0f%% %9.1f%%" % (
                L["faixa"], L["n"], L["med6"], L["med12"], L["media12"], L["pos12"], L["pior12"]))
        print("  %-10s %6d %9s %9.1f%% %9.1f%% %9.0f%% %9s   <- QUALQUER DIA (referencia)" % (
            "todos", base12["n"], "-", base12["med"], base12["media"], base12["pos"], "-"))
        print()
        print("  PRECOS DE GATILHO (mantendo dividendo e media de hoje)")
        for meta in (55, 65, 70):
            a = alvos[meta]
            if a is None:
                print("    score %d  ->  inalcancavel so com queda de preco "
                      "(precisaria de aumento de dividendo)" % meta)
            else:
                print("    score %d  ->  R$ %6.2f  (%+.1f%% do preco de hoje, DY ficaria em %.2f%%)" % (
                    meta, a, (a / px[i] - 1) * 100, dpa12[i] / a * 100))
    return res


if __name__ == "__main__":
    tickers = sys.argv[1:] or ["ABCB4"]
    saida = []
    for t in tickers:
        r = analisa(t.upper())
        if r:
            r["data"] = r["data"].isoformat()
            r["primeiro"] = r["primeiro"].isoformat()
            saida.append(r)
        print()
    import os
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "modelo_preco.json")
    json.dump(saida, open(destino, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("SALVO:", destino)
