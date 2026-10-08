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

## Módulo técnico heredado: bandas de magnitud (v2)

El módulo **«Patrones por modelos»** compara cada ePWV estimada (Argentina, Europa sana y Europa factores de riesgo) con los valores de referencia **P50 aproximado, P90 y P95 de Díaz (2018)** para la misma edad y sexo. Las bandas son `<P50`, `P50–<P90`, `P90–<P95` y `≥P95`. **En una ePWV, estar por encima de P90 NO equivale a un percentil de VOP medida ni diagnostica rigidez patológica.** Las bandas de estimación son una comparación aritmética exploratoria con la distribución normativa de VOP cf real; se indican explícitamente como tales en pantalla.

Cuando se introduce **VOP realmente medida**, se presenta su banda normativa correspondiente, las coincidencias o discordancias de las bandas estimadas, el perfil de señal detectada o no detectada y el modelo que presenta menor error absoluto respecto de esa medición. Para evitar la inferencia errónea de equivalencia clínica entre modelos, se informan diferencias exactas en m/s (`Europa – Argentina`) y dispersión máxima entre las tres estimaciones. El margen configurable de amplitud de **1,0 m/s** es **solo descriptivo**, sin validación diagnóstica.

En bases CSV/XLSX se agregan columnas de patrones, gráfico apilado por modelo, distribución de discordancias, diferencias vs edad, tablas por intervalos etarios y tablas cruzadas cuando la base dispone de VOP cf medida. No se suben bases de pacientes a GitHub.

## Estado de validación del módulo de patrones

El nuevo módulo agrega una **categorización comparativa exploratoria**, sin validación clínica propia, realizada sobre coeficientes históricos del trabajo metodológico de octubre 2026. **No equipara VOP medida a ePWV**. Es imprescindible validar clasificación, concordancia y relevancia prospectiva en una cohorte independiente antes de incorporarlo a informes diagnósticos.

## 🔬 Nuevo módulo: rigidez medida y concordancia (v3)

Pestaña «Rigidez medida y concordancia»:

1. **Elevación referencial de VOP medida**: compara la tonometría real con el P90 o P95 de Díaz 2018 (ajuste por edad y sexo) y separa «sin medición» de «por debajo del umbral». Es una posición referencial, **no** equivale a diagnosticar daño de órgano blanco o enfermedad vascular.
2. **Concordancia entre las tres ePWV**: cuántos modelos presentan una estimación numéricamente ≥ al mismo umbral (0 a 3), consenso 3/3 y acuerdos par a par con estadístico kappa binario cuando está definido. Los umbrales de VOP medida no constituyen percentiles validados para las estimaciones.
3. **Discordancia medida–estimada**: describe elevaciones medidas no señaladas por ninguno, señaladas por uno/dos/tres, y alertas estimadas sin elevación real medida. Calcula diferencias firmadas, error absoluto, tablas descriptivas 2×2 (VP, FN, FP, VN), acuerdo, sensibilidad y especificidad *respecto de la etiqueta referencial medida*; no representan validación diagnóstica ni pronóstica.
4. **Auditoría por cohorte**: matrices, gráficos, recuentos y análisis por edad/sexo; exporta CSV y un PDF individual con los resultados y advertencias.

Selector de **P90/P95** y margen aritmético configurable (por defecto 1 m/s; NO es umbral clínico). El numerador/denominador de sensibilidad y especificidad incluye solo pares con **VOP medida**. Si no hay pares, los indicadores no se calculan; si no existe un denominador válido, se presentan en blanco. Las matrices se generan sobre la muestra cargada y no prueban transportabilidad a otras poblaciones.

> **Privacidad:** la subida de bases a Streamlit Cloud procesa los datos en un servidor externo. Elimine DNI, nombres y cualquier dato identificatorio antes de subirlos. Es recomendable correr la aplicación localmente para investigación con información sensible. Los archivos cargados no se publican en GitHub automáticamente.


## v4 — FENOTIPOS CORRECTOS DE ENVEJECIMIENTO VASCULAR

**Nueva pestaña central: `🧬 EVA · Saludable · SUPERNOVA`.**

Criterio operativo **exploratorio por percentiles de VOP carótido-femoral realmente medida**, con distribución argentina ajustada por edad y sexo de Díaz et al. (2018):

| Fenotipo | Rango de VOP **medida** | Alcance |
| --- | --- | --- |
| **SUPERNOVA** | < P10 | Rigidez inusualmente baja respecto de referencia saludable de su edad y sexo |
| **Saludable / esperado** | ≥ P10 y < P90 | VOP medida dentro de la banda de referencia operacional, NO garantiza ausencia de enfermedad |
| **EVA** | ≥ P90 | Rigidez por encima del límite superior referencial seleccionado, sugerente de envejecimiento acelerado |

Permite **análisis de sensibilidad P5/P95**. Esta clasificación por percentiles es un **marco operativo para investigación**, no la fórmula de edad vascular de Bruno et al. (2020), que utiliza diferencia entre edad vascular estimada y cronológica. No existe definición EVA/SUPERNOVA estandarizada universalmente ni equivalencia demostrada de HVA referencial con ausencia de riesgo cardiovascular.

**Regla de seguridad:** sin tonometría real, `Fenotipo_VOP_medida = None` (**NO EVALUABLE**). La app **no** asigna EVA/Saludable/SUPERNOVA clínica desde ePWV derivada de edad y PAM; cuando se compara ePWV con percentiles Díaz, el campo se denomina **fenotipo TEÓRICO/simulado, NO VALIDADO**.

### Funciones nuevas

- Muestra en el paciente los tres fenotipos de referencia, sus umbrales P10/P90 individuales, el fenotipo de la medición, y la comparación teórica de tres estimadores (ARG, Europa sana, Europa con factores de riesgo).
- Resalta coincidencia categórica **3/3, parcial (1/3 o 2/3), 0/3** y error firmado/absoluto cuando hay tonometría real.
- Genera informes PDF individuales con etiquetas de **medición real vs simulación**, tablas comparativas y advertencias.
- En cohortes anónimas, produce distribuciones de fenotipos, matrices de confusión de **tres categorías**, kappa nominal, EVA y SUPERNOVA omitidas, errores por edad, y exportaciones CSV.
- Conserva la pestaña `Auditoría técnica P90/P95` antigua como comparación binaria **secundaria**, sin denominar a sus resultados fenotipos EVA/SUPERNOVA.

### Referencias de los fenotipos

- Díaz A et al. *Reference intervals and percentiles for carotid-femoral pulse wave velocity in a healthy population aged between 9 and 87 years.* J Clin Hypertens. 2018;20:659–671. doi:10.1111/jch.13251.
- Bruno RM et al. *Early and Supernormal Vascular Aging: Clinical Characteristics and Association With Incident Cardiovascular Events.* Hypertension. 2020;76:1616–1624. doi:10.1161/HYPERTENSIONAHA.120.14971. **Define fenotipos basados en Δ-edad**, NO por la regla P10/P90 aplicada aquí.
- *Analysis of vascular aging phenotypes in a high cardiovascular risk population*. Sci Rep (2025). Aplicó cfPWV < P10 como SUPERNOVA, entre P10 y P90 normal, y ≥P90 EVA, reconociendo falta de estandarización universal.

### Pruebas automáticas

`python -m pytest -q` (30 pruebas del motor, incluyendo P10/P90, P5/P95, caso sin medición, matriz 3x3 y cohortes sintéticas).

**Advertencia de desarrollo:** el código está preparado para Streamlit Community Cloud; al generar esta versión se pudieron ejecutar las pruebas del motor, pero **no fue posible instalar Streamlit en este entorno sin conexión a PyPI**. El arranque real de la interfaz debe confirmarse al desplegarlo en Streamlit.


## v5 · Interfaz gráfica profesional y dashboard EVA (octubre 2026)

La pestaña de apertura es **«Dashboard EVA»**. Incluye un **caso demostrativo ficticio** claramente identificado hasta que se ingrese un paciente real en «Paciente».

- Tarjeta de resultado de alto contraste: **EVA / Saludable-esperado / SUPERNOVA** por **VOP carótido-femoral realmente medida**. Si falta tonometría, indica **NO EVALUABLE**, aunque haya tres ePWV estimadas.
- **Mapa de puntajes Z** con franjas según P10/P90 de Díaz (2018), separando diamante de VOP realmente medida y círculos abiertos de estimaciones **TEÓRICAS — NO VALIDADAS**.
- **Nomograma edad–VOP de 9 a 87 años** para el sexo informado: curvas percentilares P10, media y P90 (alternativamente P5/P95), punto medido y predicciones con símbolos distintos.
- **Comparativa horizontal de magnitudes** de tonometría y tres ecuaciones, con diferencias respecto a medición real.
- **Cohortes anonimizadas**: distribución en porcentaje y recuento de EVA/SUPERNOVA medidos, comparación sobre el MISMO denominador de sujetos con tonometría, matrices 3 × 3 de coincidencia teórica por modelo y distribuciones por edad.
- **Reporte PDF descargable** y exportación CSV de los perfiles de cohorte. Interfaz responsive, nueva cabecera, indicadores y tablas.

### Alcance clínico y limitaciones

La elección SUPERNOVA <P10; saludable/esperado P10–<P90; EVA ≥P90 es una **taxonomía operativa de investigación**, no un estándar universal ni evidencia de riesgo, salud o edad vascular biológica. Los modelos de ePWV no han sido validados para clasificar estos fenotipos. Las categorías teóricas se diferencian en toda la interfaz de las etiquetas provenientes de VOP medida.

Para desplegar con GitHub: conectar el repositorio a Streamlit Community Cloud usando la rama `main` y el archivo principal `app.py`. **No subir datos identificatorios al repositorio ni a un despliegue público.**