# -*- coding: utf-8 -*-
"""
Configuracoes globais do Analisador.
Tudo que e "ajustavel" mora aqui, para nao precisar caçar numero magico no codigo.
"""
import os

# =====================================================================================
# CAMINHOS
# =====================================================================================
PASTA_APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_SAIDA = os.path.join(PASTA_APP, "resultados")  # relatorios CSV consolidados
PASTA_CACHE = os.path.join(PASTA_APP, ".cache")       # cache de download (opcional)

# Radar M34 (exe ja compilado pelo usuario). Procuramos em alguns lugares conhecidos.
CAMINHOS_RADAR_EXE = [
    os.path.join(os.path.expanduser("~"), "Downloads", "Radar_ANATEC_IBOV.exe"),
    os.path.join(os.path.expanduser("~"), "Downloads", "_radar_build", "dist", "Radar_ANATEC_IBOV.exe"),
]
# Log CSV que o radar grava (fallback para "ler ultimo log")
NOME_LOG_RADAR = "radar_anatec_log.csv"

# =====================================================================================
# DADOS DE MERCADO
# =====================================================================================
PERIODO_DIARIO = "5y"      # historico diario p/ tecnico, ML, regime, risco, Monte Carlo
PERIODO_INTRADAY = "1mo"   # historico 15m p/ regime intraday (estilo radar Markov)
INTERVALO_INTRADAY = "15m"
INDICE_REFERENCIA = "^BVSP"  # IBOV, para beta/correlacao
TENTATIVAS_DOWNLOAD = 3
PAUSA_ANTI_THROTTLE = 12     # segundos entre tentativas

# =====================================================================================
# PESOS DO VEREDITO UNIFICADO (filosofia EQUILIBRADA)
# Fundamentos 40% | Tecnico+Quant 35% | Regime+Risco 25%
# =====================================================================================
PESO_FUNDAMENTOS = 0.40
PESO_TECNICO = 0.35
PESO_REGIME_RISCO = 0.25

# Faixas do veredito final (score 0-100)
FAIXAS_VEREDITO = [
    (75, "COMPRA FORTE", "bold white on green"),
    (60, "COMPRA",       "green"),
    (45, "NEUTRO",       "yellow"),
    (30, "VENDA",        "red"),
    (0,  "VENDA FORTE",  "bold white on red"),
]

# =====================================================================================
# PARAMETROS TECNICOS (herdados dos seus notebooks/radares)
# =====================================================================================
ADX_MINIMO = 22          # mercado direcional (ANATEC + M34)
EMA_LONGA = 34           # Modelo 34 (Marcio Noronha / Setup 9.1 brasileiro)
RSI_SOBREVENDA = 30
RSI_SOBRECOMPRA = 70

# =====================================================================================
# MARKOV / HMM (regime)
# =====================================================================================
MARKOV_MIN_OBS = 120
HMM_REGIMES = 3
REGIME_LIMIAR = 0.65     # confianca minima do regime p/ considerar "definido"

# =====================================================================================
# MACHINE LEARNING (LightGBM multi-fator, walk-forward)
# =====================================================================================
ML_HORIZONTE = 5         # prever retorno acumulado dos proximos N pregoes
ML_SPLITS = 5            # walk-forward (TimeSeriesSplit)
ML_CUSTO_TRADE = 0.0005  # 5 bps p/ Sharpe liquido
ML_IC_MINIMO = 0.02      # Information Coefficient minimo p/ o sinal "valer"

# =====================================================================================
# MONTE CARLO (GBM)
# =====================================================================================
MC_DIAS = 252            # horizonte 1 ano
MC_SIMULACOES = 10000
MC_SEED = 42

# =====================================================================================
# EXECUCAO
# =====================================================================================
MAX_WORKERS_LISTA = 4    # paralelismo ao analisar listas grandes
