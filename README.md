# 🫀 VOP ARG — aplicación de investigación en Streamlit

App de investigación para estimación **exploratoria** de la velocidad de onda del pulso carótido-femoral (ePWV) en una población argentina. Compara el modelo candidato 2026 con ecuaciones europeas y calcula referencias normativas por sexo/edad de Díaz y cols. (2018).

## Funcionalidad

- Calculadora por **edad, sexo, PAS y PAD**; PAM = PAD + **0,4** × (PAS − PAD).
- Modelo **argentino candidato** y modelos **europeos** (sujetos sanos / factores de riesgo).
- Valores de referencia de **Díaz et al. 2018**: media, DE, P90, P95; **percentil y Z únicamente para VOP carótido-femoral realmente medida**.
- Informe individual descargable en PDF con advertencia de uso exploratorio.
- Importación de **CSV o Excel** con mapeo interactivo de columnas, incluidos encabezados en fila 2 como el Excel de Tandil. Sexo numérico: **1 = masculino, 2 = femenino**.
- Exportación de resultados y rechazos a CSV.
- Auditoría con VOP medida: **sesgo, MAE, RMSE, R², Bland–Altman, dispersión y estratificación por edad**.
- Población de aplicación restringida al intervalo documental **9–87 años**.

## Instalación local (Windows, macOS, Linux)

Requiere Python 3.11+:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Publicar en Streamlit Community Cloud

1. Ingresar a <https://share.streamlit.io/> y conectar GitHub.
2. Seleccionar el repositorio `DANIAPP4565/VOP`, rama `main`.
3. Seleccionar archivo principal **`app.py`** y desplegar.
4. La URL de Streamlit aparecerá una vez completada la implementación.

**Privacidad:** En Streamlit Community Cloud, los datos subidos se procesan en servidores remotos. No subir datos identificatorios ni resultados con nombre/DNI en servicios públicos. El repositorio GitHub únicamente contiene **código, pruebas y documentación**; no contiene datos clínicos.

## Validación

```bash
pip install pytest
python -m pytest -q
```

La app implementa coeficientes del informe *«Modelo candidato argentino para estimar la velocidad de onda del pulso carótido-femoral»*, octubre de 2026. El proyecto todavía **no cuenta con validación externa**. La tasa de error de una cohorte no equivale a precisión en un paciente individual. Los parámetros no constituyen recomendación clínica, criterio diagnóstico o sustituto de la tonometría real.

**Referencia de intervalos:** Díaz A, Zócalo Y, Bia D, Wray S, Cabrera Fischer E. *Reference intervals and percentiles for carotid-femoral pulse wave velocity in a healthy population aged between 9 and 87 years*. J Clin Hypertens. 2018;20:659–671. DOI: [10.1111/jch.13251](https://doi.org/10.1111/jch.13251).

## Autoría

Proyecto de investigación de mecánica vascular. Dr. Ricardo Daniel Olano, especialista en Cardiología e Hipertensión Arterial.

## Nuevo módulo · Patrones de rigidez referencial (v2)

El módulo **«Patrones por modelos»** compara cada ePWV estimada (Argentina, Europa sana y Europa factores de riesgo) con los valores de referencia **P50 aproximado, P90 y P95 de Díaz (2018)** para la misma edad y sexo. Las bandas son `<P50`, `P50–<P90`, `P90–<P95` y `≥P95`. **En una ePWV, estar por encima de P90 NO equivale a un percentil de VOP medida ni diagnostica rigidez patológica.** Las bandas de estimación son una comparación aritmética exploratoria con la distribución normativa de VOP cf real; se indican explícitamente como tales en pantalla.

Cuando se introduce **VOP realmente medida**, se presenta su banda normativa correspondiente, las coincidencias o discordancias de las bandas estimadas, el perfil de señal detectada o no detectada y el modelo que presenta menor error absoluto respecto de esa medición. Para evitar la inferencia errónea de equivalencia clínica entre modelos, se informan diferencias exactas en m/s (`Europa – Argentina`) y dispersión máxima entre las tres estimaciones. El margen configurable de amplitud de **1,0 m/s** es **solo descriptivo**, sin validación diagnóstica.

En bases CSV/XLSX se agregan columnas de patrones, gráfico apilado por modelo, distribución de discordancias, diferencias vs edad, tablas por intervalos etarios y tablas cruzadas cuando la base dispone de VOP cf medida. No se suben bases de pacientes a GitHub.

## Estado de validación del módulo de patrones

El nuevo módulo agrega una **categorización comparativa exploratoria**, sin validación clínica propia, realizada sobre coeficientes históricos del trabajo metodológico de octubre 2026. **No equipara VOP medida a ePWV**. Es imprescindible validar clasificación, concordancia y relevancia prospectiva en una cohorte independiente antes de incorporarlo a informes diagnósticos.