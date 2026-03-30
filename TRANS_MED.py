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
        "7": "Mancha Real", "8": "Ubeda", "11": "Chiclana de Segura", "12": "La Higuera de Arjona",
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

COORDENADAS_ESTACIONES = {
    "04": {
        "1": (36.787222, -2.704167), "2": (36.835278, -2.402222),
        "4": (37.091111, -2.302222), "5": (37.156667, -2.838611),
        "6": (37.388889, -1.770278), "7": (37.412222, -1.884167),
        "8": (37.256667, -1.800278), "10": (36.746667, -2.992222),
        "11": (36.950556, -2.158056), "12": (37.378333, -2.459444),
    },
    "11": {
        "1": (36.756944, -6.017222), "2": (36.6425, -6.013333),
        "4": (36.843056, -5.623611), "5": (36.332778, -6.1325),
        "6": (36.285, -5.84),        "7": (36.413611, -5.383611),
        "10": (36.604427, -6.171478), "11": (36.718889, -6.33),
        "101": (36.750833, -6.399722),
    },
    "14": {
        "1": (38.254167, -5.209444), "4": (37.719722, -5.16),
        "5": (37.913889, -4.503889), "6": (37.856944, -4.802778),
        "7": (37.522222, -4.885278), "8": (37.691389, -4.305833),
        "9": (37.725556, -5.226944), "101": (37.498056, -4.430833),
        "102": (38.496111, -5.115278),
    },
    "18": {
        "1": (37.564444, -2.7675),   "2": (37.875833, -2.381667),
        "3": (37.169167, -4.138056), "5": (37.416389, -3.551389),
        "6": (37.190278, -3.149722), "7": (36.923056, -3.183889),
        "8": (36.990278, -4.153611), "10": (37.018611, -3.600278),
        "11": (36.751667, -3.678889), "12": (37.241867, -3.785572),
        "101": (37.171944, -3.638333), "102": (37.215025, -2.963481),
    },
    "21": {
        "2": (37.3025, -7.243056),   "3": (37.412222, -7.059722),
        "5": (37.346944, -6.735278), "6": (37.958056, -6.945),
        "7": (37.551944, -7.248333), "8": (37.660833, -6.599167),
        "9": (37.366944, -6.541389), "10": (37.148056, -6.476389),
        "11": (37.308862, -7.015414), "12": (37.191556, -6.838311),
        "101": (37.240278, -6.802222),
    },
    "23": {
        "1": (37.747222, -3.061667), "2": (37.671667, -2.93),
        "3": (37.857778, -3.230278), "4": (38.079444, -3.235278),
        "5": (37.988611, -3.689167), "6": (37.577222, -4.078333),
        "7": (37.916389, -3.596389), "8": (37.942778, -3.300278),
        "11": (38.302778, -2.996389), "12": (37.948611, -4.0075),
        "14": (38.029167, -3.082778), "15": (37.890556, -3.771111),
        "16": (38.048889, -4.1825),  "101": (37.974167, -3.243889),
        "102": (38.063333, -3.200278), "103": (37.878333, -3.334167),
        "104": (37.940833, -3.7875),
    },
    "29": {
        "1": (36.756389, -4.5375),   "2": (36.795833, -4.131389),
        "4": (36.444444, -5.209722), "6": (37.138333, -4.835833),
        "7": (36.673611, -4.503056), "8": (36.766667, -4.715),
        "9": (36.727778, -4.678056), "10": (37.034167, -4.5625),
        "11": (37.103847, -4.418275), "101": (36.728889, -4.560556),
    },
    "41": {
        "2": (37.015556, -5.884444), "3": (36.976389, -6.126111),
        "5": (37.151667, -6.273333), "7": (37.225833, -6.133611),
        "8": (37.08, -6.046389),     "9": (37.592778, -5.076944),
        "10": (37.525, -5.228056),   "11": (37.255, -5.134722),
        "12": (37.456667, -5.924722), "13": (37.421667, -6.255),
        "15": (37.660833, -5.540556), "16": (37.176111, -5.672778),
        "17": (37.514444, -6.064167), "18": (37.218056, -5.350833),
        "19": (37.5125, -5.963889),  "20": (37.113611, -6.121111),
        "21": (37.186111, -5.945833), "22": (37.5925, -5.688611),
        "101": (37.400833, -5.5875),
    },
}

BLANQUEO = {
    "Sin blanqueo": {"dosis": None,  "factor": 1.0},
    "Ligero":       {"dosis": 17.5,  "factor": 0.9},
    "Medio":        {"dosis": 25.0,  "factor": 0.7},
    "Fuerte":       {"dosis": 40.0,  "factor": 0.4},
    "Muy fuerte":   {"dosis": 100.0, "factor": 0.1},
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

TRANS_DIFUSA = 0.75  # Transmisividad hemisférica fija para la componente difusa (PE tricapa)

def calculate_transmitted_irradiance(poa, tilt, azimuth, solar_position):
    aoi = pvlib.irradiance.aoi(tilt, azimuth, solar_position['apparent_zenith'], solar_position['azimuth'])
    aoi[aoi > 90] = 90
    trans = np.clip(0.90647838 + (-0.00277529 * aoi) + (0.00014437 * aoi**2) + (-0.00000260 * aoi**3), 0, 1)
    return poa['poa_direct'] * trans + poa['poa_diffuse'] * TRANS_DIFUSA

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

ESTRUCTURA_SOMBRA = {
    "Invernadero Parral":                        0.90,
    "Invernadero Industrial con cubierta curva": 0.85,
}

def run_calc(lat, lon, fecha, roof_type, greenhouse_azimuth, module_width, ridge_height):
    if roof_type == "Invernadero Parral":
        return calculate_radiation_gable(lat, lon, fecha, greenhouse_azimuth, module_width, ridge_height, 0)
    return calculate_radiation_curved(lat, lon, fecha, greenhouse_azimuth, module_width, ridge_height, 0)

def csv_para_excel(df):
    return df.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig")

def add_derived_columns(df):
    """Calcula y añade todas las columnas derivadas sobre el dataframe (in-place)."""
    df['RADint (MJ/m²)'] = (df['Rad. RIA (MJ/m²)'] * df['T media diaria (%)'] / 100).round(2)

    def _t_inv(row):
        t = row['T media (°C)']
        return round(t + 1.87, 2) if row['T máxima (°C)'] >= 25 else round(-0.02*t**2 + 1.494*t - 1.096, 2)

    def _t_inv_pasivos(row):
        t = row['T media (°C)']
        return round(t + 1.87, 2) if row['T máxima (°C)'] >= 25 else round(-0.0012*t**2 + 0.849*t + 5.674, 2)

    df['Tªinv (°C)']         = df.apply(_t_inv, axis=1)
    df['Tªinv_pasivos (°C)'] = df.apply(_t_inv_pasivos, axis=1)

    df['PVs_ext (kPa)']     = (0.6108 * np.exp(17.27 * df['T media (°C)']   / (df['T media (°C)']   + 237.3))).round(4)
    df['PVa_ext (kPa)']     = (df['HR media (%)'] * df['PVs_ext (kPa)'] / 100).round(4)
    df['PVS_ext_Tmin (kPa)'] = (0.6108 * np.exp(17.27 * df['T mínima (°C)'] / (df['T mínima (°C)'] + 237.3))).round(4)

    df['PV_trasplante (kPa)'] = df[['PVa_ext (kPa)', 'PVS_ext_Tmin (kPa)']].min(axis=1).round(4)

    def _pv_inv(row):
        pvs = row['PVS_ext_Tmin (kPa)']
        f   = 1.03 * row['PVa_ext (kPa)'] + 0.7
        fn  = min if row['T media (°C)'] >= 25 else max
        return round(fn(pvs, f), 4)

    df['PV_inv (kPa)'] = df.apply(_pv_inv, axis=1)

    df['PVs_inv (kPa)']         = (0.6108 * np.exp(17.27 * df['Tªinv (°C)']         / (df['Tªinv (°C)']         + 237.3))).round(4)
    df['PVs_inv_pasivos (kPa)'] = (0.6108 * np.exp(17.27 * df['Tªinv_pasivos (°C)'] / (df['Tªinv_pasivos (°C)'] + 237.3))).round(4)

    df['HR_inv_trasplante (%)']         = (100 * df['PV_trasplante (kPa)'] / df['PVs_inv (kPa)']        ).clip(upper=100).round(2)
    df['HR_inv_trasplante_pasivos (%)'] = (100 * df['PV_trasplante (kPa)'] / df['PVs_inv_pasivos (kPa)']).clip(upper=100).round(2)
    df['HR_inv (%)']         = (100 * df['PV_inv (kPa)'] / df['PVs_inv (kPa)']        ).clip(upper=100).round(2)
    df['HR_inv_pasivos (%)'] = (100 * df['PV_inv (kPa)'] / df['PVs_inv_pasivos (kPa)']).clip(upper=100).round(2)

    return df

# ── INTERFAZ ──────────────────────────────────────────────────────────────────
st.title("☀️ Transmisividad Solar en Invernaderos Mediterráneos")

st.sidebar.image("https://github.com/Jhrodri/open/blob/main/logo.png?raw=true", width=300)

st.sidebar.header("🔧 Parámetros del invernadero")
roof_type = st.sidebar.radio("Tipo de cubierta", list(ESTRUCTURA_SOMBRA.keys()))
greenhouse_azimuth = st.sidebar.slider("Orientación (°)", 0, 359, 90, 1, help="0°=N, 90°=E, 180°=S, 270°=O")
module_width  = st.sidebar.number_input("Ancho del módulo (m)", 1.0, 50.0, 8.0, 0.5)
ridge_height  = st.sidebar.number_input("Altura máxima (m)", 0.0, 20.0, 1.5, 0.1)

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
lat, lon = COORDENADAS_ESTACIONES[provincia_sel][estacion_sel]

st.sidebar.divider()
st.sidebar.subheader("🪣 Blanqueo")
blanqueo_sel = st.sidebar.selectbox(
    "Tipo de blanqueo",
    options=list(BLANQUEO.keys()),
)
if blanqueo_sel != "Sin blanqueo":
    dosis = BLANQUEO[blanqueo_sel]["dosis"]
    st.sidebar.caption(f"Dosis orientativa: **{dosis} kg de cal por cada 100 L de agua**")

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
                row = df_ria.iloc[0]
                dias_ria.append({
                    'fecha':         fecha,
                    'radiacion':     row.get('radiacion',    None),
                    'tempMedia':     row.get('tempMedia',    None),
                    'tempMax':       row.get('tempMax',      None),
                    'tempMin':       row.get('tempMin',      None),
                    'humedadMedia':  row.get('humedadMedia', None),
                    'et0':           row.get('et0',          None),
                })
            if len(dias_ria) == TARGET_DAYS:
                break

    if not dias_ria:
        st.error(f"❌ No se encontraron datos para **{nombre_est}** en los últimos {MAX_LOOKBACK} días.")
    else:
        # 2. Calcular transmisividad para cada fecha
        factor_est = ESTRUCTURA_SOMBRA[roof_type]
        resultados = []
        with st.spinner("⏳ Calculando transmisividad…"):
            for dia in dias_ria:
                _, t_media, _, df_day, _ = run_calc(lat, lon, dia['fecha'], roof_type, greenhouse_azimuth, module_width, ridge_height)
                t_noon = extract_noon_trans(df_day)
                resultados.append({
                    'Fecha':              dia['fecha'].strftime('%d/%m/%Y'),
                    'Rad. RIA (MJ/m²)':  dia['radiacion'],
                    'T media (°C)':      dia['tempMedia'],
                    'T máxima (°C)':     dia['tempMax'],
                    'T mínima (°C)':     dia['tempMin'],
                    'HR media (%)':      dia['humedadMedia'],
                    'ETo ext. (mm)':     dia['et0'],
                    'T 12:00 (%)':       round(t_noon * factor_est, 2) if t_noon is not None else None,
                    'T media diaria (%)': round(t_media * factor_est, 2),
                })

        df_res    = pd.DataFrame(resultados)
        corrected         = False
        correction_factor = 1.0

        # 3. Corrección opcional (el teórico de referencia también lleva factor_est)
        if t_noon_real > 0:
            _, _, _, df_med, _ = run_calc(lat, lon, measurement_date, roof_type, greenhouse_azimuth, module_width, ridge_height)
            t_noon_teo_med = extract_noon_trans(df_med)
            if t_noon_teo_med and t_noon_teo_med > 0:
                correction_factor = t_noon_real / (t_noon_teo_med * factor_est)
                df_res['T 12:00 (%)']        = df_res['T 12:00 (%)'].apply(lambda x: round(x * correction_factor, 2) if x is not None else None)
                df_res['T media diaria (%)'] = (df_res['T media diaria (%)'] * correction_factor).round(2)
                corrected = True

        # 4. Blanqueo
        factor_blanqueo = BLANQUEO[blanqueo_sel]["factor"]
        if factor_blanqueo < 1.0:
            df_res['T 12:00 (%)']        = df_res['T 12:00 (%)'].apply(lambda x: round(x * factor_blanqueo, 2) if x is not None else None)
            df_res['T media diaria (%)'] = (df_res['T media diaria (%)'] * factor_blanqueo).round(2)

        # 5. Columnas derivadas
        df_res = add_derived_columns(df_res)

        st.session_state.results = {
            'df':                df_res,
            'station':           nombre_est,
            'province':          nombre_prov,
            'corrected':         corrected,
            'measurement_date':  measurement_date if corrected else None,
            'blanqueo':          blanqueo_sel,
            'correction_factor': correction_factor,
            'factor_est':        factor_est,
        }

# ── RESULTADOS ────────────────────────────────────────────────────────────────
if st.session_state.results is not None:
    r = st.session_state.results
    st.subheader(f"📊 {r['station']} · {r['province']}")

    mensajes = []
    if r['corrected']:
        mensajes.append(f"Corregidos con la medición del {r['measurement_date'].strftime('%d/%m/%Y')}.")
    if r['blanqueo'] != "Sin blanqueo":
        dosis = BLANQUEO[r['blanqueo']]['dosis']
        factor_b = BLANQUEO[r['blanqueo']]['factor']
        mensajes.append(f"Blanqueo **{r['blanqueo']}** aplicado (factor {factor_b} · dosis orientativa {dosis} kg cal/100 L agua).")
    if mensajes:
        st.info("  \n".join(mensajes))

    st.dataframe(r['df'], use_container_width=True, hide_index=True)

    st.download_button(
        label="📥 Descargar CSV",
        data=csv_para_excel(r['df']),
        file_name=f"transmisividad_{r['station'].lower().replace(' ', '_')}_{date.today().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        help="Separador ';' y decimal ',' listo para Excel en español",
    )

    st.divider()
    with st.expander("➕ Añadir día con datos propios"):
        st.caption("Introduce los datos meteorológicos de un día concreto. La transmisividad se calculará con el modelo geométrico y los mismos factores activos (blanqueo y corrección).")
        with st.form("manual_day_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                man_fecha = st.date_input("Fecha", date.today() - timedelta(days=1), key="man_fecha")
                man_rad   = st.number_input("Radiación (MJ/m²)", 0.0, 50.0, 15.0, 0.1, key="man_rad")
                man_et0   = st.number_input("ETo ext. (mm)", 0.0, 20.0, 3.0, 0.1, key="man_et0")
            with col2:
                man_tmed  = st.number_input("T media (°C)", -10.0, 50.0, 20.0, 0.1, key="man_tmed")
                man_tmax  = st.number_input("T máxima (°C)", -10.0, 60.0, 25.0, 0.1, key="man_tmax")
                man_tmin  = st.number_input("T mínima (°C)", -10.0, 40.0, 15.0, 0.1, key="man_tmin")
            with col3:
                man_hr    = st.number_input("HR media (%)", 0.0, 100.0, 70.0, 1.0, key="man_hr")

            submitted = st.form_submit_button("➕ Añadir este día", type="primary")

        if submitted:
            factor_est_curr  = r.get('factor_est',        ESTRUCTURA_SOMBRA[roof_type])
            factor_corr_curr = r.get('correction_factor', 1.0)
            factor_blanq_curr = BLANQUEO[r['blanqueo']]['factor']

            with st.spinner("⏳ Calculando transmisividad para la fecha indicada…"):
                _, t_media_man, _, df_day_man, _ = run_calc(
                    lat, lon, man_fecha, roof_type, greenhouse_azimuth, module_width, ridge_height
                )
            t_noon_man = extract_noon_trans(df_day_man)

            t_noon_final  = round(t_noon_man  * factor_est_curr * factor_corr_curr * factor_blanq_curr, 2) if t_noon_man else None
            t_media_final = round(t_media_man * factor_est_curr * factor_corr_curr * factor_blanq_curr, 2)

            new_row = pd.DataFrame([{
                'Fecha':               man_fecha.strftime('%d/%m/%Y') + ' ✎',
                'Rad. RIA (MJ/m²)':   man_rad,
                'T media (°C)':       man_tmed,
                'T máxima (°C)':      man_tmax,
                'T mínima (°C)':      man_tmin,
                'HR media (%)':       man_hr,
                'ETo ext. (mm)':      man_et0,
                'T 12:00 (%)':        t_noon_final,
                'T media diaria (%)': t_media_final,
            }])

            new_row = add_derived_columns(new_row)

            st.session_state.results['df'] = pd.concat(
                [st.session_state.results['df'], new_row], ignore_index=True
            )
            st.rerun()

else:
    st.info("Configura los parámetros en el panel lateral y pulsa 'Consultar y Calcular'.")

# ── PIE ───────────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="text-align: center;">
    <p>© Hernández, J., Bonachela, S. (2026)</p>
    <p>Licencia <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">Creative Commons Attribution 4.0</a></p>
</div>
""", unsafe_allow_html=True)

