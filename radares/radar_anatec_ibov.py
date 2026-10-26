# -*- coding: utf-8 -*-
"""
=====================================================================================
 RADAR ANATEC + MODELO 34  |  Scanner IBOV -> Telegram
=====================================================================================
 Roda o dia inteiro, quieto, no terminal. Varre TODAS as empresas do IBOV
 (+ TOTS3 e CPLE3 caso nao estejam na lista) aplicando a mesma logica de Analise
 Tecnica do notebook "01. ANATEC.ipynb" (ANATEC + MODELO 34). Quando um ativo
 da sinal de COMPRA ou VENDA no ultimo candle diario fechado, o alerta e enviado
 para o Telegram.

 Este arquivo e autonomo: nao depende dos seus arquivos originais e nao altera
 nenhum deles. Telegram: variaveis de ambiente TELEGRAM_TOKEN e TELEGRAM_CHAT_ID.

 Para parar: feche a janela ou pressione Ctrl+C.
=====================================================================================
"""

import os
import sys
import time
import csv
import logging
from datetime import datetime, time as dtime

import numpy as np
import pandas as pd
import requests
import yfinance as yf
import ta

# Silencia o ruido do yfinance (mensagens "possibly delisted" / "Failed download").
# Tickers que realmente falharem sao apenas pulados; o radar segue rodando quieto.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# =====================================================================================
# CONFIGURACOES
# =====================================================================================

# --- Telegram (variaveis de ambiente; sem elas o radar so imprime) ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- Tempo entre varreduras completas (segundos) ---
# Os candles sao DIARIOS, entao nao adianta varrer muito rapido. 15 min e suficiente.
INTERVALO_CHECAGEM = 15 * 60

# --- Janela de funcionamento do mercado (horario de Brasilia) ---
# Fora desse horario (e em fins de semana) o radar dorme para economizar requisicoes.
RESPEITAR_HORARIO_PREGAO = True
PREGAO_INICIO = dtime(10, 0)
PREGAO_FIM = dtime(18, 0)

# --- Filtro operacional (igual ao notebook): so opera mercado direcional ---
ADX_MINIMO = 22

# --- Arquivo de log (registro do dia) gravado na mesma pasta do executavel ---
ARQUIVO_LOG = "radar_anatec_log.csv"

# =====================================================================================
# UNIVERSO DE ATIVOS: IBOV + TOTS3 + CPLE3
# =====================================================================================
# Composicao teorica do IBOV (carteira vigente). TOTS3 e CPLE3 sao garantidos
# pela uniao logo abaixo, caso saiam/entrem da carteira no futuro.
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

# Garante TOTS3 e CPLE3 mesmo que nao estejam na lista do IBOV.
EXTRAS = ["TOTS3", "CPLE3"]

def montar_universo():
    universo = list(IBOV)
    for t in EXTRAS:
        if t not in universo:
            universo.append(t)
    # Sufixo .SA exigido pelo Yahoo Finance / yfinance
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
                w.writerow(["Hora_Alerta", "Ativo", "Tipo", "Sinal", "Preco", "Data_Candle"])
            w.writerow([
                alerta["Hora_Alerta"], alerta["Ativo"], alerta["Tipo"],
                alerta["Sinal"], alerta["Preco"], alerta["Data_Candle"],
            ])
    except Exception as e:
        log_console(f"[Log] Falha ao gravar CSV: {e}")


# =====================================================================================
# NUCLEO DA ANALISE  (ANATEC + MODELO 34) -- portado fielmente do notebook,
# sem a parte de plotagem grafica.
# =====================================================================================
def baixar_lote(tickers, tentativas=3):
    """
    Baixa 6 meses de candles diarios de TODOS os tickers numa unica chamada
    em lote (threads). Isso evita o bloqueio/throttle do Yahoo que ocorre ao
    baixar 87 ativos um a um (causa dos falsos "possibly delisted").
    Retorna um DataFrame com MultiIndex de colunas (ticker, campo).
    """
    for tentativa in range(1, tentativas + 1):
        try:
            dados = yf.download(
                tickers, period="6mo", interval="1d",
                group_by="ticker", progress=False, threads=True,
                auto_adjust=False,
            )
            if dados is not None and not dados.empty:
                return dados
        except Exception as e:
            log_console(f"[Download lote] tentativa {tentativa} falhou: {e}")
        if tentativa < tentativas:
            time.sleep(15)  # respira antes de tentar de novo (anti-throttle)
    return None


def extrair_df_do_lote(dados, ticker):
    """Extrai o sub-DataFrame OHLC de um ticker a partir do resultado em lote."""
    if dados is None or dados.empty:
        return None
    if isinstance(dados.columns, pd.MultiIndex):
        nivel0 = dados.columns.get_level_values(0)
        if ticker not in nivel0:
            return None
        df = dados[ticker].copy()
    else:
        df = dados.copy()
    if df is None or df.empty:
        return None
    # Garante as colunas OHLC esperadas
    for col in ("Open", "High", "Low", "Close"):
        if col not in df.columns:
            return None
    return df


def analisar_df(ticker, df):
    """Retorna dict do alerta no ultimo candle fechado, ou None se nao houver sinal."""
    if df is None or df.empty:
        return None

    df = df[(df['Open'] > 0) & (df['High'] > 0) & (df['Low'] > 0) & (df['Close'] > 0)].dropna()
    if len(df) < 50:
        return None

    # --- VARIAVEIS ESTRUTURAIS DO CANDLE (ANATEC) ---
    df['O'] = df['Open']
    df['H'] = df['High']
    df['L'] = df['Low']
    df['C'] = df['Close']
    df['Cor'] = np.where(df['C'] >= df['O'], 'Verde', 'Vermelho')
    df['Corpo'] = (df['C'] - df['O']).abs()
    df['Sombra_Sup'] = df['H'] - df[['O', 'C']].max(axis=1)
    df['Sombra_Inf'] = df[['O', 'C']].min(axis=1) - df['L']

    # --- INDICADORES DO MODELO 34 E ANATEC ---
    df['MME34'] = ta.trend.ema_indicator(df['C'], window=34)
    df['Estocastico'] = ta.momentum.stoch(df['H'], df['L'], df['C'], window=14, smooth_window=3)
    df['TRIX'] = ta.trend.trix(df['C'], window=9)
    df['ADX'] = ta.trend.adx(df['H'], df['L'], df['C'], window=14)
    df['DI_mais'] = ta.trend.adx_pos(df['H'], df['L'], df['C'], window=14)
    df['DI_menos'] = ta.trend.adx_neg(df['H'], df['L'], df['C'], window=14)

    df['Tendencia_Forte'] = np.where(
        (df['C'] > df['MME34']) & (df['DI_mais'] > df['DI_menos']), 'Alta', 'Baixa')

    df['Sinal_Compra_Plot'] = np.nan
    df['Sinal_Venda_Plot'] = np.nan

    # --- LOGICA DE SINAIS (igual ao notebook) ---
    for i in range(2, len(df)):
        c_corpo = df['Corpo'].iloc[i]
        c_sombra_inf = df['Sombra_Inf'].iloc[i]
        c_sombra_sup = df['Sombra_Sup'].iloc[i]
        c_cor = df['Cor'].iloc[i]
        c_fechamento = df['C'].iloc[i]
        c_abertura = df['O'].iloc[i]
        c_maxima = df['H'].iloc[i]
        c_minima = df['L'].iloc[i]

        ant_corpo = df['Corpo'].iloc[i-1]
        ant_cor = df['Cor'].iloc[i-1]
        ant_abertura = df['O'].iloc[i-1]
        ant_fechamento = df['C'].iloc[i-1]
        ant_maxima = df['H'].iloc[i-1]
        ant_minima = df['L'].iloc[i-1]

        f_adx = df['ADX'].iloc[i]
        f_estocastico = df['Estocastico'].iloc[i]
        f_mme34 = df['MME34'].iloc[i]
        f_tendencia = df['Tendencia_Forte'].iloc[i-1]

        mercado_em_tendencia = f_adx > ADX_MINIMO

        eh_martelo_ou_enforcado = (c_sombra_inf >= 2 * c_corpo) and (c_sombra_sup <= c_corpo * 0.20) and (c_corpo > 0)
        eh_martelo_invertido = (c_sombra_sup >= 2 * c_corpo) and (c_sombra_inf <= c_corpo * 0.20) and (c_corpo > 0)
        eh_engolfo = (max(c_abertura, c_fechamento) > max(ant_abertura, ant_fechamento)) and \
                     (min(c_abertura, c_fechamento) < min(ant_abertura, ant_fechamento))
        eh_dark_cloud = (ant_cor == 'Verde' and c_cor == 'Vermelho') and \
                        (c_abertura > ant_maxima) and (c_fechamento < (ant_fechamento - 0.5 * ant_corpo))
        eh_piercing = (ant_cor == 'Vermelho' and c_cor == 'Verde') and \
                      (c_abertura < ant_minima) and (c_fechamento > (ant_fechamento + 0.5 * ant_corpo))

        if mercado_em_tendencia:
            # --- GATILHOS DE COMPRA ---
            if f_tendencia == 'Alta' or f_estocastico < 30:
                if eh_martelo_ou_enforcado and (f_estocastico < 30 or c_fechamento <= f_mme34 * 1.005):
                    df.at[df.index[i], 'Sinal_Compra_Plot'] = c_minima * 0.992
                elif eh_piercing:
                    df.at[df.index[i], 'Sinal_Compra_Plot'] = c_minima * 0.992
                elif eh_engolfo and c_cor == 'Verde' and (f_estocastico < 30 or c_fechamento <= f_mme34 * 1.005):
                    df.at[df.index[i], 'Sinal_Compra_Plot'] = c_minima * 0.992
                elif eh_martelo_invertido and f_estocastico < 25:
                    df.at[df.index[i], 'Sinal_Compra_Plot'] = c_minima * 0.992

            # --- GATILHOS DE VENDA ---
            if f_tendencia == 'Baixa' or f_estocastico > 70:
                if eh_martelo_ou_enforcado and (f_estocastico > 70 or c_fechamento >= f_mme34 * 0.995):
                    df.at[df.index[i], 'Sinal_Venda_Plot'] = c_maxima * 1.008
                elif eh_dark_cloud:
                    df.at[df.index[i], 'Sinal_Venda_Plot'] = c_maxima * 1.008
                elif eh_engolfo and c_cor == 'Vermelho' and (f_estocastico > 70 or c_fechamento >= f_mme34 * 0.995):
                    df.at[df.index[i], 'Sinal_Venda_Plot'] = c_maxima * 1.008

    # --- CAPTURA DO ALERTA NO ULTIMO CANDLE FECHADO ---
    idx = -1
    data_candle = df.index[idx].strftime("%Y-%m-%d")
    sinal_encontrado = None
    tipo_operacao = None

    if not pd.isna(df['Sinal_Compra_Plot'].iloc[idx]):
        tipo_operacao = "COMPRA"
        if (df['Sombra_Inf'].iloc[idx] >= 2 * df['Corpo'].iloc[idx]):
            sinal_encontrado = "Martelo (Fundo) [M34]"
        elif (df['Sombra_Sup'].iloc[idx] >= 2 * df['Corpo'].iloc[idx]):
            sinal_encontrado = "Martelo Invertido [M34]"
        elif ("Verde" in df['Cor'].iloc[idx] and df['Corpo'].iloc[idx] > df['Corpo'].iloc[idx-1]):
            sinal_encontrado = "Engolfo de Alta [M34]"
        else:
            sinal_encontrado = "Piercing Pattern [M34]"

    elif not pd.isna(df['Sinal_Venda_Plot'].iloc[idx]):
        tipo_operacao = "VENDA"
        if (df['Sombra_Inf'].iloc[idx] >= 2 * df['Corpo'].iloc[idx]):
            sinal_encontrado = "Enforcado (Topo) [M34]"
        elif ("Vermelho" in df['Cor'].iloc[idx] and df['Corpo'].iloc[idx] > df['Corpo'].iloc[idx-1]):
            sinal_encontrado = "Engolfo de Baixa [M34]"
        else:
            sinal_encontrado = "Dark Cloud (Nuvem Negra) [M34]"

    if not (sinal_encontrado and tipo_operacao):
        return None

    return {
        "Ativo": ticker,
        "Tipo": tipo_operacao,
        "Sinal": sinal_encontrado,
        "Preco": round(float(df['C'].iloc[idx]), 2),
        "Data_Candle": data_candle,
        "ADX": round(float(df['ADX'].iloc[idx]), 1),
        "MME34": round(float(df['MME34'].iloc[idx]), 2),
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
# LOOP PRINCIPAL
# =====================================================================================
def varrer_mercado():
    encontrados = 0
    dados = baixar_lote(ATIVOS)
    if dados is None:
        log_console("[Aviso] Falha geral no download em lote. Tentarei na proxima varredura.")
        return 0

    for ticker in ATIVOS:
        try:
            df = extrair_df_do_lote(dados, ticker)
            if df is None:
                continue  # ticker sem dados (delistado/renomeado) -> pula silenciosamente
            alerta = analisar_df(ticker, df)
            if not alerta:
                continue

            id_sinal_unico = f"{ticker}_{alerta['Data_Candle']}_{alerta['Tipo']}"
            if ultimos_sinais_detectados.get(ticker) == id_sinal_unico:
                continue  # ja avisado

            ultimos_sinais_detectados[ticker] = id_sinal_unico
            encontrados += 1

            hora = datetime.now().strftime("%H:%M:%S")
            alerta["Hora_Alerta"] = hora

            emoji = "🟢" if alerta["Tipo"] == "COMPRA" else "🔴"
            msg = (
                f"{emoji} SINAL DE {alerta['Tipo']}  |  ANATEC + MODELO 34\n\n"
                f"Ativo: {ticker}\n"
                f"Padrao: {alerta['Sinal']}\n"
                f"Preco: R$ {alerta['Preco']:.2f}\n"
                f"ADX: {alerta['ADX']}  |  MME34: {alerta['MME34']}\n"
                f"Candle: {alerta['Data_Candle']}\n"
                f"Detectado: {hora}"
            )
            enviar_telegram(msg)
            gravar_log_csv(alerta)
            log_console(f"ALERTA {alerta['Tipo']} -> {ticker} | {alerta['Sinal']} | R$ {alerta['Preco']:.2f}")

        except Exception as e:
            log_console(f"[{ticker}] erro: {e}")
    return encontrados


def executar_uma_vez():
    """
    Modo VARREDURA UNICA (--once): roda uma vez, analisa o ultimo candle DIARIO
    FECHADO de cada ativo, envia os sinais e encerra. Ideal para rodar de manha
    (ex: 8h30, agendado), quando o candle do dia anterior ja esta consolidado e
    voce recebe os sinais antes da abertura do pregao.
    """
    data_ref = datetime.now().strftime("%d/%m/%Y %H:%M")
    log_console("=" * 70)
    log_console(f"RADAR ANATEC + MODELO 34 | VARREDURA UNICA | {data_ref}")
    log_console(f"Ativos: {len(ATIVOS)} (IBOV + TOTS3/CPLE3)")
    log_console("=" * 70)
    log_console("Varrendo mercado (candle diario fechado)...")

    achou = varrer_mercado()

    log_console(f"Varredura concluida. Sinais do dia: {achou}")
    # Resumo diario no Telegram (confirma que rodou, mesmo sem sinal).
    if achou == 0:
        enviar_telegram(
            f"☀️ Bom dia! Radar ANATEC + MODELO 34 ({data_ref}).\n"
            f"Varri {len(ATIVOS)} ativos (IBOV + TOTS3/CPLE3).\n"
            f"Nenhum sinal de compra/venda no candle de ontem."
        )
    else:
        enviar_telegram(
            f"✅ Radar ANATEC + MODELO 34 ({data_ref}): "
            f"{achou} sinal(is) enviado(s) acima."
        )


def executar_em_loop():
    """Modo continuo: varre em intervalos durante o pregao (uso interativo)."""
    log_console("=" * 70)
    log_console("RADAR ANATEC + MODELO 34 iniciado (modo LOOP).")
    log_console(f"Ativos monitorados: {len(ATIVOS)} (IBOV + TOTS3/CPLE3)")
    log_console(f"Intervalo de varredura: {INTERVALO_CHECAGEM // 60} min")
    log_console(f"Log CSV: {caminho_log()}")
    log_console("=" * 70)
    enviar_telegram(
        f"🤖 Radar ANATEC + MODELO 34 ligado (modo loop).\n"
        f"Monitorando {len(ATIVOS)} ativos (IBOV + TOTS3/CPLE3).\n"
        f"Avisarei aqui a cada sinal de COMPRA ou VENDA."
    )

    try:
        while True:
            if mercado_aberto() or not RESPEITAR_HORARIO_PREGAO:
                log_console("Varrendo mercado...")
                achou = varrer_mercado()
                log_console(f"Varredura concluida. Novos alertas: {achou}")
                time.sleep(INTERVALO_CHECAGEM)
            else:
                # Fora do pregao: dorme em ciclos curtos so para checar o horario.
                time.sleep(10 * 60)
    except KeyboardInterrupt:
        log_console("Radar finalizado pelo usuario.")
        enviar_telegram("🛑 Radar ANATEC + MODELO 34 desligado.")


def main():
    # --once  -> varredura unica e encerra (modo agendado, ex: 8h30)
    # sem args (ou --loop) -> monitoramento continuo (uso interativo)
    args = [a.lower() for a in sys.argv[1:]]
    if "--once" in args or "-1" in args or "once" in args:
        executar_uma_vez()
    else:
        executar_em_loop()


if __name__ == "__main__":
    main()
