import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# Função para converter código AAAAMM em datetime
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
    indice_mes_anterior = buscar_indice_mes_anterior(df, data_inicial)
    df_periodo = df[(df['data'] >= data_inicial) & (df['data'] <= data_final)].copy()
    if df_periodo.empty or indice_mes_anterior is None:
        return None, None, None, None
    df_periodo = df_periodo.sort_values('data').reset_index(drop=True)
    df_periodo['var_mes'] = df_periodo['valor'].pct_change()
    df_periodo.loc[0, 'var_mes'] = (df_periodo.loc[0, 'valor'] / indice_mes_anterior) - 1
    ipca_acumulado = (df_periodo.iloc[-1]['valor'] / indice_mes_anterior) - 1
    valor_corrigido = valor_inicial * (1 + ipca_acumulado)
    return ipca_acumulado, df_periodo, valor_corrigido, indice_mes_anterior

def aplicar_taxa_prefixada(valor_corrigido, taxa_aa, meses):
    taxa_mensal = (1 + taxa_aa) ** (1/12) - 1
    return valor_corrigido * ((1 + taxa_mensal) ** meses)

def formatar_moeda(valor):
    return f'R$ {valor:,.4f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

def formatar_percentual(valor):
    return f'{valor*100:.4f}%'

def converter_taxa_aa_input(taxa_input):
    if isinstance(taxa_input, str):
        taxa_input = taxa_input.replace(',', '.')
        try:
            taxa_float = float(taxa_input)
            return taxa_float / 100
        except ValueError:
            st.error('Taxa anual prefixada inválida. Use números com vírgula ou ponto.')
            return None
    elif isinstance(taxa_input, (int, float)):
        return taxa_input / 100
    else:
        st.error('Taxa anual prefixada inválida.')
        return None

# Interface Streamlit
st.set_page_config(page_title="Calculadora de Correção pelo IPCA", layout="centered")
st.title('Calculadora de Correção pelo IPCA (dados IBGE/SIDRA)')

df_ipca = carregar_dados_ipca()
DATA_INICIAL_SERIE = df_ipca['data'].min().date()
DATA_FINAL_SERIE = df_ipca['data'].max().date()

data_inicial = st.date_input(
    'Data inicial',
    value=DATA_INICIAL_SERIE,
    min_value=DATA_INICIAL_SERIE,
    max_value=DATA_FINAL_SERIE,
    format="DD/MM/YYYY"
)
data_final = st.date_input(
    'Data final',
    value=DATA_FINAL_SERIE,
    min_value=DATA_INICIAL_SERIE,
    max_value=DATA_FINAL_SERIE,
    format="DD/MM/YYYY"
)
valor_inicial = st.number_input('Valor a ser corrigido (R$)', min_value=0.0, value=1000.0, format="%.2f")
taxa_aa_str = st.text_input('Taxa prefixada anual (%)', value='0,0')
taxa_aa = converter_taxa_aa_input(taxa_aa_str)

data_inicial_dt = datetime(data_inicial.year, data_inicial.month, 1)
data_final_dt = datetime(data_final.year, data_final.month, 1)

if taxa_aa is not None:
    if data_inicial_dt > data_final_dt:
        st.error('A data inicial não pode ser posterior à data final.')
    else:
        ipca_acumulado, df_mensal, valor_corrigido_ipca, indice_mes_anterior = calcular_ipca(
            df_ipca, data_inicial_dt, data_final_dt, valor_inicial
        )
        if ipca_acumulado is not None:
            meses = (data_final_dt.year - data_inicial_dt.year) * 12 + (data_final_dt.month - data_inicial_dt.month)
            valor_corrigido_taxa = aplicar_taxa_prefixada(valor_corrigido_ipca, taxa_aa, meses)
            ipca_acumulado_taxa = (valor_corrigido_taxa / valor_inicial) - 1

            st.markdown(f"**IPCA acumulado no período:** {formatar_percentual(ipca_acumulado)}")
            st.markdown(f"**IPCA acumulado no período mais taxa prefixada:** {formatar_percentual(ipca_acumulado_taxa)}")
            st.markdown(f"**Valor corrigido pelo IPCA:** {formatar_moeda(valor_corrigido_ipca)}")
            st.markdown(f"**Valor corrigido pelo IPCA mais taxa prefixada:** {formatar_moeda(valor_corrigido_taxa)}")
            st.markdown("**Valores mensais do IPCA no período:**")

            df_mensal_pt = df_mensal[['data', 'valor', 'var_mes']].copy()
            df_mensal_pt['data'] = df_mensal_pt['data'].dt.strftime('%m/%Y')
            df_mensal_pt['valor'] = df_mensal_pt['valor'].map(lambda x: f'{x:.2f}')
            df_mensal_pt['var_mes'] = df_mensal_pt['var_mes'].map(lambda x: f'{x*100:.2f}%' if pd.notnull(x) else '')
            df_mensal_pt = df_mensal_pt.rename(
                columns={'data': 'Mês/Ano', 'valor': 'Índice IPCA', 'var_mes': 'Variação Mensal'}
            ).set_index('Mês/Ano')
            st.dataframe(df_mensal_pt)
        else:
            st.warning('Não há dados disponíveis para o período selecionado ou para o mês anterior ao inicial.')
