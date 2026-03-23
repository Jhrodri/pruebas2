import streamlit as st
import requests
import pandas as pd
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# CATÁLOGO DE ESTACIONES RIA – Red de Información Agroclimática de Andalucía
# Fuente: IFAPA / Junta de Andalucía
# Clave: "cod_provincia" → {"cod_estacion": "nombre"}
# ---------------------------------------------------------------------------
PROVINCIAS = {
    "04": "Almería",
    "11": "Cádiz",
    "14": "Córdoba",
    "18": "Granada",
    "21": "Huelva",
    "23": "Jaén",
    "29": "Málaga",
    "41": "Sevilla",
}

ESTACIONES_POR_PROVINCIA = {
    "04": {  # Almería
        "1":  "La Mojonera",
        "2":  "Almería",
        "4":  "Tabernas",
        "5":  "Fiñana",
        "6":  "Virgen de Fátima-Cuevas de Almanzora",
        "7":  "Huércal-Overa",
        "8":  "Cuevas de Almanzora",
        "10": "Adra",
        "11": "Níjar",
        "12": "Tíjola",
    },
    "11": {  # Cádiz
        "1":  "Basurta-Jerez de la Frontera",
        "2":  "Jerez de la Frontera",
        
        "4":  "Villamartín",
        "5":  "Conil de la Frontera",
        "6":  "Vejer de la Frontera",
        "7":  "Jimea de La Frontera",
        "10":  "Puerto de Santa María",
        "11":  "Sanlúcar de Barrameda",
        "101": "IFAPA Centro de Chipiona",
    },
    "14": {  # Córdoba
        "1":  "Belmez",
        
        "4":  "Hornachuelos",
        "5":  "El Carpio",
        "6":  "Cordoba",
        "7":  "Santaella",
        "8":  "Baena",
        "9":  "Palma del Rio",
        "101": "IFAPA Centro de Cabra",
        "102": "IFAPA Centro de Hinojosa del Duque",
        
    },
    "18": {  # Granada
        "1":  "Baza",
        "2":  "Puebla de Don Fadrique",
        "3":  "Loja",
        
        "5":  "Iznalloz",
        "6":  "Jerez del Marquesado",
        "7":  "Cadiar",
        "8":  "Zafarraya",
        
        "10": "Padul",
        "11": "Almuñecar",
        "12": "Pinos Puente Casanueva",
        "101": "IFAPA Centro Camino del Purchil",
        "102": "Huéneja",
    },
    "21": {  # Huelva
        
        "2":  "Lepe",
        "3":  "Gibraleon",
        
        "5":  "Niebla",
        "6":  "Aroche",
        "7":  "La Puebla de Guzmán",
        "8":  "El Campillo",
        "9":  "La Palma del Condado",
        "10": "Almonte",
        "11": "Gibraleón-Manzorrales",
        "12": "Moguer El Fresno",
        "101": "IFAPA Centro Huelva. Finca EL Cebollar",
        
    },
    "23": {  # Jaén
        "1":  "Huesa",
        "2":  "Pozo Alcón",
        "3":  "San José de los Propios",
        "4":  "Sabiote",
        "5":  "Torreblascopedro",
        "6":  "Alcaudete",
        "7":  "Mancha Real",
        "8":  "Ubeda",
        "9":  "La Carolina",
        "10": "Villacarrillo",
        "11": "Chiclana de Segura",
        "12": "La Higuera de Arjona",
        "14": "Santo Tomé",
        "15": "Jaén",
        "16": "Marmolejo",
        "101": "Torreperogil",
        "102": "Villacarrillo",
        "103": "Jodar",
        "104": "IFAPA Centro Menjibar",
    },
    "29": {  # Málaga
        "1":  "Málaga",
        "2":  "Velez-Málaga",
        
        "4":  "Estepona",
        
        "6":  "Sierra Yeguas",
        "7":  "IFAPA Churriana",
        "8":  "Pizarra",
        "9":  "Cártama",
        "10": "Antequera",
        "11": "Archidona",
        "101": "IFAPA Centro de Campanillas",
    },
    "41": {  # Sevilla
        
        "2":  "Las Cabezas de San Juan",
        "3":  "Lebrija",
        
        "5":  "Aznalcázar",
        
        "7":  "La Puebla del Río I",
        "8":  "La Puebla del Río II",
        "9":  "Ecija",
        "10": "La Luisiana",
        "11": "Sevilla",
        "12": "La Rinconada",
        "13": "Sanlúcar La Mayor",
        "15": "Lora del Río",
        "16": "Los Molares",
        "17": "Guillena",
        "18": "Puebla Cazalla",
        "19": "IFAPA Centro Las Torres-Tomejil",
        "20": "Isla Mayor",
        "21": "IFAPA Centro de Los Palacios",
        "22": "Villanueva del Río y Minas",
        "101": "IFAPA Centro Las Torres-Tomejil. Finca Tomejil",
    },
}

BASE_URL    = "https://www.juntadeandalucia.es/agriculturaypesca/ifapa/riaws/datosdiarios"
TARGET_DAYS = 5   # días con datos que se quieren obtener
MAX_LOOKBACK = 15  # máximo de días hacia atrás en los que buscar

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.juntadeandalucia.es/",
}

# ---------------------------------------------------------------------------
# FUNCIONES DE CONSULTA
# ---------------------------------------------------------------------------

def obtener_dato_diario(cod_provincia, cod_estacion, fecha):
    """Consulta datos diarios de una estación. Devuelve (DataFrame|None, error|None)."""
    fecha_str = fecha.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{cod_provincia}/{cod_estacion}/{fecha_str}/true"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None, "Sin datos"
        if isinstance(data, dict):
            data = [data]
        return pd.DataFrame(data), None
    except requests.exceptions.HTTPError as e:
        return None, f"HTTP {r.status_code}"
    except Exception as e:
        return None, str(e)



# ---------------------------------------------------------------------------
# HELPERS UI
# ---------------------------------------------------------------------------

def mostrar_metricas(row):
    c1, c2, c3, c4, c5 = st.columns(5)
    temp_med = row.get("tempMedia", "N/A")
    temp_max = row.get("tempMax",   "N/A")
    precip   = row.get("precipitacion", "N/A")
    eto      = row.get("et0",       "N/A")
    Rad_med=row.get("radiacion",       "N/A")
    c1.metric("🌡️ Temp. Media",  f"{temp_med} ºC" if temp_med != "N/A" else "N/A")
    c2.metric("🔺 Temp. Máxima", f"{temp_max} ºC" if temp_max != "N/A" else "N/A")
    c3.metric("💧 Precipitación", f"{precip} mm"  if precip   != "N/A" else "N/A")
    c4.metric("🌾 ETo (FAO56)",   f"{eto:.2f} mm"     if eto      != "N/A" else "N/A")
    c5.metric("🌤️ Rad. diaria",   f"{Rad_med:.2f} MJ/m²"     if Rad_med      != "N/A" else "N/A")

def csv_para_excel(df):
    return df.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Datos RIA Andalucía",
    page_icon="🌤️",
    layout="wide",
)
st.image("https://github.com/Jhrodri/open/blob/main/logo.png?raw=true", width=260)
st.caption("© jhrodri")
st.title("🌤️ Consulta de Datos Meteorológicos – RIA Andalucía")
st.caption("Red de Información Agroclimática de Andalucía · IFAPA / Junta de Andalucía")
st.markdown("---")

# ── Controles ───────────────────────────────────────────────────────────────
col_prov, col_est, col_btn = st.columns([2, 2, 1])

with col_prov:
    provincia_sel = st.selectbox(
        "🗺️ Provincia:",
        options=list(PROVINCIAS.keys()),
        format_func=lambda x: PROVINCIAS[x],
    )

estaciones_prov = ESTACIONES_POR_PROVINCIA[provincia_sel]

with col_est:
    estacion_sel = st.selectbox(
        "🏠 Estación:",
        options=list(estaciones_prov.keys()),
        format_func=lambda x: estaciones_prov[x],
    )

with col_btn:
    st.write("")
    st.write("")
    boton = st.button("🔍 Consultar", type="primary", use_container_width=True)

st.markdown("---")

# ── Lógica principal ────────────────────────────────────────────────────────
if boton:
    nombre_prov = PROVINCIAS[provincia_sel]
    nombre_est = estaciones_prov[estacion_sel]
    dias_encontrados = []

    with st.spinner(f"⏳ Buscando los últimos {TARGET_DAYS} días con datos para {nombre_est}…"):
        for i in range(MAX_LOOKBACK):
            fecha = date.today() - timedelta(days=i + 1)
            df, error = obtener_dato_diario(provincia_sel, estacion_sel, fecha)
            if df is not None and not df.empty:
                df.insert(0, "Fecha", fecha.strftime("%d/%m/%Y"))
                dias_encontrados.append(df)
            if len(dias_encontrados) == TARGET_DAYS:
                break

    if dias_encontrados:
        df_total = pd.concat(dias_encontrados, ignore_index=True)
        n_dias = len(dias_encontrados)
        st.success(f"✅ **{nombre_est}** · {nombre_prov} · Últimos {n_dias} días con datos")

        st.markdown("#### 📊 Datos más recientes")
        mostrar_metricas(dias_encontrados[0].iloc[0])

        st.markdown("#### 📋 Últimos días")
        st.dataframe(df_total, use_container_width=True)

        nombre_archivo = (
            f"ria_{nombre_prov.lower()}_est{estacion_sel}"
            f"_{date.today().strftime('%Y%m%d')}_{n_dias}dias.csv"
        )
        st.download_button(
            label="📥 Descargar CSV (formato Excel)",
            data=csv_para_excel(df_total),
            file_name=nombre_archivo,
            mime="text/csv",
            help="Separador ';' y decimal ',' listo para Excel en español",
        )
    else:
        st.error(f"❌ No se encontraron datos para **{nombre_est}** en los últimos {MAX_LOOKBACK} días.")
        st.info("ℹ️ **HTTP 404** indica que la RIA no tiene datos disponibles para esa estación en ese período.")

else:
    st.info(
        "👆 Selecciona **provincia** y **estación**, "
        "luego pulsa **Consultar**."
    )
