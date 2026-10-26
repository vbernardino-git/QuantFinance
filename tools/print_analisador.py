# -*- coding: utf-8 -*-
"""Roda o Analisador nos papeis da carteira e salva a saida do terminal como SVG
(o "print" que aparece no README).  Uso: python tools/print_analisador.py CPLE3 ITSA4 ..."""
import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "analisador"))
os.chdir(os.path.join(RAIZ, "analisador"))

from rich.console import Console
import analisar
from nucleo import relatorio

con = Console(record=True, width=118, legacy_windows=False, force_terminal=True)
analisar.console = con
relatorio.console = con

tickers = sys.argv[1:] or ["CPLE3", "ITSA4", "VIVT3", "PSSA3"]
res = []
for t in tickers:
    r = analisar.analisar_acao(t)
    if r:
        res.append(r)
relatorio.cabecalho()
relatorio.relatorio_lista(res)
destino = os.path.join(RAIZ, "docs", "img", "analisador_carteira.svg")
con.save_svg(destino, title="python analisar.py " + " ".join(tickers))
relatorio.console = Console(record=True, width=118, legacy_windows=False, force_terminal=True)
analisar.console = relatorio.console
relatorio.cabecalho()
relatorio.relatorio_acao(res[0])
relatorio.console.save_svg(os.path.join(RAIZ, "docs", "img", f"analisador_{res[0]['ticker_limpo']}.svg"),
                           title=f"python analisar.py {res[0]['ticker_limpo']}")
print("ok", destino)
