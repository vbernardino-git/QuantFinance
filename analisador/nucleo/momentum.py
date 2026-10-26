# -*- coding: utf-8 -*-
"""
ESTRATEGIA DUAL MOMENTUM (Gary Antonacci, "Dual Momentum Investing")
+ Time-Series Momentum (Moskowitz-Ooi-Pedersen) + tilt de baixa volatilidade
  (Frazzini-Pedersen, "Betting Against Beta").

Ideia para BATER o indice (e nao virar um mini-IBOV):
  1) MOMENTUM RELATIVO  -> seleciona os ativos MAIS FORTES do universo
     (ranking por retorno passado, pulando o ultimo mes p/ evitar reversao curta).
  2) MOMENTUM ABSOLUTO  -> so fica comprado se a forca do ativo superar o CDI;
     senao, aquele "slot" vai para o CDI (ativo seguro). E isso que protege nas
     quedas (ex: 2020) e permite superar o indice no ciclo completo.
  3) FILTRO DE TENDENCIA -> exige preco acima da media de 200 dias (Faber).
  4) PONDERACAO POR CONVICCAO -> entre os escolhidos, peso por INVERSO DA VOL
     (risco-paridade simples): menos peso em quem oscila mais.

Tudo e point-in-time (causal): usa apenas precos ate a data avaliada.
Opera sobre um PAINEL de precos (DataFrame: index=datas, colunas=tickers) -> rapido.
"""
import numpy as np
import pandas as pd


def ret_janela(serie: pd.Series, lb: int, skip: int) -> float:
    """Retorno de uma serie ao longo de 'lb' pregoes, terminando 'skip' pregoes atras."""
    s = serie.dropna()
    if len(s) < lb + skip + 1:
        return np.nan
    p_now = s.iloc[-1 - skip]
    p_then = s.iloc[-1 - skip - lb]
    if p_then <= 0 or np.isnan(p_now) or np.isnan(p_then):
        return np.nan
    return p_now / p_then - 1.0


def momentum_composto(precos: pd.DataFrame, data, lookbacks=(126, 252), skip=21) -> pd.Series:
    """Score de momentum relativo: media dos z-scores transversais de cada horizonte."""
    px = precos.loc[:data]
    zs = {}
    for lb in lookbacks:
        rr = pd.Series({t: ret_janela(px[t], lb, skip) for t in precos.columns})
        mu, sd = rr.mean(), rr.std()
        zs[lb] = (rr - mu) / sd if (sd and not np.isnan(sd)) else rr * 0.0
    return pd.DataFrame(zs).mean(axis=1)


def vol_anual(precos: pd.DataFrame, data, janela=126) -> pd.Series:
    """Volatilidade anualizada recente (p/ ponderacao por inverso da vol)."""
    px = precos.loc[:data]
    return px.pct_change().tail(janela).std() * np.sqrt(252)


def abs_momentum(precos: pd.DataFrame, data, lb=252, skip=21) -> pd.Series:
    px = precos.loc[:data]
    return pd.Series({t: ret_janela(px[t], lb, skip) for t in precos.columns})


def acima_media(precos: pd.DataFrame, data, janela=200) -> pd.Series:
    px = precos.loc[:data]
    if len(px) < janela:
        return pd.Series({t: False for t in precos.columns})
    sma = px.rolling(janela).mean().iloc[-1]
    return px.iloc[-1] > sma


def selecionar(precos, data, cdi_lookback_ret, top_n=5, lookbacks=(126, 252), skip=21,
               vol_janela=126, usar_trend=True, sma_janela=200, usar_absoluto=True):
    """
    Retorna (pesos, caixa, diagnostico):
      pesos  -> dict {ticker: peso} (soma = fracao investida em acoes)
      caixa  -> fracao alocada no CDI (ativo seguro)
      diag   -> dict com info p/ inspecao
    Convencao de 'slots': o capital e dividido em TOP_N fatias; cada acao que passa
    nos filtros ocupa uma fatia (ponderada por inverso-vol entre as ocupadas), e as
    fatias vazias vao para o CDI -> a estrategia migra suavemente p/ caixa quando
    poucos ativos qualificam (defesa automatica nas quedas).
    """
    score = momentum_composto(precos, data, lookbacks, skip)
    vol = vol_anual(precos, data, vol_janela)
    absm = abs_momentum(precos, data, max(lookbacks), skip)
    acima = acima_media(precos, data, sma_janela) if usar_trend else None

    candidatos = []
    for t in score.dropna().index:
        if usar_trend and not bool(acima.get(t, False)):
            continue
        if usar_absoluto:
            a = absm.get(t, np.nan)
            if np.isnan(a) or a <= (cdi_lookback_ret if not np.isnan(cdi_lookback_ret) else 0.0):
                continue
        v = vol.get(t, np.nan)
        if np.isnan(v) or v <= 0:
            continue
        candidatos.append(t)

    candidatos = sorted(candidatos, key=lambda t: score[t], reverse=True)[:top_n]
    if not candidatos:
        return {}, 1.0, {"n_candidatos": 0, "motivo": "nenhum ativo passou (mercado fraco) -> 100% CDI"}

    raw = {t: 1.0 / vol[t] for t in candidatos}   # inverso da volatilidade (conviccao/risco)
    soma = sum(raw.values())
    investido = len(candidatos) / top_n
    pesos = {t: investido * raw[t] / soma for t in candidatos}
    caixa = 1.0 - investido
    diag = {"n_candidatos": len(candidatos),
            "scores": {t: round(float(score[t]), 2) for t in candidatos}}
    return pesos, caixa, diag
