# -*- coding: utf-8 -*-
"""
VEREDITO UNIFICADO (filosofia EQUILIBRADA, estilo gestor multiestrategia)

Combina os pilares num score 0-100:
  FUNDAMENTOS .......... 40%   (Graham, Greenblatt, Buffett, Damodaran)
  TECNICO + QUANT ...... 35%   (ANATEC+M34, Bollinger/EMAs + ML LightGBM)
  REGIME + RISCO ....... 25%   (Markov/HMM + Sharpe/Drawdown/Beta + Monte Carlo)

Reescala automaticamente quando algum pilar nao esta disponivel (graceful).
"""
import numpy as np

from . import config


def _mc_para_score(mc: dict) -> float | None:
    """Mapeia a probabilidade de lucro 1a (Monte Carlo) num score 0-100."""
    if not mc or not mc.get("ok"):
        return None
    p = mc.get("prob_lucro_1a")
    if p is None:
        return None
    # 50% prob -> 50 pts; escala suave em torno disso
    return float(np.clip(50 + (p - 0.5) * 120, 0, 100))


def consolidar(res_fund, res_tec, res_ml, res_reg, res_risco, res_mc) -> dict:
    # --- Pilar TECNICO+QUANT: tecnico 60% + ML 40% ---
    tq_parts, tq_pesos = [], []
    if res_tec and res_tec.get("ok"):
        tq_parts.append(res_tec["score"]); tq_pesos.append(0.60)
    if res_ml and res_ml.get("ok"):
        tq_parts.append(res_ml["score"]); tq_pesos.append(0.40)
    pilar_tq = (np.average(tq_parts, weights=tq_pesos) if tq_parts else None)

    # --- Pilar REGIME+RISCO: regime 40% + risco 40% + montecarlo 20% ---
    rr_parts, rr_pesos = [], []
    if res_reg and res_reg.get("ok"):
        rr_parts.append(res_reg["score"]); rr_pesos.append(0.40)
    if res_risco and res_risco.get("ok"):
        rr_parts.append(res_risco["score"]); rr_pesos.append(0.40)
    mc_score = _mc_para_score(res_mc)
    if mc_score is not None:
        rr_parts.append(mc_score); rr_pesos.append(0.20)
    pilar_rr = (np.average(rr_parts, weights=rr_pesos) if rr_parts else None)

    # --- Pilar FUNDAMENTOS ---
    pilar_f = res_fund["score"] if (res_fund and res_fund.get("ok")) else None

    # --- Agregacao final com reescala (graceful) ---
    pilares = [
        (pilar_f,  config.PESO_FUNDAMENTOS, "Fundamentos"),
        (pilar_tq, config.PESO_TECNICO,     "Tecnico+Quant"),
        (pilar_rr, config.PESO_REGIME_RISCO, "Regime+Risco"),
    ]
    num, den = 0.0, 0.0
    pilar_scores = {}
    for valor, peso, nome in pilares:
        if valor is not None and not np.isnan(valor):
            num += valor * peso
            den += peso
            pilar_scores[nome] = round(float(valor), 1)
        else:
            pilar_scores[nome] = None

    score_final = float(np.clip(num / den, 0, 100)) if den > 0 else 50.0

    # --- Rotulo do veredito ---
    rotulo, estilo = "NEUTRO", "yellow"
    for limiar, nome, est in config.FAIXAS_VEREDITO:
        if score_final >= limiar:
            rotulo, estilo = nome, est
            break

    return {
        "score_final": round(score_final, 1),
        "rotulo": rotulo,
        "estilo": estilo,
        "pilares": pilar_scores,
        "cobertura": round(den / (config.PESO_FUNDAMENTOS + config.PESO_TECNICO + config.PESO_REGIME_RISCO), 2),
    }
