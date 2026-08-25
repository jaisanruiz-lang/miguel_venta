import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import unicodedata
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# -----------------------------------
# CONFIGURACION DE LA PAGINA Y ESTILOS CSS
# -----------------------------------
st.set_page_config(page_title="Dashboard Comercial", layout="wide")

st.markdown("""
    <style>
    .main-title {
        color: #1E3A8A; /* Azul Marino */
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-weight: bold;
        padding-bottom: 10px;
    }
    div[data-testid="stMetric"] {
        background-color: #F8FAFC;
        border-left: 5px solid #10B981; /* Verde Esmeralda */
        padding: 12px;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetric"] label {
        color: #1E40AF !important;
        font-weight: 600 !important;
    }
    
    section[data-testid="stSidebar"] label {
        font-size: 14px !important; 
        font-weight: 600 !important;
        color: #1E3A8A !important;
    }
    
    section[data-testid="stSidebar"] div[data-baseweb="select"] {
        font-size: 14px !important;
    }
    
    section[data-testid="stSidebar"] span[data-baseweb="tag"] {
        font-size: 12px !important;
        padding: 4px 8px !important; 
        margin: 2px !important; 
    }
    
    ul[role="listbox"] {
        max-height: 60vh !important;
    }
    
    div[data-baseweb="popover"] div:has(> div:contains("No results")) {
        display: none !important;
    }
    ul[role="listbox"] > div {
        display: none !important;
    }
    
    section[data-testid="stSidebar"] div[data-testid="stMultiSelect"]:nth-of-type(5) div[data-baseweb="select"] > div:first-child {
        min-height: 300px !important;
        align-items: flex-start !important; 
        align-content: flex-start !important;
        background-color: #FFFFFF !important; 
        border-radius: 4px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">📊 DASHBOARD COMERCIAL</h1>', unsafe_allow_html=True)

# -----------------------------------
# FUNCIONES DE FORMATEO Y NORMALIZACIÓN
# -----------------------------------
def formatear_moneda(valor):
    if pd.isna(valor):
        return "$ 0,00"
    base = f"{valor:,.2f}"
    tabla_cambio = str.maketrans({',': '.', '.': ','})
    return f"$ {base.translate(tabla_cambio)}"

def formatear_porcentaje(valor):
    if pd.isna(valor):
        return "0,00 %"
    base = f"{valor:,.2f}"
    tabla_cambio = str.maketrans({',': '.', '.': ','})
    return f"{base.translate(tabla_cambio)} %"

def normalizar_texto(texto):
    if pd.isna(texto):
        return ""
    t = str(texto).strip().upper()
    t = t.replace('Ã±', 'Ñ').replace('Ã‘', 'Ñ').replace('BAÑOS', 'BANOS').replace('BAÑO', 'BANO')
    nfkd_form = unicodedata.normalize('NFKD', t)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

# -----------------------------------
# CARGA Y LIMPIEZA DE DATA (CACHE + GOOGLE DRIVE / LOCAL)
# -----------------------------------
@st.cache_data(ttl="5m")
def cargar_datos():
    # 1. Cargar el mapa de Áreas y Departamentos
    archivo_dist = "distribucion_miguel.csv"
    if not os.path.exists(archivo_dist):
        st.error(f"No se encontró el archivo '{archivo_dist}'.")
        st.stop()
        
    try:
        df_dist = pd.read_csv(archivo_dist, encoding="latin-1", sep=None, engine='python', on_bad_lines='skip')
    except Exception as e:
        st.error(f"❌ Error al leer '{archivo_dist}': {e}")
        st.stop()

    df_dist.columns = df_dist.columns.str.strip().str.upper()
    col_area_dist = 'ÁREA' if 'ÁREA' in df_dist.columns else ('AREA' if 'AREA' in df_dist.columns else df_dist.columns[0])
    col_dep_dist = 'DEPARTAMENTO' if 'DEPARTAMENTO' in df_dist.columns else df_dist.columns[1]
    col_cat_dist = 'CATEGORIA' if 'CATEGORIA' in df_dist.columns else df_dist.columns[2]

    df_dist['AREA'] = df_dist[col_area_dist].ffill().astype(str).str.strip().str.upper()
    df_dist['DEPARTAMENTO'] = df_dist[col_dep_dist].astype(str).str.strip().str.upper()
    df_dist['CATEGORIA'] = df_dist[col_cat_dist].astype(str).str.strip().str.upper()
    df_dist['CAT_NORM'] = df_dist['CATEGORIA'].apply(normalizar_texto)
    
    mapa_areas_cat = dict(zip(df_dist['CAT_NORM'], df_dist['AREA']))
    mapa_deps_cat = dict(zip(df_dist['CAT_NORM'], df_dist['DEPARTAMENTO']))

    # 2. Cargar Ventas
    ID_DRIVE_VENTAS = "16XYtA31ebAE1Ad2Ldj7OV-CBbxO0IVSf" 
    URL_VENTAS_NUBE = f"https://docs.google.com/uc?export=download&id={ID_DRIVE_VENTAS}"
    
    try:
        df = pd.read_csv(URL_VENTAS_NUBE, encoding="latin-1", sep=";")
    except Exception:
        try:
            df = pd.read_csv("ventas.csv", encoding="latin-1", sep=";", on_bad_lines='skip')
        except Exception as e_local:
            st.error(f"❌ Error al cargar las Ventas. Detalles: {e_local}")
            st.stop()
        
    col_año = [c for c in df.columns if 'AÑO' in c.upper() or 'AÃ' in c.upper()]
    if col_año:
        df = df.rename(columns={col_año[0]: 'AÑO'})
        
    df.columns = df.columns.str.strip()
    
    df['ImporteDivisaPrincipal'] = (
        df['ImporteDivisaPrincipal']
        .astype(str)
        .str.replace(r'\s+', '', regex=True)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
    )
    df['ImporteDivisaPrincipal'] = pd.to_numeric(df['ImporteDivisaPrincipal'], errors='coerce').fillna(0.0)
    
    if 'Usuario' in df.columns:
        df['USUARIO'] = df['Usuario'].astype(str).str.strip().str.upper()
    elif 'USUARIO' in df.columns:
        df['USUARIO'] = df['USUARIO'].astype(str).str.strip().str.upper()
    else:
        df['USUARIO'] = 'SIN USUARIO'
    
    df = df.rename(columns={
        'ImporteDivisaPrincipal': 'VENTA',
        'DescrLineaNegocio': 'CATEGORIA',
        'Nombre': 'SUCURSAL'
    })
    
    df['SUCURSAL'] = df['SUCURSAL'].str.replace('SUCURSAL ', '', regex=False).str.upper().str.strip()
    df['SUCURSAL'] = df['SUCURSAL'].replace({
        'ALUMINIOLOGO WEB': 'ALUMUNIOLOGO WED',
        'SHOWROOM - 000': 'SHOWROOM'
    })
    
    df['CATEGORIA_ORIG'] = df['CATEGORIA'].astype(str).str.strip().str.upper()
    df['CAT_NORM'] = df['CATEGORIA_ORIG'].apply(normalizar_texto)
    
    if 'DEPARTAMENTO' in df.columns:
        df['DEPARTAMENTO'] = df['DEPARTAMENTO'].astype(str).str.strip().str.upper()
        
    df['ÁREA'] = df['CAT_NORM'].map(mapa_areas_cat).fillna('OTROS')
    df['DEPARTAMENTO_NUEVO'] = df['CAT_NORM'].map(mapa_deps_cat)
    df['DEPARTAMENTO'] = df['DEPARTAMENTO_NUEVO'].fillna(df['DEPARTAMENTO']).fillna('OTRAS CATEGORIAS').astype(str).str.strip().str.upper()
    
    # 3. Cargar Metros Cuadrados
    archivo_m2 = "METROS CUADRADOS POR CATEGORIA.csv"
    if not os.path.exists(archivo_m2):
        st.error(f"No se encontró el archivo '{archivo_m2}'.")
        st.stop()
        
    df_m2 = pd.read_csv(archivo_m2, encoding="latin-1", sep=None, engine='python', on_bad_lines='skip')
    df_m2.columns = df_m2.columns.str.strip().str.upper()
    df_m2['CATEGORIA_ORIG'] = df_m2['CATEGORIA'].astype(str).str.strip().str.upper()
    df_m2['CAT_NORM'] = df_m2['CATEGORIA_ORIG'].apply(normalizar_texto)
    df_m2 = df_m2[(df_m2['CAT_NORM'] != 'NAN') & (df_m2['CAT_NORM'] != '')]
    
    df_m2['METROS'] = (
        df_m2['METROS']
        .astype(str)
        .str.replace(r'\s+', '', regex=True)
        .str.replace(',', '.', regex=False)
    )
    df_m2['METROS'] = pd.to_numeric(df_m2['METROS'], errors='coerce').fillna(0.0)
    
    df_m2['ÁREA'] = df_m2['CAT_NORM'].map(mapa_areas_cat).fillna('OTROS')
    if 'DEPARTAMENTO' in df_m2.columns:
        df_m2['DEPARTAMENTO_NUEVO'] = df_m2['CAT_NORM'].map(mapa_deps_cat)
        df_m2['DEPARTAMENTO'] = df_m2['DEPARTAMENTO_NUEVO'].fillna(df_m2['DEPARTAMENTO']).fillna('OTRAS CATEGORIAS').astype(str).str.strip().str.upper()
    else:
        df_m2['DEPARTAMENTO'] = df_m2['CAT_NORM'].map(mapa_deps_cat).fillna('OTRAS CATEGORIAS')

    # Consolidación obligatoria para evitar duplicados en llaves de merge
    df_m2 = df_m2.groupby(['ÁREA', 'DEPARTAMENTO', 'CATEGORIA_ORIG'], as_index=False)['METROS'].sum()

    # 4. Cargar Tablas Maestras de Metas (META_2026.csv y Porcentajes)
    archivo_meta_global = "META_2026.csv"
    if os.path.exists(archivo_meta_global):
        df_meta_g = pd.read_csv(archivo_meta_global, encoding="latin-1", sep=None, engine='python', on_bad_lines='skip')
        df_meta_g.columns = df_meta_g.columns.str.strip().str.upper()
        col_m_mes = [c for c in df_meta_g.columns if 'MES' in c][0] if [c for c in df_meta_g.columns if 'MES' in c] else 'MESES'
        col_m_val = [c for c in df_meta_g.columns if 'META' in c][0]
        col_m_suc = [c for c in df_meta_g.columns if 'SUCURSAL' in c][0]
        col_m_ano = [c for c in df_meta_g.columns if 'AÑO' in c or 'AÃ' in c][0] if [c for c in df_meta_g.columns if 'AÑO' in c or 'AÃ' in c] else 'AÑO'
        
        df_meta_g = df_meta_g.rename(columns={col_m_mes: 'MES', col_m_val: 'META_GLOBAL', col_m_suc: 'SUCURSAL', col_m_ano: 'AÑO'})
        df_meta_g['MES'] = df_meta_g['MES'].astype(str).str.strip().str.upper()
        df_meta_g['SUCURSAL'] = df_meta_g['SUCURSAL'].astype(str).str.strip().str.upper()
        df_meta_g['META_GLOBAL'] = (
            df_meta_g['META_GLOBAL']
            .astype(str)
            .str.replace(r'\s+', '', regex=True)
            .str.replace('.', '', regex=False)
            .str.replace(',', '.', regex=False)
        )
        df_meta_g['META_GLOBAL'] = pd.to_numeric(df_meta_g['META_GLOBAL'], errors='coerce').fillna(0.0)
    else:
        df_meta_g = pd.DataFrame(columns=['MES', 'AÑO', 'SUCURSAL', 'META_GLOBAL'])

    archivo_metas_pct = "METAS_POR_SUCURSAL_Y_CATEGORIA_PORCENTAJES.csv"
    if os.path.exists(archivo_metas_pct):
        df_metas_p = pd.read_csv(archivo_metas_pct, encoding="latin-1", sep=None, engine='python', on_bad_lines='skip')
        df_metas_p.columns = df_metas_p.columns.str.strip().str.upper()
        col_p_cat = [c for c in df_metas_p.columns if 'CAT' in c][0]
        col_p_por = [c for c in df_metas_p.columns if 'PORC' in c][0]
        col_p_suc = [c for c in df_metas_p.columns if 'SUC' in c][0]
        col_p_ano = [c for c in df_metas_p.columns if 'AÑO' in c or 'AÃ' in c][0] if [c for c in df_metas_p.columns if 'AÑO' in c or 'AÃ' in c] else 'AÑO'
        
        df_metas_p = df_metas_p.rename(columns={col_p_cat: 'CATEGORIA', col_p_por: 'PORCENTAJE', col_p_suc: 'SUCURSAL', col_p_ano: 'AÑO'})
        df_metas_p['SUCURSAL'] = df_metas_p['SUCURSAL'].astype(str).str.strip().str.upper()
        df_metas_p['CATEGORIA_ORIG'] = df_metas_p['CATEGORIA'].astype(str).str.strip().str.upper()
        df_metas_p['CAT_NORM'] = df_metas_p['CATEGORIA_ORIG'].apply(normalizar_texto)
        
        df_metas_p['PORCENTAJE'] = (
            df_metas_p['PORCENTAJE']
            .astype(str)
            .str.replace('%', '', regex=False)
            .str.replace(r'\s+', '', regex=True)
            .str.replace('.', '', regex=False)
            .str.replace(',', '.', regex=False)
        )
        df_metas_p['PORCENTAJE'] = pd.to_numeric(df_metas_p['PORCENTAJE'], errors='coerce').fillna(0.0) / 100.0
        
        df_metas_p['PORCENTAJE'] = df_metas_p.groupby('SUCURSAL')['PORCENTAJE'].transform(lambda x: x / x.sum())
    else:
        df_metas_p = pd.DataFrame(columns=['CATEGORIA_ORIG', 'CAT_NORM', 'SUCURSAL', 'AÑO', 'PORCENTAJE'])
        
    return df, df_m2, df_meta_g, df_metas_p

df, df_m2, df_meta_g, df_metas_p = cargar_datos()

# -----------------------------------
# ESTRUCTURA DE ORDENAMIENTO
# -----------------------------------
orden_meses = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 
               'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']

orden_sucursales = ['CATIA', 'LA GUAIRA', 'MARICHE', 'GUATIRE', 'ALUMUNIOLOGO WED', 
                    'DISTRIBUIDORES', 'REPRESENTANTES COMERCIALES', 'SHOWROOM']

orden_areas_personalizado = [
    'VIDRIOS Y ESPEJOS',
    'LAMINAS Y PERFILERIA ESTANDAR',
    'VENTANAS',
    'PUERTAS, DIVISIONES Y BARANDAS',
    'PROTECCION SOLAR',
    'INSUMOS Y FERRETERIA',
    'DRYWALL Y MUEBLERIA',
    'SERVICIOS',
    'SIN ÁREA',
    'OTROS'
]

df['MES'] = pd.Categorical(df['MES'].astype(str).str.upper().str.strip(), categories=orden_meses, ordered=True)
df['SUCURSAL'] = pd.Categorical(df['SUCURSAL'], categories=[s.upper() for s in orden_sucursales], ordered=True)

# -----------------------------------
# FILTROS DINÁMICOS EN CASCADA (SIDEBAR)
# -----------------------------------
st.sidebar.header("Filtros de Análisis")

año_sel = st.sidebar.selectbox("Año Seleccionado", sorted(df['AÑO'].dropna().unique(), reverse=True))

meses_disponibles = orden_meses
meses_sel = st.sidebar.multiselect("Meses", meses_disponibles, default=meses_disponibles, placeholder="Seleccione Meses...")

df_año = df[df['AÑO'] == año_sel]
df_mes = df_año[df_año['MES'].isin(meses_sel)]

sucursales_disponibles = sorted(df_mes['SUCURSAL'].dropna().unique())
if not sucursales_disponibles and not df_meta_g.empty:
    sucursales_disponibles = sorted(df_meta_g['SUCURSAL'].dropna().unique())

sucursal_sel = st.sidebar.multiselect("Sucursales", sucursales_disponibles, default=sucursales_disponibles, placeholder="Seleccione Sucursales...")
df_suc = df_mes[df_mes['SUCURSAL'].isin(sucursal_sel)]

usuarios_disponibles = sorted(df_suc['USUARIO'].dropna().unique())
usuario_sel = st.sidebar.multiselect("Usuarios (Vendedores)", usuarios_disponibles, default=usuarios_disponibles, placeholder="Seleccione Usuarios...")
df_us = df_suc[df_suc['USUARIO'].isin(usuario_sel)]

areas_en_data = df_us['ÁREA'].dropna().unique()
areas_disponibles = [a for a in orden_areas_personalizado if a in areas_en_data] + [a for a in areas_en_data if a not in orden_areas_personalizado]
area_sel = st.sidebar.multiselect("Área (Agrupación)", areas_disponibles, default=areas_disponibles, placeholder="Seleccione Áreas...")
df_ar = df_us[df_us['ÁREA'].isin(area_sel)]

departamentos_disponibles = sorted(df_ar['DEPARTAMENTO'].dropna().unique())
departamentos_sel = st.sidebar.multiselect("Departamentos", departamentos_disponibles, default=departamentos_disponibles, placeholder="Seleccione Departamentos...")

df_filtrado = df_ar[df_ar['DEPARTAMENTO'].isin(departamentos_sel)]

# -----------------------------------
# CÁLCULO OFICIAL DE LA META (MESES X PORCENTAJES)
# -----------------------------------
if not df_meta_g.empty:
    df_meta_g_sel = df_meta_g[(df_meta_g['AÑO'] == año_sel) & (df_meta_g['MES'].isin(meses_sel)) & (df_meta_g['SUCURSAL'].isin(sucursal_sel))]
    meta_por_sucursal = df_meta_g_sel.groupby('SUCURSAL')['META_GLOBAL'].sum().to_dict()
else:
    meta_por_sucursal = {}

if not df_metas_p.empty:
    df_metas_p_sel = df_metas_p[(df_metas_p['AÑO'] == año_sel) & (df_metas_p['SUCURSAL'].isin(sucursal_sel))].copy()
    records_meta = []
    for suc in sucursal_sel:
        m_val = meta_por_sucursal.get(suc, 0.0)
        df_s_pct = df_metas_p_sel[df_metas_p_sel['SUCURSAL'] == suc]
        for _, row in df_s_pct.iterrows():
            cat_orig = row['CATEGORIA_ORIG']
            pct = row['PORCENTAJE']
            records_meta.append({
                'SUCURSAL': suc,
                'CATEGORIA_ORIG': cat_orig,
                'META_VALOR': m_val * pct
            })
    df_meta_calculada = pd.DataFrame(records_meta)
    if not df_meta_calculada.empty:
        tabla_meta_final = df_meta_calculada.groupby('CATEGORIA_ORIG', as_index=False)['META_VALOR'].sum()
        tabla_meta_final = tabla_meta_final.rename(columns={'META_VALOR': 'META', 'CATEGORIA_ORIG': 'CATEGORIA'})
    else:
        tabla_meta_final = pd.DataFrame(columns=['CATEGORIA', 'META'])
else:
    tabla_meta_final = pd.DataFrame(columns=['CATEGORIA', 'META'])

# -----------------------------------
# PROCESAMIENTO MATRICIAL: REPORTE COMERCIAL PRINCIPAL
# -----------------------------------
df_m2_sel = df_m2[df_m2['DEPARTAMENTO'].isin(departamentos_sel)].copy()
df_m2_sel = df_m2_sel.rename(columns={'CATEGORIA_ORIG': 'CATEGORIA'})

tabla_actual = df_filtrado.groupby(['ÁREA', 'DEPARTAMENTO', 'CATEGORIA_ORIG'], observed=False)['VENTA'].sum().reset_index()
tabla_actual = tabla_actual.rename(columns={'CATEGORIA_ORIG': 'CATEGORIA'})

tabla_base = pd.merge(df_m2_sel[['ÁREA', 'DEPARTAMENTO', 'CATEGORIA', 'METROS']], tabla_actual, on=['ÁREA', 'DEPARTAMENTO', 'CATEGORIA'], how='outer')
if not tabla_meta_final.empty:
    tabla_base = pd.merge(tabla_base, tabla_meta_final, on=['CATEGORIA'], how='outer')
else:
    tabla_base['META'] = 0.0

archivo_dist = "distribucion_miguel.csv"
df_dist_temp = pd.read_csv(archivo_dist, encoding="latin-1", sep=None, engine='python', on_bad_lines='skip')
df_dist_temp.columns = df_dist_temp.columns.str.strip().str.upper()

col_area_t = 'ÁREA' if 'ÁREA' in df_dist_temp.columns else ('AREA' if 'AREA' in df_dist_temp.columns else df_dist_temp.columns[0])
col_dep_t = 'DEPARTAMENTO' if 'DEPARTAMENTO' in df_dist_temp.columns else df_dist_temp.columns[1]
col_cat_t = 'CATEGORIA' if 'CATEGORIA' in df_dist_temp.columns else df_dist_temp.columns[2]

df_dist_temp['AREA'] = df_dist_temp[col_area_t].ffill().astype(str).str.strip().str.upper()
df_dist_temp['DEPARTAMENTO'] = df_dist_temp[col_dep_t].astype(str).str.strip().str.upper()
df_dist_temp['CATEGORIA'] = df_dist_temp[col_cat_t].astype(str).str.strip().str.upper()
df_dist_temp['CAT_NORM'] = df_dist_temp['CATEGORIA'].apply(normalizar_texto)

mapa_areas_full = dict(zip(df_dist_temp['CAT_NORM'], df_dist_temp['AREA']))
mapa_deps_full = dict(zip(df_dist_temp['CAT_NORM'], df_dist_temp['DEPARTAMENTO']))

tabla_base['CAT_NORM'] = tabla_base['CATEGORIA'].apply(normalizar_texto)
tabla_base['ÁREA'] = tabla_base['ÁREA'].fillna(tabla_base['CAT_NORM'].map(mapa_areas_full)).fillna('OTROS')
tabla_base['DEPARTAMENTO'] = tabla_base['DEPARTAMENTO'].fillna(tabla_base['CAT_NORM'].map(mapa_deps_full)).fillna('OTRAS CATEGORIAS')

tabla_base['VENTA'] = tabla_base['VENTA'].fillna(0.0)
tabla_base['META'] = tabla_base['META'].fillna(0.0)
tabla_base['METROS'] = tabla_base['METROS'].fillna(0.0)
tabla_base = tabla_base.rename(columns={'METROS': 'M2'})

tabla_base = tabla_base[tabla_base['ÁREA'].isin(area_sel) & tabla_base['DEPARTAMENTO'].isin(departamentos_sel)]
tabla_base = tabla_base[(tabla_base['VENTA'] > 0) | (tabla_base['META'] > 0) | (tabla_base['M2'] > 0)]

tabla_base['AVANCE'] = np.where(tabla_base['META'] > 0, (tabla_base['VENTA'] / tabla_base['META']) * 100, 0.0)
tabla_base['EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)'] = np.where(tabla_base['M2'] > 0, tabla_base['VENTA'] / tabla_base['M2'], 0.0)
tabla_base['ORDEN_REGISTRO'] = 0

subtotales = tabla_base.groupby(['ÁREA'], observed=False).agg({'VENTA': 'sum', 'META': 'sum', 'M2': 'sum'}).reset_index()
subtotales['DEPARTAMENTO'] = 'TOTAL ÁREA'
subtotales['CATEGORIA'] = '-'
subtotales['AVANCE'] = np.where(subtotales['META'] > 0, (subtotales['VENTA'] / subtotales['META']) * 100, 0.0)
subtotales['EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)'] = np.where(subtotales['M2'] > 0, subtotales['VENTA'] / subtotales['M2'], 0.0)
subtotales['ORDEN_REGISTRO'] = 1

total_g_venta = tabla_base["VENTA"].sum()
total_g_meta = subtotales["META"].sum()
total_g_m2 = subtotales["M2"].sum()
total_g_avance = (total_g_venta / total_g_meta) * 100 if total_g_meta > 0 else 0.0
total_g_eficiencia = total_g_venta / total_g_m2 if total_g_m2 > 0 else 0.0

fila_total_general = pd.DataFrame([{
    'ÁREA': 'TOTAL GENERAL',
    'DEPARTAMENTO': 'TOTAL GENERAL',
    'CATEGORIA': 'REPORTE CONSOLIDADO',
    'M2': total_g_m2,
    'VENTA': total_g_venta,
    'META': total_g_meta,
    'AVANCE': total_g_avance,
    'EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)': total_g_eficiencia,
    'ORDEN_REGISTRO': 2
}])

tabla_final = pd.concat([tabla_base.drop(columns=['CAT_NORM']), subtotales, fila_total_general], ignore_index=True)

areas_presentes_extra = [a for a in tabla_final['ÁREA'].unique() if a not in orden_areas_personalizado and a != 'TOTAL GENERAL']
lista_orden_final = orden_areas_personalizado + areas_presentes_extra + ['TOTAL GENERAL']

tabla_final['ÁREA'] = pd.Categorical(tabla_final['ÁREA'], categories=lista_orden_final, ordered=True)
tabla_final = tabla_final.sort_values(by=["ÁREA", "ORDEN_REGISTRO", "DEPARTAMENTO", "VENTA"], ascending=[True, True, True, False])
tabla_final = tabla_final.drop(columns=['M2', 'ORDEN_REGISTRO'])
tabla_final = tabla_final[['ÁREA', 'DEPARTAMENTO', 'CATEGORIA', 'VENTA', 'META', 'AVANCE', 'EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)']]

df_para_excel = tabla_final.copy()
df_render_app = tabla_final.copy()
df_render_app['VENTA'] = df_render_app['VENTA'].apply(formatear_moneda)
df_render_app['META'] = df_render_app['META'].apply(formatear_moneda)
df_render_app['AVANCE'] = df_render_app['AVANCE'].apply(formatear_porcentaje)
df_render_app['EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)'] = df_render_app['EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)'].apply(formatear_moneda)

df_render_app = df_render_app.rename(columns={'DEPARTAMENTO': 'DEPARTAMENTO', 'CATEGORIA': 'CATEGORÍA'})

def aplicar_colores_matriz(row):
    if row['DEPARTAMENTO'] == 'TOTAL GENERAL':
        return ['font-weight: bold; background-color: #A7F3D0; color: #047857; border-top: 2px double #047857; border-bottom: 2px double #047857;'] * len(row)
    elif row['DEPARTAMENTO'] == 'TOTAL ÁREA':
        return ['font-weight: bold; background-color: #D1FAE5; color: #065F46; border-bottom: 2px solid #10B981;'] * len(row)
    return ['background-color: #FFFFFF; color: #1F2937; border-bottom: 1px solid #E5E7EB;'] * len(row)

tabla_estilizada = (
    df_render_app.style
    .apply(aplicar_colores_matriz, axis=1)
    .set_properties(**{'text-align': 'right', 'font-family': 'Arial'})
)

total_ventas = total_g_venta
meta_dinamica_total = total_g_meta
avance_general = total_g_avance
eficiencia_total = total_g_eficiencia

# -----------------------------------
# PROCESAMIENTO MATRICIAL: REPORTE DE VENDEDORES
# -----------------------------------
tabla_us_actual = df_filtrado.groupby(['USUARIO', 'ÁREA', 'CATEGORIA_ORIG'], observed=False)['VENTA'].sum().reset_index()
tabla_us_actual = tabla_us_actual.rename(columns={'CATEGORIA_ORIG': 'CATEGORIA'})

if not tabla_meta_final.empty:
    tabla_us_actual = pd.merge(tabla_us_actual, tabla_meta_final, on=['CATEGORIA'], how='left')
else:
    tabla_us_actual['META'] = 0.0
tabla_us_actual['META'] = tabla_us_actual['META'].fillna(0.0)

total_ventas_cat = tabla_us_actual.groupby('CATEGORIA')['VENTA'].transform('sum')
proporcion_usuario = np.where(total_ventas_cat > 0, tabla_us_actual['VENTA'] / total_ventas_cat, 0.0)
tabla_us_actual['META_ASIGNADA'] = tabla_us_actual['META'] * proporcion_usuario

tabla_us_agrupado = tabla_us_actual.groupby(['USUARIO', 'ÁREA'], observed=False).agg({'VENTA': 'sum', 'META_ASIGNADA': 'sum'}).reset_index()
tabla_us_agrupado = tabla_us_agrupado.rename(columns={'META_ASIGNADA': 'META'})

tabla_us_agrupado['AVANCE'] = np.where(tabla_us_agrupado['META'] > 0, (tabla_us_agrupado['VENTA'] / tabla_us_agrupado['META']) * 100, 0.0)
tabla_us_agrupado['ORDEN_REGISTRO'] = 0

subtotales_us = tabla_us_agrupado.groupby('USUARIO', observed=False).agg({'VENTA': 'sum', 'META': 'sum'}).reset_index()
subtotales_us['ÁREA'] = 'TOTAL VENDEDOR'
subtotales_us['AVANCE'] = np.where(subtotales_us['META'] > 0, (subtotales_us['VENTA'] / subtotales_us['META']) * 100, 0.0)
subtotales_us['ORDEN_REGISTRO'] = 1

tot_us_v = subtotales_us['VENTA'].sum()
tot_us_m = subtotales_us['META'].sum()
tot_us_a = (tot_us_v / tot_us_m * 100) if tot_us_m > 0 else 0.0

total_us = pd.DataFrame([{
    'USUARIO': 'TOTAL GENERAL',
    'ÁREA': 'REPORTE CONSOLIDADO',
    'VENTA': tot_us_v,
    'META': tot_us_m,
    'AVANCE': tot_us_a,
    'ORDEN_REGISTRO': 2
}])

tabla_us_final = pd.concat([tabla_us_agrupado, subtotales_us, total_us], ignore_index=True)
tabla_us_final = tabla_us_final.sort_values(by=["USUARIO", "ORDEN_REGISTRO", "VENTA"], ascending=[True, True, False])
tabla_us_final = tabla_us_final.drop(columns=['ORDEN_REGISTRO'])
df_para_excel_us = tabla_us_final.copy()

# -----------------------------------
# FUNCIONES DE GENERACIÓN DE EXPORTABLES
# -----------------------------------
def generar_excel_descarga_sumable(dataframe, sheet_name='Reporte'):
    output = io.BytesIO()
    df_excel = dataframe.copy()
    if 'DEPARTAMENTO' in df_excel.columns:
        df_excel = df_excel[df_excel['DEPARTAMENTO'] != 'TOTAL ÁREA']
    if 'ÁREA' in df_excel.columns and 'USUARIO' in df_excel.columns:
        df_excel = df_excel[df_excel['ÁREA'] != 'TOTAL VENDEDOR']
        
    df_excel['AVANCE'] = df_excel['AVANCE'] / 100.0
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_excel.to_excel(writer, index=False, sheet_name=sheet_name)
        worksheet = writer.sheets[sheet_name]
        formato_numero_excel = '#,##0.00'
        formato_porcentaje_excel = '0.00%'
        
        for row in range(2, len(df_excel) + 2):
            if 'DEPARTAMENTO' in df_excel.columns:
                worksheet[f'D{row}'].number_format = formato_numero_excel
                worksheet[f'E{row}'].number_format = formato_numero_excel
                worksheet[f'F{row}'].number_format = formato_porcentaje_excel
                worksheet[f'G{row}'].number_format = formato_numero_excel
            else:
                worksheet[f'C{row}'].number_format = formato_numero_excel
                worksheet[f'D{row}'].number_format = formato_numero_excel
                worksheet[f'E{row}'].number_format = formato_porcentaje_excel
                
    return output.getvalue()

def generar_pdf_descarga(dataframe, año, ventas, meta, avance, eficiencia):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#1E3A8A'), spaceAfter=8)
    subtitle_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#4B5563'), spaceAfter=12)
    header_table_style = ParagraphStyle('HeaderTable', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.white, alignment=1)
    cell_table_style = ParagraphStyle('CellTable', parent=styles['Normal'], fontSize=8, leading=10, alignment=2)
    cell_total_style = ParagraphStyle('CellTotal', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold', alignment=2)
    
    story.append(Paragraph(f"<b>REPORTE EJECUTIVO COMERCIAL - AÑO {año}</b>", title_style))
    story.append(Paragraph(f"Filtros aplicados - Ventas Totales: {ventas} | Meta Oficial: {meta} | Avance: {avance} | EFICIENCIA (VENTA/M2): {eficiencia}", subtitle_style))
    story.append(Spacer(1, 8))
    
    data_tabla = [[Paragraph("<b>ÁREA</b>", header_table_style), 
                   Paragraph("<b>DEPARTAMENTO</b>", header_table_style), 
                   Paragraph("<b>CATEGORÍA</b>", header_table_style), 
                   Paragraph("<b>VENTA</b>", header_table_style), 
                   Paragraph("<b>META</b>", header_table_style), 
                   Paragraph("<b>AVANCE</b>", header_table_style), 
                   Paragraph("<b>EFICIENCIA (VENTA/M2)</b>", header_table_style)]]
    
    estilos_celdas = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    
    for i, row in enumerate(dataframe.values):
        idx_fila = i + 1
        es_total_general = (row[1] == 'TOTAL GENERAL')
        es_subtotal = (row[1] == 'TOTAL ÁREA')  
        
        style_actual = cell_total_style if (es_subtotal or es_total_general) else cell_table_style
        
        data_tabla.append([
            Paragraph(str(row[0]), style_actual),
            Paragraph(str(row[1]), style_actual),
            Paragraph(str(row[2]), style_actual),
            Paragraph(formatear_moneda(row[3]), style_actual),
            Paragraph(formatear_moneda(row[4]), style_actual),
            Paragraph(formatear_porcentaje(row[5]), style_actual),
            Paragraph(formatear_moneda(row[6]), style_actual)
        ])
        
        if es_total_general:
            estilos_celdas.append(('BACKGROUND', (0, idx_fila), (-1, idx_fila), colors.HexColor('#A7F3D0')))
            estilos_celdas.append(('TEXTCOLOR', (0, idx_fila), (-1, idx_fila), colors.HexColor('#047857')))
        elif es_subtotal:
            estilos_celdas.append(('BACKGROUND', (0, idx_fila), (-1, idx_fila), colors.HexColor('#D1FAE5')))
            estilos_celdas.append(('TEXTCOLOR', (0, idx_fila), (-1, idx_fila), colors.HexColor('#065F46')))
            
    pdf_table = Table(data_tabla, colWidths=[120, 130, 130, 80, 80, 60, 80])
    pdf_table.setStyle(TableStyle(estilos_celdas))
    story.append(pdf_table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def generar_pdf_usuarios(dataframe, año):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#1E3A8A'), spaceAfter=8)
    header_table_style = ParagraphStyle('HeaderTable', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.white, alignment=1)
    cell_table_style = ParagraphStyle('CellTable', parent=styles['Normal'], fontSize=8, leading=10, alignment=2)
    cell_total_style = ParagraphStyle('CellTotal', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold', alignment=2)
    
    story.append(Paragraph(f"<b>REPORTE DE VENDEDORES POR ÁREA - AÑO {año}</b>", title_style))
    story.append(Spacer(1, 8))
    
    data_tabla = [[Paragraph("<b>USUARIO (VENDEDOR)</b>", header_table_style), 
                   Paragraph("<b>ÁREA</b>", header_table_style), 
                   Paragraph("<b>VENTA</b>", header_table_style), 
                   Paragraph("<b>META</b>", header_table_style), 
                   Paragraph("<b>AVANCE</b>", header_table_style)]]
    
    estilos_celdas = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    
    for i, row in enumerate(dataframe.values):
        idx_fila = i + 1
        es_total_general = (row[0] == 'TOTAL GENERAL')
        es_subtotal = (row[1] == 'TOTAL VENDEDOR')  
        
        style_actual = cell_total_style if (es_subtotal or es_total_general) else cell_table_style
        
        data_tabla.append([
            Paragraph(str(row[0]), style_actual),
            Paragraph(str(row[1]), style_actual),
            Paragraph(formatear_moneda(row[2]), style_actual),
            Paragraph(formatear_moneda(row[3]), style_actual),
            Paragraph(formatear_porcentaje(row[4]), style_actual)
        ])
        
        if es_total_general:
            estilos_celdas.append(('BACKGROUND', (0, idx_fila), (-1, idx_fila), colors.HexColor('#A7F3D0')))
            estilos_celdas.append(('TEXTCOLOR', (0, idx_fila), (-1, idx_fila), colors.HexColor('#047857')))
        elif es_subtotal:
            estilos_celdas.append(('BACKGROUND', (0, idx_fila), (-1, idx_fila), colors.HexColor('#D1FAE5')))
            estilos_celdas.append(('TEXTCOLOR', (0, idx_fila), (-1, idx_fila), colors.HexColor('#065F46')))
            
    pdf_table = Table(data_tabla, colWidths=[160, 160, 80, 80, 60])
    pdf_table.setStyle(TableStyle(estilos_celdas))
    story.append(pdf_table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# -----------------------------------
# RENDERIZADO DE LA INTERFAZ COMPLETA
# -----------------------------------
with st.expander("📊 ANÁLISIS - KPIs DE VENTAS", expanded=True):
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("VENTAS TOTALES", formatear_moneda(total_ventas))
    col2.metric("META OFICIAL", formatear_moneda(meta_dinamica_total))
    col3.metric("PORCENTAJE DE AVANCE", formatear_porcentaje(avance_general))
    col4.metric("EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)", formatear_moneda(eficiencia_total))

    st.markdown("---")
    
    st.dataframe(tabla_estilizada, use_container_width=True, height=530, hide_index=True)

    st.markdown("### 📥 MENÚ DE DESCARGA DE REPORTES")
    st.info("El informe de Excel se descarga libre de filas de subtotales y con codificación contable nativa de miles/decimales, permitiéndote realizar operaciones matemáticas al instante.")
    
    # Fila 1: Reportes Comerciales Principales
    st.markdown("#### 📄 Reportes Principales (Área/Departamento/Categoría)")
    bot1, bot2 = st.columns(2)
    data_excel_comercial = generar_excel_descarga_sumable(df_para_excel, sheet_name='Reporte Comercial')
    bot1.download_button(
        label="🟩 Descargar Reporte Principal en Excel",
        data=data_excel_comercial,
        file_name=f"Reporte_Comercial_{año_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    data_pdf_comercial = generar_pdf_descarga(tabla_final, año_sel, formatear_moneda(total_ventas), formatear_moneda(meta_dinamica_total), formatear_porcentaje(avance_general), formatear_moneda(eficiencia_total))
    bot2.download_button(
        label="🟦 Descargar Reporte Principal en PDF",
        data=data_pdf_comercial,
        file_name=f"Reporte_Comercial_{año_sel}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

    st.markdown("---")

    # Fila 2: Reportes de Vendedores
    st.markdown("#### 🧑‍💼 Reportes de Vendedores (Usuario/Área)")
    bot3, bot4 = st.columns(2)
    data_excel_vendedores = generar_excel_descarga_sumable(df_para_excel_us, sheet_name='Vendedores')
    bot3.download_button(
        label="🟩 Descargar Reporte de Vendedores en Excel",
        data=data_excel_vendedores,
        file_name=f"Reporte_Vendedores_{año_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    data_pdf_vendedores = generar_pdf_usuarios(df_para_excel_us, año_sel)
    bot4.download_button(
        label="🟦 Descargar Reporte de Vendedores en PDF",
        data=data_pdf_vendedores,
        file_name=f"Reporte_Vendedores_{año_sel}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
