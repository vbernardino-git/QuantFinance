# -*- coding: utf-8 -*-
"""
PILAR TECNICO  (Analise Tecnica classica + ANATEC + Modelo 34)
Fontes: Alexander Elder (Trading for a Living), Thomas Bulkowski (Encyclopedia of
Candlestick Charts), John Bollinger, Gerald Appel (MACD), Setup 9.1/MME34 (BR).

Porta fielmente a logica de sinais do seu radar_anatec_ibov.py e adiciona uma
leitura estrutural (tendencia, momentum, bandas) consolidada num score 0-100.
"""
import numpy as np
import pandas as pd
import ta

from . import config


def _indicadores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["O"], df["H"], df["L"], df["C"] = df["Open"], df["High"], df["Low"], df["Close"]
    df["Cor"] = np.where(df["C"] >= df["O"], "Verde", "Vermelho")
    df["Corpo"] = (df["C"] - df["O"]).abs()
    df["Sombra_Sup"] = df["H"] - df[["O", "C"]].max(axis=1)
    df["Sombra_Inf"] = df[["O", "C"]].min(axis=1) - df["L"]

    # Medias / tendencia
    df["EMA9"] = ta.trend.ema_indicator(df["C"], window=9)
    df["EMA21"] = ta.trend.ema_indicator(df["C"], window=21)
    df["EMA50"] = ta.trend.ema_indicator(df["C"], window=50)
    df["MME34"] = ta.trend.ema_indicator(df["C"], window=config.EMA_LONGA)
    df["SMA200"] = df["C"].rolling(200).mean()

    # Momentum / forca
    df["RSI"] = ta.momentum.RSIIndicator(df["C"], window=14).rsi()
    df["Estocastico"] = ta.momentum.stoch(df["H"], df["L"], df["C"], window=14, smooth_window=3)
    macd = ta.trend.MACD(df["C"])
    df["MACD"] = macd.macd()
    df["MACD_sinal"] = macd.macd_signal()
    df["MACD_hist"] = macd.macd_diff()
    df["TRIX"] = ta.trend.trix(df["C"], window=9)
    df["ADX"] = ta.trend.adx(df["H"], df["L"], df["C"], window=14)
    df["DI_mais"] = ta.trend.adx_pos(df["H"], df["L"], df["C"], window=14)
    df["DI_menos"] = ta.trend.adx_neg(df["H"], df["L"], df["C"], window=14)

    # Bollinger (multi-desvio, estilo seu painel quant)
    meio = df["C"].rolling(20).mean()
    desv = df["C"].rolling(20).std()
    df["BB_meio"] = meio
    df["BB_sup2"] = meio + 2 * desv
    df["BB_inf2"] = meio - 2 * desv
    df["BB_pctB"] = (df["C"] - df["BB_inf2"]) / (df["BB_sup2"] - df["BB_inf2"])

    df["Tendencia_Forte"] = np.where(
        (df["C"] > df["MME34"]) & (df["DI_mais"] > df["DI_menos"]), "Alta", "Baixa")
    return df


def _sinal_anatec_m34(df: pd.DataFrame) -> dict:
    """Detecta o padrao de candle/ANATEC no ultimo candle fechado (igual ao radar)."""
    df = df.copy()
    df["Sinal_Compra"] = np.nan
    df["Sinal_Venda"] = np.nan

    for i in range(2, len(df)):
        c_corpo = df["Corpo"].iloc[i]; c_si = df["Sombra_Inf"].iloc[i]; c_ss = df["Sombra_Sup"].iloc[i]
        c_cor = df["Cor"].iloc[i]; c_fech = df["C"].iloc[i]; c_ab = df["O"].iloc[i]
        ant_cor = df["Cor"].iloc[i-1]; ant_ab = df["O"].iloc[i-1]; ant_fe = df["C"].iloc[i-1]
        ant_corpo = df["Corpo"].iloc[i-1]; ant_max = df["H"].iloc[i-1]; ant_min = df["L"].iloc[i-1]

        f_adx = df["ADX"].iloc[i]; f_est = df["Estocastico"].iloc[i]
        f_mme = df["MME34"].iloc[i]; f_tend = df["Tendencia_Forte"].iloc[i-1]
        em_tendencia = f_adx > config.ADX_MINIMO

        martelo = (c_si >= 2*c_corpo) and (c_ss <= c_corpo*0.20) and (c_corpo > 0)
        martelo_inv = (c_ss >= 2*c_corpo) and (c_si <= c_corpo*0.20) and (c_corpo > 0)
        engolfo = (max(c_ab, c_fech) > max(ant_ab, ant_fe)) and (min(c_ab, c_fech) < min(ant_ab, ant_fe))
        dark = (ant_cor == "Verde" and c_cor == "Vermelho") and (c_ab > ant_max) and (c_fech < (ant_fe - 0.5*ant_corpo))
        piercing = (ant_cor == "Vermelho" and c_cor == "Verde") and (c_ab < ant_min) and (c_fech > (ant_fe + 0.5*ant_corpo))

        if em_tendencia:
            if f_tend == "Alta" or f_est < 30:
                if martelo and (f_est < 30 or c_fech <= f_mme*1.005):
                    df.iat[i, df.columns.get_loc("Sinal_Compra")] = 1
                elif piercing:
                    df.iat[i, df.columns.get_loc("Sinal_Compra")] = 1
                elif engolfo and c_cor == "Verde" and (f_est < 30 or c_fech <= f_mme*1.005):
                    df.iat[i, df.columns.get_loc("Sinal_Compra")] = 1
                elif martelo_inv and f_est < 25:
                    df.iat[i, df.columns.get_loc("Sinal_Compra")] = 1
            if f_tend == "Baixa" or f_est > 70:
                if martelo and (f_est > 70 or c_fech >= f_mme*0.995):
                    df.iat[i, df.columns.get_loc("Sinal_Venda")] = 1
                elif dark:
                    df.iat[i, df.columns.get_loc("Sinal_Venda")] = 1
                elif engolfo and c_cor == "Vermelho" and (f_est > 70 or c_fech >= f_mme*0.995):
                    df.iat[i, df.columns.get_loc("Sinal_Venda")] = 1

    idx = -1
    tipo, padrao = None, None
    if not pd.isna(df["Sinal_Compra"].iloc[idx]):
        tipo = "COMPRA"
        if df["Sombra_Inf"].iloc[idx] >= 2*df["Corpo"].iloc[idx]:
            padrao = "Martelo (fundo)"
        elif df["Sombra_Sup"].iloc[idx] >= 2*df["Corpo"].iloc[idx]:
            padrao = "Martelo invertido"
        elif df["Cor"].iloc[idx] == "Verde" and df["Corpo"].iloc[idx] > df["Corpo"].iloc[idx-1]:
            padrao = "Engolfo de alta"
        else:
            padrao = "Piercing pattern"
    elif not pd.isna(df["Sinal_Venda"].iloc[idx]):
        tipo = "VENDA"
        if df["Sombra_Inf"].iloc[idx] >= 2*df["Corpo"].iloc[idx]:
            padrao = "Enforcado (topo)"
        elif df["Cor"].iloc[idx] == "Vermelho" and df["Corpo"].iloc[idx] > df["Corpo"].iloc[idx-1]:
            padrao = "Engolfo de baixa"
        else:
            padrao = "Dark cloud (nuvem negra)"
    return {"tipo": tipo, "padrao": padrao}


def analisar(df_diario: pd.DataFrame) -> dict:
    """
    Retorna leitura tecnica + sub-score 0-100.
    Score combina: estrutura de tendencia (EMAs/MME34/SMA200), forca (ADX),
    momentum (RSI/MACD/Estocastico), posicao em Bollinger e o gatilho ANATEC+M34.
    """
    if df_diario is None or len(df_diario) < 60:
        return {"ok": False, "score": 50.0, "erro": "historico insuficiente"}

    df = _indicadores(df_diario)
    u = df.iloc[-1]
    sinal = _sinal_anatec_m34(df)

    preco = float(u["C"])
    pontos = 50.0  # neutro
    notas = []

    # --- Estrutura de tendencia (ate +-22) ---
    if not np.isnan(u["EMA9"]) and not np.isnan(u["EMA21"]) and not np.isnan(u["EMA50"]):
        if u["EMA9"] > u["EMA21"] > u["EMA50"]:
            pontos += 10; notas.append("EMAs alinhadas em ALTA (9>21>50)")
        elif u["EMA9"] < u["EMA21"] < u["EMA50"]:
            pontos -= 10; notas.append("EMAs alinhadas em BAIXA (9<21<50)")
    if not np.isnan(u["MME34"]):
        if preco > u["MME34"]:
            pontos += 6; notas.append("Preco acima da MME34 (Modelo 34: comprador)")
        else:
            pontos -= 6; notas.append("Preco abaixo da MME34 (Modelo 34: vendedor)")
    if not np.isnan(u["SMA200"]):
        if preco > u["SMA200"]:
            pontos += 6; notas.append("Acima da media de 200 (tendencia primaria de alta)")
        else:
            pontos -= 6; notas.append("Abaixo da media de 200 (tendencia primaria de baixa)")

    # --- Forca direcional (ADX/DI) ---
    if not np.isnan(u["ADX"]):
        if u["ADX"] > config.ADX_MINIMO:
            if u["DI_mais"] > u["DI_menos"]:
                pontos += 5; notas.append(f"ADX {u['ADX']:.0f} forte com DI+ dominante")
            else:
                pontos -= 5; notas.append(f"ADX {u['ADX']:.0f} forte com DI- dominante")
        else:
            notas.append(f"ADX {u['ADX']:.0f} fraco (mercado lateral)")

    # --- Momentum (RSI/MACD/Estocastico) ---
    rsi = u["RSI"]
    if not np.isnan(rsi):
        if rsi < config.RSI_SOBREVENDA:
            pontos += 5; notas.append(f"RSI {rsi:.0f} sobrevendido (reversao potencial)")
        elif rsi > config.RSI_SOBRECOMPRA:
            pontos -= 5; notas.append(f"RSI {rsi:.0f} sobrecomprado")
        elif rsi > 50:
            pontos += 2
        else:
            pontos -= 2
    if not np.isnan(u["MACD_hist"]):
        if u["MACD_hist"] > 0:
            pontos += 3; notas.append("MACD positivo (momentum comprador)")
        else:
            pontos -= 3; notas.append("MACD negativo (momentum vendedor)")

    # --- Bollinger (%B) ---
    if not np.isnan(u["BB_pctB"]):
        if u["BB_pctB"] < 0.05:
            pontos += 3; notas.append("Colado na banda inferior (esticado p/ baixo)")
        elif u["BB_pctB"] > 0.95:
            pontos -= 3; notas.append("Colado na banda superior (esticado p/ cima)")

    # --- Gatilho ANATEC + Modelo 34 (peso alto: e o seu setup proprio) ---
    if sinal["tipo"] == "COMPRA":
        pontos += 12; notas.append(f"SINAL ANATEC+M34 de COMPRA: {sinal['padrao']}")
    elif sinal["tipo"] == "VENDA":
        pontos -= 12; notas.append(f"SINAL ANATEC+M34 de VENDA: {sinal['padrao']}")

    score = float(np.clip(pontos, 0, 100))
    return {
        "ok": True,
        "score": score,
        "preco": round(preco, 2),
        "rsi": None if np.isnan(rsi) else round(float(rsi), 1),
        "adx": None if np.isnan(u["ADX"]) else round(float(u["ADX"]), 1),
        "mme34": None if np.isnan(u["MME34"]) else round(float(u["MME34"]), 2),
        "sma200": None if np.isnan(u["SMA200"]) else round(float(u["SMA200"]), 2),
        "macd_hist": None if np.isnan(u["MACD_hist"]) else round(float(u["MACD_hist"]), 3),
        "estocastico": None if np.isnan(u["Estocastico"]) else round(float(u["Estocastico"]), 1),
        "bb_pctB": None if np.isnan(u["BB_pctB"]) else round(float(u["BB_pctB"]), 2),
        "sinal_anatec": sinal,
        "tendencia": str(u["Tendencia_Forte"]),
        "notas": notas,
    }
