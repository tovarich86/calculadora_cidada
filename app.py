import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# Datas limites conhecidas para o IPCA (ajuste conforme atualização da série)
DATA_INICIAL_SERIE = datetime(1980, 1, 1)
DATA_FINAL_SERIE = datetime.today()

def validar_datas(data_inicial, data_final):
    # Ajusta datas para o range disponível na série
    if data_inicial < DATA_INICIAL_SERIE:
        st.warning(f'Data inicial ajustada para {DATA_INICIAL_SERIE.strftime("%d/%m/%Y")} (início da série).')
        data_inicial = DATA_INICIAL_SERIE
    if data_final > DATA_FINAL_SERIE:
        st.warning(f'Data final ajustada para {DATA_FINAL_SERIE.strftime("%d/%m/%Y")} (último dado disponível).')
        data_final = DATA_FINAL_SERIE
    if data_inicial > data_final:
        st.error('Data inicial não pode ser superior à data final.')
        return None, None
    # Limite de 10 anos por requisição
    anos = (data_final.year - data_inicial.year) + ((data_final.month - data_inicial.month) / 12)
    if anos > 10:
        st.error('O intervalo máximo permitido pela API é de 10 anos.')
        return None, None
    return data_inicial, data_final

def get_ipca_data(data_inicial, data_final):
    # Formata datas para dd/MM/yyyy
    di = data_inicial.strftime('%d/%m/%Y')
    df = data_final.strftime('%d/%m/%Y')
    url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.4449/dados?formato=json&dataInicial={di}&dataFinal={df}'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            st.error('Nenhum dado encontrado para o período selecionado.')
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df['data'] = pd.to_datetime(df['data'], dayfirst=True)
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce')
        df = df.dropna(subset=['valor'])
        return df
    except requests.exceptions.RequestException as e:
        st.error(f'Erro na consulta à API do Banco Central: {e}')
        return pd.DataFrame()
    except ValueError:
        st.error('Erro ao processar os dados retornados pela API.')
        return pd.DataFrame()

# Interface Streamlit
st.title('Calculadora Otimizada de Correção pelo IPCA')

data_inicial = st.date_input('Data Inicial', DATA_INICIAL_SERIE)
data_final = st.date_input('Data Final', DATA_FINAL_SERIE)
valor_inicial = st.number_input('Valor a ser corrigido', min_value=0.0, value=1000.0)
taxa_aa = st.number_input('Taxa anual prefixada (%)', min_value=0.0, value=0.0) / 100

data_inicial, data_final = validar_datas(data_inicial, data_final)

if data_inicial and data_final:
    df_ipca = get_ipca_data(data_inicial, data_final)
    if not df_ipca.empty:
        ipca_acumulado = (df_ipca['valor'] / 100 + 1).prod() - 1
        valor_corrigido_ipca = valor_inicial * (1 + ipca_acumulado)
        meses = (data_final.year - data_inicial.year) * 12 + (data_final.month - data_inicial.month)
        taxa_mensal = (1 + taxa_aa) ** (1/12) - 1
        valor_corrigido_taxa = valor_corrigido_ipca * ((1 + taxa_mensal) ** meses)

        st.write(f'IPCA acumulado no período: {ipca_acumulado:.4%}')
        st.write(f'Valor corrigido pelo IPCA: R$ {valor_corrigido_ipca:.2f}')
        st.write(f'Valor corrigido pelo IPCA mais taxa prefixada: R$ {valor_corrigido_taxa:.2f}')
        st.write('Valores mensais do IPCA no período:')
        st.dataframe(df_ipca.set_index('data'))
