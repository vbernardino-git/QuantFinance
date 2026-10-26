# -*- coding: utf-8 -*-
"""
PILAR MACHINE LEARNING (preditor multi-fator de retorno)
Fontes: Marcos Lopez de Prado (Advances in Financial Machine Learning - walk-forward,
sem look-ahead, Information Coefficient), Grinold & Kahn (Active Portfolio Management - IC).

Porta o notebook '02. ML Return Predictor': LightGBM sobre fatores de momentum,
volatilidade, tendencia, reversao a media e volume, com validacao walk-forward
(TimeSeriesSplit). So confia no sinal se o IC out-of-sample for relevante.
"""
import warnings
import numpy as np
import pandas as pd
import ta

from . import config

warnings.filterwarnings("ignore")

try:
    from lightgbm import LGBMRegressor
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.preprocessing import StandardScaler
    from scipy.stats import spearmanr
    _TEM_ML = True
except Exception:
    _TEM_ML = False

FEATURES = ["volatility_20", "momentum_10", "momentum_30", "zscore_20",
            "rsi", "atr", "macd", "macd_signal", "volume_zscore"]


def _montar(df_diario: pd.DataFrame) -> pd.DataFrame | None:
    df = df_diario.copy()
    if "Volume" not in df.columns:
        df["Volume"] = np.nan
    df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
    h = config.ML_HORIZONTE
    df["target"] = df["log_return"].rolling(h).sum().shift(-h)
    df["volatility_20"] = df["log_return"].rolling(20).std()
    df["momentum_10"] = df["Close"] / df["Close"].shift(10) - 1
    df["momentum_30"] = df["Close"] / df["Close"].shift(30) - 1
    df["zscore_20"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).std()
    df["rsi"] = ta.momentum.RSIIndicator(close=df["Close"], window=14).rsi()
    df["atr"] = ta.volatility.AverageTrueRange(high=df["High"], low=df["Low"],
                                               close=df["Close"], window=14).average_true_range()
    macd = ta.trend.MACD(df["Close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["volume_zscore"] = (df["Volume"] - df["Volume"].rolling(20).mean()) / df["Volume"].rolling(20).std()
    df["volume_zscore"] = df["volume_zscore"].fillna(0)
    df = df.dropna(subset=FEATURES + ["target"])
    return df if len(df) >= 250 else None


def analisar(df_diario: pd.DataFrame) -> dict:
    """Retorna previsao de retorno {ML_HORIZONTE}d, qualidade (IC/Sharpe) e sub-score 0-100."""
    if not _TEM_ML:
        return {"ok": False, "score": 50.0, "notas": ["LightGBM/sklearn indisponivel."]}
    df = _montar(df_diario)
    if df is None:
        return {"ok": False, "score": 50.0, "notas": ["Historico insuficiente p/ ML (precisa ~1 ano+)."]}

    X = df[FEATURES]
    y = df["target"]

    tscv = TimeSeriesSplit(n_splits=config.ML_SPLITS)
    preds_oos, reais_oos, ics = [], [], []
    for tr, te in tscv.split(X):
        sc = StandardScaler()
        Xtr = sc.fit_transform(X.iloc[tr]); Xte = sc.transform(X.iloc[te])
        m = LGBMRegressor(n_estimators=400, learning_rate=0.01, max_depth=6,
                          subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=-1)
        m.fit(Xtr, y.iloc[tr])
        p = m.predict(Xte)
        preds_oos.extend(p); reais_oos.extend(y.iloc[te].values)
        try:
            ic, _ = spearmanr(p, y.iloc[te])
            if not np.isnan(ic):
                ics.append(ic)
        except Exception:
            pass

    preds_oos = np.array(preds_oos); reais_oos = np.array(reais_oos)
    ic_geral = float(np.mean(ics)) if ics else 0.0
    acerto_dir = float(np.mean(np.sign(preds_oos) == np.sign(reais_oos))) if len(preds_oos) else np.nan

    # Sharpe da estrategia sign(pred) (liquido de custo)
    h = config.ML_HORIZONTE
    pos = np.sign(preds_oos)
    turn = np.abs(np.diff(np.concatenate(([0], pos))))
    bruto = pos * reais_oos / h
    liq = bruto - turn * config.ML_CUSTO_TRADE / h
    sharpe = float((liq.mean() / liq.std()) * np.sqrt(252)) if liq.std() else np.nan

    # Previsao "ao vivo": reajusta no dataset inteiro
    sc = StandardScaler(); Xfull = sc.fit_transform(X)
    m = LGBMRegressor(n_estimators=400, learning_rate=0.01, max_depth=6,
                      subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=-1)
    m.fit(Xfull, y)
    forecast = float(m.predict(sc.transform(X.iloc[-1:]))[0])
    limiar = 0.5 * float(np.std(reais_oos))
    if forecast > limiar:
        sinal = "LONG"
    elif forecast < -limiar:
        sinal = "SHORT"
    else:
        sinal = "NEUTRO"

    # --- Score: direcao prevista PESADA pela confiabilidade (IC) ---
    confiavel = ic_geral >= config.ML_IC_MINIMO
    base = 50.0
    if limiar > 0:
        intensidade = float(np.clip(forecast / (2 * limiar), -1, 1))  # -1..1
    else:
        intensidade = 0.0
    fator_conf = float(np.clip(ic_geral / 0.10, 0, 1)) if ic_geral > 0 else 0.0
    score = float(np.clip(base + intensidade * 40 * (0.4 + 0.6 * fator_conf), 0, 100))

    notas = [
        f"Previsao {h}d: {forecast:+.2%} -> {sinal}",
        f"IC (Spearman, walk-forward): {ic_geral:+.3f} " + ("(util)" if confiavel else "(fraco - sinal pouco confiavel)"),
    ]
    if not np.isnan(acerto_dir):
        notas.append(f"Acerto direcional OOS: {acerto_dir:.0%}")
    if not np.isnan(sharpe):
        notas.append(f"Sharpe liquido da estrategia: {sharpe:.2f}")

    return {
        "ok": True, "score": score, "forecast": forecast, "sinal": sinal,
        "ic": ic_geral, "confiavel": confiavel,
        "acerto_direcional": None if np.isnan(acerto_dir) else round(acerto_dir, 3),
        "sharpe": None if np.isnan(sharpe) else round(sharpe, 2),
        "notas": notas,
    }
