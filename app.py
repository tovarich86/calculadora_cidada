import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

def codigo_para_datetime(codigo):
    codigo_str = str(codigo)
    ano = int(codigo_str[:4])
    mes = int(codigo_str[4:6])
    return datetime(ano, mes, 1)

@st.cache_data
def carregar_dados_ipca():
    url = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/all/p/all/d/v63%202,v69%202,v2266%2013,v2263%202,v2264%202,v2265%202?formato=json"
    response = requests.get(url)
    dados_json = response.json()
    df = pd.DataFrame(dados_json[1:])
    df = df[df['D2C'] == '2266']
    df['data'] = df['D3C'].apply(codigo_para_datetime)
    df['valor'] = pd.to_numeric(df['V'], errors='coerce')
    df = df.sort_values('data').reset_index(drop=True)
    return df

def buscar_indice_mes_anterior(df, data_inicial):
    mes_anterior = data_inicial - timedelta(days=1)
    mes_anterior = datetime(mes_anterior.year, mes_anterior.month, 1)
    indice = df[df['data'] == mes_anterior]['valor']
    if not indice.empty:
        return indice.values[0]
    else:
        return None

def calcular_ipca(df, data_inicial, data_final, valor_inicial):
    # Busca índice do mês anterior ao mês inicial
    indice_mes_anterior = buscar_indice_mes_anterior(df, data_inicial)
    df_periodo = df[(df['data'] >= data_inicial) & (df['data'] <= data_final)].copy()
    if df_periodo.empty or indice_mes_anterior is None:
        return None, None, None, None
    df_periodo = df_periodo.sort_values('data').reset_index(drop=True)
    # Calcula variação mensal corretamente
    df_periodo['var_mes'] = df_periodo['valor'].pct_change()
    # Corrige o primeiro mês: variação em relação ao mês anterior ao período
    df_periodo.loc[0, 'var_mes'] = (df_periodo.loc[0, 'valor'] / indice_mes_anterior) - 1
    # Acumulado: índice final / índice mês anterior ao inicial - 1
    ipca_acumulado = (df_periodo.iloc[-1]['valor'] / indice_mes_anterior) - 1
    valor_corrigido = valor_inicial * (1 + ipca_acumulado)
    return ipca_acumulado, df_periodo, valor_corrigido, indice_mes_anterior

def aplicar_taxa_prefixada(valor_corrigido, taxa_aa, meses):
    taxa_mensal = (1 + taxa_aa) ** (1/12) - 1
    return valor_corrigido * ((1 + taxa_mensal) ** meses)

# Interface Streamlit
st.title('Calculadora de Correção pelo IPCA (dados IBGE/SIDRA)')

df_ipca = carregar_dados_ipca()
DATA_INICIAL_SERIE = df_ipca['data'].min().date()
DATA_FINAL_SERIE = df_ipca['data'].max().date()

data_inicial = st.date_input(
    'Data Inicial',
    value=DATA_INICIAL_SERIE,
    min_value=DATA_INICIAL_SERIE,
    max_value=DATA_FINAL_SERIE
)
data_final = st.date_input(
    'Data Final',
    value=DATA_FINAL_SERIE,
    min_value=DATA_INICIAL_SERIE,
    max_value=DATA_FINAL_SERIE
)
valor_inicial = st.number_input('Valor a ser corrigido', min_value=0.0, value=1000.0)
taxa_aa = st.number_input('Taxa anual prefixada (%)', min_value=0.0, value=0.0) / 100

data_inicial_dt = datetime(data_inicial.year, data_inicial.month, 1)
data_final_dt = datetime(data_final.year, data_final.month, 1)

if data_inicial_dt > data_final_dt:
    st.error('Data inicial não pode ser superior à data final.')
else:
    ipca_acumulado, df_mensal, valor_corrigido_ipca, indice_mes_anterior = calcular_ipca(
        df_ipca, data_inicial_dt, data_final_dt, valor_inicial
    )
    if ipca_acumulado is not None:
        meses = (data_final_dt.year - data_inicial_dt.year) * 12 + (data_final_dt.month - data_inicial_dt.month)
        valor_corrigido_taxa = aplicar_taxa_prefixada(valor_corrigido_ipca, taxa_aa, meses)
        ipca_acumulado_taxa = (valor_corrigido_taxa / valor_inicial) - 1

        st.write(f'IPCA acumulado no período: {ipca_acumulado:.4%}')
        st.write(f'IPCA acumulado no período mais taxa prefixada: {ipca_acumulado_taxa:.4%}')
        st.write(f'Valor corrigido pelo IPCA: R$ {valor_corrigido_ipca:.2f}')
        st.write(f'Valor corrigido pelo IPCA mais taxa prefixada: R$ {valor_corrigido_taxa:.2f}')
        st.write('Valores mensais do IPCA no período:')
        st.dataframe(df_mensal[['data', 'valor', 'var_mes']].rename(
            columns={'data': 'Data', 'valor': 'Índice IPCA', 'var_mes': 'Variação Mensal'}
        ).set_index('Data'))
    else:
        st.warning('Não há dados disponíveis para o período selecionado ou para o mês anterior ao inicial.')
