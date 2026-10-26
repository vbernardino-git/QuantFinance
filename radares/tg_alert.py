import pandas as pd
import yfinance as yf
import requests
import glob
import os

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def enviar_mensagem(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg
    }
    requests.post(url, data=payload)


def get_tickers():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    arquivos = glob.glob(os.path.join(BASE_DIR, "magic-formula-*.xlsx"))

    if not arquivos:
        raise FileNotFoundError(f"Nenhum arquivo Excel encontrado em {BASE_DIR}")

    arquivo_mais_recente = max(arquivos, key=os.path.getmtime)

    df = pd.read_excel(arquivo_mais_recente)

    top10 = df.head(10)

    tickers = top10["Papel"].tolist()

    return [t + ".SA" for t in tickers]


if __name__ == "__main__":

    tickers = get_tickers()

    dados = yf.download(tickers, period="1y", auto_adjust=True)["Close"]

    mensagem_final = "📊 ALERTAS MAGIC FORMULA\n\n"

    for ticker in tickers:
        try:
            serie = dados[ticker].dropna()

            preco = serie.iloc[-1]
            mm21 = serie.rolling(21).mean().iloc[-1]
            mm200 = serie.rolling(200).mean().iloc[-1]

            max_52s = serie.max()
            max_6m = serie[-126:].max()

            alertas = []

            if preco < mm21:
                alertas.append("⚠️ MM21")

            if preco < mm200:
                alertas.append("🚨 MM200")

            if preco <= max_52s * 0.75:
                alertas.append("💰 25% abaixo da máx 52s")

            if preco <= max_6m * 0.80:
                alertas.append("📉 20% abaixo da máx 6m")

            if alertas:
                mensagem_final += f"{ticker} ({preco:.2f}) → {', '.join(alertas)}\n"

        except Exception:
            mensagem_final += f"{ticker} erro ao processar\n"

    if mensagem_final.strip() != "📊 ALERTAS MAGIC FORMULA":
        enviar_mensagem(mensagem_final)
        print("Mensagem enviada!")
    else:
        print("Nenhum alerta hoje.")