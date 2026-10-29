# QuantFinance

**O laboratório quantitativo que eu uso para montar e gerir a minha carteira de ações real na B3:** otimização de Markowitz, Monte Carlo, detecção de regime (Markov/HMM), machine learning, valuation e um analisador que junta tudo num veredito de 0 a 100.

Todos os números e gráficos abaixo vêm **da minha carteira e das minhas operações de verdade**: extrato de movimentação da B3 (2025–2026), notas de corretagem e a posição atual na corretora.

![Python](https://img.shields.io/badge/python-3.14-blue) ![dados](https://img.shields.io/badge/dados-Yahoo%20%C2%B7%20BCB%20%C2%B7%20B3%20%C2%B7%20StatusInvest-lightgrey) [![Contato: LinkedIn](https://img.shields.io/badge/contato-LinkedIn-0a66c2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/viniciusbernardino01/) [![Instagram @vnbernardino](https://img.shields.io/badge/instagram-%40vnbernardino-C13584?logo=instagram&logoColor=white)](https://www.instagram.com/vnbernardino/)

---

## Resultados em 30 segundos

| | |
|---|---|
| **Operações reais analisadas** | 45 ordens · **21 vendas** · jan/2025 → out/2026 |
| **Resultado realizado** | **+13,4%** (≈ 4,7% a.m.) sobre o custo das posições vendidas (preço médio, sem taxas) · acerto de **76%** |
| **Por ano** | 2025: **0,0%** (0,0% a.m.) · 2026: **+22,9%** (≈ 5,3% a.m.), 8 vendas, todas no lucro |
| **Melhores trades** | TOTS3 **+35%** (≈ 5,5% a.m.) e EQTL3 **+37%** (≈ 19% a.m.), out/2026 · PETR4 **+22,7%** (≈ 4,2% a.m.), fev/2026 |
| **Referência: CDI** | 14,15% a.a. (1,11% a.m.) |
| **Carteira atual** | CPLE3 · ITSA4 · VIVT3 · PSSA3 (+ caixa) · **+11,4%** sobre o custo |
| **Markowitz** | carteira atual: Sharpe **0,73** · o máximo Sharpe da fronteira: **0,87** com a mesma vol (18%) |
| **Monte Carlo (1 ano, 10 mil caminhos)** | VaR 95% **−3,5%** (−0,3% a.m.) · CVaR 95% **−10,9%** (−1,0% a.m.) · P(bater o CDI) **76%** |
| **Pesos atuais × IBOV (3 anos)** | **2,3x contra 1,8x** do IBOV no mesmo período (≈ 2,3% a.m. contra 1,6% a.m.) |

> Valores de out/2026. **a.m.** = taxa mensal composta equivalente: (1 + retorno)^(1/meses) − 1. Nos trades, "meses" é o tempo que cada posição ficou na carteira; no agregado, é o prazo médio ponderado pelo custo. Para reproduzir: `python carteira/analise_carteira.py` (preços atualizados do Yahoo).

---

## 1. Meus trades reais

![Resultado realizado acumulado](docs/img/trades_resultado_rs.png)

Cada degrau é uma venda real. A apuração usa **preço médio ponderado** (a regra da Receita, igual ao que a corretora informa), não FIFO. 2025 foi o ano de ajuste: limpei posições antigas que não faziam sentido (RANI3, SOJA3, BBAS3) e girei muito em operações curtas. Em 2026 mudei o processo — menos operações, mais convicção, decisão apoiada nas ferramentas deste repositório — e o resultado realizado do ano chegou a **+22,9% em 8 vendas, todas no lucro**.

| Ano | Vendas | Ganhos | Perdas | Resultado | Prazo médio | a.m. | Acerto |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025 | 13 | +2,3% | −2,2% | **0,0%** | 1,0 mês | 0,0% | 62% |
| **2026** | **8** | **+22,9%** | **0,0%** | **+22,9%** | **4,0 meses** | **≈ 5,3%** | **100%** |
| Total | 21 | +14,3% | −0,9% | +13,4% | 2,7 meses | ≈ 4,7% | 76% |

Como sai o resultado: **lucro das vendas ÷ custo das vendas**, então cada venda pesa pelo dinheiro que estava nela. Ganhos e perdas estão na mesma base (% do custo total do ano). Em 2025 os ganhos (+2,3%) foram praticamente anulados pelas perdas da limpeza de janeiro (SOJA3 −21%, RANI3 −15%, BBAS3 −8%), o que dá **0,0%**. Em 2026 não teve perda, e as três posições grandes (PETR4, TOTS3, EQTL3) carregaram o resultado. CDI de referência: 1,11% a.m.

### Petrobras (PETR4): a posição do fim de 2025

Montei a posição de PETR4 em duas compras, em set/25 e dez/25. Enquanto segurava, deixei as ações no aluguel (BTC). Saí na alta de fevereiro, em duas vendas (05/02 e 13/02/2026). Resultado: **+22,7%** em cerca de 5 meses (≈ 4,2% a.m.). Somando os proventos que o aluguel reembolsou (fev–mar/26), o ganho total da posição foi de **+25%** (≈ 4,6% a.m.).

> No extrato da B3 o aluguel aparece como "Liquidação": a ação emprestada sai **sem preço** e volta dias depois com a mesma quantidade. O `trades_b3.py` casa cada saída sem preço com a devolução seguinte e tira o par do cálculo, porque não é compra nem venda. Conferi contra o extrato da conta no Inter: as devoluções não movimentam caixa, só as compras e as vendas de verdade.

### TOTS3 e EQTL3: por que vendi em outubro

Em 20/10/2026 vendi as duas de uma vez: **TOTS3 com +35%** em ~5,5 meses (≈ 5,5% a.m.) e **EQTL3 com +37%** em ~1,8 mês (≈ 19% a.m.), sobre o preço médio. Três motivos:

1. **Pagavam pouco dividendo.** As duas são teses de crescimento, não de renda, e não se encaixam na estratégia de dividendos da carteira (BESST + Bazin).
2. **Concentravam o ganho.** Sozinhas, sustentavam a maior parte da valorização da carteira. Se elas devolvessem a alta, a carteira inteira devolveria junto.
3. **Risco eleitoral (o principal).** Na reta final da eleição presidencial de 2026 eu vi risco de volatilidade forte na bolsa. Preferi realizar o lucro antes do resultado em vez de apostar no desfecho.
4. **A tese da TOTS3 tinha se esgotado.** Comprei olhando o P/VP: em 2026 o papel negociava a um P/VP bem abaixo do de 2021, e a tese era essa diferença fechar. Com a alta, o P/VP deixou de ser atraente e não sobrou margem para justificar ficar na posição.

Base: [`carteira/dados/round_trips.csv`](carteira/dados/round_trips.csv) · motor: [`carteira/trades_b3.py`](carteira/trades_b3.py)

## 2. A carteira hoje

![Carteira atual](docs/img/carteira_atual.png)

Estratégia: **BESST** do Barsi (Bancos, Energia, Saneamento, Seguros, Telecom) + dividendos, com preço de entrada pelo **método Bazin**.

![Preço teto Bazin](docs/img/bazin_preco_teto.png)

## 3. Markowitz — a fronteira eficiente da minha carteira

![Fronteira eficiente](docs/img/markowitz_fronteira.png)

Fronteira calculada com 3 anos de retornos diários dos 4 papéis que tenho + os 4 candidatos que estudei para a última troca, **long-only e com teto de 40% por papel** (sem o teto, o otimizador concentra tudo em 1–2 ações, o que ninguém deveria fazer na vida real). Taxa livre de risco = CDI (14,15% a.a., 1,11% a.m.).

![Pesos atual x ótimo](docs/img/markowitz_pesos.png)

O que eu tirei disso: a minha carteira está **perto da fronteira** (mesma vol do máximo Sharpe, ~2 p.p. a menos de retorno: 27,6% × 30,0% a.a., ou 2,06% × 2,21% a.m.). O otimizador zera VIVT3 (o pior Sharpe dos 4 que tenho) e pede mais PSSA3, que tem uma das **menores correlações** com o resto:

![Correlação](docs/img/correlacao.png)

## 4. Monte Carlo — 10.000 futuros possíveis para a carteira

![Monte Carlo](docs/img/monte_carlo_carteira.png)

GBM **multivariado**: os choques diários são correlacionados via **decomposição de Cholesky** da matriz de covariância real, então o modelo sabe que CPLE3 e ITSA4 tendem a cair juntas. Daí sai o VaR/CVaR da carteira inteira, não de cada ação isolada.

> **Ressalva honesta:** o drift é a média histórica de 3 anos (~28% a.a., ~2,1% a.m.), um período bom para esses papéis. O número que eu levo a sério é a **cauda** (CVaR −10,9% em 1 ano, −1,0% a.m.), não a mediana.

Também rodo o Monte Carlo papel a papel. O da TOTS3 ([notebook 01](notebooks/01_monte_carlo_gbm.ipynb)), rodado em jun/2026 com o papel uns 5% abaixo do meu preço médio, dava a média ~15% acima do preço da época e o percentil 95 perto do dobro. Vendi em outubro com **+35%** (≈ 5,5% a.m.), dentro do cone:

![Monte Carlo TOTS3](docs/img/notebooks/01_monte_carlo_gbm_2.png)

## 5. Risco: pesos de hoje × IBOV

![Carteira vs IBOV](docs/img/carteira_vs_ibov.png)

| Papel | Ret. a.a. | Ret. a.m. | Vol a.a. | Sharpe | Sortino | Beta IBOV | Máx. DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| CPLE3 | 30,3% | 2,23% | 22,8% | 0,71 | 1,20 | 0,98 | −17,9% |
| ITSA4 | 31,3% | 2,30% | 22,2% | 0,77 | 1,30 | 1,17 | −19,3% |
| VIVT3 | 17,9% | 1,38% | 24,2% | 0,16 | 0,21 | 0,72 | −28,5% |
| PSSA3 | 28,9% | 2,14% | 23,9% | 0,62 | 0,90 | 0,68 | −19,3% |

Tabela completa (com os candidatos): [`resultados/risco_por_ativo.csv`](resultados/risco_por_ativo.csv)

## 6. Analisador — 9 metodologias, 1 veredito

Antes de comprar qualquer papel, eu rodo o `analisar.py`. Ele junta fundamentos, técnica, ML, regime e risco num score de 0 a 100. Saída real, rodada na minha carteira:

![Analisador - ranking da carteira](docs/img/analisador_carteira.svg)

<details>
<summary><b>Relatório completo de um papel (CPLE3)</b></summary>

![Analisador CPLE3](docs/img/analisador_CPLE3.svg)

</details>

| Pilar | Peso | Métodos | Base teórica |
|---|---:|---|---|
| Fundamentos | 40% | qualidade, valuation, saúde, crescimento; Magic Formula | Graham, Greenblatt, Buffett, Damodaran |
| Técnico + Quant | 35% | ANATEC + Modelo 34, EMAs, Bollinger, RSI/MACD; **LightGBM walk-forward** com Information Coefficient | Elder, Bollinger, López de Prado, Grinold & Kahn |
| Regime + Risco | 25% | **Markov switching** (prob. filtrada, sem look-ahead), **HMM/KMeans**, Sharpe/Sortino/DD/Beta, **Monte Carlo** (VaR/CVaR) | Hamilton, Rabiner, Sharpe, Markowitz, Hull, Glasserman |

Detalhes: [`analisador/README.md`](analisador/README.md)

---

## O que os dados me ensinaram

1. **No Brasil, o benchmark é o CDI, não o IBOV.** Toda decisão aqui é medida contra a Selic do mesmo período, e Sharpe e drawdown pesam tanto quanto o retorno.
2. **Giro alto não paga.** 13 vendas em 2025 deram 0,0% (0,0% a.m.); 8 vendas com mais convicção em 2026 deram +22,9% (≈ 5,3% a.m., contra 1,11% a.m. do CDI).
3. **Markowitz sem restrição é inútil na prática.** O teto de 40% por papel é o que torna a resposta utilizável.
4. **Média de dividendos engana.** A média de DPA de 5 anos infla quem cortou dividendo ou teve um ano extraordinário. Antes de confiar no preço teto, confiro a renda conservadora = mín(média de 5 anos, últimos 12 meses) e a tendência do DPA.

---

## Estrutura

```
QuantFinance/
├─ carteira/                    ← a MINHA carteira
│  ├─ analise_carteira.py       ← Markowitz + Monte Carlo + risco + trades + Bazin → docs/img
│  ├─ trades_b3.py              ← extrato da B3 → ordens + resultado por preço médio
│  ├─ modelo_preco.py           ← ponto de compra estatístico (z-scores de preço, percentil, DY, drawdown) + backtest
│  ├─ proventos.py · selic.py   ← proventos (StatusInvest) e Selic acumulada (BCB SGS 4390)
│  └─ dados/                    ← carteira.json, trades.csv, round_trips.csv, selic_mensal.json
├─ analisador/                  ← analisador unificado (9 métodos → veredito 0-100)
│  ├─ analisar.py · ANALISAR.bat
│  └─ nucleo/                   ← tecnico, fundamentos, regime, ml, montecarlo, risco, veredito...
├─ notebooks/
│  ├─ 01_monte_carlo_gbm        ← GBM, VaR/CVaR por ativo
│  ├─ 02_ml_return_predictor    ← previsão de retorno multi-fator
│  └─ 03_lbo_model              ← modelo de LBO (valuation)
├─ radares/                     ← scanners do IBOV em tempo real (Markov, ANATEC/M34) com alerta no Telegram,
│                                  Magic Formula (Fundamentus) e agenda/arbitragem de proventos
├─ resultados/                  ← resumo.json, risco_por_ativo.csv, trades_por_ano.csv
└─ docs/img/                    ← todos os gráficos deste README
```

## Como rodar

```bash
pip install -r requirements.txt

python carteira/analise_carteira.py              # refaz todos os gráficos da carteira
python carteira/trades_b3.py movimentacao.xlsx   # extrato da Área do Investidor B3 → trades
python analisador/analisar.py PETR4 VALE3        # veredito 0-100
python radares/radar_markov_ibov.py --once       # varredura de regime no IBOV
```

Os radares mandam alerta no Telegram se as variáveis `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID` estiverem definidas; sem elas, só imprimem no terminal.

**Fontes (todas gratuitas):** Yahoo Finance (preços), Banco Central SGS 12/4390 (CDI/Selic), Área do Investidor B3 (operações), StatusInvest e Fundamentus (fundamentos e proventos).

---

**Quer conversar sobre o projeto ou uma vaga?** Me chama no [LinkedIn](https://www.linkedin.com/in/viniciusbernardino01/) ou no Instagram [@vnbernardino](https://www.instagram.com/vnbernardino/).

*Projeto pessoal de estudo. Nada aqui é recomendação de investimento.*
