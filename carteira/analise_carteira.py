# -*- coding: utf-8 -*-
"""
Analise de risco da MINHA carteira real (dados/carteira.json) + historico de trades.

    python carteira/analise_carteira.py

Gera em docs/img/ os graficos do README e em resultados/resumo.json os numeros:
  1. Markowitz  - fronteira eficiente (long-only, teto de 40% por papel), carteira atual
                  x maximo Sharpe (rf = CDI) x minima variancia
  2. Monte Carlo - 10.000 caminhos de 1 ano da carteira (GBM multivariado com Cholesky,
                  correlacao real entre os papeis): VaR/CVaR 95%, prob. de bater o CDI
  3. Risco       - vol, beta, drawdown, Sharpe/Sortino por papel + matriz de correlacao
  4. Trades      - resultado realizado de cada venda (preco medio) 2025 em diante
  5. Bazin       - cotacao x preco teto
"""
import json, os, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from scipy.optimize import minimize

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
IMG = os.path.join(RAIZ, "docs", "img")
SAIDA = os.path.join(RAIZ, "resultados")
os.makedirs(IMG, exist_ok=True)
os.makedirs(SAIDA, exist_ok=True)

ANOS = 3
DIAS = 252
N_SIM = 10_000
TETO_PESO = 0.40
SEED = 42

# ---- paleta (fundo preto): cor so onde carrega informacao ---------------------------
AZUL, LARANJA, VERDE_AGUA, VERMELHO = "#3987e5", "#d95926", "#199e70", "#e66767"
CINZA, CINZA_CLARO, TINTA, TINTA_2 = "#898781", "#383835", "#f0efec", "#c3c2b7"
FUNDO = "#0d0d0d"
plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "font.size": 10.5, "font.family": "DejaVu Sans",
    "axes.edgecolor": CINZA_CLARO, "axes.linewidth": 0.8, "axes.grid": True,
    "grid.color": "#2c2c2a", "grid.linewidth": 0.7, "axes.spines.top": False,
    "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 13,
    "axes.titlelocation": "left", "axes.labelcolor": TINTA_2, "xtick.color": TINTA_2,
    "ytick.color": TINTA_2, "legend.frameon": False, "figure.facecolor": FUNDO,
    "axes.facecolor": FUNDO, "text.color": TINTA, "axes.titlecolor": TINTA,
    "legend.labelcolor": TINTA_2, "axes.axisbelow": True,
})
BRL = mtick.FuncFormatter(lambda v, _: f"R$ {v:,.0f}".replace(",", "."))
PCT = mtick.PercentFormatter(1.0, decimals=0)
from matplotlib.colors import LinearSegmentedColormap
AZUIS = LinearSegmentedColormap.from_list("azuis", ["#141b24", "#184f95", "#3987e5", "#9ec5f4"])  # perto de 0 some no fundo


def salvar(fig, nome):
    fig.savefig(os.path.join(IMG, nome), bbox_inches="tight", facecolor=FUNDO)
    plt.close(fig)
    print("  ->", nome)


def subtitulo(ax, txt):
    ax.text(0, 1.02, txt, transform=ax.transAxes, color=TINTA_2, fontsize=9.5, va="bottom")


# =====================================================================================
# DADOS
# =====================================================================================
cart = json.load(open(os.path.join(AQUI, "dados", "carteira.json"), encoding="utf-8"))
pos = pd.DataFrame(cart["posicoes"]).set_index("ticker")
atuais = list(pos.index)
candidatos = cart["candidatos_troca"]
universo = atuais + candidatos
rf = cart["cdi_aa"]

print("Baixando precos (Yahoo)...")
px = yf.download([t + ".SA" for t in universo] + ["^BVSP"], period=f"{ANOS}y",
                 auto_adjust=True, progress=False)["Close"]
px.columns = [c.replace(".SA", "") for c in px.columns]
px = px[px.index < pd.Timestamp.today().normalize()]  # so pregoes fechados (o candle do dia vem parcial/sujo)
px = px.dropna(how="all").ffill().dropna()
ibov = px.pop("^BVSP")
ret = np.log(px / px.shift(1)).dropna()
ret_ibov = np.log(ibov / ibov.shift(1)).dropna()

cot = px.iloc[-1]
pos["cotacao"] = cot[atuais]
pos["valor"] = pos["qtd"] * pos["cotacao"]
pos["custo"] = pos["qtd"] * pos["preco_medio"]
pos["peso"] = pos["valor"] / pos["valor"].sum()
pos["lp"] = pos["valor"] - pos["custo"]
patrimonio_acoes = float(pos["valor"].sum())

mu = ret.mean() * DIAS
cov = ret.cov() * DIAS

# =====================================================================================
# 1. MARKOWITZ
# =====================================================================================
print("Markowitz...")


def perf(w, cols):
    m, c = mu[cols].values, cov.loc[cols, cols].values
    r = float(w @ m)
    v = float(np.sqrt(w @ c @ w))
    return r, v


def otimizar(cols, objetivo, alvo=None):
    n = len(cols)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    if alvo is not None:
        cons.append({"type": "eq", "fun": lambda w: perf(w, cols)[0] - alvo})
    bnds = [(0, TETO_PESO)] * n
    w0 = np.repeat(1 / n, n)
    if objetivo == "sharpe":
        f = lambda w: -(perf(w, cols)[0] - rf) / perf(w, cols)[1]
    else:
        f = lambda w: perf(w, cols)[1]
    return minimize(f, w0, method="SLSQP", bounds=bnds, constraints=cons).x


rng = np.random.default_rng(SEED)
nuvem = rng.dirichlet(np.ones(len(universo)), 15_000)
nuvem = nuvem[(nuvem <= TETO_PESO).all(axis=1)]
nv_r = nuvem @ mu[universo].values
nv_v = np.sqrt(np.einsum("ij,jk,ik->i", nuvem, cov.loc[universo, universo].values, nuvem))

w_sharpe = otimizar(universo, "sharpe")
w_minvar = otimizar(universo, "minvar")
r_ms, v_ms = perf(w_sharpe, universo)
r_mv, v_mv = perf(w_minvar, universo)
alvos = np.linspace(r_mv, max(mu[universo].max() * 0.98, r_mv + 0.01), 40)
fronteira = []
for a in alvos:
    w = otimizar(universo, "minvar", alvo=a)
    r_, v_ = perf(w, universo)
    if abs(r_ - a) < 5e-3:
        fronteira.append((v_, r_))
fronteira = np.array(fronteira)

w_atual = pos["peso"].values
r_at, v_at = perf(w_atual, atuais)
sh = lambda r, v: (r - rf) / v

fig, ax = plt.subplots(figsize=(10, 6.2))
ax.scatter(nv_v, nv_r, s=3, color=CINZA_CLARO, alpha=0.6, lw=0, label="15 mil carteiras aleatórias")
ax.plot(fronteira[:, 0], fronteira[:, 1], color=AZUL, lw=2, label="Fronteira eficiente")
for t in universo:
    v_t = np.sqrt(cov.loc[t, t])
    ax.scatter(v_t, mu[t], s=26, color=FUNDO, edgecolor=CINZA, lw=1.2, zorder=3)
    ax.annotate(t, (v_t, mu[t]), xytext=(5, 3), textcoords="offset points", fontsize=8.5, color=TINTA_2)
pts = [(v_at, r_at, "Minha carteira", LARANJA, "o"),
       (v_ms, r_ms, "Máximo Sharpe", AZUL, "D"),
       (v_mv, r_mv, "Mínima variância", VERDE_AGUA, "s")]
for v_, r_, nome, cor, mk in pts:
    ax.scatter(v_, r_, s=110, color=cor, marker=mk, edgecolor=FUNDO, lw=2, zorder=5)
    ax.annotate(f"{nome}\nret {r_:.0%} · vol {v_:.0%} · Sharpe {sh(r_, v_):.2f}", (v_, r_),
                xytext=(12, -6), textcoords="offset points", fontsize=8.8, color=TINTA, fontweight="bold")
ax.axhline(rf, color=CINZA, lw=1, ls="--")
ax.text(ax.get_xlim()[0], rf, f"  CDI {rf:.2%}", va="bottom", fontsize=8.5, color=TINTA_2)
ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
ax.set_xlabel("Volatilidade anual"); ax.set_ylabel("Retorno anual (média histórica)")
ax.set_title("Markowitz — fronteira eficiente da minha carteira", pad=22)
subtitulo(ax, f"{ANOS} anos de pregões · long-only · máx. {TETO_PESO:.0%} por papel · "
              f"atuais {', '.join(atuais)} + candidatos {', '.join(candidatos)}")
ax.legend(loc="lower left", fontsize=9)
salvar(fig, "markowitz_fronteira.png")

# pesos atual x otimos
fig, ax = plt.subplots(figsize=(10, 3.8))
x = np.arange(len(universo)); lg = 0.27
pa = pd.Series(w_atual, index=atuais).reindex(universo).fillna(0).values
for i, (vals, nome, cor) in enumerate([(pa, "Minha carteira", LARANJA),
                                       (w_sharpe, "Máximo Sharpe", AZUL),
                                       (w_minvar, "Mínima variância", VERDE_AGUA)]):
    ax.bar(x + (i - 1) * lg, vals, lg - 0.03, color=cor, label=nome)
ax.set_xticks(x, universo); ax.yaxis.set_major_formatter(PCT)
ax.set_title("Pesos: o que eu tenho × o que o otimizador sugere", pad=8)
ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=9)
salvar(fig, "markowitz_pesos.png")

# =====================================================================================
# 2. MONTE CARLO (carteira, GBM multivariado)
# =====================================================================================
print("Monte Carlo...")
mu_d = ret[atuais].mean().values
cov_d = ret[atuais].cov().values
L = np.linalg.cholesky(cov_d)
z = rng.standard_normal((DIAS, N_SIM, len(atuais)))
choques = z @ L.T
drift = mu_d - 0.5 * np.diag(cov_d)
log_paths = np.cumsum(drift + choques, axis=0)
precos_sim = cot[atuais].values * np.exp(log_paths)               # (dias, sim, ativos)
valor_sim = (precos_sim * pos["qtd"].values).sum(axis=2)          # (dias, sim)
valor_sim = np.vstack([np.full(N_SIM, patrimonio_acoes), valor_sim])
final = valor_sim[-1]
pnl = final / patrimonio_acoes - 1
var95 = np.percentile(pnl, 5)
cvar95 = pnl[pnl <= var95].mean()
p_lucro = (pnl > 0).mean()
p_cdi = (pnl > rf).mean()

fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [2.2, 1]}, sharey=True)
d = np.arange(DIAS + 1)
faixas = [(5, 95, 0.12), (25, 75, 0.25)]
for lo, hi, a in faixas:
    ax.fill_between(d, np.percentile(valor_sim, lo, axis=1), np.percentile(valor_sim, hi, axis=1),
                    color=AZUL, alpha=a, lw=0, label=f"P{lo}–P{hi}")
for k in rng.choice(N_SIM, 40, replace=False):
    ax.plot(d, valor_sim[:, k], color=AZUL, lw=0.4, alpha=0.25)
ax.plot(d, np.median(valor_sim, axis=1), color=AZUL, lw=2, label="Mediana")
ax.plot(d, patrimonio_acoes * np.exp(np.log1p(rf) * d / DIAS), color=CINZA, lw=1.4, ls="--", label="CDI")
ax.yaxis.set_major_formatter(BRL); ax.set_xlabel("Pregões à frente")
ax.set_title(f"Monte Carlo — {N_SIM:,} caminhos de 1 ano da minha carteira".replace(",", "."), pad=22)
subtitulo(ax, f"GBM multivariado com Cholesky (correlação real entre {', '.join(atuais)}) · "
              f"ponto de partida R$ {patrimonio_acoes:,.0f}".replace(",", ".").replace(". ", ", "))
ax.legend(loc="upper left", fontsize=9)
ax2.hist(final, bins=70, orientation="horizontal", color=AZUL, alpha=0.75, edgecolor=FUNDO, lw=0.3)
lim_var = patrimonio_acoes * (1 + var95)
ax2.axhline(lim_var, color=VERMELHO, lw=1.5)
ax2.axhline(patrimonio_acoes, color=CINZA, lw=1, ls=":")
ax2.text(ax2.get_xlim()[1] * 0.97, lim_var, f"VaR 95%  {var95:.1%}\nCVaR 95% {cvar95:.1%}",
         ha="right", va="top", fontsize=9, color=TINTA, fontweight="bold")
ax2.text(ax2.get_xlim()[1] * 0.97, np.percentile(final, 97),
         f"P(lucro) {p_lucro:.0%}\nP(bater CDI) {p_cdi:.0%}", ha="right", va="top", fontsize=9, color=TINTA)
ax2.set_xlabel("Nº de cenários"); ax2.set_title("Distribuição em 1 ano", pad=22)
salvar(fig, "monte_carlo_carteira.png")

# =====================================================================================
# 3. RISCO POR ATIVO + CORRELACAO
# =====================================================================================
print("Risco...")
linhas = []
for t in universo:
    r = ret[t]
    alinh = pd.concat([r, ret_ibov], axis=1, join="inner")
    beta = np.cov(alinh.iloc[:, 0], alinh.iloc[:, 1])[0, 1] / alinh.iloc[:, 1].var()
    curva = np.exp(r.cumsum())
    dd = (curva / curva.cummax() - 1).min()
    neg = r[r < 0].std() * np.sqrt(DIAS)
    linhas.append({"ticker": t, "carteira": t in atuais, "ret_aa": mu[t], "vol_aa": np.sqrt(cov.loc[t, t]),
                   "sharpe": (mu[t] - rf) / np.sqrt(cov.loc[t, t]), "sortino": (mu[t] - rf) / neg,
                   "beta_ibov": beta, "max_dd": dd})
risco = pd.DataFrame(linhas).set_index("ticker")
risco.round(4).to_csv(os.path.join(SAIDA, "risco_por_ativo.csv"))

fig, ax = plt.subplots(figsize=(7.4, 6.2))
corr = ret[universo].corr()
m = np.triu(np.ones_like(corr, dtype=bool), 1)
im = ax.imshow(np.ma.array(corr, mask=m), cmap=AZUIS, vmin=0, vmax=1)
ax.set_xticks(range(len(universo)), universo, rotation=45, ha="right")
ax.set_yticks(range(len(universo)), universo)
ax.grid(False)
for i in range(len(universo)):
    for j in range(i + 1):
        v = corr.iloc[i, j]
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8.5,
                color=FUNDO if v > 0.6 else TINTA)
for s in ax.spines.values():
    s.set_visible(False)
ax.set_title("Correlação dos retornos diários", pad=8)
fig.colorbar(im, ax=ax, shrink=0.75)
salvar(fig, "correlacao.png")

# drawdown carteira atual (pesos de hoje, rebalanceada) x IBOV
r_cart = (ret[atuais] * pos["peso"].values).sum(axis=1)
c_cart = np.exp(r_cart.cumsum()); c_ibov = np.exp(ret_ibov.reindex(r_cart.index).fillna(0).cumsum())
fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
a1.plot(c_cart.index, c_cart, color=LARANJA, lw=1.8, label="Carteira atual (pesos de hoje)")
a1.plot(c_ibov.index, c_ibov, color=CINZA, lw=1.4, label="IBOV")
a1.set_title(f"Pesos atuais aplicados nos últimos {ANOS} anos × IBOV", pad=22)
subtitulo(a1, "teste retrospectivo: os pesos foram escolhidos hoje, então isto mede o perfil de risco, não a habilidade de escolha")
a1.legend(loc="upper left", fontsize=9); a1.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.1f}x"))
for c, cor, nome in [(c_cart, LARANJA, "Carteira"), (c_ibov, CINZA, "IBOV")]:
    a2.plot(c.index, c / c.cummax() - 1, color=cor, lw=1.2)
a2.yaxis.set_major_formatter(PCT); a2.set_ylabel("Drawdown")
salvar(fig, "carteira_vs_ibov.png")

# =====================================================================================
# 4. TRADES REAIS
# =====================================================================================
print("Trades...")
rt = pd.read_csv(os.path.join(AQUI, "dados", "round_trips.csv"), parse_dates=["data_venda"])
rt = rt[rt.status != "sem_custo"].sort_values("data_venda").reset_index(drop=True)
rt["acum"] = rt["resultado"].cumsum()
fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.4), sharex=True, gridspec_kw={"height_ratios": [1.5, 1]})
a1.step(rt["data_venda"], rt["acum"], where="post", color=AZUL, lw=2)
a1.fill_between(rt["data_venda"], rt["acum"], step="post", color=AZUL, alpha=0.08)
a1.yaxis.set_major_formatter(BRL)
a1.set_title(f"Resultado realizado acumulado — {len(rt)} vendas reais "
             f"({rt.data_venda.dt.year.min()}–{rt.data_venda.dt.year.max()})", pad=22)
subtitulo(a1, "extrato de movimentação da B3 + notas de corretagem · apurado por preço médio · sem taxas")
for _, t in rt.nlargest(4, "resultado").iterrows():
    a1.annotate(f"{t.ticker} {t.resultado_pct:+.0%}", (t.data_venda, t.acum), xytext=(-8, 8),
                textcoords="offset points", ha="right", fontsize=8.5, color=TINTA)
por_dia = rt.groupby("data_venda")["resultado"].sum()
a2.bar(por_dia.index, por_dia.values, width=9, color=np.where(por_dia.values >= 0, AZUL, VERMELHO))
a2.axhline(0, color=CINZA, lw=0.8)
a2.yaxis.set_major_formatter(BRL); a2.set_ylabel("Por dia de venda")
salvar(fig, "trades_resultado.png")

anual = rt.groupby(rt.data_venda.dt.year).agg(resultado=("resultado", "sum"), vendas=("resultado", "size"),
                                              acerto=("resultado", lambda s: (s > 0).mean()))
anual.to_csv(os.path.join(SAIDA, "trades_por_ano.csv"))

# =====================================================================================
# 5. CARTEIRA ATUAL + BAZIN
# =====================================================================================
fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
ordem = pos.sort_values("valor")
a1.barh(ordem.index, ordem["valor"], color=AZUL, height=0.55)
for i, (t, r) in enumerate(ordem.iterrows()):
    a1.text(r.valor, i, f"  {r.peso:.0%} · {r.setor}", va="center", fontsize=9, color=TINTA_2)
a1.xaxis.set_major_locator(mtick.MaxNLocator(4)); a1.xaxis.set_major_formatter(BRL)
a1.set_title("Posição atual (valor de mercado)", pad=8)
a1.set_xlim(0, ordem["valor"].max() * 1.45)
lp_pct = (ordem["lp"] / ordem["custo"])
a2.barh(ordem.index, lp_pct, color=np.where(lp_pct >= 0, AZUL, VERMELHO), height=0.55)
for i, (t, v) in enumerate(lp_pct.items()):
    a2.text(v, i, f"  {v:+.1%}  (R$ {ordem.loc[t, 'lp']:+,.0f})".replace(",", "."),
            va="center", ha="left" if v >= 0 else "right", fontsize=9, color=TINTA)
a2.axvline(0, color=CINZA, lw=0.8); a2.xaxis.set_major_formatter(PCT)
a2.set_title("Lucro/prejuízo sobre o preço médio", pad=8)
lim = max(abs(lp_pct).max() * 1.9, 0.1); a2.set_xlim(-lim, lim)
salvar(fig, "carteira_atual.png")

bz = pd.DataFrame(cart["bazin"]["ativos"]).set_index("ticker")
bz_px = yf.download([t + ".SA" for t in bz.index], period="10d", auto_adjust=False, progress=False)["Close"]
bz_px = bz_px[bz_px.index < pd.Timestamp.today().normalize()].ffill().iloc[-1]
bz["cotacao"] = [float(bz_px[t + ".SA"]) for t in bz.index]
bz["margem"] = bz["teto"] / bz["cotacao"] - 1
bz = bz.sort_values("margem")
fig, ax = plt.subplots(figsize=(9, 3.8))
y = np.arange(len(bz))
ax.hlines(y, bz["teto"], bz["cotacao"], color=CINZA_CLARO, lw=3)
ax.scatter(bz["teto"], y, color=AZUL, s=70, zorder=3, label="Preço teto Bazin (DPA 5a ÷ 6%)")
ax.scatter(bz["cotacao"], y, color=LARANJA, s=70, zorder=3, label="Cotação")
for i, (t, r) in enumerate(bz.iterrows()):
    ax.text(max(r.teto, r.cotacao), i, f"   {'COMPRAR' if r.margem > 0 else 'AGUARDAR'} ({r.margem:+.0%})",
            va="center", fontsize=9, color=TINTA, fontweight="bold" if r.margem > 0 else "normal")
ax.set_yticks(y, bz.index); ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"R$ {v:.0f}"))
ax.set_xlim(0, bz[["teto", "cotacao"]].max().max() * 1.35)
ax.set_title("Preço teto (método Bazin) × cotação", pad=8)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=9)
salvar(fig, "bazin_preco_teto.png")

# =====================================================================================
# RESUMO
# =====================================================================================
resumo = {
    "data_precos": str(px.index[-1].date()),
    "patrimonio_acoes": round(patrimonio_acoes, 2),
    "caixa": cart["caixa"],
    "lucro_aberto": round(float(pos["lp"].sum()), 2),
    "markowitz": {
        "atual": {"ret": r_at, "vol": v_at, "sharpe": sh(r_at, v_at),
                  "pesos": dict(zip(atuais, np.round(w_atual, 4)))},
        "max_sharpe": {"ret": r_ms, "vol": v_ms, "sharpe": sh(r_ms, v_ms),
                       "pesos": dict(zip(universo, np.round(w_sharpe, 4)))},
        "min_var": {"ret": r_mv, "vol": v_mv, "sharpe": sh(r_mv, v_mv),
                    "pesos": dict(zip(universo, np.round(w_minvar, 4)))},
    },
    "monte_carlo": {"var95": var95, "cvar95": cvar95, "p_lucro": p_lucro, "p_bater_cdi": p_cdi,
                    "mediana_1a": float(np.median(final)), "p5_1a": float(np.percentile(final, 5)),
                    "p95_1a": float(np.percentile(final, 95))},
    "trades": {"vendas": int(len(rt)), "resultado_total": round(float(rt.resultado.sum()), 2),
               "acerto": float((rt.resultado > 0).mean()),
               "ganho_medio": float(rt.loc[rt.resultado > 0, "resultado"].mean()),
               "perda_media": float(rt.loc[rt.resultado < 0, "resultado"].mean())},
}
json.dump(resumo, open(os.path.join(SAIDA, "resumo.json"), "w", encoding="utf-8"),
          indent=2, ensure_ascii=False, default=float)
print(json.dumps(resumo, indent=2, ensure_ascii=False, default=float))
print(risco.round(3).to_string())
print(anual.to_string())
