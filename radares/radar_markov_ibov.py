# -*- coding: utf-8 -*-
"""
=====================================================================================
 RADAR MARKOV (Mudanca de Regime)  |  Scanner IBOV -> Telegram
=====================================================================================
 Roda o dia inteiro, quieto, no terminal. A cada 5 MINUTOS varre as acoes do IBOV
 (+ TOTS3 e CPLE3) usando a MESMA logica de mudanca de regime de Markov calibrada
 no notebook "06. Markov Regression" (candle de 15 min, prob. FILTRADA, sem
 look-ahead, com confirmacao anti-ruido). Quando um ativo MUDA DE DIRECAO
 (entra no regime de ALTA = compra, ou no regime de BAIXA = venda), o alerta e
 enviado para o Telegram.

 Autonomo: nao depende dos seus outros arquivos e nao altera nenhum deles.
 Credenciais do Telegram via variaveis de ambiente TELEGRAM_TOKEN / TELEGRAM_CHAT_ID.

   python "radar_markov_ibov.py"            -> monitoramento continuo (a cada 5 min)
   python "radar_markov_ibov.py" --once     -> uma varredura so e encerra

 Para parar (modo loop): feche a janela ou pressione Ctrl+C.
=====================================================================================
"""

import os
import sys
import time
import csv
import warnings
import logging
from datetime import datetime, time as dtime

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

# Silencia o ruido do yfinance e do statsmodels.
warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# =====================================================================================
# CONFIGURACOES
# =====================================================================================

# --- Telegram (variaveis de ambiente; sem elas o radar so imprime) ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- Tempo entre varreduras (segundos) ---
INTERVALO_CHECAGEM = 5 * 60          # o sistema analisa a cada 5 minutos

# --- Dados / modelo de Markov (mesmos parametros do notebook calibrado) ---
INTERVALO_CANDLE = "15m"             # tempo grafico
PERIODO          = "1mo"             # historico p/ estabilizar os 2 regimes
LIMIAR           = 0.85              # confianca minima do regime p/ emitir aviso
CONFIRMA         = 2                 # nº de velas seguidas no regime p/ confirmar (anti-ruido)
MIN_OBS          = 120              # minimo de candles p/ tentar ajustar o modelo

# --- Janela de funcionamento do mercado (horario de Brasilia) ---
RESPEITAR_HORARIO_PREGAO = True
PREGAO_INICIO = dtime(10, 0)
PREGAO_FIM = dtime(18, 0)

# --- Arquivo de log (registro do dia) gravado na mesma pasta do executavel ---
ARQUIVO_LOG = "radar_markov_log.csv"

# =====================================================================================
# UNIVERSO DE ATIVOS: IBOV + TOTS3 + CPLE3
# =====================================================================================
IBOV = [
    "ALOS3", "ABEV3", "ASAI3", "AURE3", "AZUL4", "AZZA3", "B3SA3", "BBSE3",
    "BBDC3", "BBDC4", "BRAP4", "BBAS3", "BRKM5", "BRAV3", "BRFS3", "BPAC11",
    "CXSE3", "CRFB3", "CCRO3", "CMIG4", "COGN3", "CPLE6", "CSAN3", "CPFE3",
    "CMIN3", "CVCB3", "CYRE3", "DXCO3", "ELET3", "ELET6", "EMBR3", "ENGI11",
    "ENEV3", "EGIE3", "EQTL3", "EZTC3", "FLRY3", "GGBR4", "GOAU4", "NTCO3",
    "HAPV3", "HYPE3", "IGTI11", "IRBR3", "ISAE4", "ITSA4", "ITUB4", "JBSS3",
    "KLBN11", "RENT3", "LREN3", "LWSA3", "MGLU3", "MRFG3", "BEEF3", "MRVE3",
    "MULT3", "PCAR3", "PETR3", "PETR4", "RECV3", "PRIO3", "PETZ3", "RADL3",
    "RAIZ4", "RDOR3", "RAIL3", "SBSP3", "SANB11", "STBP3", "SMTO3", "CSNA3",
    "SLCE3", "SUZB3", "TAEE11", "VIVT3", "TIMS3", "TOTS3", "UGPA3", "USIM5",
    "VALE3", "VAMO3", "VBBR3", "VIVA3", "WEGE3", "YDUQ3",
]
EXTRAS = ["TOTS3", "CPLE3"]


def montar_universo():
    universo = list(IBOV)
    for t in EXTRAS:
        if t not in universo:
            universo.append(t)
    return [t + ".SA" for t in universo]


ATIVOS = montar_universo()

# Memoria: ultimo sinal unico ja enviado por ativo (evita alerta repetido)
ultimos_sinais_detectados = {ticker: None for ticker in ATIVOS}


# =====================================================================================
# TELEGRAM
# =====================================================================================
def enviar_telegram(msg):
    """Envia mensagem ao Telegram. Falha de rede nao derruba o radar."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=20)
    except Exception as e:
        log_console(f"[Telegram] Falha ao enviar: {e}")


# =====================================================================================
# LOG
# =====================================================================================
def caminho_log():
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, ARQUIVO_LOG)


def log_console(texto):
    print(f"{datetime.now().strftime('%H:%M:%S')} | {texto}", flush=True)


def gravar_log_csv(alerta):
    caminho = caminho_log()
    existe = os.path.isfile(caminho)
    try:
        with open(caminho, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            if not existe:
                w.writerow(["Hora_Alerta", "Ativo", "Direcao", "Prob_Regime", "Preco", "Candle"])
            w.writerow([
                alerta["Hora_Alerta"], alerta["Ativo"], alerta["Direcao"],
                alerta["Prob"], alerta["Preco"], alerta["Candle"],
            ])
    except Exception as e:
        log_console(f"[Log] Falha ao gravar CSV: {e}")


# =====================================================================================
# DOWNLOAD EM LOTE (anti-throttle do Yahoo)
# =====================================================================================
def baixar_lote(tickers, tentativas=3):
    """Baixa candles de 15m de TODOS os tickers numa unica chamada em lote."""
    for tentativa in range(1, tentativas + 1):
        try:
            dados = yf.download(
                tickers, period=PERIODO, interval=INTERVALO_CANDLE,
                group_by="ticker", progress=False, threads=True,
                auto_adjust=True,
            )
            if dados is not None and not dados.empty:
                return dados
        except Exception as e:
            log_console(f"[Download lote] tentativa {tentativa} falhou: {e}")
        if tentativa < tentativas:
            time.sleep(15)  # respira antes de tentar de novo (anti-throttle)
    return None


def extrair_close(dados, ticker):
    """Extrai a serie de fechamento (Close) de um ticker a partir do lote."""
    if dados is None or dados.empty:
        return None
    try:
        if isinstance(dados.columns, pd.MultiIndex):
            if ticker not in dados.columns.get_level_values(0):
                return None
            serie = dados[ticker]["Close"]
        else:
            serie = dados["Close"]
    except Exception:
        return None
    serie = pd.to_numeric(serie, errors="coerce").dropna()
    return serie if len(serie) else None


# =====================================================================================
# NUCLEO DA ANALISE  (MUDANCA DE REGIME DE MARKOV) -- portado do notebook 06.
# =====================================================================================
def analisar_markov(ticker, serie_close):
    """
    Retorna dict do alerta se o ULTIMO candle confirmou uma MUDANCA DE REGIME
    (entrada no regime de alta = compra, ou no de baixa = venda); senao, None.
    """
    if serie_close is None or len(serie_close) < MIN_OBS:
        return None

    returns = serie_close.pct_change().dropna()
    if len(returns) < MIN_OBS:
        return None

    # --- Modelo de Markov de 2 regimes (media E variancia mudam entre regimes) ---
    try:
        res = MarkovRegression(
            returns, k_regimes=2, switching_trend=True, switching_variance=True
        ).fit(disp=False)
    except Exception:
        return None  # nao convergiu / serie degenerada -> pula

    # --- Probabilidade FILTRADA (so passado/presente; sem look-ahead) ---
    prob = res.filtered_marginal_probabilities
    regime = prob.values.argmax(axis=1)

    # --- Descobre QUAL regime e o de ALTA pela media de retorno (indice 0/1 varia) ---
    medias = pd.Series(returns.values).groupby(regime).mean()
    if len(medias) < 2:
        return None
    regime_alta = int(medias.idxmax())
    prob_alta = prob.iloc[:, regime_alta]

    if len(prob_alta) < CONFIRMA + 1:
        return None

    # --- Confirmacao: CONFIRMA velas seguidas no regime ---
    acima = prob_alta > LIMIAR
    abaixo = prob_alta < (1 - LIMIAR)
    conf_alta = acima.rolling(CONFIRMA).sum() == CONFIRMA
    conf_baixa = abaixo.rolling(CONFIRMA).sum() == CONFIRMA

    # --- Evento no ULTIMO candle = a confirmacao ACABOU de passar a valer ---
    virou_alta = bool(conf_alta.iloc[-1]) and not bool(conf_alta.iloc[-2])
    virou_baixa = bool(conf_baixa.iloc[-1]) and not bool(conf_baixa.iloc[-2])

    if not (virou_alta or virou_baixa):
        return None

    direcao = "ALTA (Compra)" if virou_alta else "BAIXA (Venda)"
    candle_ts = serie_close.index[-1]
    return {
        "Ativo": ticker.replace(".SA", ""),
        "Direcao": direcao,
        "Compra": virou_alta,
        "Prob": round(float(prob_alta.iloc[-1]) if virou_alta
                       else float(1 - prob_alta.iloc[-1]), 2),
        "Preco": round(float(serie_close.iloc[-1]), 2),
        "Candle": candle_ts.strftime("%Y-%m-%d %H:%M"),
        "CandleId": candle_ts.isoformat(),
    }


# =====================================================================================
# CONTROLE DE PREGAO
# =====================================================================================
def mercado_aberto():
    if not RESPEITAR_HORARIO_PREGAO:
        return True
    agora = datetime.now()
    if agora.weekday() >= 5:  # 5 = sabado, 6 = domingo
        return False
    return PREGAO_INICIO <= agora.time() <= PREGAO_FIM


# =====================================================================================
# VARREDURA
# =====================================================================================
def varrer_mercado():
    encontrados = 0
    dados = baixar_lote(ATIVOS)
    if dados is None:
        log_console("[Aviso] Falha geral no download em lote. Tentarei na proxima varredura.")
        return 0

    for ticker in ATIVOS:
        try:
            serie = extrair_close(dados, ticker)
            if serie is None:
                continue  # sem dados (delistado/iliquido) -> pula silenciosamente
            alerta = analisar_markov(ticker, serie)
            if not alerta:
                continue

            # Dedup: nao reenvia o MESMO sinal (mesmo ativo+candle+direcao)
            tipo = "COMPRA" if alerta["Compra"] else "VENDA"
            id_sinal_unico = f"{alerta['Ativo']}_{alerta['CandleId']}_{tipo}"
            if ultimos_sinais_detectados.get(ticker) == id_sinal_unico:
                continue

            ultimos_sinais_detectados[ticker] = id_sinal_unico
            encontrados += 1

            hora = datetime.now().strftime("%H:%M:%S")
            alerta["Hora_Alerta"] = hora

            emoji = "🟢" if alerta["Compra"] else "🔴"
            msg = (
                f"{emoji} MUDANCA DE REGIME (Markov)\n\n"
                f"Ativo: {alerta['Ativo']}\n"
                f"Direcao: {alerta['Direcao']}\n"
                f"Confianca do regime: {alerta['Prob']:.0%}\n"
                f"Preco: R$ {alerta['Preco']:.2f}\n"
                f"Candle (15m): {alerta['Candle']}\n"
                f"Detectado: {hora}"
            )
            enviar_telegram(msg)
            gravar_log_csv(alerta)
            log_console(
                f"ALERTA {tipo} -> {alerta['Ativo']} | regime {alerta['Prob']:.0%} | R$ {alerta['Preco']:.2f}"
            )

        except Exception as e:
            log_console(f"[{ticker}] erro: {e}")
    return encontrados


# =====================================================================================
# MODOS DE EXECUCAO
# =====================================================================================
def executar_uma_vez():
    data_ref = datetime.now().strftime("%d/%m/%Y %H:%M")
    log_console("=" * 70)
    log_console(f"RADAR MARKOV | VARREDURA UNICA | {data_ref}")
    log_console(f"Ativos: {len(ATIVOS)} (IBOV + TOTS3/CPLE3) | candle {INTERVALO_CANDLE}")
    log_console("=" * 70)
    achou = varrer_mercado()
    log_console(f"Varredura concluida. Mudancas de regime: {achou}")
    if achou == 0:
        enviar_telegram(
            f"📡 Radar Markov ({data_ref}).\n"
            f"Varri {len(ATIVOS)} ativos (candle {INTERVALO_CANDLE}).\n"
            f"Nenhuma mudanca de regime no ultimo candle."
        )
    else:
        enviar_telegram(f"✅ Radar Markov ({data_ref}): {achou} mudanca(s) de regime acima.")


def executar_em_loop():
    log_console("=" * 70)
    log_console("RADAR MARKOV iniciado (modo LOOP).")
    log_console(f"Ativos monitorados: {len(ATIVOS)} (IBOV + TOTS3/CPLE3)")
    log_console(f"Candle: {INTERVALO_CANDLE} | Varredura a cada {INTERVALO_CHECAGEM // 60} min")
    log_console(f"Log CSV: {caminho_log()}")
    log_console("=" * 70)
    enviar_telegram(
        f"🤖 Radar Markov ligado.\n"
        f"Monitorando {len(ATIVOS)} ativos do IBOV (candle {INTERVALO_CANDLE}), "
        f"analisando a cada {INTERVALO_CHECAGEM // 60} min.\n"
        f"Avisarei aqui cada vez que um ativo mudar de direcao (regime)."
    )

    try:
        while True:
            if mercado_aberto() or not RESPEITAR_HORARIO_PREGAO:
                inicio = time.time()
                log_console("Varrendo mercado...")
                achou = varrer_mercado()
                dur = time.time() - inicio
                log_console(f"Varredura concluida em {dur:.0f}s. Novos alertas: {achou}")
                # Desconta o tempo gasto para manter o ritmo de 5 min.
                time.sleep(max(30, INTERVALO_CHECAGEM - dur))
            else:
                time.sleep(10 * 60)  # fora do pregao: dorme em ciclos curtos
    except KeyboardInterrupt:
        log_console("Radar finalizado pelo usuario.")
        enviar_telegram("🛑 Radar Markov desligado.")


def main():
    args = [a.lower() for a in sys.argv[1:]]
    if "--once" in args or "-1" in args or "once" in args:
        executar_uma_vez()
    else:
        executar_em_loop()


if __name__ == "__main__":
    main()
