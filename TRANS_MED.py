import streamlit as st
import pandas as pd
import numpy as np
import pvlib
import io

# --- Configuración de la página de Streamlit ---
st.set_page_config(page_title="Estudio Solar Anual - Invernaderos", layout="wide")

# --- CÁLCULO PARA CUBIERTA A DOS AGUAS  ---
def calculate_radiation_gable(lat, lon, date, greenhouse_azimuth, module_width, ridge_height, measured_external_energy_MJ):
    if module_width > 0 and ridge_height >= 0:
        roof_tilt = np.degrees(np.arctan(ridge_height / (module_width / 2)))
    else:
        roof_tilt = 0

    tz, location, times, solar_position, dni_ideal, dhi_ideal, ghi_ideal, dni_extra = setup_solar_model(lat, lon, date)
    dni_real, dhi_real, ghi_real, model_type = scale_solar_model(ghi_ideal, dni_ideal, dhi_ideal, times, measured_external_energy_MJ)
    
    surface_azimuth_1, surface_azimuth_2 = (greenhouse_azimuth + 90) % 360, (greenhouse_azimuth - 90 + 360) % 360
    label_1, label_2 = f"Cara a {surface_azimuth_1}°", f"Cara a {surface_azimuth_2}°"

    poa_1 = pvlib.irradiance.get_total_irradiance(roof_tilt, surface_azimuth_1, solar_position['apparent_zenith'], solar_position['azimuth'], dni_real, ghi_real, dhi_real, dni_extra=dni_extra, model='haydavies')
    poa_2 = pvlib.irradiance.get_total_irradiance(roof_tilt, surface_azimuth_2, solar_position['apparent_zenith'], solar_position['azimuth'], dni_real, ghi_real, dhi_real, dni_extra=dni_extra, model='haydavies')

    irrad_transmitida_1 = calculate_transmitted_irradiance(poa_1, roof_tilt, surface_azimuth_1, solar_position)
    irrad_transmitida_2 = calculate_transmitted_irradiance(poa_2, roof_tilt, surface_azimuth_2, solar_position)

    cos_tilt = np.cos(np.radians(roof_tilt))
    if cos_tilt > 0.001:
        aporte_suelo_1, aporte_suelo_2 = irrad_transmitida_1 / (2 * cos_tilt), irrad_transmitida_2 / (2 * cos_tilt)
    else:
        aporte_suelo_1, aporte_suelo_2 = pd.Series(0, index=times), pd.Series(0, index=times)
    
    irradiancia_suelo = aporte_suelo_1 + aporte_suelo_2
    energia_interior_kWh_m2, transmisividad_global, df_results = finalize_results(irradiancia_suelo, ghi_real, times, {"label_1": label_1, "aporte_1": aporte_suelo_1, "label_2": label_2, "aporte_2": aporte_suelo_2})
    
    return energia_interior_kWh_m2, transmisividad_global, roof_tilt, df_results, model_type

# --- CÁLCULO PARA CUBIERTA CURVA (LÓGICA CORREGIDA) ---
def calculate_radiation_curved(lat, lon, date, greenhouse_azimuth, module_width, ridge_height, measured_external_energy_MJ):
    N_SEGMENTS = 50  # Aumentamos segmentos para mayor precisión

    if ridge_height < 0.01:
        return calculate_radiation_gable(lat, lon, date, greenhouse_azimuth, module_width, 0, measured_external_energy_MJ)

    W, H = module_width, ridge_height
    radius = (H**2 + (W/2)**2) / (2*H)
    theta_max = np.arcsin((W/2) / radius)
    
    tz, location, times, solar_position, dni_ideal, dhi_ideal, ghi_ideal, dni_extra = setup_solar_model(lat, lon, date)
    dni_real, dhi_real, ghi_real, model_type = scale_solar_model(ghi_ideal, dni_ideal, dhi_ideal, times, measured_external_energy_MJ)
    
    # Esta variable acumulará la Potencia por unidad de largo (W/m)
    total_power_per_length = pd.Series(0.0, index=times)
    angles = np.linspace(-theta_max, theta_max, N_SEGMENTS)
    d_theta = angles[1] - angles[0] # Ancho angular de cada segmento en radianes
    
    for i in range(N_SEGMENTS - 1):
        angle_mid = (angles[i] + angles[i+1]) / 2
        
        segment_tilt = np.degrees(abs(angle_mid))
        segment_azimuth = (greenhouse_azimuth - 90 + 360) % 360 if angle_mid < 0 else (greenhouse_azimuth + 90) % 360

        poa_segment = pvlib.irradiance.get_total_irradiance(segment_tilt, segment_azimuth, solar_position['apparent_zenith'], solar_position['azimuth'], dni_real, ghi_real, dhi_real, dni_extra=dni_extra, model='haydavies')
        irrad_transmitida_segment = calculate_transmitted_irradiance(poa_segment, segment_tilt, segment_azimuth, solar_position)
        
        # --- LÓGICA CORRECTA Y SIMPLIFICADA ---
        # Longitud de arco del segmento (dS = R * d_theta)
        arc_length_segment = radius * d_theta
        
        # Potencia que atraviesa el segmento por unidad de largo del invernadero (W/m)
        power_per_length_segment = irrad_transmitida_segment * arc_length_segment
        
        total_power_per_length += power_per_length_segment

    # Irradiancia media en el suelo = Potencia total por largo / Ancho del suelo
    irradiancia_suelo = total_power_per_length / W

    energia_interior_kWh_m2, transmisividad_global, df_results = finalize_results(irradiancia_suelo, ghi_real, times)
    return energia_interior_kWh_m2, transmisividad_global, 0, df_results, model_type


# --- Funciones de Ayuda Refactorizadas (sin cambios) ---
def setup_solar_model(lat, lon, date):
    tz = f'Etc/GMT{int(-lon/15)}'
    location = pvlib.location.Location(latitude=lat, longitude=lon, tz=tz, altitude=200)
    start_date = pd.Timestamp(date, tz=tz)
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
        scaling_factor = measured_MJ / energia_ideal_MJ
        dni_real, dhi_real, ghi_real = dni_ideal * scaling_factor, dhi_ideal * scaling_factor, ghi_ideal * scaling_factor
        model_type = "real"
    else:
        dni_real, dhi_real, ghi_real = dni_ideal, dhi_ideal, ghi_ideal
        model_type = "ideal"
    return dni_real, dhi_real, ghi_real, model_type

def calculate_transmitted_irradiance(poa, tilt, azimuth, solar_position):
    aoi = pvlib.irradiance.aoi(tilt, azimuth, solar_position['apparent_zenith'], solar_position['azimuth'])
    aoi[aoi > 90] = 90
    transmisividad_directa = np.clip((0.90647838+(-0.00277529*aoi) +( 0.00014437*aoi**2)+( -0.00000260*aoi**3)), 0, 1)
    transmisividad_difusa = 0.75
    irrad_transmitida = poa['poa_direct'] * transmisividad_directa
    return irrad_transmitida

def finalize_results(irradiancia_suelo, ghi_real, times, aportes=None):
    intervalo_horas = (times[1] - times[0]).total_seconds() / 3600
    energia_interior_kWh_m2 = irradiancia_suelo.sum() * intervalo_horas / 1000
    energia_exterior_kWh_m2 = ghi_real.sum() * intervalo_horas / 1000
    transmisividad_global = (energia_interior_kWh_m2 / energia_exterior_kWh_m2 * 100) if energia_exterior_kWh_m2 > 0 else 0
    
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
    return energia_interior_kWh_m2, transmisividad_global, df_results

# --- Interfaz de Usuario ---
st.title("☀️ **PAGINA EN PRUEBAS** Estudio Solar Anual para Invernaderos Mediterráneos")
st.markdown("**Calcula la transmisividad diaria para todos los días del año. EL MODELO NO ES EXPLOTABLE. ES UNA VERSIÓN EN PRUEBAS.**")
st.sidebar.image("https://github.com/Jhrodri/open/blob/main/logo.png?raw=true", width=300)
st.sidebar.header("🔧 Parámetros de Entrada")
roof_type = st.sidebar.radio("Tipo de Cubierta", ["A dos aguas", "Curva"])

lat = st.sidebar.number_input("Latitud (grados)", -90.0, 90.0, 36.8, 0.5)
lon = st.sidebar.number_input("Longitud (grados)", -180.0, 180.0, -2.4, 0.5)
greenhouse_azimuth = st.sidebar.slider("Orientación del invernadero (°)", 0, 359, 90, 1, help="0°=N, 90°=E, 180°=S, 270°=O. El eje es perpendicular a las caras del techo.")

st.sidebar.subheader("Dimensiones del invernadero")
module_width = st.sidebar.number_input("Ancho del módulo (m)", 1.0, 50.0, 8.0, 0.5)
help_text_height = "Para 'A dos aguas': altura de canal a cumbrera. Para 'Curva': altura máxima del arco."
ridge_height = st.sidebar.number_input("Altura máxima de la cumbrera (m)", 0.0, 20.0, 1.5, 0.1, help=help_text_height)

if st.sidebar.button("Calcular transmisividad anual", type="primary"):
    resultados = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for day_of_year in range(1, 366):
        date = (pd.Timestamp("2025-01-01") + pd.Timedelta(days=day_of_year - 1)).date()
        status_text.text(f"Calculando día {day_of_year}/365...")

        if roof_type == "A dos aguas":
            _, transmisividad_media, _, df_day, _ = calculate_radiation_gable(
                lat, lon, date, greenhouse_azimuth, module_width, ridge_height, 0)
        else:
            _, transmisividad_media, _, df_day, _ = calculate_radiation_curved(
                lat, lon, date, greenhouse_azimuth, module_width, ridge_height, 0)

        fila_mediodia = df_day[df_day['Hora'] == '12:00']
        if not fila_mediodia.empty:
            I_ext = fila_mediodia['Radiación Exterior (W/m²)'].values[0]
            I_inv = fila_mediodia['Radiación en Invernadero (W/m²)'].values[0]
            trans_noon = round((I_inv / I_ext) * 100, 2) if I_ext > 0 else None
        else:
            trans_noon = None

        if trans_noon and trans_noon > 0:
            k = round(transmisividad_media / trans_noon, 4)
        else:
            k = None

        resultados.append({
            'Día del año': day_of_year,
            'Transmisividad a las 12:00 (%)': trans_noon,
            'Transmisividad media diaria (%)': round(transmisividad_media, 2),
            'K (media/mediodía)': k,
        })
        progress_bar.progress(day_of_year / 365)

    progress_bar.empty()
    status_text.empty()

    df_anual = pd.DataFrame(resultados)
    st.dataframe(df_anual, use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_anual.to_excel(writer, index=False, sheet_name='Transmisividad Anual')

    st.download_button(
        label="Descargar resultados en Excel",
        data=buffer.getvalue(),
        file_name=f"transmisividad_anual_{roof_type.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Selecciona el tipo de cubierta y los parámetros. Después haz clic en 'Calcular transmisividad anual'.")

# INICIO BLOQUE EXPANDERS (desactivado)
if False:
 with st.expander("🔬 Información sobre el modelo"):
    st.markdown("""

## Introducción

Esta app calcula la radiación solar que llega al suelo de un invernadero, considerando la geometría de la cubierta, la posición solar, y las propiedades de transmisión de la luz diferenciando dos geometrías de cubierta: **cubierta lineal a dos aguas** y **cubierta curva**.

Los valores obtenidos serían representativos de un módulo central del invernadero no afectado por las paredes laterales.

## Principios Físicos

### 1. Determinación de la radiación exterior

La radiación solar se descompone en tres componentes fundamentales:

- **DNI**: Irradiancia Normal Directa (perpendicular a los rayos solares)
- **DHI**: Irradiancia Horizontal Difusa  
- **GHI**: Irradiancia Global Horizontal

**GHI = DNI × cos(θz) + DHI**

donde θz es el ángulo cenital solar .

Cuando se dispone de mediciones reales, se aplica un factor de escalado:

**factor_escalado = E_medida / E_ideal**

**Todos los valores calculados mediante el modelo de cielo claro de Ineichen-Perez**

### 2. Geometría de Invernaderos

#### 2.1 Cubierta a Dos Aguas

Para invernaderos con cubierta a dos aguas, la inclinación β de la cubierta se calcula geométricamente:

**β = arctan(h / (W/2))**

donde:
- h: Altura de canal a cumbrera
- W: Ancho total del módulo

Las dos caras de la cubierta tienen orientaciones azimutales opuestas:
- **Cara 1**: α₁ = (α_inv + 90°) mod 360°
- **Cara 2**: α₂ = (α_inv - 90°) mod 360°

donde α_inv es la orientación del eje longitudinal del invernadero.

#### 2.2 Cubierta Curva

Para cubiertas curvas, se modela como un arco circular con:

**R = (h² + (W/2)²) / (2h)**

**θ_max = arcsin((W/2) / R)**

donde:
- R: Radio del arco circular
- θ_max: Ángulo máximo del arco desde la vertical

El arco se discretiza en N segmentos para integración numérica, con:

**Δθ = 2θ_max / N** (Por defecto N=50)

### 3. Cálculo de Irradiancia en Superficies Inclinadas

#### 3.1 Modelo de Hay-Davies
La irradiancia total en una superficie inclinada (POA) se calcula mediante:

**POA = I_b × R_b + I_d × (1 + cos(β))/2 × (1 - A_i) + I_d × A_i × R_b + ρ × GHI × (1 - cos(β))/2**

donde:
- I_b: Irradiancia directa en superficie horizontal
- I_d: Irradiancia difusa en superficie horizontal  
- R_b: Factor geométrico para radiación directa
- β: Inclinación de la superficie
- ρ: Albedo del suelo (reflectancia)
- A_i: Índice de anisotropía:

A_i = DNI / I_0
donde:

- I_0 = Irradiancia extraterrestre en superficie normal al sol
- I_0 = I_sc × (1 + 0.033 × cos(360°n/365))
- I_sc = Constante solar (≈ 1367 W/m²)
- n = Día del año

#### 3.2 Factor Geométrico para Radiación Directa

**R_b = cos(AOI) / cos(θz)**

donde AOI es el ángulo de incidencia entre el rayo solar y la normal a la superficie.

#### 3.3 Ángulo de Incidencia
El ángulo de incidencia (AOI) se calcula mediante:

**cos(AOI) = cos(θ_z) × cos(β) + sin(θ_z) × sin(β) × cos(γ_s - γ)**

donde:
- θ_z = Ángulo cenital solar aparente
- β = Ángulo de inclinación de la superficie
- γ_s = Ángulo de azimut solar
- γ: Ángulo de azimut de la superficie

También puede calcularse como: **cos(AOI) = sin(δ) × sin(φ) × cos(β) - sin(δ) × cos(φ) × sin(β) × cos(α) + cos(δ) × cos(φ) × cos(β) × cos(ω) + cos(δ) × sin(φ) × sin(β) × cos(α) × cos(ω) + cos(δ) × sin(β) × sin(α) × sin(ω)**


donde:
- δ: Declinación solar
- φ: Latitud del lugar
- α: Azimut de la superficie
- ω: Ángulo horario solar


### 4. Transmisividad

#### 4.1 Transmisividad Direccional
La transmisión a la radiación directa en función del ángulo de incidencia se modela mediante un polinomio cúbico obtenido experimentalmente a partir de un plástico tricapa. 

- Si AOI > 90°, entonces AOI = 90° y la transmisividad es 0
- 0 ≤ τ_dir ≤ 1

donde AOI está expresado en grados.

#### 4.2 Transmisividad Difusa
Para radiación difusa se asume un valor constante:

**τ_dif = 0.75** (75% de transmisión)

#### 4.3 Radiación Transmitida
La radiación que atraviesa la cubierta se calcula como:

**I_trans = POA_directa × τ_dir(AOI) + POA_difusa × τ_dif**

### 5. Integración Espacial

#### 5.1 Cubierta a Dos Aguas
La irradiancia en el suelo se calcula como la suma de aportes de ambas caras de la cubierta:

**I_suelo,1 = I_trans,1 / (2 × cos(β))**

**I_suelo,2 = I_trans,2 / (2 × cos(β))**

**I_suelo,total = I_suelo,1 + I_suelo,2**

donde:
- I_trans,1 e I_trans,2 son las irradiancias transmitidas por cada cara
- β es la inclinación de la cubierta
- El factor 2 considera que cada cara cubre la mitad del área horizontal
- cos(β) es la proyección de la superficie inclinada sobre la horizontal

#### 5.2 Cubierta Curva
Para cubiertas curvas se integra sobre todos los segmentos (50 en esta simulación):

**Para cada segmento i:**
- **Longitud de arco**: Δs_i = R × Δθ
- **Potencia transmitida por unidad de longitud**: P_i = I_trans,i × Δs_i
- **Potencia total por unidad de longitud**: P_total = Σ P_i

**Irradiancia media en el suelo:**

**I_suelo = P_total / W**

donde W es el ancho del módulo al nivel del suelo.

### 6. Integración Temporal

#### 6.1 Resolución Temporal
Los cálculos se realizan con intervalos de tiempo regulares (típicamente 10 minutos) a lo largo del día.

#### 6.2 Energía Diaria
La energía se calcula integrando la potencia instantánea a lo largo del tiempo:

**E_interior = Σ(I_suelo(t) × Δt)**

donde:
- I_suelo(t): Irradiancia en el suelo en el tiempo t [W/m²]
- Δt: Intervalo de tiempo [h]
- E_interior: Energía total diaria en el interior [kWh/m²]

Para la conversión a MJ/m²:

**E_interior [MJ/m²] = E_interior [kWh/m²] × 3.6**


### 7. Transmisividad Global del Invernadero
La trasmisividad global se calcula como:

**τ_global = (E_interior / E_exterior) × 100%**

donde:
- E_interior: Energía diaria recibida en el suelo del invernadero [kWh/m² o MJ/m²]
- E_exterior: Energía diaria de radiación solar exterior [kWh/m² o MJ/m²]


## Limitaciones y Consideraciones del Modelo

### Simplificaciones Adoptadas
1. **Transmisividad constante espectral**: No considera variaciones en función de la longitud de onda ni dependencia de la temperatura
2. **Geometría idealizada**: Asume estructuras perfectamente regulares sin elementos estructurales intermedios
3. **Ausencia de sombreado y reflexiones internas**
4. **Propiedades ópticas uniformes**: Asume propiedades constantes en toda la cubierta

### Condiciones de Validez
- Válido para cubiertas transparentes o translúcidas
- Geometrías simétricas respecto al eje longitudinal
- Terreno plano y sin obstáculos externos

## Aplicaciones del Modelo

Este marco matemático es aplicable para:
- **Diseño**: Determinación de orientación y geometría que maximicen la transmisión solar
- **Análisis energético**: Cuantificación de la energía solar diaria
- **Sistemas de control**: Base para estrategias de ventilación y sombreado
- **Comparación de materiales**: Evaluación de diferentes cubiertas transparentes (cambiando el polinomio empírico)

## Fundamentos Teóricos de Referencia

- **Modelo Ineichen**: Modelo empírico para irradiancia de cielo despejado
- **Modelo Hay-Davies**: Modelo físico para irradiancia en superficies inclinadas
- **Ecuaciones solares fundamentales**: Basadas en mecánica celeste y geometría esférica


    
    
    """)

 with st.expander("🔬 Diagrama de flujo"):
    st.markdown("""
## 📊 Diagrama de Flujo del Modelo

### **1. ENTRADA DE DATOS**
```
📍 Ubicación (lat, lon) + Fecha
🏠 Geometría del invernadero (tipo, dimensiones, orientación)
📏 Radiación medida (opcional)
```

### **2. CONFIGURACIÓN SOLAR**
```
setup_solar_model()
    ↓
🌍 Crear objeto Location (pvlib)
⏰ Serie temporal (10 min, 1 día)  
🌞 Posición solar
🌤️ MODELO INEICHEN → DNI_ideal, GHI_ideal, DHI_ideal
🌌 Irradiancia extraterrestre
```

### **3. ESCALADO DE DATOS**
```
scale_solar_model()
    ↓
¿Hay medición real?
    ├─ SÍ → 📏 ESCALADO: factor = E_medida/E_ideal
    │       DNI_real = DNI_ideal × factor
    └─ NO  → 🌤️ CIELO CLARO: usar valores ideales
```

### **4. GEOMETRÍA DE CUBIERTA**

#### **Cubierta A Dos Aguas:**
```
calculate_radiation_gable()
    ↓
β = arctan(H/(W/2))
Cara 1: azimuth₁ = orientación + 90°
Cara 2: azimuth₂ = orientación - 90°
    ↓
🏠 HAY-DAVIES para cada cara
get_total_irradiance(model='haydavies')
    ↓
POA₁, POA₂
```

#### **Cubierta Curva:**
```
calculate_radiation_curved()
    ↓
R = (H² + (W/2)²)/(2H)
Dividir en 50 segmentos
    ↓
Para cada segmento i:
    ├─ Calcular tilt_i y azimuth_i
    ├─ 🏠 HAY-DAVIES → POA_segment_i
    └─ Longitud de arco = R × Δθ
```

### **5. TRANSMISIVIDAD**
```
calculate_transmitted_irradiance()
    ↓
📐 Ángulo de incidencia (AOI)
    ↓
🔬 Transmisividad direccional:
τ_dir = polinomio_empirico(AOI)
🌫️ Transmisividad difusa: τ_dif = 0.75
    ↓
💡 I_transmitida = POA_directa × τ_dir + POA_difusa × τ_dif
```

### **6. INTEGRACIÓN ESPACIAL**

#### **Dos Aguas:**
```
I_suelo₁ = I_trans₁ / (2 × cos(β))
I_suelo₂ = I_trans₂ / (2 × cos(β))
I_suelo_total = I_suelo₁ + I_suelo₂
```

#### **Curva:**
```
Para cada segmento:
    Potencia_i = I_trans_i × longitud_arco_i
Potencia_total = Σ Potencia_i
I_suelo = Potencia_total / ancho_invernadero
```

### **7. RESULTADOS FINALES**
```
finalize_results()
    ↓
📊 Integración temporal:
E_interior = Σ(I_suelo × Δt) [kWh/m²]
    ↓
📈 Transmisividad global:
τ_global = (E_interior / E_exterior) × 100%
    ↓
📋 DataFrame con series temporales
```

---

## 🔬 Modelos Físicos Utilizados

| Etapa | Modelo | Propósito |
|-------|--------|-----------|
| **1** | 🌤️ **Ineichen-Perez** | Irradiancia de cielo claro |
| **2** | 📏 **Escalado lineal** | Calibración con datos reales |
| **3** | 🏠 **Hay-Davies** | Transposición a superficies inclinadas |
| **4** | 🔬 **Polinomio empírico** | Transmisividad direccional |
| **5** | 📊 **Integración numérica** | Energía diaria total |

---



  """) 
# Pie de página side

footer_html = """
<div style="text-align: center;">
    <p>© jhrodri</p>
    <p>Licencia <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">Creative Commons Attribution 4.0</a></p>
</div>
"""
# Usamos st.sidebar.markdown para renderizarlo
st.sidebar.markdown(footer_html, unsafe_allow_html=True)    
