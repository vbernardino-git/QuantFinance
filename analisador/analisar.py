# -*- coding: utf-8 -*-
"""
=====================================================================================
 ANALISADOR PROFISSIONAL DE ACOES — B3   |   Programa unificado
=====================================================================================
 Une, num so lugar, todas as metodologias dos seus projetos:

   FUNDAMENTOS .... Graham/Dodd, Joel Greenblatt (Magic Formula), Buffett, Damodaran
   TECNICO+QUANT .. ANATEC + Modelo 34 (seu setup), Bollinger/EMAs, RSI/MACD,
                    + ML LightGBM multi-fator walk-forward (Lopez de Prado)
   REGIME+RISCO ... Markov Switching (Hamilton) + HMM, Sharpe/Drawdown/Beta,
                    Monte Carlo GBM (Hull): VaR, CVaR, prob. de lucro

 Tudo termina num VEREDITO unico 0-100 (filosofia equilibrada: 40/35/25).

 Uso:
   python analisar.py                  -> menu interativo
   python analisar.py PETR4            -> analisa 1 acao direto
   python analisar.py PETR4 VALE3 ...  -> analisa varias
   python analisar.py --radar          -> roda o Radar M34 e analisa os sinais
   python analisar.py --ibov           -> analisa o IBOV inteiro (demorado)
=====================================================================================
"""
import sys
import warnings

warnings.filterwarnings("ignore")

# Garante UTF-8 no console do Windows (evita UnicodeEncodeError com caracteres ricos).
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.live import Live
from rich.text import Text

from nucleo import (config, universo, dados, tecnico, fundamentos,
                    regime, ml, montecarlo, risco, veredito, relatorio, radar)

console = Console(legacy_windows=False)


# =====================================================================================
# ANALISE DE UMA ACAO (roda todos os pilares)
# =====================================================================================
def analisar_acao(ticker: str, progresso=None) -> dict | None:
    ticker = universo.normalizar(ticker)
    limpo = universo.limpar(ticker)

    def passo(txt):
        if progresso:
            progresso(f"{limpo}: {txt}")

    passo("baixando precos diarios")
    df = dados.baixar_diario(ticker)
    if df is None or len(df) < 60:
        console.print(f"[red]✗ {limpo}: sem dados de preco suficientes (delistado? ticker errado?)[/red]")
        return None

    passo("baixando intraday 15m")
    intraday = dados.baixar_intraday(ticker)

    passo("baixando indice IBOV (beta)")
    idx = dados.baixar_indice()

    passo("fundamentos")
    fund_raw = dados.buscar_fundamentos(ticker)
    res_fund = fundamentos.analisar(fund_raw)

    passo("tecnico (ANATEC + M34)")
    res_tec = tecnico.analisar(df)

    passo("machine learning (LightGBM)")
    res_ml = ml.analisar(df)

    passo("regime (Markov + HMM)")
    res_reg = regime.analisar(df["Close"], intraday)

    passo("risco")
    res_risco = risco.analisar(df, idx)

    passo("monte carlo")
    res_mc = montecarlo.analisar(df)

    v = veredito.consolidar(res_fund, res_tec, res_ml, res_reg, res_risco, res_mc)

    return {
        "ticker": ticker, "ticker_limpo": limpo,
        "nome": res_fund.get("nome") or (fund_raw.get("dados", {}) or {}).get("nome") or limpo,
        "setor": res_fund.get("setor") or (fund_raw.get("dados", {}) or {}).get("setor"),
        "fundamentos": res_fund, "_fund_raw": fund_raw,
        "tecnico": res_tec, "ml": res_ml, "regime": res_reg,
        "risco": res_risco, "montecarlo": res_mc, "veredito": v,
    }


# =====================================================================================
# FLUXOS
# =====================================================================================
def _analisar_varios(tickers: list[str], detalhar_um=True):
    tickers = list(dict.fromkeys(tickers))  # remove duplicados preservando ordem
    if not tickers:
        console.print("[yellow]Lista vazia.[/yellow]")
        return
    resultados = []
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TextColumn("{task.completed}/{task.total}"),
                  TimeElapsedColumn(), console=console) as prog:
        tarefa = prog.add_task("Analisando...", total=len(tickers))
        for t in tickers:
            prog.update(tarefa, description=f"[cyan]{universo.limpar(t)}[/cyan]")
            try:
                r = analisar_acao(t, progresso=lambda s: prog.update(tarefa, description=f"[cyan]{s}[/cyan]"))
                if r:
                    resultados.append(r)
            except KeyboardInterrupt:
                console.print("[yellow]Interrompido pelo usuario.[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]✗ {universo.limpar(t)}: erro {e}[/red]")
            prog.advance(tarefa)

    if not resultados:
        console.print("[yellow]Nenhuma acao analisada com sucesso.[/yellow]")
        return

    relatorio.cabecalho()
    if len(resultados) == 1 and detalhar_um:
        relatorio.relatorio_acao(resultados[0])
    else:
        for r in resultados:
            relatorio.relatorio_acao(r)
        relatorio.relatorio_lista(resultados)

    caminho = relatorio.exportar_csv(resultados)
    console.print(f"\n[green]✓ Resultados salvos em:[/green] {caminho}")


def _fluxo_radar():
    exe = radar.localizar_exe()
    if not exe:
        console.print("[red]Radar_ANATEC_IBOV.exe nao encontrado.[/red] "
                      "Coloque-o em Downloads ou ajuste CAMINHOS_RADAR_EXE em nucleo/config.py.")
        return
    console.print(f"[cyan]Rodando o Radar M34 (varredura unica)...[/cyan] [dim]{exe}[/dim]")
    console.print("[dim]Isso baixa e analisa o IBOV inteiro; pode levar 1-3 min. Ctrl+C cancela.[/dim]\n")
    linhas_recentes = []

    def mostra(linha):
        if linha.strip():
            console.print(f"[dim]radar |[/dim] {linha}")

    try:
        sinais = radar.rodar_radar_once(callback_linha=mostra)
    except KeyboardInterrupt:
        console.print("[yellow]Radar cancelado.[/yellow]")
        return
    except Exception as e:
        console.print(f"[red]Falha no radar: {e}[/red]")
        return

    if not sinais:
        console.print("\n[yellow]O radar nao retornou sinais de compra/venda no ultimo candle.[/yellow]")
        if not _sim("Quer analisar mesmo assim o ultimo log salvo do radar?"):
            return
        sinais = radar.ler_ultimo_log()
        if not sinais:
            console.print("[yellow]Nenhum sinal no log tambem.[/yellow]")
            return

    tickers = [s["ticker"] for s in sinais]
    console.print(f"\n[green]Radar sinalizou {len(tickers)} ativo(s):[/green] " +
                  ", ".join(universo.limpar(t) for t in tickers))
    _analisar_varios(tickers, detalhar_um=False)


def _sim(pergunta):
    return Prompt.ask(f"[bold]{pergunta}[/bold] (s/n)", choices=["s", "n"], default="s") == "s"


# =====================================================================================
# MENU
# =====================================================================================
def menu():
    relatorio.cabecalho()
    while True:
        console.print("[bold]O que voce quer analisar?[/bold]")
        console.print("  [cyan]1[/cyan] — Uma acao (digite o codigo)")
        console.print("  [cyan]2[/cyan] — Uma lista de acoes (digito eu)")
        console.print("  [cyan]3[/cyan] — Lista do Radar M34 (roda o radar agora)")
        console.print("  [cyan]4[/cyan] — IBOV inteiro (~89 acoes, demorado)")
        console.print("  [cyan]0[/cyan] — Sair")
        op = Prompt.ask("Opcao", choices=["1", "2", "3", "4", "0"], default="1")

        if op == "0":
            console.print("[dim]Ate logo.[/dim]")
            return
        if op == "1":
            t = Prompt.ask("Codigo da acao (ex: PETR4)")
            _analisar_varios([t], detalhar_um=True)
        elif op == "2":
            txt = Prompt.ask("Cole os codigos (ex: PETR4, VALE3, ITUB4)")
            _analisar_varios(universo.parse_lista_usuario(txt), detalhar_um=False)
        elif op == "3":
            _fluxo_radar()
        elif op == "4":
            if _sim(f"Vai analisar {len(universo.universo_ibov())} acoes com tudo ligado. Confirma?"):
                _analisar_varios(universo.universo_ibov(), detalhar_um=False)

        console.print()
        if not _sim("Fazer outra analise?"):
            console.print("[dim]Ate logo.[/dim]")
            return
        console.print()


# =====================================================================================
# ENTRADA
# =====================================================================================
def main():
    args = sys.argv[1:]
    if not args:
        menu()
        return
    flags = [a.lower() for a in args]
    if "--radar" in flags:
        relatorio.cabecalho()
        _fluxo_radar()
    elif "--ibov" in flags:
        relatorio.cabecalho()
        _analisar_varios(universo.universo_ibov(), detalhar_um=False)
    else:
        tickers = [universo.normalizar(a) for a in args if not a.startswith("-")]
        _analisar_varios(tickers, detalhar_um=(len(tickers) == 1))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Encerrado.[/yellow]")
