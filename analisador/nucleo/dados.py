# -*- coding: utf-8 -*-
"""
Camada de dados: download de precos (diario + intraday) e fundamentos via yfinance.
Centraliza retentativas anti-throttle e a normalizacao de colunas (pandas 3.x / MultiIndex).
"""
import time
import logging
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

from . import config

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


# =====================================================================================
# OHLC DIARIO (um ticker)
# =====================================================================================
def _achatar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Achata MultiIndex de colunas (yfinance) para colunas simples Open/High/...."""
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        # mantem o nivel que contem Open/High/Low/Close/Volume
        nivel0 = df.columns.get_level_values(0)
        if any(c in ("Open", "High", "Low", "Close", "Volume") for c in nivel0):
            df.columns = df.columns.get_level_values(0)
        else:
            df.columns = df.columns.get_level_values(-1)
    return df


def baixar_diario(ticker: str, periodo: str = None) -> pd.DataFrame | None:
    """6m..5y de candles diarios de UM ticker, OHLCV limpo. None se falhar."""
    periodo = periodo or config.PERIODO_DIARIO
    for tentativa in range(1, config.TENTATIVAS_DOWNLOAD + 1):
        try:
            df = yf.download(
                ticker, period=periodo, interval="1d",
                auto_adjust=True, progress=False, threads=False,
            )
            if df is not None and not df.empty:
                df = _achatar_colunas(df)
                cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
                df = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
                if not df.empty:
                    return df
        except Exception:
            pass
        if tentativa < config.TENTATIVAS_DOWNLOAD:
            time.sleep(config.PAUSA_ANTI_THROTTLE)
    return None


def baixar_intraday(ticker: str) -> pd.Series | None:
    """Serie de fechamento 15m (~1 mes) para o regime intraday. None se falhar."""
    for tentativa in range(1, config.TENTATIVAS_DOWNLOAD + 1):
        try:
            df = yf.download(
                ticker, period=config.PERIODO_INTRADAY,
                interval=config.INTERVALO_INTRADAY,
                auto_adjust=True, progress=False, threads=False,
            )
            if df is not None and not df.empty:
                df = _achatar_colunas(df)
                if "Close" in df.columns:
                    s = pd.to_numeric(df["Close"], errors="coerce").dropna()
                    if len(s):
                        return s
        except Exception:
            pass
        if tentativa < config.TENTATIVAS_DOWNLOAD:
            time.sleep(config.PAUSA_ANTI_THROTTLE)
    return None


def baixar_indice(periodo: str = None) -> pd.Series | None:
    """Fechamento diario do IBOV (^BVSP) para beta/correlacao."""
    df = baixar_diario(config.INDICE_REFERENCIA, periodo)
    if df is None or "Close" not in df.columns:
        return None
    return df["Close"]


# =====================================================================================
# FUNDAMENTOS (um ticker)
# =====================================================================================
def _serie_segura(obj, *chaves):
    """Tenta varias chaves num DataFrame de demonstrativo; retorna a 1a linha existente."""
    if obj is None or not hasattr(obj, "index"):
        return None
    for ch in chaves:
        if ch in obj.index:
            linha = obj.loc[ch].dropna()
            if len(linha):
                return linha
    return None


def buscar_fundamentos(ticker: str) -> dict:
    """
    Coleta um pacote robusto de fundamentos via yfinance:
    .info (multiplos prontos) + demonstrativos (DRE/Balanco/Fluxo) p/ Magic Formula.
    Retorna dict 'cru' (sem julgamento); o scoring fica em fundamentos.py.
    """
    pacote = {"ok": False, "info": {}, "erro": None}
    try:
        emp = yf.Ticker(ticker)
        info = {}
        try:
            info = emp.info or {}
        except Exception:
            info = {}
        pacote["info"] = info

        # Demonstrativos anuais (podem falhar para alguns papeis)
        try:
            dre = emp.financials
        except Exception:
            dre = None
        try:
            balanco = emp.balance_sheet
        except Exception:
            balanco = None
        try:
            fluxo = emp.cashflow
        except Exception:
            fluxo = None

        # --- EBIT (DRE) p/ EV/EBIT (Greenblatt earnings yield) ---
        ebit = _serie_segura(dre, "EBIT", "Operating Income", "Ebit")
        ebit_val = float(ebit.iloc[0]) if ebit is not None else np.nan

        receita = _serie_segura(dre, "Total Revenue", "Operating Revenue")
        lucro = _serie_segura(dre, "Net Income", "Net Income Common Stockholders")

        # CAGR de receita e lucro (crescimento) usando os anos disponiveis
        def _cagr(serie):
            try:
                s = serie.dropna()
                if len(s) < 2:
                    return np.nan
                # demonstrativos vem do mais recente p/ o mais antigo
                recente, antigo = float(s.iloc[0]), float(s.iloc[-1])
                anos = len(s) - 1
                if antigo <= 0 or recente <= 0 or anos <= 0:
                    return np.nan
                return (recente / antigo) ** (1 / anos) - 1
            except Exception:
                return np.nan

        cagr_receita = _cagr(receita) if receita is not None else np.nan
        cagr_lucro = _cagr(lucro) if lucro is not None else np.nan

        # --- Balanco p/ ROIC e saude ---
        ativo_total = _serie_segura(balanco, "Total Assets")
        passivo_circ = _serie_segura(balanco, "Current Liabilities", "Total Current Liabilities")
        ativo_circ = _serie_segura(balanco, "Current Assets", "Total Current Assets")
        patrimonio = _serie_segura(balanco, "Stockholders Equity", "Common Stock Equity",
                                   "Total Stockholder Equity")

        ev = info.get("enterpriseValue", np.nan)
        ev_ebit = (ev / ebit_val) if (ev and ebit_val and ebit_val > 0 and not np.isnan(ev)) else np.nan
        earnings_yield = (ebit_val / ev) if (ev and ebit_val and ev > 0) else np.nan  # Greenblatt

        # ROIC aproximado (Greenblatt ROC): EBIT / (capital de giro liq + ativo fixo)
        roic_proxy = np.nan
        try:
            at = float(ativo_total.iloc[0]) if ativo_total is not None else np.nan
            pc = float(passivo_circ.iloc[0]) if passivo_circ is not None else np.nan
            if not np.isnan(at) and not np.isnan(pc) and not np.isnan(ebit_val):
                capital_investido = at - pc
                if capital_investido > 0:
                    roic_proxy = ebit_val / capital_investido
        except Exception:
            pass

        # Liquidez corrente (Graham: margem de seguranca)
        liq_corrente = np.nan
        try:
            ac = float(ativo_circ.iloc[0]) if ativo_circ is not None else np.nan
            pc = float(passivo_circ.iloc[0]) if passivo_circ is not None else np.nan
            if not np.isnan(ac) and not np.isnan(pc) and pc > 0:
                liq_corrente = ac / pc
        except Exception:
            pass

        pacote["dados"] = {
            "nome": info.get("longName") or info.get("shortName") or ticker,
            "setor": info.get("sector"),
            "industria": info.get("industry"),
            "preco": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "pl": info.get("trailingPE"),
            "pl_forward": info.get("forwardPE"),
            "pvp": info.get("priceToBook"),
            "ps": info.get("priceToSalesTrailing12Months"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "ev_ebit": ev_ebit,
            "earnings_yield": earnings_yield,
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "roic_proxy": roic_proxy,
            "margem_bruta": info.get("grossMargins"),
            "margem_operacional": info.get("operatingMargins"),
            "margem_liquida": info.get("profitMargins"),
            "dividend_yield": info.get("dividendYield"),
            "payout": info.get("payoutRatio"),
            "divida_pl": info.get("debtToEquity"),
            "liquidez_corrente": liq_corrente if not np.isnan(liq_corrente) else info.get("currentRatio"),
            "cobertura_juros": None,
            "fcf": info.get("freeCashflow"),
            "fcf_yield": ((info.get("freeCashflow") / info.get("marketCap"))
                          if info.get("freeCashflow") and info.get("marketCap") else np.nan),
            "cagr_receita": cagr_receita,
            "cagr_lucro": cagr_lucro,
            "beta_info": info.get("beta"),
            "preco_alvo": info.get("targetMeanPrice"),
            "recomendacao": info.get("recommendationKey"),
        }
        pacote["ok"] = True
    except Exception as e:
        pacote["erro"] = str(e)
    return pacote
