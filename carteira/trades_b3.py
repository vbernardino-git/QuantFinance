# -*- coding: utf-8 -*-
"""
Historico REAL de operacoes a partir do extrato "Movimentacao" da Area do Investidor (B3).

    python carteira/trades_b3.py caminho/movimentacao-AAAA-MM-DD.xlsx

- Usa as liquidacoes de renda variavel (Credito = compra, Debito = venda).
  Linhas "Transferencia" puras (sem "Liquidacao") sao movimento de custodia e ficam de fora.
- Aluguel de acoes (BTB): a acao emprestada sai como "Debito - Liquidacao" SEM preco e volta
  como "Credito - Liquidacao" com a mesma quantidade (com preco de referencia). Nao e compra
  nem venda: o par sai do calculo (aconteceu em PETR4 e TAEE11, conferido com o caixa do Inter).
- Venda sem preco que nao tenha devolucao casada recebe o fechamento do dia (Yahoo) e fica
  marcada como "preco estimado" na coluna obs.
- O relatorio comeca em INICIO (2025), mas o preco medio usa o historico inteiro.
- Acrescenta dados/trades_manuais.csv (operacoes depois do ultimo extrato).
- Apura cada venda pelo preco medio (regra da Receita) e grava:
    dados/trades.csv        -> todas as ordens
    dados/round_trips.csv   -> cada venda com o preco medio e o resultado realizado
"""
import os, re, sys
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, "dados")
INICIO = pd.Timestamp("2025-01-01")


def ler_extrato(caminho):
    df = pd.read_excel(caminho)
    df.columns = ["es", "data", "mov", "produto", "inst", "qtd", "preco", "valor"]
    df = df[df["mov"].astype(str).str.contains("Liquida", na=False)].copy()
    df["ticker"] = df["produto"].astype(str).str.extract(r"^([A-Z]{4}\d{1,2})\b")[0]
    df = df[df["ticker"].notna()]
    out = pd.DataFrame({
        "data": pd.to_datetime(df["data"], dayfirst=True),
        "ticker": df["ticker"],
        "lado": df["es"].map({"Credito": "C", "Debito": "V"}),
        "qtd": df["qtd"].astype(float),
        "preco": pd.to_numeric(df["preco"], errors="coerce"),
        "obs": "extrato B3",
    })
    out = tirar_aluguel(out.sort_values("data", kind="stable"))
    sem = out["preco"].isna() & (out["lado"] == "V")
    for i, t in out[sem].iterrows():
        out.loc[i, "preco"] = fechamento(t.ticker, t.data)
        out.loc[i, "obs"] = "preco estimado (fechamento do dia; extrato sem preco)"
    return out[out["preco"].notna()]


def tirar_aluguel(out):
    """Casa cada saida sem preco (emprestimo BTB) com a proxima entrada de mesma quantidade
    do mesmo papel (devolucao) e remove as duas."""
    fora, abertos = set(), {}  # ticker -> [(idx, qtd)] emprestimos em aberto
    for i, t in out.iterrows():
        if t.lado == "V" and pd.isna(t.preco):
            abertos.setdefault(t.ticker, []).append((i, t.qtd))
        elif t.lado == "C":
            for k, (j, q) in enumerate(abertos.get(t.ticker, [])):
                if q == t.qtd and t.data > out.loc[j, "data"]:
                    fora |= {i, j}
                    del abertos[t.ticker][k]
                    break
    return out.drop(index=list(fora))


def fechamento(ticker, data):
    import yfinance as yf
    d = yf.download(ticker + ".SA", start=data - pd.Timedelta(days=7), end=data + pd.Timedelta(days=1),
                    auto_adjust=False, progress=False)["Close"].squeeze().dropna()
    return round(float(d.iloc[-1]), 2) if len(d) else None


def preco_medio(trades):
    """Apura cada venda pelo PRECO MEDIO ponderado (regra da Receita/B3, a mesma da planilha).
    Venda sem estoque conhecido (compra anterior ao extrato) entra como 'sem_custo'."""
    pos, saida = {}, []  # ticker -> [qtd, custo_total, data_primeira_compra]
    ordem = trades.assign(_k=trades["lado"].map({"C": 0, "V": 1})).sort_values(["data", "_k"], na_position="first")
    for _, t in ordem.iterrows():
        q, custo, ini = pos.get(t.ticker, [0.0, 0.0, None])
        if t.lado == "C":
            pos[t.ticker] = [q + t.qtd, custo + t.qtd * t.preco, ini if q > 0 else t.data]
            continue
        if q <= 1e-9:
            saida.append({"data_venda": t.data, "ticker": t.ticker, "qtd": t.qtd, "preco_venda": t.preco,
                          "preco_medio": None, "resultado": None, "resultado_pct": None,
                          "dias": None, "status": "sem_custo"})
            continue
        pm = custo / q
        vend = min(t.qtd, q)
        res = vend * (t.preco - pm)
        dias = (t.data - ini).days if pd.notna(ini) and pd.notna(t.data) else None
        saida.append({"data_venda": t.data, "ticker": t.ticker, "qtd": vend, "preco_venda": t.preco,
                      "preco_medio": round(pm, 4), "resultado": round(res, 2),
                      "resultado_pct": round(t.preco / pm - 1, 4), "dias": dias,
                      "status": "ok" if t.qtd <= q + 1e-9 else "parcial"})
        resto = q - vend
        pos[t.ticker] = [resto, pm * resto, ini if resto > 1e-9 else None]
    return pd.DataFrame(saida)


if __name__ == "__main__":
    trades = ler_extrato(sys.argv[1])
    manuais = pd.read_csv(os.path.join(DADOS, "trades_manuais.csv"), parse_dates=["data"])
    trades = pd.concat([trades, manuais], ignore_index=True)
    rt = preco_medio(trades)
    rt = rt.merge(trades[trades.lado == "V"][["data", "ticker", "obs"]].drop_duplicates(["data", "ticker"]),
                  left_on=["data_venda", "ticker"], right_on=["data", "ticker"], how="left").drop(columns="data")
    trades = trades[trades["data"].isna() | (trades["data"] >= INICIO)]
    rt = rt[rt["data_venda"] >= INICIO]
    trades.sort_values("data", na_position="first").to_csv(os.path.join(DADOS, "trades.csv"), index=False, date_format="%Y-%m-%d")
    rt.to_csv(os.path.join(DADOS, "round_trips.csv"), index=False, date_format="%Y-%m-%d")
    ok = rt[rt.status != "sem_custo"]
    print(f"{len(trades)} ordens | {len(rt)} vendas | {len(ok)} com custo conhecido")
    print(f"Resultado realizado: R$ {ok.resultado.sum():,.2f} | acerto {(ok.resultado > 0).mean():.0%}")
