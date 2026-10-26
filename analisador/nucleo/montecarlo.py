# -*- coding: utf-8 -*-
"""
PILAR MONTE CARLO (simulacao estocastica - GBM)
Fontes: John C. Hull (Options, Futures and Other Derivatives), Glasserman
(Monte Carlo Methods in Financial Engineering). Porta o notebook '01. Monte Carlo':
Movimento Browniano Geometrico vetorizado -> distribuicao de preco a 1 ano,
VaR 95%, Expected Shortfall (CVaR) e probabilidade de lucro.
"""
import numpy as np
import pandas as pd

from . import config


def analisar(df_diario: pd.DataFrame) -> dict:
    if df_diario is None or len(df_diario) < 120:
        return {"ok": False, "notas": ["Historico insuficiente p/ Monte Carlo."]}

    close = df_diario["Close"]
    log_ret = np.log(close / close.shift(1)).dropna()
    if len(log_ret) < 60:
        return {"ok": False, "notas": ["Retornos insuficientes."]}

    s0 = float(close.iloc[-1])
    mu_d = float(log_ret.mean())
    sig_d = float(log_ret.std())
    mu_ann = mu_d * 252
    sig_ann = sig_d * np.sqrt(252)

    rng = np.random.default_rng(config.MC_SEED)
    dias = config.MC_DIAS; sim = config.MC_SIMULACOES
    Z = rng.standard_normal(size=(dias, sim))
    incr = (mu_d - 0.5 * sig_d**2) + sig_d * Z
    log_paths = np.log(s0) + np.cumsum(incr, axis=0)
    finais = np.exp(log_paths[-1, :])

    pnl_pct = (finais / s0 - 1.0) * 100
    var95_preco = float(np.percentile(finais, 5))
    var95_ret = float(np.percentile(pnl_pct, 5))
    es95 = float(pnl_pct[pnl_pct <= var95_ret].mean())  # CVaR / Expected Shortfall
    prob_lucro = float(np.mean(finais > s0))
    p50 = float(np.percentile(finais, 50))
    p95 = float(np.percentile(finais, 95))

    notas = [
        f"Drift anual {mu_ann:+.1%} | Vol anual {sig_ann:.1%}",
        f"Preco mediano projetado 1a: R$ {p50:.2f} (atual R$ {s0:.2f})",
        f"Prob. de terminar no lucro em 1a: {prob_lucro:.0%}",
        f"VaR 95% (1a): {var95_ret:.1f}%  | CVaR/ES 95%: {es95:.1f}%",
    ]
    return {
        "ok": True, "preco_atual": round(s0, 2),
        "mu_ann": mu_ann, "sig_ann": sig_ann,
        "preco_mediano_1a": round(p50, 2), "preco_p05_1a": round(var95_preco, 2),
        "preco_p95_1a": round(p95, 2),
        "prob_lucro_1a": round(prob_lucro, 3),
        "var95": round(var95_ret, 1), "cvar95": round(es95, 1),
        "notas": notas,
    }
