import streamlit as st
import pandas as pd
import numpy as np
import pvlib
import requests
from datetime import datetime, date, timedelta

st.set_page_config(page_title="Transmisividad Solar - Invernaderos", layout="wide")

# ── CATÁLOGO RIA ──────────────────────────────────────────────────────────────
PROVINCIAS = {
    "04": "Almería", "11": "Cádiz",  "14": "Córdoba", "18": "Granada",
    "21": "Huelva",  "23": "Jaén",   "29": "Málaga",  "41": "Sevilla",
}

ESTACIONES_POR_PROVINCIA = {
    "04": {
        "1": "La Mojonera", "2": "Almería", "4": "Tabernas", "5": "Fiñana",
        "6": "Virgen de Fátima-Cuevas de Almanzora", "7": "Huércal-Overa",
        "8": "Cuevas de Almanzora", "10": "Adra", "11": "Níjar", "12": "Tíjola",
    },
    "11": {
        "1": "Basurta-Jerez de la Frontera", "2": "Jerez de la Frontera",
        "4": "Villamartín", "5": "Conil de la Frontera", "6": "Vejer de la Frontera",
        "7": "Jimea de La Frontera", "10": "Puerto de Santa María",
        "11": "Sanlúcar de Barrameda", "101": "IFAPA Centro de Chipiona",
    },
    "14": {
        "1": "Belmez", "4": "Hornachuelos", "5": "El Carpio", "6": "Cordoba",
        "7": "Santaella", "8": "Baena", "9": "Palma del Rio",
        "101": "IFAPA Centro de Cabra", "102": "IFAPA Centro de Hinojosa del Duque",
    },
    "18": {
        "1": "Baza", "2": "Puebla de Don Fadrique", "3": "Loja", "5": "Iznalloz",
        "6": "Jerez del Marquesado", "7": "Cadiar", "8": "Zafarraya",
        "10": "Padul", "11": "Almuñecar", "12": "Pinos Puente Casanueva",
        "101": "IFAPA Centro Camino del Purchil", "102": "Huéneja",
    },
    "21": {
        "2": "Lepe", "3": "Gibraleon", "5": "Niebla", "6": "Aroche",
        "7": "La Puebla de Guzmán", "8": "El Campillo", "9": "La Palma del Condado",
        "10": "Almonte", "11": "Gibraleón-Manzorrales", "12": "Moguer El Fresno",
        "101": "IFAPA Centro Huelva. Finca EL Cebollar",
    },
    "23": {
        "1": "Huesa", "2": "Pozo Alcón", "3": "San José de los Propios",
        "4": "Sabiote", "5": "Torreblascopedro", "6": "Alcaudete",
        "7": "Mancha Real", "8": "Ubeda", "9": "La Carolina",
        "10": "Villacarrillo", "11": "Chiclana de Segura", "12": "La Higuera de Arjona",
        "14": "Santo Tomé", "15": "Jaén", "16": "Marmolejo",
        "101": "Torreperogil", "102": "Villacarrillo", "103": "Jodar",
        "104": "IFAPA Centro Menjibar",
    },
    "29": {
        "1": "Málaga", "2": "Velez-Málaga", "4": "Estepona",
        "6": "Sierra Yeguas", "7": "IFAPA Churriana", "8": "Pizarra",
        "9": "Cártama", "10": "Antequera", "11": "Archidona",
        "101": "IFAPA Centro de Campanillas",
    },
    "41": {
        "2": "Las Cabezas de San Juan", "3": "Lebrija", "5": "Aznalcázar",
        "7": "La Puebla del Río I", "8": "La Puebla del Río II", "9": "Ecija",
        "10": "La Luisiana", "11": "Sevilla", "12": "La Rinconada",
        "13": "Sanlúcar La Mayor", "15": "Lora del Río", "16": "Los Molares",
        "17": "Guillena", "18": "Puebla Cazalla",
        "19": "IFAPA Centro Las Torres-Tomejil", "20": "Isla Mayor",
        "21": "IFAPA Centro de Los Palacios", "22": "Villanueva del Río y Minas",
        "101": "IFAPA Centro Las Torres-Tomejil. Finca Tomejil",
    },
}

BASE_URL     = "https://www.juntadeandalucia.es/agriculturaypesca/ifapa/riaws/datosdiarios"
TARGET_DAYS  = 5
MAX_LOOKBACK = 15
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.juntadeandalucia.es/",
}

# ── FUNCIÓN RIA ───────────────────────────────────────────────────────────────
def obtener_dato_diario(cod_provincia, cod_estacion, fecha):
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
    except requests.exceptions.HTTPError:
        return None, f"HTTP {r.status_code}"
    except Exception as e:
        return None, str(e)

# ── FUNCIONES TRANS_MED ──────────────────────────────────────────────────────
def setup_solar_model(lat, lon, date_obj):
    tz = f'Etc/GMT{int(-lon/15)}'
    location = pvlib.location.Location(latitude=lat, longitude=lon, tz=tz, altitude=200)
    start_date = pd.Timestamp(date_obj, tz=tz)
    end_date = start_date + pd.Timedelta(days=1)
    times = pd.date_range(start=start_date, end=end_date, freq='10min', inclusive='left')
    solar_position = location.get_solarposition(times)
    clearsky = location.get_clearsky(solar_position.index, model='ineichen')
    dni_ideal, dhi_ideal, ghi_ideal = clearsky['dni'], clearsky['dhi'], clearsky['ghi']
    dni_extra = pvlib.irradiance.get_extra_radiation(times)
    return tz, location, times, solar_position, dni_ideal, dhi_ideal, ghi_ideal, dni_extra

def scale_solar_model(ghi_ideal, dni_ideal, dhi_ideal, times, measured_MJ):
    intervalo_horas = (times[1] - times[0]).total_seconds() / 3600
    energia_ideal_MJ = (ghi_ideal.sum() * intervalo_horas / 1000) * 3.6
    if measured_MJ and measured_MJ > 0 and energia_ideal_MJ > 0:
        f = measured_MJ / energia_ideal_MJ
        return dni_ideal * f, dhi_ideal * f, ghi_ideal * f, "real"
    return dni_ideal, dhi_ideal, ghi_ideal, "ideal"

def calculate_transmitted_irradiance(poa, tilt, azimuth, solar_position):
    aoi = pvlib.irradiance.aoi(tilt, azimuth, solar_position['apparent_zenith'], solar_position['azimuth'])
    aoi[aoi > 90] = 90
    trans = np.clip(0.90647838 + (-0.00277529 * aoi) + (0.00014437 * aoi**2) + (-0.00000260 * aoi**3), 0, 1)
    return poa['poa_direct'] * trans

def finalize_results(irradiancia_suelo, ghi_real, times, aportes=None):
    intervalo_horas = (times[1] - times[0]).total_seconds() / 3600
    energia_interior = irradiancia_suelo.sum() * intervalo_horas / 1000
    energia_exterior = ghi_real.sum() * intervalo_horas / 1000
    transmisividad = (energia_interior / energia_exterior * 100) if energia_exterior > 0 else 0
    df_data = {
        'Hora': irradiancia_suelo.index,
        'Radiación Exterior (W/m²)': ghi_real.values,
        'Radiación en Invernadero (W/m²)': irradiancia_suelo.values,
    }
    if aportes:
        df_data[aportes["label_1"]] = aportes["aporte_1"].values
        df_data[aportes["label_2"]] = aportes["aporte_2"].values
    df_results = pd.DataFrame(df_data)
    df_results['Hora'] = df_results['Hora'].dt.strftime('%H:%M')
    return energia_interior, transmisividad, df_results

def calculate_radiation_gable(lat, lon, date_obj, greenhouse_azimuth, module_width, ridge_height, measured_MJ):
    roof_tilt = np.degrees(np.arctan(ridge_height / (module_width / 2))) if module_width > 0 and ridge_height >= 0 else 0
    tz, location, times, solar_position, dni_ideal, dhi_ideal, ghi_ideal, dni_extra = setup_solar_model(lat, lon, date_obj)
    dni_real, dhi_real, ghi_real, model_type = scale_solar_model(ghi_ideal, dni_ideal, dhi_ideal, times, measured_MJ)
    az1, az2 = (greenhouse_azimuth + 90) % 360, (greenhouse_azimuth - 90 + 360) % 360
    poa_1 = pvlib.irradiance.get_total_irradiance(roof_tilt, az1, solar_position['apparent_zenith'], solar_position['azimuth'], dni_real, ghi_real, dhi_real, dni_extra=dni_extra, model='haydavies')
    poa_2 = pvlib.irradiance.get_total_irradiance(roof_tilt, az2, solar_position['apparent_zenith'], solar_position['azimuth'], dni_real, ghi_real, dhi_real, dni_extra=dni_extra, model='haydavies')
    irrad_1 = calculate_transmitted_irradiance(poa_1, roof_tilt, az1, solar_position)
    irrad_2 = calculate_transmitted_irradiance(poa_2, roof_tilt, az2, solar_position)
    cos_tilt = np.cos(np.radians(roof_tilt))
    if cos_tilt > 0.001:
        aporte_1, aporte_2 = irrad_1 / (2 * cos_tilt), irrad_2 / (2 * cos_tilt)
    else:
        aporte_1, aporte_2 = pd.Series(0, index=times), pd.Series(0, index=times)
    irradiancia_suelo = aporte_1 + aporte_2
    aportes = {"label_1": f"Cara a {az1}°", "aporte_1": aporte_1, "label_2": f"Cara a {az2}°", "aporte_2": aporte_2}
    energia, trans, df_results = finalize_results(irradiancia_suelo, ghi_real, times, aportes)
    return energia, trans, roof_tilt, df_results, model_type

def calculate_radiation_curved(lat, lon, date_obj, greenhouse_azimuth, module_width, ridge_height, measured_MJ):
    N_SEGMENTS = 50
    if ridge_height < 0.01:
        return calculate_radiation_gable(lat, lon, date_obj, greenhouse_azimuth, module_width, 0, measured_MJ)
    W, H = module_width, ridge_height
    radius = (H**2 + (W/2)**2) / (2*H)
    theta_max = np.arcsin((W/2) / radius)
    tz, location, times, solar_position, dni_ideal, dhi_ideal, ghi_ideal, dni_extra = setup_solar_model(lat, lon, date_obj)
    dni_real, dhi_real, ghi_real, model_type = scale_solar_model(ghi_ideal, dni_ideal, dhi_ideal, times, measured_MJ)
    total_power = pd.Series(0.0, index=times)
    angles = np.linspace(-theta_max, theta_max, N_SEGMENTS)
    d_theta = angles[1] - angles[0]
    for i in range(N_SEGMENTS - 1):
        angle_mid = (angles[i] + angles[i+1]) / 2
        seg_tilt = np.degrees(abs(angle_mid))
        seg_az = (greenhouse_azimuth - 90 + 360) % 360 if angle_mid < 0 else (greenhouse_azimuth + 90) % 360
        poa = pvlib.irradiance.get_total_irradiance(seg_tilt, seg_az, solar_position['apparent_zenith'], solar_position['azimuth'], dni_real, ghi_real, dhi_real, dni_extra=dni_extra, model='haydavies')
        irrad = calculate_transmitted_irradiance(poa, seg_tilt, seg_az, solar_position)
        total_power += irrad * radius * d_theta
    irradiancia_suelo = total_power / W
    energia, trans, df_results = finalize_results(irradiancia_suelo, ghi_real, times)
    return energia, trans, 0, df_results, model_type

def extract_noon_trans(df):
    row = df[df['Hora'] == '12:00']
    if not row.empty:
        I_ext = row['Radiación Exterior (W/m²)'].values[0]
        I_inv = row['Radiación en Invernadero (W/m²)'].values[0]
        return round((I_inv / I_ext) * 100, 2) if I_ext > 0 else None
    return None

def run_calc(lat, lon, fecha, roof_type, greenhouse_azimuth, module_width, ridge_height):
    if roof_type == "A dos aguas":
        return calculate_radiation_gable(lat, lon, fecha, greenhouse_azimuth, module_width, ridge_height, 0)
    return calculate_radiation_curved(lat, lon, fecha, greenhouse_azimuth, module_width, ridge_height, 0)

def csv_para_excel(df):
    return df.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig")

# ── INTERFAZ ──────────────────────────────────────────────────────────────────
st.title("☀️ SOLO PARA PRUEBAS Transmisividad Solar en Invernaderos Mediterráneos")

st.sidebar.image("https://github.com/Jhrodri/open/blob/main/logo.png?raw=true", width=300)

st.sidebar.header("🔧 Parámetros del invernadero")
roof_type = st.sidebar.radio("Tipo de cubierta", ["A dos aguas", "Curva"])
greenhouse_azimuth = st.sidebar.slider("Orientación (°)", 0, 359, 90, 1, help="0°=N, 90°=E, 180°=S, 270°=O")
module_width  = st.sidebar.number_input("Ancho del módulo (m)", 1.0, 50.0, 8.0, 0.5)
ridge_height  = st.sidebar.number_input("Altura máxima (m)", 0.0, 20.0, 1.5, 0.1)

st.sidebar.divider()
st.sidebar.subheader("📍 Ubicación")
lat = st.sidebar.number_input("Latitud (°)",  -90.0,  90.0, 36.8, 0.5)
lon = st.sidebar.number_input("Longitud (°)", -180.0, 180.0, -2.4, 0.5)

st.sidebar.divider()
st.sidebar.subheader("🌐 Estación RIA")
provincia_sel = st.sidebar.selectbox(
    "Provincia",
    options=list(PROVINCIAS.keys()),
    format_func=lambda x: PROVINCIAS[x],
)
estaciones_prov = ESTACIONES_POR_PROVINCIA[provincia_sel]
estacion_sel = st.sidebar.selectbox(
    "Estación",
    options=list(estaciones_prov.keys()),
    format_func=lambda x: estaciones_prov[x],
)

st.sidebar.divider()
st.sidebar.subheader("📏 Medición real (opcional)")
st.sidebar.caption("Medición en día de cielo despejado para corregir los valores teóricos.")
measurement_date = st.sidebar.date_input("Fecha de la medición", date.today() - timedelta(days=1))
t_noon_real = st.sidebar.number_input("T medida al mediodía (%)", 0.0, 100.0, 0.0, 0.1)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if 'results' not in st.session_state:
    st.session_state.results = None

# ── BOTÓN ─────────────────────────────────────────────────────────────────────
if st.sidebar.button("Consultar y Calcular", type="primary"):
    nombre_est  = estaciones_prov[estacion_sel]
    nombre_prov = PROVINCIAS[provincia_sel]

    # 1. Obtener últimos 5 días con datos de la RIA
    dias_ria = []
    with st.spinner(f"⏳ Buscando datos en {nombre_est}…"):
        for i in range(MAX_LOOKBACK):
            fecha = date.today() - timedelta(days=i + 1)
            df_ria, _ = obtener_dato_diario(provincia_sel, estacion_sel, fecha)
            if df_ria is not None and not df_ria.empty:
                dias_ria.append({
                    'fecha': fecha,
                    'radiacion': df_ria.iloc[0].get('radiacion', None),
                })
            if len(dias_ria) == TARGET_DAYS:
                break

    if not dias_ria:
        st.error(f"❌ No se encontraron datos para **{nombre_est}** en los últimos {MAX_LOOKBACK} días.")
    else:
        # 2. Calcular transmisividad para cada fecha
        resultados = []
        with st.spinner("⏳ Calculando transmisividad…"):
            for dia in dias_ria:
                _, t_media, _, df_day, _ = run_calc(lat, lon, dia['fecha'], roof_type, greenhouse_azimuth, module_width, ridge_height)
                t_noon = extract_noon_trans(df_day)
                resultados.append({
                    'Fecha':              dia['fecha'].strftime('%d/%m/%Y'),
                    'Rad. RIA (MJ/m²)':   dia['radiacion'],
                    'T 12:00 (%)':        t_noon,
                    'T media diaria (%)': round(t_media, 2),
                })

        df_res    = pd.DataFrame(resultados)
        corrected = False

        # 3. Corrección opcional
        if t_noon_real > 0:
            _, _, _, df_med, _ = run_calc(lat, lon, measurement_date, roof_type, greenhouse_azimuth, module_width, ridge_height)
            t_noon_teo_med = extract_noon_trans(df_med)
            if t_noon_teo_med and t_noon_teo_med > 0:
                factor = t_noon_real / t_noon_teo_med
                df_res['T 12:00 (%)']        = df_res['T 12:00 (%)'].apply(lambda x: round(x * factor, 2) if x is not None else None)
                df_res['T media diaria (%)'] = (df_res['T media diaria (%)'] * factor).round(2)
                corrected = True

        st.session_state.results = {
            'df':               df_res,
            'station':          nombre_est,
            'province':         nombre_prov,
            'corrected':        corrected,
            'measurement_date': measurement_date if corrected else None,
        }

# ── RESULTADOS ────────────────────────────────────────────────────────────────
if st.session_state.results is not None:
    r = st.session_state.results
    st.subheader(f"📊 {r['station']} · {r['province']}")

    if r['corrected']:
        st.info(f"Valores corregidos con la medición del {r['measurement_date'].strftime('%d/%m/%Y')}.")

    st.dataframe(r['df'], use_container_width=True, hide_index=True)

    st.download_button(
        label="📥 Descargar CSV",
        data=csv_para_excel(r['df']),
        file_name=f"transmisividad_{r['station'].lower().replace(' ', '_')}_{date.today().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        help="Separador ';' y decimal ',' listo para Excel en español",
    )
else:
    st.info("Configura los parámetros en el panel lateral y pulsa 'Consultar y Calcular'.")

# ── PIE ───────────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="text-align: center;">
    <p>© jhrodri</p>
    <p>Licencia <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">Creative Commons Attribution 4.0</a></p>
</div>
""", unsafe_allow_html=True)

