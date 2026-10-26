# -*- coding: utf-8 -*-
"""
Integracao com o RADAR ANATEC + MODELO 34 (seu Radar_ANATEC_IBOV.exe).

Modo principal: roda o exe com --once (varredura unica), captura o stdout em tempo
real e extrai os ativos que deram sinal de COMPRA/VENDA. Fallback: le o CSV de log.
"""
import os
import re
import csv
import subprocess

from . import config
from . import universo

_RE_ALERTA = re.compile(r"ALERTA\s+(COMPRA|VENDA)\s*->\s*([A-Z0-9]+\.SA)", re.IGNORECASE)


def localizar_exe() -> str | None:
    for caminho in config.CAMINHOS_RADAR_EXE:
        if os.path.isfile(caminho):
            return caminho
    return None


def rodar_radar_once(callback_linha=None, timeout=900) -> list[dict]:
    """
    Executa o radar em varredura unica. Retorna lista de {'ticker','tipo'}.
    callback_linha(str): opcional, recebe cada linha do radar p/ exibir progresso.
    """
    exe = localizar_exe()
    if not exe:
        raise FileNotFoundError(
            "Radar_ANATEC_IBOV.exe nao encontrado em:\n  - " +
            "\n  - ".join(config.CAMINHOS_RADAR_EXE))

    sinais = {}
    try:
        proc = subprocess.Popen(
            [exe, "--once"],
            cwd=os.path.dirname(exe),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
    except Exception as e:
        raise RuntimeError(f"Falha ao iniciar o radar: {e}")

    try:
        for linha in proc.stdout:
            linha = linha.rstrip()
            if callback_linha:
                callback_linha(linha)
            m = _RE_ALERTA.search(linha)
            if m:
                tipo = m.group(1).upper()
                ticker = universo.normalizar(m.group(2))
                sinais[ticker] = tipo  # ultimo tipo vence (raro repetir)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
    except KeyboardInterrupt:
        proc.kill()
        raise

    return [{"ticker": t, "tipo": tp} for t, tp in sinais.items()]


def ler_ultimo_log() -> list[dict]:
    """
    Fallback: le o radar_anatec_log.csv (na pasta do exe) e retorna os ativos
    do ultimo dia registrado. Util quando nao se quer esperar a varredura.
    """
    exe = localizar_exe()
    pasta = os.path.dirname(exe) if exe else os.path.join(os.path.expanduser("~"), "Downloads")
    caminho = os.path.join(pasta, config.NOME_LOG_RADAR)
    if not os.path.isfile(caminho):
        return []

    linhas = []
    try:
        with open(caminho, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                linhas.append(row)
    except Exception:
        return []
    if not linhas:
        return []

    # pega o ultimo Data_Candle registrado
    datas = [r.get("Data_Candle", "") for r in linhas if r.get("Data_Candle")]
    if not datas:
        ultimas = linhas[-20:]
    else:
        ultima = max(datas)
        ultimas = [r for r in linhas if r.get("Data_Candle") == ultima]

    out = {}
    for r in ultimas:
        t = universo.normalizar(r.get("Ativo", ""))
        if t:
            out[t] = (r.get("Tipo") or "").upper()
    return [{"ticker": t, "tipo": tp} for t, tp in out.items()]
