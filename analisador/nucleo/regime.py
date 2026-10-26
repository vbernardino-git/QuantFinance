# -*- coding: utf-8 -*-
"""
PILAR REGIME (Mudanca de Regime de Mercado)
Fontes: James D. Hamilton (Regime-Switching Models / Markov Switching),
Rabiner (Hidden Markov Models). Porta a logica do seu radar_markov_ibov.py e do
notebook 05/06, agora em base DIARIA (horizonte de investidor) + HMM de 3 estados.

Regime de ALTA -> favoravel a comprado; regime de BAIXA -> favoravel a vendido.
Sub-score 0-100.
"""
import warnings
import numpy as np
import pandas as pd

from . import config

warnings.filterwarnings("ignore")

try:
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
    _TEM_MARKOV = True
except Exception:
    _TEM_MARKOV = False

try:
    from hmmlearn.hmm import GaussianHMM
    _TEM_HMM = True
except Exception:
    _TEM_HMM = False

from sklearn.preprocessing import StandardScaler
try:
    from sklearn.cluster import KMeans
    _TEM_KMEANS = True
except Exception:
    _TEM_KMEANS = False


def _markov_diario(close: pd.Series) -> dict | None:
    """Probabilidade FILTRADA (sem look-ahead) de estar no regime de ALTA."""
    if not _TEM_MARKOV or close is None or len(close) < config.MARKOV_MIN_OBS:
        return None
    returns = close.pct_change().dropna()
    if len(returns) < config.MARKOV_MIN_OBS:
        return None
    try:
        res = MarkovRegression(returns, k_regimes=2, switching_trend=True,
                               switching_variance=True).fit(disp=False)
    except Exception:
        return None
    prob = res.filtered_marginal_probabilities
    regime = prob.values.argmax(axis=1)
    medias = pd.Series(returns.values).groupby(regime).mean()
    if len(medias) < 2:
        return None
    regime_alta = int(medias.idxmax())
    prob_alta = float(prob.iloc[:, regime_alta].iloc[-1])
    return {"prob_alta": prob_alta,
            "estado": "ALTA" if prob_alta > 0.5 else "BAIXA"}


def _features_regime(close: pd.Series) -> pd.DataFrame | None:
    returns = np.log(close / close.shift(1))
    df = pd.DataFrame(index=close.index)
    df["returns"] = returns
    df["vol20"] = returns.rolling(20).std()
    df["mom20"] = close.pct_change(20)
    df["ma_ratio"] = close / close.rolling(50).mean()
    df = df.dropna()
    return df if len(df) >= 60 else None


def _hmm_diario(close: pd.Series) -> dict | None:
    """Gaussian HMM (3 estados) -> rotula o estado atual por retorno medio. Fallback KMeans."""
    feats = _features_regime(close)
    if feats is None:
        return None
    X = StandardScaler().fit_transform(feats.values)

    estados = None
    metodo = None
    if _TEM_HMM:
        try:
            m = GaussianHMM(n_components=config.HMM_REGIMES, covariance_type="full",
                            n_iter=200, random_state=42)
            m.fit(X)
            estados = m.predict(X)
            metodo = "HMM"
        except Exception:
            estados = None
    if estados is None and _TEM_KMEANS:
        try:
            estados = KMeans(n_clusters=config.HMM_REGIMES, random_state=42,
                             n_init=10).fit_predict(X)
            metodo = "KMeans"
        except Exception:
            return None
    if estados is None:
        return None

    ret = feats["returns"].values
    medias = pd.Series(ret).groupby(estados).mean()
    estado_atual = int(estados[-1])
    melhor = int(medias.idxmax()); pior = int(medias.idxmin())
    if estado_atual == melhor:
        leitura = "ALTA"
    elif estado_atual == pior:
        leitura = "BAIXA"
    else:
        leitura = "NEUTRO"
    return {"metodo": metodo, "estado_atual": estado_atual,
            "leitura": leitura, "ret_medio_estado": float(medias.loc[estado_atual])}


def analisar(close_diario: pd.Series, close_intraday: pd.Series | None = None) -> dict:
    """
    Combina Markov (diario), HMM/KMeans (diario) e Markov intraday (opcional)
    num sub-score 0-100. Cada componente disponivel "vota".
    """
    componentes = []
    notas = []
    detalhe = {}

    mk = _markov_diario(close_diario)
    if mk:
        detalhe["markov_diario"] = mk
        p = mk["prob_alta"]
        componentes.append(p * 100)
        notas.append(f"Markov diario: regime {mk['estado']} (prob. alta {p:.0%})")

    hmm = _hmm_diario(close_diario)
    if hmm:
        detalhe["hmm"] = hmm
        mapa = {"ALTA": 80.0, "NEUTRO": 50.0, "BAIXA": 20.0}
        componentes.append(mapa[hmm["leitura"]])
        notas.append(f"{hmm['metodo']} (3 estados): regime atual {hmm['leitura']}")

    if close_intraday is not None and len(close_intraday) >= config.MARKOV_MIN_OBS:
        mki = _markov_diario(close_intraday)  # mesma rotina serve p/ qualquer serie
        if mki:
            detalhe["markov_intraday"] = mki
            componentes.append(mki["prob_alta"] * 100)
            notas.append(f"Markov intraday 15m: regime {mki['estado']} (prob. alta {mki['prob_alta']:.0%})")

    if not componentes:
        return {"ok": False, "score": 50.0, "notas": ["Regime indisponivel."], "detalhe": {}}

    score = float(np.clip(np.mean(componentes), 0, 100))
    return {"ok": True, "score": score, "notas": notas, "detalhe": detalhe}
