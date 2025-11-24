import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import unicodedata
import re

# ----------------------------------------------------------
# FUNCIONES DE TEXTO
# ----------------------------------------------------------
def normalizar(texto: str) -> str:
    """Pasa a minúsculas, elimina tildes y espacios dobles."""
    if not isinstance(texto, str):
        texto = str(texto)

    # Remover acentos
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

    # Minúsculas + limpiar espacios
    texto = texto.lower().strip()
    texto = re.sub(r"\s+", " ", texto)

    return texto


# ----------------------------------------------------------
# CARGA DEL EXCEL
# ----------------------------------------------------------
import zipfile
import pandas as pd

@st.cache_data
def cargar_excel():
    # Ruta del archivo ZIP en Hugging Face
    zip_path = "CALCULADORA.zip"  # El nombre exacto del archivo ZIP subido

    # Archivo Excel dentro del ZIP
    xlsm_name = "CALCULADORA DE MACRO Y MICRONUTRIENTES 2023.xlsm"  # Nombre del archivo Excel dentro del ZIP

    # Extraer y leer el archivo Excel desde el ZIP
    with zipfile.ZipFile(zip_path) as z:
        with z.open(xlsm_name) as f:
            df = pd.read_excel(f, engine="openpyxl", header=2)

    # Asegurar que la primera columna se llame "Alimento"
    primera_col = df.columns[0]
    if primera_col != "Alimento":
        df = df.rename(columns={primera_col: "Alimento"})

    # Limpiar los valores
    df["Alimento"] = df["Alimento"].astype(str).str.strip()
    df["Alimento_normalizado"] = df["Alimento"].apply(normalizar)

    return df


    # Asegurar que la primera columna se llame "Alimento"
    primera_col = df.columns[0]
    if primera_col != "Alimento":
        df = df.rename(columns={primera_col: "Alimento"})

    # Limpiar espacios en el nombre del alimento
    df["Alimento"] = df["Alimento"].astype(str).str.strip()

    # Columna normalizada (sin tildes, minúsculas) para las búsquedas
    df["Alimento_normalizado"] = df["Alimento"].apply(normalizar)

    return df


    # Asegurar que la primera columna se llame "Alimento"
    primera_col = df.columns[0]
    if primera_col != "Alimento":
        df = df.rename(columns={primera_col: "Alimento"})

    # Limpiar espacios en el nombre del alimento
    df["Alimento"] = df["Alimento"].astype(str).str.strip()

    # Columna normalizada (sin tildes, minúsculas) para las búsquedas
    df["Alimento_normalizado"] = df["Alimento"].apply(normalizar)

    return df


df_base = cargar_excel()

def cargar_personalizados():
    """Lee un CSV con alimentos agregados por el usuario."""
    try:
        dfp = pd.read_csv("alimentos_personalizados.csv")
    except FileNotFoundError:
        # Si no existe, devolvemos un DF vacío con las mismas columnas
        dfp = pd.DataFrame(columns=df_base.columns)

    # Aseguramos que tenga las mismas columnas que la tabla base
    for col in df_base.columns:
        if col not in dfp.columns:
            dfp[col] = 0

    # Mismo orden de columnas
    dfp = dfp[df_base.columns]

    return dfp

df_personal = cargar_personalizados()

# Unimos tabla oficial + personalizados
df = pd.concat([df_base, df_personal], ignore_index=True)

# Limpiamos nombre y columna normalizada nuevamente
df["Alimento"] = df["Alimento"].astype(str).str.strip()
df["Alimento_normalizado"] = df["Alimento"].apply(normalizar)


# ----------------------------------------------------------
# FUNCIÓN PARA BUSCAR ALIMENTO (SIN TILDES / PARCIAL)
# ----------------------------------------------------------
def buscar_alimento(nombre: str):
    nombre_norm = normalizar(nombre)
    coincidencias = df[df["Alimento_normalizado"].str.contains(nombre_norm, na=False)]
    if coincidencias.empty:
        return None
    return coincidencias.iloc[0]  # primera coincidencia


# ----------------------------------------------------------
# FUNCIÓN PARA CALCULAR SELLOS (según valores por 100 g/ml y tipo)
# ----------------------------------------------------------
def calcular_sellos(fila, tipo_producto: str):
    """
    tipo_producto: "Sólido" o "Líquido"
    Usa los umbrales oficiales de la fase final del etiquetado chileno.
    """
    sellos = []

    energia = fila.get("Energía(kcal)", 0)           # por 100 g/ml
    azucares = fila.get("Azúcares totales (g)", 0)   # por 100 g/ml
    grasas_sat = fila.get("AG Sat (g)", 0)           # por 100 g/ml
    sodio = fila.get("Sodio (mg)", 0)                # por 100 g/ml

    # Umbrales oficiales fase 3 (actual)
    if tipo_producto == "Sólido":
        umbrales = {
            "calorias": 275,   # kcal / 100 g
            "azucares": 10,    # g / 100 g
            "grasas_sat": 4,   # g / 100 g
            "sodio": 400       # mg / 100 g
        }
    else:  # Líquido
        umbrales = {
            "calorias": 70,    # kcal / 100 ml
            "azucares": 5,     # g / 100 ml
            "grasas_sat": 3,   # g / 100 ml
            "sodio": 100       # mg / 100 ml
        }

    if energia >= umbrales["calorias"]:
        sellos.append("ALTO EN CALORÍAS")
    if azucares >= umbrales["azucares"]:
        sellos.append("ALTO EN AZÚCARES")
    if grasas_sat >= umbrales["grasas_sat"]:
        sellos.append("ALTO EN GRASAS SATURADAS")
    if sodio >= umbrales["sodio"]:
        sellos.append("ALTO EN SODIO")

    return sellos


# ----------------------------------------------------------
# CONSTRUCTOR DE ETIQUETA HTML TIPO MANUAL CHILENO
# ----------------------------------------------------------
def construir_etiqueta_html_manual(
    nombre_producto,
    porcion,
    porciones_envase,
    # macros
    energia_100, energia_porcion,   # energia_porcion ya no se usa, se recalcula adentro
    prot_100, prot_porcion,
    grasa_total_100, grasa_total_porcion,
    grasa_sat_100, grasa_sat_porcion,
    hdc_100, hdc_porcion,
    azucar_100, azucar_porcion,
    sodio_100, sodio_porcion,
    # desglose grasas opcional
    mono_100=0.0, mono_porcion=0.0,
    poli_100=0.0, poli_porcion=0.0,
    trans_100=0.0, trans_porcion=0.0,
    incluir_desglose_grasas=False,
    # fibra opcional
    fibra_100=0.0, fibra_porcion=0.0,
    incluir_fibra=False,
    # micronutrientes opcionales
    calcio_100=0.0, calcio_porcion=0.0,
    hierro_100=0.0, hierro_porcion=0.0,
    zinc_100=0.0, zinc_porcion=0.0,
    vitd_100=0.0, vitd_porcion=0.0,
    vitb12_100=0.0, vitb12_porcion=0.0,
    folatos_100=0.0, folatos_porcion=0.0,
    incluir_micros=False,
    texto_porcion=None,   # 👈 ahora el parámetro con default va al final
):

    """
    Devuelve un bloque HTML con el formato tipo manual chileno:
    encabezado negro, tabla con columnas 100 g y 1 porción.
    La columna "1 porción" SIEMPRE se calcula como:
        valor_100 * (porcion / 100)
    """

    # Factor de conversión de 100 g/ml a la porción declarada
    factor_porcion = porcion / 100.0

    def v_porcion(v100):
        try:
            return float(v100) * factor_porcion
        except (TypeError, ValueError):
            return 0.0

    # --------- MACROS (se recalculan por porción aquí dentro) ---------
    energia_porcion_calc      = v_porcion(energia_100)
    prot_porcion_calc         = v_porcion(prot_100)
    grasa_total_porcion_calc  = v_porcion(grasa_total_100)
    grasa_sat_porcion_calc    = v_porcion(grasa_sat_100)
    hdc_porcion_calc          = v_porcion(hdc_100)
    azucar_porcion_calc       = v_porcion(azucar_100)
    sodio_porcion_calc        = v_porcion(sodio_100)

    mono_porcion_calc         = v_porcion(mono_100)
    poli_porcion_calc         = v_porcion(poli_100)
    trans_porcion_calc        = v_porcion(trans_100)

    fibra_porcion_calc        = v_porcion(fibra_100)

    calcio_porcion_calc       = v_porcion(calcio_100)
    hierro_porcion_calc       = v_porcion(hierro_100)
    zinc_porcion_calc         = v_porcion(zinc_100)
    vitd_porcion_calc         = v_porcion(vitd_100)
    vitb12_porcion_calc       = v_porcion(vitb12_100)
    folatos_porcion_calc      = v_porcion(folatos_100)

    filas = []

    # nombre, valor 100 g, valor 1 porción, decimales
    filas.append(("Energía (kcal)", energia_100, energia_porcion_calc, 0))
    filas.append(("Proteínas (g)", prot_100, prot_porcion_calc, 1))
    filas.append(("Grasa Total (g)", grasa_total_100, grasa_total_porcion_calc, 1))

    # Grasas bajo Grasa Total
    if incluir_desglose_grasas:
        filas.append(("  Saturadas (g)", grasa_sat_100, grasa_sat_porcion_calc, 1))
        filas.append(("  Monoinsaturadas (g)", mono_100, mono_porcion_calc, 1))
        filas.append(("  Poliinsaturadas (g)", poli_100, poli_porcion_calc, 1))
        filas.append(("  Trans (g)", trans_100, trans_porcion_calc, 2))
    else:
        # al menos saturadas (norma chilena)
        filas.append(("  Saturadas (g)", grasa_sat_100, grasa_sat_porcion_calc, 1))

    filas.append(("H. de C. Disp. (g)", hdc_100, hdc_porcion_calc, 1))
    filas.append(("Azúcares Totales (g)", azucar_100, azucar_porcion_calc, 1))
    filas.append(("Sodio (mg)", sodio_100, sodio_porcion_calc, 1))

    if incluir_fibra:
        filas.append(("Fibra Alimentaria (g)", fibra_100, fibra_porcion_calc, 1))

    # Construir filas HTML de la tabla principal
    filas_html = ""
    for nombre, v100, vpor, dec in filas:
        fmt = f"{{:.{dec}f}}"
        filas_html += f"""
  <tr>
    <td style="border-bottom:1px solid #ccc; padding:2px 4px;">{nombre}</td>
    <td style="border-bottom:1px solid #ccc; padding:2px 4px; text-align:right;">{fmt.format(v100)}</td>
    <td style="border-bottom:1px solid #ccc; padding:2px 4px; text-align:right;">{fmt.format(vpor)}</td>
  </tr>
"""

    # Micronutrientes (bloque aparte, sólo si se pide)
    micros_html = ""
    if incluir_micros:
        micros_html = f"""
  <div style="border-top:1px solid #000; margin-top:6px; padding-top:4px; font-size:11px; font-weight:bold;">
    Micronutrientes (por porción)
  </div>
  <div style="font-size:11px; margin-top:3px;">
    Calcio: {calcio_porcion_calc:.0f} mg<br>
    Hierro: {hierro_porcion_calc:.1f} mg<br>
    Zinc: {zinc_porcion_calc:.2f} mg<br>
    Vitamina D: {vitd_porcion_calc:.2f} µg<br>
    Vitamina B12: {vitb12_porcion_calc:.2f} µg<br>
    Folatos: {folatos_porcion_calc:.1f} µg
  </div>
"""

    # Texto que se mostrará como descripción de la porción en la etiqueta
    if texto_porcion:
        porcion_label = texto_porcion
    else:
        porcion_label = f"{porcion:.0f} g/ml"

    html = f"""
<div style="border:2px solid #000; width:340px; font-family:Arial,sans-serif; background:#ffffff; color:#000;">
  <div style="background:#000; color:#fff; text-align:center; font-weight:bold; padding:4px 0; font-size:14px;">
    INFORMACIÓN NUTRICIONAL
  </div>
  <div style="padding:4px 6px; border-bottom:1px solid #000; font-size:12px;">
    <b>Porción:</b> {porcion_label}<br>
    <b>Porciones por envase:</b> {porciones_envase:.0f}
  </div>
  <table style="width:100%; border-collapse:collapse; font-size:12px;">
    <tr>
      <th style="border-bottom:1px solid #000; padding:2px 4px; text-align:left;"></th>
      <th style="border-bottom:1px solid #000; padding:2px 4px; text-align:center;">100 g</th>
      <th style="border-bottom:1px solid #000; padding:2px 4px; text-align:center;">1 porción</th>
    </tr>
    {filas_html}
  </table>
  {micros_html}
</div>
"""
    return html



# ----------------------------------------------------------
# FUNCIÓN PARA GENERAR IMAGEN DE ETIQUETA (PNG)
# (formato simple, usa mismos macros; se puede refinar luego)
# ----------------------------------------------------------
def generar_imagen_etiqueta(
    nombre_alimento,
    porcion,
    porciones_envase,
    energia_porcion,
    energia_100,
    proteinas_porcion,
    grasas_total_porcion,
    grasas_sat_porcion,
    hdc_porcion,
    azucares_porcion,
    sodio_porcion,
    sodio_100,
    fibra_porcion=0.0,
    fibra_100=0.0,
    trans_porcion=0.0,
    trans_100=0.0,
    incluir_fibra=False,
    incluir_trans=False,
    texto_porcion=None,
):
    # Tamaño base de la imagen
    img = Image.new("RGB", (800, 900), "white")
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.load_default()
    font_bold = ImageFont.load_default()
    font_normal = ImageFont.load_default()

    x_margin = 40
    y = 30

    draw.text((x_margin, y), "INFORMACIÓN NUTRICIONAL", font=font_title, fill="black")
    y += 30

    draw.text((x_margin, y), f"Producto: {nombre_alimento}", font=font_normal, fill="black")
    y += 25

    # Texto de porción en la imagen
    if texto_porcion:
        porcion_label_img = texto_porcion
    else:
        porcion_label_img = f"{porcion:.0f} g/ml"

    draw.text((x_margin, y), f"Porción: {porcion_label_img}", font=font_normal, fill="black")
    y += 20
    draw.text((x_margin, y), f"Porciones por envase: {porciones_envase}", font=font_normal, fill="black")
    y += 30

    draw.line((x_margin, y, 760, y), fill="black", width=2)
    y += 10

    draw.text((x_margin, y), "Nutriente", font=font_bold, fill="black")
    draw.text((x_margin + 300, y), f"Por {porcion:.0f} g/ml", font=font_bold, fill="black")
    draw.text((x_margin + 550, y), "Por 100 g/ml", font=font_bold, fill="black")
    y += 25

    draw.line((x_margin, y, 760, y), fill="black", width=1)
    y += 10

    def fila(nutriente, valor_porcion_str, valor_100_str):
        nonlocal y
        draw.text((x_margin, y), nutriente, font=font_normal, fill="black")
        draw.text((x_margin + 300, y), valor_porcion_str, font=font_normal, fill="black")
        draw.text((x_margin + 550, y), valor_100_str, font=font_normal, fill="black")
        y += 22

    fila("Energía (kcal)", f"{energia_porcion:.0f}", f"{energia_100:.0f}")
    fila("Proteínas (g)", f"{proteinas_porcion:.1f}", "-")
    fila("Grasas totales (g)", f"{grasas_total_porcion:.1f}", "-")
    fila("   de las cuales saturadas (g)", f"{grasas_sat_porcion:.1f}", "-")
    fila("Hidratos de carbono disp. (g)", f"{hdc_porcion:.1f}", "-")
    fila("   azúcares totales (g)", f"{azucares_porcion:.1f}", "-")
    fila("Sodio (mg)", f"{sodio_porcion:.0f}", f"{sodio_100:.0f}")

    if incluir_fibra:
        fila("Fibra alimentaria (g)", f"{fibra_porcion:.1f}", f"{fibra_100:.1f}")

    if incluir_trans:
        fila("Grasas trans (g)", f"{trans_porcion:.2f}", f"{trans_100:.2f}")

    y += 20
    draw.line((x_margin, y, 760, y), fill="black", width=2)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ----------------------------------------------------------
# INTERFAZ STREAMLIT
# ----------------------------------------------------------
st.set_page_config(page_title="Calculadora Nutricional Chile", layout="wide")

# ================= CABECERA CENTRADA CON LOGO =================
from PIL import Image
import streamlit as st

# Cargar logo (asegúrate del nombre del archivo)
logo = Image.open("logonr-300x60.png")  # <-- cambia el nombre si es distinto

# Convertir logo a bytes para usarlo en HTML
import base64
from io import BytesIO

buffer = BytesIO()
logo.save(buffer, format="PNG")
logo_b64 = base64.b64encode(buffer.getvalue()).decode()

# Mostrar logo centrado con HTML puro
st.markdown(
    f"""
    <div style="text-align:center; margin-top:20px; margin-bottom:10px;">
        <img src="data:image/png;base64,{logo_b64}" width="250">
    </div>
    """,
    unsafe_allow_html=True
)

# Título centrado
st.markdown(
    """
    <h1 style="text-align:center;">
        Creador de Etiquetas Nutricionales de Alimentos Chilena
    </h1>
    """,
    unsafe_allow_html=True
)

# ======= INSTRUCCIONES DE USO (texto centrado) =======

# ====== INSTRUCCIONES DE USO ======
with st.expander("📘 Ver instrucciones de uso"):
    st.markdown("""
    ### 🧮 Calculadora de Etiquetado Nutricional de Alimentos Chilenos

    - 🥗 **Alimento individual**  
      - Busca un alimento escribiendo su nombre (con o sin tildes).  
      - Define la **porción** que quieres evaluar:  
        - Ej.: `1 mandarina`, `3/4 taza`, `1 rebanada`, etc.  
        - Indica cuántos **g/ml** equivale esa porción (ej.: 120 g, 50 ml).  
      - Indica cuántas **porciones por envase** tiene el producto.  
      - El programa calcula automáticamente los nutrientes **por 100 g/ml** y **por porción**.

    - 🍲 **Preparación / Receta**  
      - Activa el modo de **preparación con varios alimentos**.  
      - Agrega todos los alimentos que componen la receta y sus **cantidades (g/ml)**.  
      - Define la **porción de la preparación** (ej.: `1 taza`, `1 porción (plato)`) y su equivalente en g/ml.  
      - Indica cuántas **porciones por preparación/envase** obtienes.

    - ⚙️ **Opciones avanzadas**  
      - Puedes mostrar el **desglose de grasas** (saturadas, monoinsaturadas, poliinsaturadas, trans).  
      - Puedes incluir **fibra alimentaria** y **micronutrientes** (Ca, Fe, Zn, Vit D, B12, Folatos) cuando estén disponibles en la base de datos.

    - ⚠️ **Sellos de advertencia MINSAL**  
      - Los sellos se calculan automáticamente según los valores por **100 g o 100 ml**, de acuerdo con la **normativa chilena vigente**.  
      - Si corresponde, se mostrarán los octógonos de **“ALTO EN…”** (azúcares, calorías, grasas saturadas, sodio) y podrás descargarlos en PNG.

    - 🧾 **Etiqueta y descargas**  
      - La etiqueta nutricional se genera de forma automática con un formato similar al del **manual de etiquetado chileno**.  
      - Puedes **previsualizar** la etiqueta y descargarla como **imagen PNG** para usarla en el envase o en tus informes.
    """)



# ===================== MODO 1: UN SOLO ALIMENTO =====================
st.header("🥛 Un solo alimento")

col1, col2 = st.columns([2, 1])

with col1:
    alimento_ingresado = st.text_input("🔍 Buscar alimento (con o sin tildes):", "")

with col2:
    # Descripción de la porción + equivalente en g/ml
    col_por1, col_por2 = st.columns(2)
    with col_por1:
        descripcion_porcion = st.text_input(
            "Descripción de la porción",
            value="1 porción",
            help="Ej: 1 mandarina, 1 unidad, 3/4 taza, 1 vaso, etc."
        )
    with col_por2:
        porcion = st.number_input(
            "Equivalente (g/ml) de esa porción",
            value=100,
            min_value=1,
            step=1,
            format="%d",
            help="Cuántos g o ml son esa porción (ej: 1 mandarina = 120 g)"
        )

    porciones_envase = st.number_input(
        "Porciones por envase",
        value=1,
        min_value=1,
        step=1,
        format="%d",
    )

    tipo_producto = st.radio("Tipo de producto", ["Sólido", "Líquido"])

    st.markdown("**Opciones de detalle en la etiqueta:**")
    incluir_desglose_grasas = st.checkbox(
        "Mostrar desglose de grasas (sat/mono/poli/trans)", value=False
    )
    incluir_fibra = st.checkbox("Incluir Fibra Alimentaria", value=False)
    incluir_micros = st.checkbox(
        "Incluir micronutrientes (Ca, Fe, Zn, Vit D, B12, Folatos)", value=False
    )

if alimento_ingresado:

    resultado = buscar_alimento(alimento_ingresado)

    if resultado is None:
        st.error("❌ No se encontró el alimento. Prueba con otra palabra o parte del nombre.")
    else:
        st.success(f"✔ Se encontró: **{resultado['Alimento']}**")

        # Factor de porción respecto a la columna Cantidad(g/ml)
        cantidad_base = resultado.get("Cantidad(g/ml)", 100)
        if not isinstance(cantidad_base, (int, float)) or cantidad_base == 0:
            cantidad_base = 100  # seguridad

        factor = porcion / cantidad_base

        # ------------------- DATOS POR PORCIÓN (TABLA COMPLETA) -------------------
        st.subheader(f"Resultados nutricionales para {porcion:.0f} g/ml")

        datos_porcionados = {}
        for columna, valor in resultado.items():
            if isinstance(valor, (int, float)):
                datos_porcionados[columna] = round(valor * factor, 2)
            else:
                datos_porcionados[columna] = valor

        df_resultado = pd.DataFrame(datos_porcionados, index=[0])

        columnas_ocultas = ["Columna1", "Fuente"]
        df_mostrar = df_resultado.drop(
            columns=[c for c in columnas_ocultas if c in df_resultado.columns],
            errors="ignore"
        )
        st.dataframe(df_mostrar, use_container_width=True)

        # ------------------- OBTENER VALORES CLAVE -------------------
        energia_porcion = datos_porcionados.get("Energía(kcal)", 0.0)
        energia_100 = resultado.get("Energía(kcal)", 0.0)

        proteinas_porcion = datos_porcionados.get("Proteínas (g)", 0.0)
        proteinas_100 = resultado.get("Proteínas (g)", 0.0)

        grasas_total_porcion = datos_porcionados.get("Lípidos totales (g)", 0.0)
        grasas_total_100 = resultado.get("Lípidos totales (g)", 0.0)

        grasas_sat_porcion = datos_porcionados.get("AG Sat (g)", 0.0)
        grasas_sat_100 = resultado.get("AG Sat (g)", 0.0)

        hdc_porcion = datos_porcionados.get("HdeC disp (g)", 0.0)
        hdc_100 = resultado.get("HdeC disp (g)", 0.0)

        azucares_porcion = datos_porcionados.get("Azúcares totales (g)", 0.0)
        azucares_100 = resultado.get("Azúcares totales (g)", 0.0)

        sodio_porcion = datos_porcionados.get("Sodio (mg)", 0.0)
        sodio_100 = resultado.get("Sodio (mg)", 0.0)

        # Grasas mono/poli/trans
        mono_porcion = datos_porcionados.get("AG Mono (g)", 0.0)
        mono_100 = resultado.get("AG Mono (g)", 0.0)
        poli_porcion = datos_porcionados.get("AG Poli (g)", 0.0)
        poli_100 = resultado.get("AG Poli (g)", 0.0)

        # Fibra y trans
        fibra_porcion = datos_porcionados.get("Fibra Total (g)", 0.0)
        fibra_100 = resultado.get("Fibra Total (g)", 0.0)
        trans_porcion = datos_porcionados.get("AG Trans (g)", 0.0)
        trans_100 = resultado.get("AG Trans (g)", 0.0)

        # Micronutrientes
        calcio_porcion = datos_porcionados.get("Calcio (mg)", 0.0)
        calcio_100 = resultado.get("Calcio (mg)", 0.0)
        hierro_porcion = datos_porcionados.get("Hierro (mg)", 0.0)
        hierro_100 = resultado.get("Hierro (mg)", 0.0)
        zinc_porcion = datos_porcionados.get("Zinc (mg)", 0.0)
        zinc_100 = resultado.get("Zinc (mg)", 0.0)
        vitd_porcion = datos_porcionados.get("Vit D (ug)", 0.0)
        vitd_100 = resultado.get("Vit D (ug)", 0.0)
        vitb12_porcion = datos_porcionados.get("Vit B12 (ug)", 0.0)
        vitb12_100 = resultado.get("Vit B12 (ug)", 0.0)
        folatos_porcion = datos_porcionados.get("Folatos (ug)", 0.0)
        folatos_100 = resultado.get("Folatos (ug)", 0.0)

        # ------------------- ETIQUETA NUTRICIONAL HTML (FORMATO MANUAL) -------------------
        st.subheader("🧾 Etiqueta nutricional (vista previa)")
        st.markdown(f"**Producto:** {resultado['Alimento']}")

        # Texto de porción para mostrar en la etiqueta (ej: "1 mandarina (120 g/ml)")
        desc_clean = (descripcion_porcion or "").strip()
        if desc_clean:
            texto_porcion = f"{desc_clean} ({porcion:.0f} g/ml)"
        else:
            texto_porcion = f"{porcion:.0f} g/ml"

        etiqueta_html = construir_etiqueta_html_manual(
            nombre_producto=resultado["Alimento"],
            porcion=porcion,
            porciones_envase=porciones_envase,
            texto_porcion=texto_porcion,
            energia_100=energia_100,
            energia_porcion=energia_porcion,
            prot_100=proteinas_100,
            prot_porcion=proteinas_porcion,
            grasa_total_100=grasas_total_100,
            grasa_total_porcion=grasas_total_porcion,
            grasa_sat_100=grasas_sat_100,
            grasa_sat_porcion=grasas_sat_porcion,
            hdc_100=hdc_100,
            hdc_porcion=hdc_porcion,
            azucar_100=azucares_100,
            azucar_porcion=azucares_porcion,
            sodio_100=sodio_100,
            sodio_porcion=sodio_porcion,
            mono_100=mono_100,
            mono_porcion=mono_porcion,
            poli_100=poli_100,
            poli_porcion=poli_porcion,
            trans_100=trans_100,
            trans_porcion=trans_porcion,
            incluir_desglose_grasas=incluir_desglose_grasas,
            fibra_100=fibra_100,
            fibra_porcion=fibra_porcion,
            incluir_fibra=incluir_fibra,
            calcio_100=calcio_100,
            calcio_porcion=calcio_porcion,
            hierro_100=hierro_100,
            hierro_porcion=hierro_porcion,
            zinc_100=zinc_100,
            zinc_porcion=zinc_porcion,
            vitd_100=vitd_100,
            vitd_porcion=vitd_porcion,
            vitb12_100=vitb12_100,
            vitb12_porcion=vitb12_porcion,
            folatos_100=folatos_100,
            folatos_porcion=folatos_porcion,
            incluir_micros=incluir_micros,
        )
        st.markdown(etiqueta_html, unsafe_allow_html=True)

        # ------------------- GENERAR IMAGEN Y BOTÓN DE DESCARGA -------------------
        st.subheader("📥 Descargar etiqueta como imagen PNG")

        img_buf = generar_imagen_etiqueta(
            nombre_alimento=resultado["Alimento"],
            porcion=porcion,
            porciones_envase=porciones_envase,
            energia_porcion=energia_porcion,
            energia_100=energia_100,
            proteinas_porcion=proteinas_porcion,
            grasas_total_porcion=grasas_total_porcion,
            grasas_sat_porcion=grasas_sat_porcion,
            hdc_porcion=hdc_porcion,
            azucares_porcion=azucares_porcion,
            sodio_porcion=sodio_porcion,
            sodio_100=sodio_100,
            fibra_porcion=fibra_porcion,
            fibra_100=fibra_100,
            trans_porcion=trans_porcion,
            trans_100=trans_100,
            incluir_fibra=incluir_fibra,
            incluir_trans=incluir_desglose_grasas,  # trans como parte del desglose
            texto_porcion=texto_porcion,
        )

        st.download_button(
            label="⬇️ Descargar etiqueta PNG",
            data=img_buf,
            file_name=f"etiqueta_{resultado['Alimento']}.png",
            mime="image/png"
        )


        # ------------------- SELLOS MINSAL -------------------
        st.subheader("⚠️ Sellos de advertencia (según 100 g o 100 ml)")

        # Calculamos los sellos usando la misma función que ya existe
        sellos_unidad = calcular_sellos(resultado, tipo_producto)

        if not sellos_unidad:
            st.success(
                f"✅ Este producto ({tipo_producto.lower()}) NO presenta sellos de advertencia "
                "según los umbrales oficiales de la fase actual."
            )
        else:
            st.write("Sellos que debe llevar este alimento:")

            # Texto -> clave interna
            mapa_clave = {
                "ALTO EN AZÚCARES": "azucares",
                "ALTO EN CALORÍAS": "calorias",
                "ALTO EN GRASAS SATURADAS": "grasas",
                "ALTO EN SODIO": "sodio",
            }

            # Clave -> (ruta imagen, texto)
            imagenes_sellos = {
                "azucares": ("sellos/alto_azucares.png", "ALTO EN AZÚCARES"),
                "calorias": ("sellos/alto_calorias.png", "ALTO EN CALORÍAS"),
                "grasas": ("sellos/alto_grasas.png", "ALTO EN GRASAS SATURADAS"),
                "sodio": ("sellos/alto_sodio.png", "ALTO EN SODIO"),
            }

            claves_activas = [mapa_clave[s] for s in sellos_unidad if s in mapa_clave]

            cols = st.columns(len(claves_activas))
            for col, clave in zip(cols, claves_activas):
                ruta, texto = imagenes_sellos[clave]
                with col:
                    img = Image.open(ruta)
                    st.image(img, width=120)

                    with open(ruta, "rb") as f:
                        img_bytes = f.read()

                    st.download_button(
                        label=f"Descargar {texto}.png",
                        data=img_bytes,
                        file_name=f"{texto.replace(' ', '_').lower()}.png",
                        mime="image/png",
                    )

        st.divider()

# ===================== MODO 2: PREPARACIÓN CON VARIOS ALIMENTOS =====================
st.header("🥣 Preparación con varios alimentos")

nombre_prep = st.text_input("Nombre de la preparación", "Leche con plátano")
tipo_producto_prep = st.radio("Tipo de producto de la preparación", ["Sólido", "Líquido"], key="tipo_prep_radio")

# Filtrar solo alimentos (sin títulos ni bibliografía)
alimentos_filtrados = df["Alimento"].dropna().astype(str).str.strip()

patron_titulos = r"^\s*\d+(\.\d+)*\s+[A-Za-zÁÉÍÓÚáéíóúñÑ]"
patron_bibliografia = r"^\s*\d+\.\s+[A-Za-z]"
patron_calculo = r"^\s*\d+\.\s+Valor"

alimentos_filtrados = alimentos_filtrados[
    ~alimentos_filtrados.str.match(patron_titulos) &
    ~alimentos_filtrados.str.match(patron_bibliografia) &
    ~alimentos_filtrados.str.match(patron_calculo)
]

alimentos_filtrados = alimentos_filtrados[alimentos_filtrados != ""]

opciones_alimentos = sorted(alimentos_filtrados.unique().tolist(), key=normalizar)

# 🔎 Búsqueda manual sin tildes para la lista de preparación
busqueda_prep = st.text_input(
    "Buscar en la lista de alimentos para la preparación (con o sin tildes):",
    ""
)

if busqueda_prep:
    filtro_norm = normalizar(busqueda_prep)
    opciones_filtradas = [
        a for a in opciones_alimentos
        if filtro_norm in normalizar(a)
    ]
else:
    opciones_filtradas = opciones_alimentos

seleccionados = st.multiselect(
    "Selecciona los alimentos de la preparación",
    opciones_filtradas
)


cantidades = {}
total_peso = 0.0

for alim in seleccionados:
    cant = st.number_input(
        f"Cantidad de {alim} (g/ml)",
        min_value=0.0,
        value=100.0,
        key=f"prep_{alim}"
    )
    cantidades[alim] = cant
    total_peso += cant

# Definir porción de la preparación una vez calculado el peso total
default_porcion_prep = int(total_peso) if total_peso > 0 else 200

col_prep1, col_prep2 = st.columns(2)
with col_prep1:
    descripcion_porcion_prep = st.text_input(
        "Descripción de la porción de la preparación",
        value="1 porción",
        help="Ej: 1 taza, 1 vaso, 1 plato, etc.",
        key="desc_porcion_prep",
    )
with col_prep2:
    porcion_prep = st.number_input(
        "Equivalente (g/ml) de esa porción",
        value=default_porcion_prep,
        min_value=1,
        step=1,
        format="%d",
        key="porcion_prep",
    )

porciones_envase_prep = st.number_input(
    "Porciones por envase/preparación",
    value=1,
    min_value=1,
    step=1,
    format="%d",
    key="porciones_envase_prep",
)


if st.button("Calcular preparación"):
    if not seleccionados or total_peso == 0:
        st.error("Debes seleccionar al menos un alimento y asignar cantidades mayores a 0.")
    else:
        # Columnas numéricas (macro + micro)
        numeric_cols = df.select_dtypes(include="number").columns
        total_nutr = {col: 0.0 for col in numeric_cols}

        for alim in seleccionados:
            cant = cantidades[alim]
            if cant <= 0:
                continue
            fila = df[df["Alimento"] == alim].iloc[0]
            base = fila.get("Cantidad(g/ml)", 100)
            if not isinstance(base, (int, float)) or base == 0:
                base = 100
            factor_alim = cant / base
            for col in numeric_cols:
                val = fila.get(col, 0)
                if pd.notna(val):
                    total_nutr[col] += float(val) * factor_alim

        factor_porcion_prep = porcion_prep / total_peso
        datos_porcion_prep = {col: round(total_nutr[col] * factor_porcion_prep, 2) for col in numeric_cols}

        st.subheader(f"Resultados nutricionales de la preparación por {porcion_prep:.0f} g/ml")

        df_prep = pd.DataFrame(datos_porcion_prep, index=[0])

        columnas_ocultas = ["Columna1", "Fuente"]
        df_prep_mostrar = df_prep.drop(
            columns=[c for c in columnas_ocultas if c in df_prep.columns],
            errors="ignore"
        )
        st.dataframe(df_prep_mostrar, use_container_width=True)

        # Totales y valores por 100 g/ml
        energia_total = total_nutr.get("Energía(kcal)", 0.0)
        energia_porcion_prep = datos_porcion_prep.get("Energía(kcal)", 0.0)
        energia_100_prep = energia_total / total_peso * 100 if total_peso > 0 else 0.0

        prot_total_prep = total_nutr.get("Proteínas (g)", 0.0)
        proteinas_porcion_prep = datos_porcion_prep.get("Proteínas (g)", 0.0)
        proteinas_100_prep = prot_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        grasa_total_total = total_nutr.get("Lípidos totales (g)", 0.0)
        grasas_total_porcion_prep = datos_porcion_prep.get("Lípidos totales (g)", 0.0)
        grasas_total_100_prep = grasa_total_total / total_peso * 100 if total_peso > 0 else 0.0

        grasa_sat_total = total_nutr.get("AG Sat (g)", 0.0)
        grasas_sat_porcion_prep = datos_porcion_prep.get("AG Sat (g)", 0.0)
        grasas_sat_100_prep = grasa_sat_total / total_peso * 100 if total_peso > 0 else 0.0

        hdc_total_prep = total_nutr.get("HdeC disp (g)", 0.0)
        hdc_porcion_prep = datos_porcion_prep.get("HdeC disp (g)", 0.0)
        hdc_100_prep = hdc_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        azucares_total = total_nutr.get("Azúcares totales (g)", 0.0)
        azucares_porcion_prep = datos_porcion_prep.get("Azúcares totales (g)", 0.0)
        azucares_100_prep = azucares_total / total_peso * 100 if total_peso > 0 else 0.0

        sodio_total = total_nutr.get("Sodio (mg)", 0.0)
        sodio_porcion_prep = datos_porcion_prep.get("Sodio (mg)", 0.0)
        sodio_100_prep = sodio_total / total_peso * 100 if total_peso > 0 else 0.0

        # Grasas mono/poli/trans
        mono_total_prep = total_nutr.get("AG Mono (g)", 0.0)
        mono_porcion_prep = datos_porcion_prep.get("AG Mono (g)", 0.0)
        mono_100_prep = mono_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        poli_total_prep = total_nutr.get("AG Poli (g)", 0.0)
        poli_porcion_prep = datos_porcion_prep.get("AG Poli (g)", 0.0)
        poli_100_prep = poli_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        # Fibra y trans
        fibra_total_prep = total_nutr.get("Fibra Total (g)", 0.0)
        fibra_porcion_prep = datos_porcion_prep.get("Fibra Total (g)", 0.0)
        fibra_100_prep = fibra_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        trans_total_prep = total_nutr.get("AG Trans (g)", 0.0)
        trans_porcion_prep = datos_porcion_prep.get("AG Trans (g)", 0.0)
        trans_100_prep = trans_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        # Micronutrientes
        calcio_total_prep = total_nutr.get("Calcio (mg)", 0.0)
        calcio_porcion_prep = datos_porcion_prep.get("Calcio (mg)", 0.0)
        calcio_100_prep = calcio_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        hierro_total_prep = total_nutr.get("Hierro (mg)", 0.0)
        hierro_porcion_prep = datos_porcion_prep.get("Hierro (mg)", 0.0)
        hierro_100_prep = hierro_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        zinc_total_prep = total_nutr.get("Zinc (mg)", 0.0)
        zinc_porcion_prep = datos_porcion_prep.get("Zinc (mg)", 0.0)
        zinc_100_prep = zinc_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        vitd_total_prep = total_nutr.get("Vit D (ug)", 0.0)
        vitd_porcion_prep = datos_porcion_prep.get("Vit D (ug)", 0.0)
        vitd_100_prep = vitd_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        vitb12_total_prep = total_nutr.get("Vit B12 (ug)", 0.0)
        vitb12_porcion_prep = datos_porcion_prep.get("Vit B12 (ug)", 0.0)
        vitb12_100_prep = vitb12_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        folatos_total_prep = total_nutr.get("Folatos (ug)", 0.0)
        folatos_porcion_prep = datos_porcion_prep.get("Folatos (ug)", 0.0)
        folatos_100_prep = folatos_total_prep / total_peso * 100 if total_peso > 0 else 0.0

        # ------------------- ETIQUETA NUTRICIONAL HTML PREPARACIÓN -------------------
        st.subheader("🧾 Etiqueta nutricional de la preparación (vista previa)")
        st.markdown(f"**Preparación:** {nombre_prep}")

        # Texto de porción de la preparación (ej: "1 taza (250 g/ml)")
        desc_prep_clean = (descripcion_porcion_prep or "").strip()
        if desc_prep_clean:
            texto_porcion_prep = f"{desc_prep_clean} ({porcion_prep:.0f} g/ml)"
        else:
            texto_porcion_prep = f"{porcion_prep:.0f} g/ml"

        etiqueta_prep_html = construir_etiqueta_html_manual(
            nombre_producto=nombre_prep,
            porcion=porcion_prep,
            porciones_envase=porciones_envase_prep,
            texto_porcion=texto_porcion_prep,
            energia_100=energia_100_prep,
            energia_porcion=energia_porcion_prep,
            prot_100=proteinas_100_prep,
            prot_porcion=proteinas_porcion_prep,
            grasa_total_100=grasas_total_100_prep,
            grasa_total_porcion=grasas_total_porcion_prep,
            grasa_sat_100=grasas_sat_100_prep,
            grasa_sat_porcion=grasas_sat_porcion_prep,
            hdc_100=hdc_100_prep,
            hdc_porcion=hdc_porcion_prep,
            azucar_100=azucares_100_prep,
            azucar_porcion=azucares_porcion_prep,
            sodio_100=sodio_100_prep,
            sodio_porcion=sodio_porcion_prep,
            mono_100=mono_100_prep,
            mono_porcion=mono_porcion_prep,
            poli_100=poli_100_prep,
            poli_porcion=poli_porcion_prep,
            trans_100=trans_100_prep,
            trans_porcion=trans_porcion_prep,
            incluir_desglose_grasas=incluir_desglose_grasas,
            fibra_100=fibra_100_prep,
            fibra_porcion=fibra_porcion_prep,
            incluir_fibra=incluir_fibra,
            calcio_100=calcio_100_prep,
            calcio_porcion=calcio_porcion_prep,
            hierro_100=hierro_100_prep,
            hierro_porcion=hierro_porcion_prep,
            zinc_100=zinc_100_prep,
            zinc_porcion=zinc_porcion_prep,
            vitd_100=vitd_100_prep,
            vitd_porcion=vitd_porcion_prep,
            vitb12_100=vitb12_100_prep,
            vitb12_porcion=vitb12_porcion_prep,
            folatos_100=folatos_100_prep,
            folatos_porcion=folatos_porcion_prep,
            incluir_micros=incluir_micros,
        )
        st.markdown(etiqueta_prep_html, unsafe_allow_html=True)

        # ------------------- IMAGEN PNG DE LA PREPARACIÓN -------------------
        st.subheader("📥 Descargar etiqueta de la preparación como PNG")

        img_buf_prep = generar_imagen_etiqueta(
            nombre_alimento=nombre_prep,
            porcion=porcion_prep,
            porciones_envase=porciones_envase_prep,
            energia_porcion=energia_porcion_prep,
            energia_100=energia_100_prep,
            proteinas_porcion=proteinas_porcion_prep,
            grasas_total_porcion=grasas_total_porcion_prep,
            grasas_sat_porcion=grasas_sat_porcion_prep,
            hdc_porcion=hdc_porcion_prep,
            azucares_porcion=azucares_porcion_prep,
            sodio_porcion=sodio_porcion_prep,
            sodio_100=sodio_100_prep,
            fibra_porcion=fibra_porcion_prep,
            fibra_100=fibra_100_prep,
            trans_porcion=trans_porcion_prep,
            trans_100=trans_100_prep,
            incluir_fibra=incluir_fibra,
            incluir_trans=incluir_desglose_grasas,
            texto_porcion=texto_porcion_prep,
        )

        st.download_button(
            label="⬇️ Descargar etiqueta PNG de la preparación",
            data=img_buf_prep,
            file_name=f"etiqueta_{nombre_prep}.png",
            mime="image/png"
        )


        # ------------------- SELLOS MINSAL PARA LA PREPARACIÓN -------------------
        st.subheader("⚠️ Sellos de advertencia de la preparación (según 100 g/ml)")

        fila_sellos_prep = {
            "Energía(kcal)": energia_100_prep,
            "Azúcares totales (g)": azucares_100_prep,
            "AG Sat (g)": grasas_sat_100_prep,
            "Sodio (mg)": sodio_100_prep,
        }

        sellos_prep = calcular_sellos(fila_sellos_prep, tipo_producto_prep)

        if not sellos_prep:
            st.success(
                f"✅ Esta preparación ({tipo_producto_prep.lower()}) NO presenta sellos de advertencia "
                "según los umbrales oficiales de la fase actual."
            )
        else:
            st.write("Sellos que debe llevar esta preparación:")

            mapa_clave = {
                "ALTO EN AZÚCARES": "azucares",
                "ALTO EN CALORÍAS": "calorias",
                "ALTO EN GRASAS SATURADAS": "grasas",
                "ALTO EN SODIO": "sodio",
            }

            imagenes_sellos = {
                "azucares": ("sellos/alto_azucares.png", "ALTO EN AZÚCARES"),
                "calorias": ("sellos/alto_calorias.png", "ALTO EN CALORÍAS"),
                "grasas": ("sellos/alto_grasas.png", "ALTO EN GRASAS SATURADAS"),
                "sodio": ("sellos/alto_sodio.png", "ALTO EN SODIO"),
            }

            claves_activas = [mapa_clave[s] for s in sellos_prep if s in mapa_clave]

            cols = st.columns(len(claves_activas))
            for col, clave in zip(cols, claves_activas):
                ruta, texto = imagenes_sellos[clave]
                with col:
                    img = Image.open(ruta)
                    st.image(img, width=120)

                    with open(ruta, "rb") as f:
                        img_bytes = f.read()

                    st.download_button(
                        label=f"Descargar {texto}.png",
                        data=img_bytes,
                        file_name=f"{texto.replace(' ', '_').lower()}.png",
                        mime="image/png",
                    )

        st.divider()


# Mostrar tabla completa
with st.expander("📊 Ver tabla completa del Excel"):
    st.dataframe(df, use_container_width=True)

# ===================== ALIMENTOS PERSONALIZADOS =====================
st.header("➕ Agregar alimento personalizado")

with st.expander("Agregar un alimento que no está en la tabla"):
    nombre_nuevo = st.text_input("Nombre del alimento nuevo")

    st.markdown("Valores nutricionales por **100 g/ml** (como en la tabla oficial):")
    cant_base = 100.0

    energia_nueva = st.number_input("Energía (kcal)", min_value=0.0, step=0.1)
    prot_nueva   = st.number_input("Proteínas (g)", min_value=0.0, step=0.1)
    grasa_tot_n  = st.number_input("Grasa Total (g)", min_value=0.0, step=0.1)
    grasa_sat_n  = st.number_input("Grasa Saturada (g)", min_value=0.0, step=0.1)
    hdc_nueva    = st.number_input("H. de C. Disp. (g)", min_value=0.0, step=0.1)
    azuc_nueva   = st.number_input("Azúcares Totales (g)", min_value=0.0, step=0.1)
    fibra_nueva  = st.number_input("Fibra Total (g)", min_value=0.0, step=0.1)
    sodio_nuevo  = st.number_input("Sodio (mg)", min_value=0.0, step=1.0)

    st.markdown("Opcional: grasas específicas")
    ag_mono_n = st.number_input("AG Mono (g)", min_value=0.0, step=0.1)
    ag_poli_n = st.number_input("AG Poli (g)", min_value=0.0, step=0.1)
    ag_trans_n = st.number_input("AG Trans (g)", min_value=0.0, step=0.01)

    if st.button("Guardar alimento personalizado"):
        if not nombre_nuevo.strip():
            st.error("Escribe un nombre para el alimento.")
        else:
            nueva_fila = {col: 0 for col in df_base.columns}
            nueva_fila["Alimento"] = nombre_nuevo.strip()
            nueva_fila["Cantidad(g/ml)"] = cant_base
            nueva_fila["Energía(kcal)"] = energia_nueva
            nueva_fila["Proteínas (g)"] = prot_nueva
            nueva_fila["Lípidos totales (g)"] = grasa_tot_n
            nueva_fila["AG Sat (g)"] = grasa_sat_n
            nueva_fila["HdeC disp (g)"] = hdc_nueva
            nueva_fila["Azúcares totales (g)"] = azuc_nueva
            nueva_fila["Fibra Total (g)"] = fibra_nueva
            nueva_fila["Sodio (mg)"] = sodio_nuevo
            nueva_fila["AG Mono (g)"] = ag_mono_n
            nueva_fila["AG Poli (g)"] = ag_poli_n
            nueva_fila["AG Trans (g)"] = ag_trans_n

            try:
                dfp = pd.read_csv("alimentos_personalizados.csv")
            except FileNotFoundError:
                dfp = pd.DataFrame(columns=df_base.columns)

            dfp = pd.concat([dfp, pd.DataFrame([nueva_fila])], ignore_index=True)
            dfp.to_csv("alimentos_personalizados.csv", index=False)

            st.success("👏 Alimento guardado correctamente.")
            st.rerun()


# ===================== ADMINISTRAR PERSONALIZADOS =====================
st.subheader("🛠 Administrar alimentos personalizados")

df_personal = cargar_personalizados()

if df_personal is not None and not df_personal.empty:
    st.markdown("Alimentos personalizados actualmente registrados:")
    st.dataframe(
        df_personal[["Alimento"] + [c for c in df_personal.columns if c != "Alimento"]],
        use_container_width=True
    )

    col_admin1, col_admin2 = st.columns(2)

    # ----------- BORRAR -----------
    with col_admin1:
        st.markdown("### 🗑 Eliminar alimento")

        nombre_borrar = st.selectbox(
            "Selecciona un alimento personalizado para eliminar",
            ["(ninguno)"] + df_personal["Alimento"].astype(str).tolist()
        )

        if nombre_borrar != "(ninguno)":
            if st.button("🗑 Eliminar este alimento"):
                dfp = pd.read_csv("alimentos_personalizados.csv")
                dfp = dfp[dfp["Alimento"] != nombre_borrar]
                dfp.to_csv("alimentos_personalizados.csv", index=False)

                st.success(f"Se eliminó '{nombre_borrar}'.")
                st.rerun()

    # ----------- EDITAR -----------
    with col_admin2:
        st.markdown("### ✏️ Editar alimento")

        nombre_editar = st.selectbox(
            "Selecciona un alimento para editar",
            ["(ninguno)"] + df_personal["Alimento"].astype(str).tolist()
        )

        if nombre_editar != "(ninguno)":
            fila_edit = df_personal[df_personal["Alimento"] == nombre_editar].iloc[0]

            nuevo_nombre = st.text_input(
                "Nuevo nombre",
                value=str(fila_edit["Alimento"])
            )

            energia_edit = st.number_input("Energía (kcal)",
                value=float(fila_edit["Energía(kcal)"]), step=0.1)

            prot_edit = st.number_input("Proteínas (g)",
                value=float(fila_edit["Proteínas (g)"]), step=0.1)

            grasa_tot_edit = st.number_input("Grasa Total (g)",
                value=float(fila_edit["Lípidos totales (g)"]), step=0.1)

            grasa_sat_edit = st.number_input("Grasa Saturada (g)",
                value=float(fila_edit["AG Sat (g)"]), step=0.1)

            hdc_edit = st.number_input("H. de C. Disp. (g)",
                value=float(fila_edit["HdeC disp (g)"]), step=0.1)

            azuc_edit = st.number_input("Azúcares Totales (g)",
                value=float(fila_edit["Azúcares totales (g)"]), step=0.1)

            fibra_edit = st.number_input("Fibra Total (g)",
                value=float(fila_edit["Fibra Total (g)"]), step=0.1)

            sodio_edit = st.number_input("Sodio (mg)",
                value=float(fila_edit["Sodio (mg)"]), step=1.0)

            # grasas detalladas
            mono_edit = st.number_input("AG Mono (g)",
                value=float(fila_edit["AG Mono (g)"]), step=0.1)
            poli_edit = st.number_input("AG Poli (g)",
                value=float(fila_edit["AG Poli (g)"]), step=0.1)
            trans_edit = st.number_input("AG Trans (g)",
                value=float(fila_edit["AG Trans (g)"]), step=0.01)

            if st.button("💾 Guardar cambios"):
                dfp = pd.read_csv("alimentos_personalizados.csv")
                mask = dfp["Alimento"] == nombre_editar

                dfp.loc[mask, "Alimento"] = nuevo_nombre
                dfp.loc[mask, "Energía(kcal)"] = energia_edit
                dfp.loc[mask, "Proteínas (g)"] = prot_edit
                dfp.loc[mask, "Lípidos totales (g)"] = grasa_tot_edit
                dfp.loc[mask, "AG Sat (g)"] = grasa_sat_edit
                dfp.loc[mask, "HdeC disp (g)"] = hdc_edit
                dfp.loc[mask, "Azúcares totales (g)"] = azuc_edit
                dfp.loc[mask, "Fibra Total (g)"] = fibra_edit
                dfp.loc[mask, "Sodio (mg)"] = sodio_edit
                dfp.loc[mask, "AG Mono (g)"] = mono_edit
                dfp.loc[mask, "AG Poli (g)"] = poli_edit
                dfp.loc[mask, "AG Trans (g)"] = trans_edit

                dfp.to_csv("alimentos_personalizados.csv", index=False)

                st.success("Cambios guardados correctamente.")
                st.rerun()

else:
    st.info("No hay alimentos personalizados.")
