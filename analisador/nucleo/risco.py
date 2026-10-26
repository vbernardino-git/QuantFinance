# -*- coding: utf-8 -*-
"""
PILAR RISCO (metricas de risco/retorno)
Fontes: William Sharpe (Sharpe ratio), Markowitz (vol como risco), pratica de
gestao de risco (max drawdown, beta de mercado, downside deviation/Sortino).
"""
import numpy as np
import pandas as pd


def _alinhar(ativo: pd.Series, indice: pd.Series):
    df = pd.concat([ativo.rename("a"), indice.rename("m")], axis=1).dropna()
    return df["a"], df["m"]


def analisar(df_diario: pd.DataFrame, close_indice: pd.Series | None = None) -> dict:
    if df_diario is None or len(df_diario) < 120:
        return {"ok": False, "score": 50.0, "notas": ["Historico insuficiente p/ risco."]}

    close = df_diario["Close"]
    ret = close.pct_change().dropna()
    if len(ret) < 60:
        return {"ok": False, "score": 50.0, "notas": ["Retornos insuficientes."]}

    vol_ann = float(ret.std() * np.sqrt(252))
    ret_ann = float((1 + ret.mean())**252 - 1)
    sharpe = float((ret.mean() / ret.std()) * np.sqrt(252)) if ret.std() else np.nan
    downside = ret[ret < 0]
    sortino = float((ret.mean() / downside.std()) * np.sqrt(252)) if len(downside) and downside.std() else np.nan

    # Max drawdown sobre a curva de preco
    curva = (1 + ret).cumprod()
    pico = curva.cummax()
    dd = (curva / pico - 1.0)
    max_dd = float(dd.min())

    # Beta vs IBOV
    beta = np.nan
    if close_indice is not None:
        ri, rm = _alinhar(ret, close_indice.pct_change().dropna())
        if len(ri) > 60 and rm.var() > 0:
            beta = float(np.cov(ri, rm)[0, 1] / rm.var())

    # --- Score de risco: recompensa retorno ajustado, pune drawdown e vol extrema ---
    pontos = 50.0
    notas = []
    if not np.isnan(sharpe):
        pontos += float(np.clip(sharpe, -1.5, 1.5)) * 12
        notas.append(f"Sharpe {sharpe:.2f} | Sortino " + (f"{sortino:.2f}" if not np.isnan(sortino) else "n/d"))
    notas.append(f"Vol anual {vol_ann:.0%} | Retorno anual hist. {ret_ann:+.0%}")
    notas.append(f"Max drawdown {max_dd:.0%}")
    if max_dd < -0.55:
        pontos -= 12; notas.append("Drawdown historico severo (>55%)")
    elif max_dd < -0.40:
        pontos -= 6
    if vol_ann > 0.60:
        pontos -= 6; notas.append("Volatilidade muito alta (>60% a.a.)")
    if not np.isnan(beta):
        notas.append(f"Beta vs IBOV {beta:.2f} " + ("(defensiva)" if beta < 0.8 else "(agressiva)" if beta > 1.2 else "(neutra)"))

    score = float(np.clip(pontos, 0, 100))
    return {
        "ok": True, "score": score,
        "vol_ann": round(vol_ann, 4), "ret_ann": round(ret_ann, 4),
        "sharpe": None if np.isnan(sharpe) else round(sharpe, 2),
        "sortino": None if np.isnan(sortino) else round(sortino, 2),
        "max_drawdown": round(max_dd, 4),
        "beta": None if np.isnan(beta) else round(beta, 2),
        "notas": notas,
    }
