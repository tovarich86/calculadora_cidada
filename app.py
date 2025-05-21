import pandas as pd
import requests
from datetime import datetime

def codigo_para_datetime(codigo):
    codigo_str = str(codigo)
    ano = int(codigo_str[:4])
    mes = int(codigo_str[4:6])
    return datetime(ano, mes, 1)

def carregar_dados_ipca():
    url = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/all/p/all/d/v63%202,v69%202,v2266%2013,v2263%202,v2264%202,v2265%202?formato=json"
    response = requests.get(url)
    dados_json = response.json()
    df = pd.DataFrame(dados_json[1:])  # Ignora cabeçalho
    df = df[df['D2C'] == '2266']       # Filtra número-índice IPCA
    df['data'] = df['D3C'].apply(codigo_para_datetime)
    df['valor'] = pd.to_numeric(df['V'], errors='coerce')
    df = df.sort_values('data').reset_index(drop=True)
    return df

def calcular_ipca_composto_mensal_primeiro_mes(df, data_inicial, data_final, valor_inicial):
    df_periodo = df[(df['data'] >= data_inicial) & (df['data'] <= data_final)].copy()
    if df_periodo.empty:
        return None, None, None
    df_periodo = df_periodo.sort_values('data').reset_index(drop=True)
    df_periodo['var_mes'] = df_periodo['valor'].pct_change()
    df_periodo.loc[0, 'var_mes'] = df_periodo.loc[0, 'valor'] / 100  # inflação mensal do primeiro mês
    ipca_acumulado = (1 + df_periodo['var_mes']).prod() - 1
    valor_corrigido = valor_inicial * (1 + ipca_acumulado)
    return ipca_acumulado, df_periodo, valor_corrigido

def aplicar_taxa_prefixada(valor_corrigido, taxa_aa, meses):
    taxa_mensal = (1 + taxa_aa) ** (1/12) - 1
    return valor_corrigido * ((1 + taxa_mensal) ** meses)

# Parâmetros de exemplo
valor_inicial = 1000.0
data_inicial = datetime(2023, 1, 1)
data_final = datetime(2023, 4, 1)
taxa_aa = 0.065  # 6,5% a.a.

data_inicial_dt = datetime(data_inicial.year, data_inicial.month, 1)
data_final_dt = datetime(data_final.year, data_final.month, 1)

ipca_acumulado, df_mensal, valor_corrigido_ipca = calcular_ipca_composto_mensal_primeiro_mes(
    carregar_dados_ipca(), data_inicial_dt, data_final_dt, valor_inicial
)

meses = (data_final_dt.year - data_inicial_dt.year) * 12 + (data_final_dt.month - data_inicial_dt.month)
valor_corrigido_taxa = aplicar_taxa_prefixada(valor_corrigido_ipca, taxa_aa, meses)
ipca_acumulado_taxa = (valor_corrigido_taxa / valor_inicial) - 1

# Resultados na ordem solicitada
print(f"IPCA acumulado no período: {ipca_acumulado:.4%}")
print(f"IPCA acumulado no período mais taxa prefixada: {ipca_acumulado_taxa:.4%}")
print(f"Valor corrigido pelo IPCA: R$ {valor_corrigido_ipca:.2f}")
print(f"Valor corrigido pelo IPCA mais taxa prefixada: R$ {valor_corrigido_taxa:.2f}")
print("\nValores mensais do IPCA no período:")
print(df_mensal[['data', 'valor', 'var_mes']].rename(
    columns={'data': 'Data', 'valor': 'Índice IPCA', 'var_mes': 'Variação Mensal'}
))
