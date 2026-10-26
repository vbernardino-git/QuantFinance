# -*- coding: utf-8 -*-
"""
Universo de ativos e normalizacao de tickers (B3 -> Yahoo Finance).
"""

# Composicao teorica do IBOV (mesma base dos seus radares) + garantidos extras.
IBOV = [
    "ALOS3", "ABEV3", "ASAI3", "AURE3", "AZUL54", "AZZA3", "B3SA3", "BBSE3",
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


def normalizar(ticker: str) -> str:
    """Garante o sufixo .SA exigido pelo Yahoo Finance, sem duplicar."""
    t = ticker.strip().upper()
    if not t:
        return t
    if t.startswith("^"):  # indices (^BVSP) passam direto
        return t
    if not t.endswith(".SA"):
        t = t + ".SA"
    return t


def limpar(ticker: str) -> str:
    """Remove o .SA para exibicao amigavel."""
    return ticker.upper().replace(".SA", "")


def universo_ibov():
    """Lista completa IBOV + extras, ja com sufixo .SA."""
    universo = list(IBOV)
    for t in EXTRAS:
        if t not in universo:
            universo.append(t)
    return [normalizar(t) for t in universo]


def parse_lista_usuario(texto: str):
    """
    Converte uma string digitada ('petr4, vale3 itub4;bbas3') numa lista
    de tickers normalizados, aceitando virgula, espaco, ponto-e-virgula ou quebra.
    """
    import re
    brutos = re.split(r"[\s,;]+", texto.strip())
    return [normalizar(t) for t in brutos if t.strip()]
