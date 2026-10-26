# In[ ]:


import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time


# In[ ]:


time.sleep(5)

url = "https://www.fundamentus.com.br/resultado.php"

session = requests.Session()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": "https://www.fundamentus.com.br/",
    "Origin": "https://www.fundamentus.com.br",
    "Content-Type": "application/x-www-form-urlencoded",
    "Connection": "keep-alive"
}

session.headers.update(headers)

data = {
    "liq_min": "300000"
}

def pegar_html():
    for i in range(5):
        try:
            response = session.post(url, data=data, timeout=10)

            if response.status_code == 200 and "<table" in response.text:
                print("✅ Dados obtidos")
                return response.text

            else:
                print(f"Tentativa {i+1} falhou")

        except Exception as e:
            print(f"Erro: {e}")

        time.sleep(5)

    return None


html = pegar_html()

# 🔥 fallback (IMPORTANTE)
if html is None:
    print("⚠️ Tentando via GET (fallback)...")

    try:
        response = session.get(url, timeout=10)
        html = response.text

        if "<table" not in html:
            raise Exception("Ainda bloqueado")

    except:
        raise Exception("❌ Fundamentus bloqueou completamente no GitHub")


# In[ ]:


soup = BeautifulSoup(html, "html.parser")

tabela_html = soup.find("table")

if tabela_html is None:
    raise Exception("❌ Não encontrou tabela — bloqueio ativo")
else:
    print("✅ Tabela encontrada")


# In[ ]:


headers_html = tabela_html.find("tr").find_all("th")
colunas_nomes = [h.text.strip() for h in headers_html]


# In[ ]:


try:
    idx_papel = colunas_nomes.index("Papel")
    idx_ev_ebit = colunas_nomes.index("EV/EBIT")
    idx_roic = colunas_nomes.index("ROIC")
except ValueError:
    raise Exception("Estrutura do site mudou ❌")


# In[ ]:


linhas = tabela_html.find_all("tr")[1:]

dados = []

for linha in linhas:
    colunas = linha.find_all("td")

    if len(colunas) < len(colunas_nomes):
        continue

    try:
        papel = colunas[idx_papel].text.strip()
        ev_ebit = colunas[idx_ev_ebit].text.strip()
        roic = colunas[idx_roic].text.strip()

        dados.append([papel, ev_ebit, roic])
    except:
        continue


# In[ ]:


tabela = pd.DataFrame(dados, columns=["Papel", "EV/EBIT", "ROIC"])


# In[ ]:


def limpar_numero(valor):
    try:
        valor = str(valor).strip().replace('%', '')

        if ',' in valor and '.' in valor:
            valor = valor.replace('.', '').replace(',', '.')
        elif ',' in valor:
            valor = valor.replace(',', '.')

        return float(valor)
    except:
        return None


# In[ ]:


tabela["ROIC"] = tabela["ROIC"].apply(limpar_numero)
tabela["EV/EBIT"] = tabela["EV/EBIT"].apply(limpar_numero)


# In[ ]:


tabela = tabela[
    (tabela["EV/EBIT"] > 0) &
    (~tabela["ROIC"].isna())
].copy()


# In[ ]:


tabela["clas 1"] = tabela["EV/EBIT"].rank(ascending=True, method="min")
tabela["clas 2"] = tabela["ROIC"].rank(ascending=False, method="min")
tabela["clas final"] = tabela["clas 1"] + tabela["clas 2"]
tabela["rank"] = tabela["clas final"].rank(ascending=True, method="min")


# In[ ]:


tabela = tabela.sort_values("rank")


# In[ ]:


hoje = datetime.now().strftime("%Y-%m-%d")
nome_arquivo = f"magic-formula-{hoje}.xlsx"

tabela.to_excel(nome_arquivo, index=False)


# In[ ]:


print(tabela.head(10))
print(f"\nArquivo '{nome_arquivo}' criado com sucesso ✅")

