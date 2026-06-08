import streamlit as st
import pandas as pd
import numpy as np
import os
import io
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# -----------------------------------
# CONFIGURACION DE LA PAGINA Y ESTILOS CSS
# -----------------------------------
st.set_page_config(page_title="Dashboard Comercial", layout="wide")

# Estilos visuales personalizados
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
    
    /* --- FUENTE PARA LOS TÍTULOS Y TEXTOS DE LOS FILTROS --- */
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
    
    /* AGRANDAR EL MENÚ DESPLEGABLE DE BÚSQUEDA AL HACER CLIC */
    ul[role="listbox"] {
        max-height: 60vh !important;
    }
    
    /* --- ELIMINAR "NO RESULTS" --- */
    div[data-baseweb="popover"] div:has(> div:contains("No results")) {
        display: none !important;
    }
    ul[role="listbox"] > div {
        display: none !important;
    }
    
    /* --- AGRANDAR EXCLUSIVAMENTE EL FONDO DEL FILTRO DE DEPARTAMENTOS --- */
    /* Apunta estrictamente al CUARTO multiselect (Departamentos) por la inclusión del filtro de Áreas */
    section[data-testid="stSidebar"] div[data-testid="stMultiSelect"]:nth-of-type(4) div[data-baseweb="select"] > div:first-child {
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
# FUNCIONES DE FORMATEO REGIONAL
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

# -----------------------------------
# CARGA Y LIMPIEZA DE DATA (CACHE + GOOGLE DRIVE / LOCAL)
# -----------------------------------
@st.cache_data(ttl="5m")
def cargar_datos():
    # 1. Cargar el mapa de Áreas desde archivo externo local (distribucion_miguel.csv)
    # Al estar afuera, si lo modificas en PC o GitHub se actualizará automáticamente sin tocar código
    archivo_dist = "distribucion_miguel.csv"
    if not os.path.exists(archivo_dist):
        st.error(f"No se encontró el archivo '{archivo_dist}'. Por favor súbelo o colócalo en la misma carpeta.")
        st.stop()
        
    df_dist = pd.read_csv(archivo_dist, encoding="latin-1", sep=";")
    
    # ffill() llena hacia abajo las agrupaciones de Área vacías originadas por celdas combinadas
    df_dist['AREA'] = df_dist['AREA'].ffill().astype(str).str.strip().str.upper()
    df_dist['DEPARTAMENTO'] = df_dist['DEPARTAMENTO'].astype(str).str.strip().str.upper()
    df_dist['DEPARTAMENTO'] = df_dist['DEPARTAMENTO'].str.replace('BAÃ\x91O', 'BAÑO', regex=False)
    mapa_areas = dict(zip(df_dist['DEPARTAMENTO'], df_dist['AREA']))

    # 2. Cargar Ventas con el link fijo de Drive y fallback al archivo local
    ID_DRIVE_VENTAS = "16XYtA31ebAE1Ad2Ldj7OV-CBbxO0IVSf" 
    URL_VENTAS_NUBE = f"https://docs.google.com/uc?export=download&id={ID_DRIVE_VENTAS}"
    
    try:
        df = pd.read_csv(URL_VENTAS_NUBE, encoding="latin-1", sep=";")
    except Exception:
        try:
            df = pd.read_csv("ventas.csv", encoding="latin-1", sep=";")
        except Exception as e_local:
            st.error(f"❌ Error al cargar las Ventas. Asegúrate de tener conexión a Google Drive o el archivo local 'ventas.csv'. Detalles: {e_local}")
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
    
    df['Nombre'] = df['Nombre'].str.replace('SUCURSAL ', '', regex=False).str.upper().str.strip()
    df['Nombre'] = df['Nombre'].replace({
        'ALUMINIOLOGO WEB': 'ALUMUNIOLOGO WED',
        'SHOWROOM - 000': 'SHOWROOM'
    })
    
    if 'DEPARTAMENTO' in df.columns:
        df['DEPARTAMENTO'] = df['DEPARTAMENTO'].astype(str).str.strip().str.upper()
        df['DEPARTAMENTO'] = df['DEPARTAMENTO'].str.replace('BAÃ\x91O', 'BAÑO', regex=False)
        
    # Asignar el Área a las ventas mediante el diccionario creado con distribucion_miguel.csv
    df['ÁREA'] = df['DEPARTAMENTO'].map(mapa_areas).fillna('SIN ÁREA')
    
    # 3. Cargar Metros Cuadrados desde archivo externo local
    # Igual que el archivo de áreas, si se modifica externamente se reflejará aquí
    archivo_m2 = "METROS CUADRADOS POR CATEGORIA.csv"
    if not os.path.exists(archivo_m2):
        st.error(f"No se encontró el archivo '{archivo_m2}'. Por favor súbelo o colócalo en la misma carpeta.")
        st.stop()
        
    df_m2 = pd.read_csv(archivo_m2, encoding="latin-1", sep=";")
    df_m2.columns = df_m2.columns.str.strip()
    
    if 'DEPARTAMENTO' in df_m2.columns:
        df_m2['DEPARTAMENTO'] = df_m2['DEPARTAMENTO'].ffill().astype(str).str.strip().str.upper()
        df_m2['DEPARTAMENTO'] = df_m2['DEPARTAMENTO'].str.replace('BAÃ\x91O', 'BAÑO', regex=False)
        
    df_m2['CATEGORIA'] = df_m2['CATEGORIA'].astype(str).str.strip().str.upper()
    df_m2 = df_m2[(df_m2['CATEGORIA'] != 'NAN') & (df_m2['CATEGORIA'] != '')]
    
    df_m2['METROS'] = (
        df_m2['METROS']
        .astype(str)
        .str.replace(r'\s+', '', regex=True)
        .str.replace(',', '.', regex=False)
    )
    df_m2['METROS'] = pd.to_numeric(df_m2['METROS'], errors='coerce').fillna(0.0)
        
    return df, df_m2

df, df_m2 = cargar_datos()

df = df.rename(columns={
    'ImporteDivisaPrincipal': 'VENTA',
    'DescrLineaNegocio': 'CATEGORIA',
    'Nombre': 'SUCURSAL'
})
df['CATEGORIA'] = df['CATEGORIA'].astype(str).str.strip().str.upper()

# -----------------------------------
# ESTRUCTURA DE ORDENAMIENTO ESTRICTO
# -----------------------------------
orden_meses = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 
               'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']

orden_sucursales = ['CATIA', 'LA GUAIRA', 'MARICHE', 'GUATIRE', 'ALUMUNIOLOGO WED', 
                    'DISTRIBUIDORES', 'REPRESENTANTES COMERCIALES', 'SHOWROOM']

orden_departamentos_base = [
    'VENTANAS Y PUERTAS CORREDIZAS', 'VENTANAS ABATIBLES', 'DIVISIONES DE AMBIENTE',
    'PERFILES ESTANDAR', 'PRODUCTOS ESTANDAR', 'PUERTAS EXTERIORES', 'PUERTAS INTERIORES',
    'BARANDAS', 'PUERTAS DE BAÑO', 'VIDRIOS', 'SIL Y SELL', 'HERRAMIENTAS',
    'IMPULSO', 'CERRADURAS Y CANDADOS', 'PERSIANAS Y MOSQUITEROS', 'LAMINAS'
]

otros_deps = [d for d in df['DEPARTAMENTO'].dropna().unique() if d not in orden_departamentos_base]
orden_departamentos = orden_departamentos_base + otros_deps

df['MES'] = pd.Categorical(df['MES'].astype(str).str.upper().str.strip(), categories=orden_meses, ordered=True)
df['SUCURSAL'] = pd.Categorical(df['SUCURSAL'], categories=[s.upper() for s in orden_sucursales], ordered=True)
df['DEPARTAMENTO'] = pd.Categorical(df['DEPARTAMENTO'], categories=orden_departamentos, ordered=True)

# -----------------------------------
# FILTROS (SIDEBAR LATERAL)
# -----------------------------------
st.sidebar.header("Filtros de Análisis")

año_sel = st.sidebar.selectbox("Año Seleccionado", sorted(df['AÑO'].dropna().unique(), reverse=True))

meses_en_data = df['MES'].dropna().unique()
meses_disponibles = [m for m in orden_meses if m in meses_en_data]
meses_sel = st.sidebar.multiselect("Meses", meses_disponibles, default=meses_disponibles, placeholder="Seleccione Meses...")

sucursales_en_data = df['SUCURSAL'].dropna().unique()
sucursales_disponibles = [s for s in orden_sucursales if s in sucursales_en_data]
sucursal_sel = st.sidebar.multiselect("Sucursales", sucursales_disponibles, default=sucursales_disponibles, placeholder="Seleccione Sucursales...")

# --- FILTRO NUEVO: ÁREAS ---
areas_en_data = df['ÁREA'].dropna().unique()
area_sel = st.sidebar.multiselect("Área (Agrupación)", sorted(areas_en_data), default=sorted(areas_en_data), placeholder="Seleccione Áreas...")

# --- FILTRO DEPENDIENTE: DEPARTAMENTOS ---
df_areas_filtradas = df[df['ÁREA'].isin(area_sel)]
departamentos_en_data = df_areas_filtradas['DEPARTAMENTO'].dropna().unique()
departamentos_disponibles = [d for d in orden_departamentos if d in departamentos_en_data]
departamentos_sel = st.sidebar.multiselect("Departamentos", departamentos_disponibles, default=departamentos_disponibles, placeholder="Seleccione Departamentos...")

# Filtrar Data de Transacciones
df_filtrado = df[(df['AÑO'] == año_sel) & (df['MES'].isin(meses_sel)) & (df['SUCURSAL'].isin(sucursal_sel)) & (df['DEPARTAMENTO'].isin(departamentos_sel)) & (df['ÁREA'].isin(area_sel))]
df_año_anterior = df[(df['AÑO'] == (año_sel - 1)) & (df['MES'].isin(meses_sel)) & (df['SUCURSAL'].isin(sucursal_sel)) & (df['DEPARTAMENTO'].isin(departamentos_sel)) & (df['ÁREA'].isin(area_sel))]

# -----------------------------------
# PROCESAMIENTO MATRICIAL DE LOS DATOS
# -----------------------------------
df_m2_sel = df_m2[df_m2['DEPARTAMENTO'].isin(departamentos_sel)].copy()

tabla_ant = df_año_anterior.groupby(['DEPARTAMENTO', 'CATEGORIA'], observed=False)['VENTA'].sum().reset_index()
tabla_ant = tabla_ant.rename(columns={'VENTA': 'META'})
tabla_ant['META'] = tabla_ant['META'] * 2

tabla_actual = df_filtrado.groupby(['DEPARTAMENTO', 'CATEGORIA'], observed=False)['VENTA'].sum().reset_index()

tabla_ventas = pd.merge(tabla_actual, tabla_ant, on=['DEPARTAMENTO', 'CATEGORIA'], how='outer')
tabla_base = pd.merge(df_m2_sel[['DEPARTAMENTO', 'CATEGORIA', 'METROS']], tabla_ventas, on=['DEPARTAMENTO', 'CATEGORIA'], how='outer')

tabla_base['VENTA'] = tabla_base['VENTA'].fillna(0.0)
tabla_base['META'] = tabla_base['META'].fillna(0.0)
tabla_base['METROS'] = tabla_base['METROS'].fillna(0.0)
tabla_base = tabla_base.rename(columns={'METROS': 'M2'})

tabla_base = tabla_base[(tabla_base['VENTA'] > 0) | (tabla_base['META'] > 0) | (tabla_base['M2'] > 0)]

tabla_base['AVANCE'] = np.where(tabla_base['META'] > 0, (tabla_base['VENTA'] / tabla_base['META']) * 100, 0.0)
tabla_base['EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)'] = np.where(tabla_base['M2'] > 0, tabla_base['VENTA'] / tabla_base['M2'], 0.0)
tabla_base['ORDEN_REGISTRO'] = 0

# Generación de Subtotales por Departamento
subtotales = tabla_base.groupby('DEPARTAMENTO', observed=False).agg({'VENTA': 'sum', 'META': 'sum', 'M2': 'sum'}).reset_index()
subtotales['CATEGORIA'] = 'TOTAL DEPARTAMENTO'
subtotales['AVANCE'] = np.where(subtotales['META'] > 0, (subtotales['VENTA'] / subtotales['META']) * 100, 0.0)
subtotales['EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)'] = np.where(subtotales['M2'] > 0, subtotales['VENTA'] / subtotales['M2'], 0.0)
subtotales['ORDEN_REGISTRO'] = 1

# Generación de la Fila del TOTAL GENERAL del Reporte
total_g_venta = tabla_base["VENTA"].sum()
total_g_meta = subtotales["META"].sum()
total_g_m2 = subtotales["M2"].sum()
total_g_avance = (total_g_venta / total_g_meta) * 100 if total_g_meta > 0 else 0.0
total_g_eficiencia = total_g_venta / total_g_m2 if total_g_m2 > 0 else 0.0

fila_total_general = pd.DataFrame([{
    'DEPARTAMENTO': 'TOTAL GENERAL',
    'CATEGORIA': 'REPORTE CONSOLIDADO',
    'M2': total_g_m2,
    'VENTA': total_g_venta,
    'META': total_g_meta,
    'AVANCE': total_g_avance,
    'EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)': total_g_eficiencia,
    'ORDEN_REGISTRO': 2
}])

# Unificación final de la matriz
tabla_final = pd.concat([tabla_base, subtotales, fila_total_general], ignore_index=True)

# Mantener orden estructural jerárquico
tabla_final['DEPARTAMENTO'] = pd.Categorical(
    tabla_final['DEPARTAMENTO'], 
    categories=orden_departamentos + ['TOTAL GENERAL'], 
    ordered=True
)
tabla_final = tabla_final.sort_values(by=["DEPARTAMENTO", "ORDEN_REGISTRO", "VENTA"], ascending=[True, True, False])
tabla_final = tabla_final.drop(columns=['M2', 'ORDEN_REGISTRO'])

# Clon limpio con números reales para construir la exportación a Excel formulable
df_para_excel = tabla_final.copy()

# Dar formato estético de texto para mostrar de forma visual en la App
df_render_app = tabla_final.copy()
df_render_app['VENTA'] = df_render_app['VENTA'].apply(formatear_moneda)
df_render_app['META'] = df_render_app['META'].apply(formatear_moneda)
df_render_app['AVANCE'] = df_render_app['AVANCE'].apply(formatear_porcentaje)
df_render_app['EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)'] = df_render_app['EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)'].apply(formatear_moneda)

# Renombrar para cabeceras más estéticas en la UI de la App
df_render_app = df_render_app.rename(columns={
    'DEPARTAMENTO': 'DEPARTAMENTO',
    'CATEGORIA': 'CATEGORÍA'
})

# -----------------------------------
# DISEÑO DE COLORES TOTALMENTE EXTENDIDO A LA APP
# -----------------------------------
def aplicar_colores_matriz(row):
    if row['DEPARTAMENTO'] == 'TOTAL GENERAL':
        return ['font-weight: bold; background-color: #A7F3D0; color: #047857; border-top: 2px double #047857; border-bottom: 2px double #047857;'] * len(row)
    elif row['CATEGORÍA'] == 'TOTAL DEPARTAMENTO':
        return ['font-weight: bold; background-color: #D1FAE5; color: #065F46; border-bottom: 2px solid #10B981;'] * len(row)
    return ['background-color: #FFFFFF; color: #1F2937; border-bottom: 1px solid #E5E7EB;'] * len(row)

tabla_estilizada = (
    df_render_app.style
    .apply(aplicar_colores_matriz, axis=1)
    .set_properties(**{'text-align': 'right', 'font-family': 'Arial'})
)

# -----------------------------------
# KPIs GLOBALES (SINCERADOS)
# -----------------------------------
total_ventas = total_g_venta
meta_dinamica_total = total_g_meta
avance_general = total_g_avance
eficiencia_total = total_g_eficiencia

# -----------------------------------
# FUNCIONES DE GENERACIÓN DE EXPORTABLES
# -----------------------------------
def generar_excel_descarga_sumable(dataframe):
    output = io.BytesIO()
    
    df_excel = dataframe[dataframe['CATEGORIA'] != 'TOTAL DEPARTAMENTO'].copy()
    df_excel['AVANCE'] = df_excel['AVANCE'] / 100.0
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='Reporte Comercial')
        
        workbook = writer.book
        worksheet = writer.sheets['Reporte Comercial']
        
        formato_numero_excel = '#,##0.00'
        formato_porcentaje_excel = '0.00%'
        
        for row in range(2, len(df_excel) + 2):
            worksheet[f'C{row}'].number_format = formato_numero_excel
            worksheet[f'D{row}'].number_format = formato_numero_excel
            worksheet[f'E{row}'].number_format = formato_porcentaje_excel
            worksheet[f'F{row}'].number_format = formato_numero_excel
            
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
    story.append(Paragraph(f"Filtros aplicados - Ventas Totales: {ventas} | Meta Dinámica: {meta} | Avance: {avance} | EFICIENCIA EXHIBICION FRONTAL (VENTA/M2): {eficiencia}", subtitle_style))
    story.append(Spacer(1, 8))
    
    data_tabla = [[Paragraph("<b>DEPARTAMENTO</b>", header_table_style), 
                    Paragraph("<b>CATEGORÍA</b>", header_table_style), 
                    Paragraph("<b>VENTA</b>", header_table_style), 
                    Paragraph("<b>META</b>", header_table_style), 
                    Paragraph("<b>AVANCE</b>", header_table_style), 
                    Paragraph("<b>EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)</b>", header_table_style)]]
    
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
        es_subtotal = (row[1] == 'TOTAL DEPARTAMENTO')
        
        style_actual = cell_total_style if (es_subtotal or es_total_general) else cell_table_style
        
        data_tabla.append([
            Paragraph(str(row[0]), style_actual),
            Paragraph(str(row[1]), style_actual),
            Paragraph(formatear_moneda(row[2]), style_actual),
            Paragraph(formatear_moneda(row[3]), style_actual),
            Paragraph(formatear_porcentaje(row[4]), style_actual),
            Paragraph(formatear_moneda(row[5]), style_actual)
        ])
        
        if es_total_general:
            estilos_celdas.append(('BACKGROUND', (0, idx_fila), (-1, idx_fila), colors.HexColor('#A7F3D0')))
            estilos_celdas.append(('TEXTCOLOR', (0, idx_fila), (-1, idx_fila), colors.HexColor('#047857')))
        elif es_subtotal:
            estilos_celdas.append(('BACKGROUND', (0, idx_fila), (-1, idx_fila), colors.HexColor('#D1FAE5')))
            estilos_celdas.append(('TEXTCOLOR', (0, idx_fila), (-1, idx_fila), colors.HexColor('#065F46')))
            
    pdf_table = Table(data_tabla, colWidths=[160, 160, 100, 100, 70, 100])
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
    col2.metric("META FIJADA (X2)", formatear_moneda(meta_dinamica_total))
    col3.metric("PORCENTAJE DE AVANCE", formatear_porcentaje(avance_general))
    col4.metric("EFICIENCIA EXHIBICION FRONTAL (VENTA/M2)", formatear_moneda(eficiencia_total))

    st.markdown("---")
    
    st.dataframe(tabla_estilizada, use_container_width=True, height=530, hide_index=True)

    st.markdown("### 📥 MENÚ DE DESCARGA DE REPORTES")
    st.info("El informe de Excel se descarga libre de filas de subtotales y con codificación contable nativa de miles/decimales, permitiéndote realizar operaciones matemáticas al instante.")
    
    bot1, bot2 = st.columns(2)
    
    data_excel = generar_excel_descarga_sumable(df_para_excel)
    bot1.download_button(
        label="🟩 Descargar Reporte en Excel (Sumable)",
        data=data_excel,
        file_name=f"Reporte_Comercial_{año_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    
    data_pdf = generar_pdf_descarga(
        tabla_final, 
        año_sel, 
        formatear_moneda(total_ventas), 
        formatear_moneda(meta_dinamica_total), 
        formatear_porcentaje(avance_general), 
        formatear_moneda(eficiencia_total)
    )
    bot2.download_button(
        label="🟦 Descargar Reporte Completo en PDF",
        data=data_pdf,
        file_name=f"Reporte_Comercial_{año_sel}.pdf",
        mime="application/pdf",
        use_container_width=True
    )