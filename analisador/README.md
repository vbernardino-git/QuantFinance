# 📊 Analisador Profissional de Ações — B3

Programa **unificado** que junta, num só lugar e com **execução simplificada**, todas as
metodologias dos seus projetos de mercado financeiro. Analisa **uma ação** ou **uma lista**
(digitada por você ou **vinda do Radar M34**) e entrega um **veredito único de 0 a 100**
(COMPRA FORTE → VENDA FORTE), com o racional detalhado de cada método.

---

## 🚀 Como usar (simples)

**Duplo-clique no `ANALISAR.bat`.** Na primeira vez ele instala o que falta (uma vez só) e
abre o menu:

```
  1 — Uma ação (digite o código)
  2 — Uma lista de ações (você digita)
  3 — Lista do Radar M34 (roda o radar agora e analisa os sinais)
  4 — IBOV inteiro (~89 ações, demorado)
  0 — Sair
```

### Pela linha de comando (opcional)
```bat
python analisar.py PETR4              ::  uma ação
python analisar.py PETR4 VALE3 ITUB4  ::  várias
python analisar.py --radar            ::  roda o Radar M34 e analisa os sinais
python analisar.py --ibov             ::  IBOV inteiro
```

Cada execução salva também um **CSV consolidado** em `resultados\` (uma linha por ação,
todos os indicadores e scores — ótimo pra filtrar e comparar no Excel).

---

## 🧠 As 9 metodologias unificadas e o embasamento

O veredito segue a **filosofia equilibrada** de um gestor multiestratégia:

| Pilar | Peso | O que entra | Embasamento (livros/autores) |
|---|---|---|---|
| **Fundamentos** | **40%** | Qualidade (ROE/ROIC/margens), Valuation (P/L, P/VP, EV/EBIT, FCF yield, earnings yield), Saúde (dívida/PL, liquidez), Crescimento (CAGR receita/lucro) | Benjamin **Graham** & Dodd — *Security Analysis* / *O Investidor Inteligente*; Joel **Greenblatt** — *The Little Book That Beats the Market* (Magic Formula: EV/EBIT + ROIC); Warren **Buffett** (qualidade/moat); Aswath **Damodaran** (valuation) |
| **Técnico + Quant** | **35%** | ANATEC + Modelo 34 (seu setup: candles + MME34 + Estocástico + ADX/DI + TRIX), EMAs 9/21/50/200, Bollinger, RSI/MACD; + **ML LightGBM** multi-fator com validação *walk-forward* e *Information Coefficient* | Alexander **Elder** — *Trading for a Living*; Thomas **Bulkowski** — *Encyclopedia of Candlestick Charts*; John **Bollinger**; Gerald **Appel** (MACD); Marcos **López de Prado** — *Advances in Financial ML* (walk-forward, IC); **Grinold & Kahn** (IC) |
| **Regime + Risco** | **25%** | Markov Switching (prob. filtrada, sem look-ahead) diário e intraday 15m; HMM/KMeans 3 estados; Sharpe/Sortino/Max Drawdown/Beta; **Monte Carlo GBM** (VaR, CVaR/ES, prob. de lucro) | James D. **Hamilton** — *Regime-Switching*; **Rabiner** (HMM); William **Sharpe**; Harry **Markowitz** — *Portfolio Selection*; John **Hull** — *Options, Futures*; **Glasserman** (Monte Carlo) |

> O score de cada pilar é **reescalado automaticamente** quando algum dado falta (ex.: banco
> sem EV/EBIT), então o veredito nunca quebra — apenas indica a cobertura de dados.

### Faixas do veredito
| Score | Veredito |
|---|---|
| ≥ 75 | **COMPRA FORTE** |
| 60–74 | **COMPRA** |
| 45–59 | **NEUTRO** |
| 30–44 | **VENDA** |
| < 30 | **VENDA FORTE** |

---

## 🛰️ Integração com o Radar M34

A opção **3** (ou `--radar`) executa o seu `Radar_ANATEC_IBOV.exe --once`, captura em tempo
real os ativos que deram **sinal de compra/venda** no último candle e manda esses ativos
direto pra análise completa. O programa procura o exe em:

- `…\Downloads\Radar_ANATEC_IBOV.exe`
- `…\Downloads\_radar_build\dist\Radar_ANATEC_IBOV.exe`

Se não achar (ou se quiser editar), ajuste `CAMINHOS_RADAR_EXE` em `nucleo/config.py`.

---

## 🗂️ Estrutura

```
Analisador/
├─ ANALISAR.bat          ← duplo-clique pra rodar
├─ analisar.py           ← orquestrador + menu
├─ requirements.txt
├─ resultados/           ← CSVs consolidados (gerados a cada execução)
└─ nucleo/
   ├─ config.py          ← todos os parâmetros ajustáveis
   ├─ universo.py        ← IBOV + normalização de tickers
   ├─ dados.py           ← download de preços + fundamentos (yfinance)
   ├─ tecnico.py         ← ANATEC+M34, Bollinger, EMAs, RSI/MACD → score técnico
   ├─ fundamentos.py     ← Graham/Greenblatt/Buffett → score fundamentalista
   ├─ regime.py          ← Markov + HMM/KMeans → score de regime
   ├─ ml.py              ← LightGBM walk-forward → previsão + score
   ├─ montecarlo.py      ← GBM: VaR/CVaR/prob. de lucro
   ├─ risco.py           ← Sharpe/Sortino/Drawdown/Beta
   ├─ veredito.py        ← combina tudo no score 0-100
   └─ relatorio.py       ← relatório rico no terminal + export CSV
```

## ⚙️ Ajustes
Tudo que é "calibrável" mora em `nucleo/config.py`: pesos do veredito, ADX mínimo, EMA do
Modelo 34, parâmetros do ML, número de simulações Monte Carlo, etc.

## ⚠️ Observações
- Dados via **Yahoo Finance** (gratuito); fundamentos de bancos/ETFs podem vir incompletos —
  o programa trata isso sem quebrar.
- `hmmlearn` é **opcional**. Se não instalar no Python 3.14, o pilar de regime usa
  automaticamente **KMeans + Markov** (sem perda de funcionamento).
- Ferramenta de **apoio à decisão** e estudo — não é recomendação de investimento.
