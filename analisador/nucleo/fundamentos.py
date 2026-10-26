# -*- coding: utf-8 -*-
"""
PILAR FUNDAMENTALISTA
Fontes: Benjamin Graham & David Dodd (Security Analysis / The Intelligent Investor),
Joel Greenblatt (The Little Book That Beats the Market - Magic Formula),
Warren Buffett (qualidade + moat: ROE/ROIC altos e consistentes),
Aswath Damodaran (valuation por multiplos e FCF).

Transforma o pacote cru de dados.buscar_fundamentos() num sub-score 0-100,
combinando 4 dimensoes: QUALIDADE, VALUATION, SAUDE FINANCEIRA e CRESCIMENTO.
"""
import numpy as np


def _val(d, chave):
    v = d.get(chave)
    if v is None:
        return np.nan
    try:
        v = float(v)
        return np.nan if np.isnan(v) else v
    except (TypeError, ValueError):
        return np.nan


def _faixa(valor, ruim, otimo, invertido=False):
    """
    Normaliza 'valor' em 0..1 entre os limites ruim->otimo.
    invertido=True quando MENOR e melhor (ex: P/L, EV/EBIT, divida).
    """
    if np.isnan(valor):
        return None
    if invertido:
        if valor <= otimo:
            return 1.0
        if valor >= ruim:
            return 0.0
        return (ruim - valor) / (ruim - otimo)
    else:
        if valor >= otimo:
            return 1.0
        if valor <= ruim:
            return 0.0
        return (valor - ruim) / (otimo - ruim)


def analisar(pacote: dict) -> dict:
    """Retorna sub-score fundamentalista 0-100 + leitura por dimensao."""
    if not pacote or not pacote.get("ok"):
        return {"ok": False, "score": 50.0, "erro": pacote.get("erro") if pacote else "sem dados",
                "notas": ["Fundamentos indisponiveis (papel/ETF/banco com schema diferente)."],
                "dimensoes": {}}

    d = pacote["dados"]
    notas = []
    dims = {}

    # ---- ROE / ROA podem vir em fracao (0.18) no yfinance ----
    roe = _val(d, "roe"); roa = _val(d, "roa"); roic = _val(d, "roic_proxy")
    mg_op = _val(d, "margem_operacional"); mg_liq = _val(d, "margem_liquida")

    # =============================== QUALIDADE (Buffett/Greenblatt) ===============================
    q = []
    f = _faixa(roe, 0.05, 0.20);  q.append(f) if f is not None else None
    f = _faixa(roic, 0.05, 0.15); q.append(f) if f is not None else None
    f = _faixa(mg_liq, 0.02, 0.20); q.append(f) if f is not None else None
    f = _faixa(mg_op, 0.05, 0.25); q.append(f) if f is not None else None
    qualidade = float(np.mean(q)) if q else None
    dims["qualidade"] = qualidade
    if roe is not None and not np.isnan(roe):
        notas.append(f"ROE {roe*100:.1f}% " + ("(forte)" if roe >= 0.15 else "(fraco)" if roe < 0.08 else "(medio)"))
    if not np.isnan(roic):
        notas.append(f"ROIC~{roic*100:.1f}% (Greenblatt: capital bem alocado)" if roic >= 0.12
                     else f"ROIC~{roic*100:.1f}% (baixo retorno s/ capital)")

    # =============================== VALUATION (Graham/Damodaran/Greenblatt) ===============================
    v = []
    pl = _val(d, "pl"); pvp = _val(d, "pvp"); ev_ebit = _val(d, "ev_ebit")
    ey = _val(d, "earnings_yield"); fcf_y = _val(d, "fcf_yield"); dy = _val(d, "dividend_yield")
    f = _faixa(pl, 25, 6, invertido=True); v.append(f) if f is not None else None
    f = _faixa(pvp, 4, 0.8, invertido=True); v.append(f) if f is not None else None
    f = _faixa(ev_ebit, 18, 5, invertido=True); v.append(f) if f is not None else None  # Magic Formula
    f = _faixa(ey, 0.03, 0.15); v.append(f) if f is not None else None                  # earnings yield
    f = _faixa(fcf_y, 0.02, 0.12); v.append(f) if f is not None else None
    valuation = float(np.mean(v)) if v else None
    dims["valuation"] = valuation
    if not np.isnan(pl):
        notas.append(f"P/L {pl:.1f} " + ("(barato)" if pl < 10 else "(caro)" if pl > 20 else "(justo)"))
    if not np.isnan(ev_ebit):
        notas.append(f"EV/EBIT {ev_ebit:.1f} " + ("(barato - Magic Formula)" if ev_ebit < 8 else "(esticado)" if ev_ebit > 15 else "(ok)"))
    if not np.isnan(pvp):
        notas.append(f"P/VP {pvp:.2f}")
    if not np.isnan(dy) and dy > 0:
        # yfinance 1.3.x entrega dividendYield ja em pontos percentuais (ex: 9.5 = 9,5%).
        notas.append(f"Dividend yield {dy:.1f}%")

    # =============================== SAUDE FINANCEIRA (Graham: margem de seguranca) ===============================
    s = []
    div_pl = _val(d, "divida_pl"); liq = _val(d, "liquidez_corrente")
    # debtToEquity do yfinance costuma vir em % (ex: 80 = 0.8). Normaliza.
    if not np.isnan(div_pl) and div_pl > 5:
        div_pl = div_pl / 100
    f = _faixa(div_pl, 2.0, 0.3, invertido=True); s.append(f) if f is not None else None
    f = _faixa(liq, 0.8, 2.0); s.append(f) if f is not None else None
    saude = float(np.mean(s)) if s else None
    dims["saude"] = saude
    if not np.isnan(div_pl):
        notas.append(f"Divida/PL {div_pl:.2f} " + ("(conservadora)" if div_pl < 0.6 else "(alavancada)" if div_pl > 1.2 else "(moderada)"))
    if not np.isnan(liq):
        notas.append(f"Liquidez corrente {liq:.2f} " + ("(folgada)" if liq >= 1.5 else "(apertada)" if liq < 1 else ""))

    # =============================== CRESCIMENTO (Damodaran/Fisher) ===============================
    g = []
    cr = _val(d, "cagr_receita"); cl = _val(d, "cagr_lucro")
    f = _faixa(cr, -0.05, 0.20); g.append(f) if f is not None else None
    f = _faixa(cl, -0.05, 0.20); g.append(f) if f is not None else None
    crescimento = float(np.mean(g)) if g else None
    dims["crescimento"] = crescimento
    if not np.isnan(cr):
        notas.append(f"CAGR receita {cr*100:.1f}%")
    if not np.isnan(cl):
        notas.append(f"CAGR lucro {cl*100:.1f}%")

    # =============================== AGREGACAO ===============================
    # Pesos internos: qualidade 30, valuation 35, saude 20, crescimento 15.
    # Reescala pelos disponiveis (graceful) -> sempre 0..100.
    pesos = {"qualidade": 0.30, "valuation": 0.35, "saude": 0.20, "crescimento": 0.15}
    num, den = 0.0, 0.0
    for k, p in pesos.items():
        if dims.get(k) is not None and not np.isnan(dims[k]):
            num += dims[k] * p
            den += p
    if den == 0:
        score = 50.0
        notas.append("Poucos fundamentos disponiveis: score neutro.")
    else:
        score = float(np.clip((num / den) * 100, 0, 100))

    return {
        "ok": True,
        "score": score,
        "dimensoes": {k: (None if v is None else round(v * 100, 0)) for k, v in dims.items()},
        "nome": d.get("nome"),
        "setor": d.get("setor"),
        "preco_alvo": d.get("preco_alvo"),
        "recomendacao": d.get("recomendacao"),
        "notas": notas,
    }
