# -*- coding: utf-8 -*-
"""
Apresentacao: relatorio rico no terminal (rich) para 1 acao e tabela consolidada
para listas, alem do export CSV automatico dos resultados.
"""
import os
import csv
import datetime as dt

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich import box

from . import config

console = Console(legacy_windows=False)


def _fmt(v, suf="", casas=2, mult=1):
    if v is None:
        return "[dim]n/d[/dim]"
    try:
        return f"{v*mult:.{casas}f}{suf}"
    except (TypeError, ValueError):
        return str(v)


def _barra(score):
    """Mini barra textual 0-100."""
    if score is None:
        return "[dim]----------[/dim]"
    n = int(round(score / 10))
    cor = "green" if score >= 60 else "yellow" if score >= 45 else "red"
    return f"[{cor}]{'█'*n}{'░'*(10-n)}[/{cor}] {score:.0f}"


def cabecalho():
    console.print()
    console.rule("[bold cyan]ANALISADOR PROFISSIONAL DE ACOES — B3[/bold cyan]")
    console.print(
        "[dim]Fundamentos (Graham/Greenblatt/Buffett) · Tecnico+Quant (ANATEC+M34/ML) · "
        "Regime+Risco (Markov/HMM/Monte Carlo)[/dim]", justify="center")
    console.print()


def relatorio_acao(r: dict):
    """r = dicionario completo de uma acao (vindo de analisar_acao)."""
    tic = r["ticker_limpo"]
    nome = r.get("nome") or tic
    setor = r.get("setor") or ""
    v = r["veredito"]

    # --- Painel do veredito (markup parseado, p/ as barras coloridas funcionarem) ---
    titulo = Text(f" {tic} ", style="bold")
    pil = v["pilares"]
    linhas = [
        f"[bold white]{nome}[/bold white]",
        f"[dim]{setor}[/dim]",
        "",
        f"[{v['estilo']}]VEREDITO: {v['rotulo']}[/{v['estilo']}]   [bold]Score {v['score_final']}/100[/bold]",
        "",
        f"Fundamentos    {_pil_txt(pil.get('Fundamentos'))}",
        f"Tecnico+Quant  {_pil_txt(pil.get('Tecnico+Quant'))}",
        f"Regime+Risco   {_pil_txt(pil.get('Regime+Risco'))}",
    ]
    if v.get("cobertura", 1) < 0.99:
        linhas.append(f"\n[dim][cobertura de dados: {v['cobertura']*100:.0f}%][/dim]")
    cab = Text.from_markup("\n".join(linhas))
    console.print(Panel(cab, title=titulo, border_style=_borda(v["score_final"]), box=box.DOUBLE, expand=False))

    # --- Tabelas lado a lado ---
    console.print(Columns([_tab_fund(r), _tab_tec(r)], equal=False, expand=False))
    console.print(Columns([_tab_regime_risco(r), _tab_proj(r)], equal=False, expand=False))

    # --- Notas (racional, estilo book) ---
    _imprimir_notas(r)
    console.print()


def _pil_txt(score):
    return _barra(score) if score is not None else "[dim]indisponivel[/dim]"


def _borda(score):
    return "green" if score >= 60 else "yellow" if score >= 45 else "red"


def _tab_fund(r):
    f = r.get("fundamentos") or {}
    d = (r.get("_fund_raw") or {}).get("dados", {}) if r.get("_fund_raw") else {}
    t = Table(title="FUNDAMENTOS", box=box.SIMPLE, title_style="bold cyan", show_header=False)
    t.add_column("k", style="dim"); t.add_column("v", justify="right")
    if f.get("ok"):
        dims = f.get("dimensoes", {})
        t.add_row("Qualidade", _num(dims.get("qualidade"), "/100"))
        t.add_row("Valuation", _num(dims.get("valuation"), "/100"))
        t.add_row("Saude fin.", _num(dims.get("saude"), "/100"))
        t.add_row("Crescimento", _num(dims.get("crescimento"), "/100"))
    t.add_row("P/L", _num(d.get("pl")))
    t.add_row("P/VP", _num(d.get("pvp")))
    t.add_row("EV/EBIT", _num(d.get("ev_ebit")))
    t.add_row("ROE", _pct(d.get("roe")))
    dpl = d.get("divida_pl")
    if dpl is not None:
        try:
            dpl = float(dpl)
            if dpl > 5:  # yfinance entrega debtToEquity em % -> normaliza p/ razao
                dpl = dpl / 100
        except (TypeError, ValueError):
            pass
    t.add_row("Div/PL", _num(dpl))
    return t


def _tab_tec(r):
    tc = r.get("tecnico") or {}
    ml = r.get("ml") or {}
    t = Table(title="TECNICO + QUANT", box=box.SIMPLE, title_style="bold cyan", show_header=False)
    t.add_column("k", style="dim"); t.add_column("v", justify="right")
    t.add_row("Preco", _num(tc.get("preco")))
    t.add_row("Tendencia", str(tc.get("tendencia", "n/d")))
    t.add_row("RSI", _num(tc.get("rsi"), casas=0))
    t.add_row("ADX", _num(tc.get("adx"), casas=0))
    t.add_row("MME34", _num(tc.get("mme34")))
    sa = (tc.get("sinal_anatec") or {})
    t.add_row("ANATEC+M34", (sa.get("tipo") + ": " + (sa.get("padrao") or "")) if sa.get("tipo") else "[dim]sem gatilho[/dim]")
    if ml.get("ok"):
        t.add_row("ML prev. 5d", _pct(ml.get("forecast")))
        t.add_row("ML sinal", str(ml.get("sinal")))
        t.add_row("ML IC", _num(ml.get("ic"), casas=3))
    return t


def _tab_regime_risco(r):
    rg = r.get("regime") or {}
    rk = r.get("risco") or {}
    t = Table(title="REGIME + RISCO", box=box.SIMPLE, title_style="bold cyan", show_header=False)
    t.add_column("k", style="dim"); t.add_column("v", justify="right")
    det = rg.get("detalhe", {})
    if "markov_diario" in det:
        md = det["markov_diario"]
        t.add_row("Markov (diario)", f"{md['estado']} ({md['prob_alta']:.0%})")
    if "hmm" in det:
        t.add_row("HMM/KMeans", det["hmm"]["leitura"])
    t.add_row("Vol anual", _pct(rk.get("vol_ann"), casas=0))
    t.add_row("Sharpe", _num(rk.get("sharpe")))
    t.add_row("Max drawdown", _pct(rk.get("max_drawdown"), casas=0))
    t.add_row("Beta IBOV", _num(rk.get("beta")))
    return t


def _tab_proj(r):
    mc = r.get("montecarlo") or {}
    t = Table(title="MONTE CARLO (1 ano)", box=box.SIMPLE, title_style="bold cyan", show_header=False)
    t.add_column("k", style="dim"); t.add_column("v", justify="right")
    if mc.get("ok"):
        t.add_row("Preco mediano", _num(mc.get("preco_mediano_1a")))
        t.add_row("Cenario 5%", _num(mc.get("preco_p05_1a")))
        t.add_row("Cenario 95%", _num(mc.get("preco_p95_1a")))
        t.add_row("Prob. lucro", _pct(mc.get("prob_lucro_1a"), casas=0))
        t.add_row("VaR 95%", _num(mc.get("var95"), suf="%", casas=1))
        t.add_row("CVaR 95%", _num(mc.get("cvar95"), suf="%", casas=1))
    else:
        t.add_row("status", "[dim]indisponivel[/dim]")
    return t


def _imprimir_notas(r):
    blocos = [
        ("Fundamentos", (r.get("fundamentos") or {}).get("notas")),
        ("Tecnico", (r.get("tecnico") or {}).get("notas")),
        ("ML", (r.get("ml") or {}).get("notas")),
        ("Regime", (r.get("regime") or {}).get("notas")),
        ("Risco", (r.get("risco") or {}).get("notas")),
        ("Monte Carlo", (r.get("montecarlo") or {}).get("notas")),
    ]
    linhas = []
    for nome, notas in blocos:
        if notas:
            for n in notas:
                linhas.append(f"[cyan]•[/cyan] [dim]{nome}:[/dim] {n}")
    if linhas:
        console.print(Panel("\n".join(linhas), title="Racional da analise", border_style="dim", box=box.ROUNDED))


def _num(v, suf="", casas=2):
    if v is None:
        return "[dim]n/d[/dim]"
    try:
        fv = float(v)
        if fv != fv:  # NaN
            return "[dim]n/d[/dim]"
        return f"{fv:.{casas}f}{suf}"
    except (TypeError, ValueError):
        return str(v)


def _pct(v, casas=1):
    if v is None:
        return "[dim]n/d[/dim]"
    try:
        v = float(v)
        if v != v:  # NaN
            return "[dim]n/d[/dim]"
        if abs(v) < 1.5:  # fracao -> %
            v = v * 100
        return f"{v:.{casas}f}%"
    except (TypeError, ValueError):
        return str(v)


# =====================================================================================
# LISTA CONSOLIDADA
# =====================================================================================
def relatorio_lista(resultados: list[dict]):
    if not resultados:
        console.print("[yellow]Nenhum resultado para exibir.[/yellow]")
        return
    resultados = sorted(resultados, key=lambda r: r["veredito"]["score_final"], reverse=True)

    t = Table(title="RANKING CONSOLIDADO", box=box.HEAVY_HEAD, title_style="bold cyan", header_style="bold")
    t.add_column("#", justify="right", style="dim")
    t.add_column("Ativo", style="bold")
    t.add_column("Veredito")
    t.add_column("Score", justify="right")
    t.add_column("Fund", justify="right")
    t.add_column("Tec+Q", justify="right")
    t.add_column("Reg+Ri", justify="right")
    t.add_column("ANATEC+M34")
    t.add_column("ML 5d", justify="right")
    t.add_column("Prob+1a", justify="right")
    for i, r in enumerate(resultados, 1):
        v = r["veredito"]; pil = v["pilares"]
        sa = ((r.get("tecnico") or {}).get("sinal_anatec") or {})
        ml = r.get("ml") or {}
        mc = r.get("montecarlo") or {}
        t.add_row(
            str(i), r["ticker_limpo"],
            Text(v["rotulo"], style=v["estilo"]),
            f"[{_borda(v['score_final'])}]{v['score_final']:.0f}[/{_borda(v['score_final'])}]",
            _cell(pil.get("Fundamentos")), _cell(pil.get("Tecnico+Quant")), _cell(pil.get("Regime+Risco")),
            (sa.get("tipo") or "-") if sa else "-",
            (f"{ml.get('forecast')*100:+.1f}%" if ml.get("ok") and ml.get("forecast") is not None else "-"),
            (f"{mc.get('prob_lucro_1a')*100:.0f}%" if mc.get("ok") and mc.get("prob_lucro_1a") is not None else "-"),
        )
    console.print()
    console.print(t)


def _cell(score):
    if score is None:
        return "[dim]-[/dim]"
    return f"[{_borda(score)}]{score:.0f}[/{_borda(score)}]"


def exportar_csv(resultados: list[dict]) -> str:
    os.makedirs(config.PASTA_SAIDA, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    caminho = os.path.join(config.PASTA_SAIDA, f"analise_{stamp}.csv")
    campos = ["ticker", "nome", "setor", "veredito", "score_final",
              "pilar_fundamentos", "pilar_tecnico_quant", "pilar_regime_risco",
              "preco", "pl", "pvp", "ev_ebit", "roe", "divida_pl",
              "rsi", "adx", "mme34", "anatec_m34",
              "ml_prev_5d", "ml_ic", "ml_sinal",
              "regime_markov", "hmm", "vol_ann", "sharpe", "max_drawdown", "beta",
              "mc_preco_mediano_1a", "mc_prob_lucro_1a", "mc_var95", "mc_cvar95"]
    with open(caminho, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=campos, delimiter=";")
        w.writeheader()
        for r in sorted(resultados, key=lambda x: x["veredito"]["score_final"], reverse=True):
            v = r["veredito"]; pil = v["pilares"]
            tc = r.get("tecnico") or {}; ml = r.get("ml") or {}
            rg = r.get("regime") or {}; rk = r.get("risco") or {}; mc = r.get("montecarlo") or {}
            d = (r.get("_fund_raw") or {}).get("dados", {}) if r.get("_fund_raw") else {}
            det = rg.get("detalhe", {})
            sa = (tc.get("sinal_anatec") or {})
            w.writerow({
                "ticker": r["ticker_limpo"], "nome": r.get("nome"), "setor": r.get("setor"),
                "veredito": v["rotulo"], "score_final": v["score_final"],
                "pilar_fundamentos": pil.get("Fundamentos"),
                "pilar_tecnico_quant": pil.get("Tecnico+Quant"),
                "pilar_regime_risco": pil.get("Regime+Risco"),
                "preco": tc.get("preco"), "pl": d.get("pl"), "pvp": d.get("pvp"),
                "ev_ebit": d.get("ev_ebit"), "roe": d.get("roe"), "divida_pl": d.get("divida_pl"),
                "rsi": tc.get("rsi"), "adx": tc.get("adx"), "mme34": tc.get("mme34"),
                "anatec_m34": (sa.get("tipo") or ""),
                "ml_prev_5d": ml.get("forecast"), "ml_ic": ml.get("ic"), "ml_sinal": ml.get("sinal"),
                "regime_markov": (det.get("markov_diario", {}) or {}).get("estado"),
                "hmm": (det.get("hmm", {}) or {}).get("leitura"),
                "vol_ann": rk.get("vol_ann"), "sharpe": rk.get("sharpe"),
                "max_drawdown": rk.get("max_drawdown"), "beta": rk.get("beta"),
                "mc_preco_mediano_1a": mc.get("preco_mediano_1a"),
                "mc_prob_lucro_1a": mc.get("prob_lucro_1a"),
                "mc_var95": mc.get("var95"), "mc_cvar95": mc.get("cvar95"),
            })
    return caminho
