"""VOP ARG | calculadora ePWV, referencias Díaz y auditoría de lotes."""
from __future__ import annotations

from io import BytesIO
import math
import re
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from patterns import MODELS, BAND_ORDER, evaluate_patterns
from concordance_ui import render as render_concordance
from aging_ui import render as render_aging
from engine import (
    AGE_BANDS, MODEL_VERSION, REFERENCE, analyze_rows,
    calculate, metrics,
)

st.set_page_config(page_title="VOP ARG | Mecánica vascular", page_icon="🫀", layout="wide")
st.markdown("""<style>
.block-container {max-width:1250px; padding-top:1.8rem; padding-bottom:2rem}
h1,h2,h3 {color:#12304A}
[data-testid='stMetric'] {background:#EDF5F7; border-left:4px solid #008A80;
  border-radius:10px; padding:16px}
div.stButton > button[kind='primary'] {background:#087E77; color:white}
.smallcap {font-size:0.78rem;letter-spacing:.11em;color:#07867e;font-weight:700}
</style>""", unsafe_allow_html=True)


def patient_pdf(result: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=42)
    styles = getSampleStyleSheet()
    story = [Paragraph("Informe de VOP estimada (uso exploratorio)", styles["Title"]),
             Spacer(1, 14),
             Paragraph("<b>No validado externamente. No reemplaza tonometría carótido-femoral ni constituye diagnóstico.</b>", styles["BodyText"]),
             Spacer(1, 16)]
    fields = [
        ("Identificador", result["Identificador"] or "Sin identificador"),
        ("Edad / sexo", f'{result["Edad"]:.0f} años / {result["Sexo"]}'),
        ("PAS / PAD", f'{result["PAS"]:.0f} / {result["PAD"]:.0f} mmHg'),
        ("PAM (0,4)", f'{result["PAM_0_4"]:.1f} mmHg'),
        ("ePWV Argentina (candidata)", f'{result["ePWV_ARG"]:.2f} m/s'),
        ("ePWV europea sana", f'{result["ePWV_Europa_sana"]:.2f} m/s'),
        ("ePWV europea riesgo", f'{result["ePWV_Europa_riesgo"]:.2f} m/s'),
        ("Referencia Díaz media ± DE", f'{result["Diaz_media_normativa"]:.2f} ± {result["Diaz_DE_normativa"]:.2f} m/s'),
        ("Referencia Díaz P90 / P95", f'{result["Diaz_P90"]:.2f} / {result["Diaz_P95"]:.2f} m/s'),
    ]
    fields += [
        ('Límite SUPERNOVA (P10)', f'{result["Umbral_SUPERNOVA_m_s"]:.2f} m/s'),
        ('Límite EVA (P90)', f'{result["Umbral_EVA_m_s"]:.2f} m/s'),
        ('Fenotipo real medido (P10/P90)', result['Fenotipo_VOP_medida'] or 'NO EVALUABLE — sin VOP medida'),
        ('Entre modelos estimados', result['Concordancia_3_estimados']),
        ('Comparación con VOP medida', result['Concordancia_medida_estimados']),
        ('Delta Europa sana - ARG', f'{result["Delta_Europa_sana_menos_ARG_m_s"]:+.2f} m/s'),
        ('Delta Europa FR - ARG', f'{result["Delta_Europa_riesgo_menos_ARG_m_s"]:+.2f} m/s'),
    ]
    for k, label in (('ARG','Argentina'),('EU_SANA','Europa sana'),('EU_FR','Europa riesgo')):
        fields.append((f'Categoria teórica ePWV {label}', result[f'Fenotipo_teorico_{k}'] + ' (NO VALIDADA)'))
    if result["VOP_medida"] is not None:
        fields.extend([
            ("VOP realmente medida", f'{result["VOP_medida"]:.2f} m/s'),
            ("Percentil Díaz de VOP MEDIDA", f'{result["Diaz_percentil_VOP_medida"]:.1f}'),
            ("Z Díaz de VOP MEDIDA", f'{result["Diaz_Z_VOP_medida"]:.2f}'),
            ("Error candidata (estimada - medida)", f'{result["Error_ARG"]:+.2f} m/s'),
        ])
    t = Table([["Variable", "Valor"]] + [[str(k), str(v)] for k,v in fields], colWidths=[245, 250])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#12304A")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#E9F3F5")]),
        ("GRID",(0,0),(-1,-1),.2,colors.HexColor("#D1E3E5")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("BOTTOMPADDING",(0,0),(-1,-1),9), ("TOPPADDING",(0,0),(-1,-1),9),
    ]))
    story += [t, Spacer(1, 18), Paragraph("Fuente normativa: " + REFERENCE, styles["BodyText"]),
              Spacer(1, 12), Paragraph("EVA y SUPERNOVA (criterio exploratorio): con VOP medida P10/P90 de Díaz, corregido por edad y sexo. SUPERNOVA <P10, saludable/esperado P10 a <P90 y EVA >=P90. Las ePWV estimadas NO son VOP medida: sus categorías son solo simulaciones, no fenotipos clínicos validados ni diagnósticos. No existe consenso internacional universal sobre los cortes.", styles["BodyText"])]
    doc.build(story)
    return buf.getvalue()


def csv_data(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig").encode("utf-8-sig")


def read_table(upload, header_row: int):
    if upload.name.lower().endswith(".xlsx"):
        return pd.read_excel(upload, header=header_row-1)
    upload.seek(0)
    try:
        return pd.read_csv(upload, header=header_row-1, sep=None, engine="python", encoding="utf-8-sig")
    except UnicodeDecodeError:
        upload.seek(0)
        return pd.read_csv(upload, header=header_row-1, sep=None, engine="python", encoding="latin-1")


def clean_col(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower().translate(str.maketrans("áéíóúñ", "aeioun")))


def guess(cols, key):
    variants={
        "Edad": ["edad","age","anios","anos"],
        "Sexo": ["sexo","sex","genero"],
        "PAS": ["pas","tas","sbp","sistolica","presionsistolica"],
        "PAD": ["pad","tad","dbp","diastolica","presiondiastolica"],
        "VOP": ["vopmedida","cfpwvmedida","cfpwv","vopreal","vopcf","vopcorregida","vop","pwvmedida"],
        "ID": ["identificador","idpaciente","codigo","paciente","id"],
    }[key]
    for name in variants:
        matches = [col for col in cols if clean_col(col)==name]
        if matches:
            return matches[0]
    return None


def make_histogram(result):
    labels = ["Argentina candidata", "Europa sana", "Europa con FR", "Díaz media normativa"]
    values = [result["ePWV_ARG"], result["ePWV_Europa_sana"],
              result["ePWV_Europa_riesgo"], result["Diaz_media_normativa"]]
    fig=go.Figure(go.Bar(y=labels,x=values,orientation="h",marker_color=["#008A80","#5A88B7","#A8794F","#9AA5AE"],
                         text=[f"{v:.2f}" for v in values],textposition="auto"))
    if result["VOP_medida"] is not None:
        fig.add_vline(x=result["VOP_medida"], line_dash="dash", line_color="#B34040",
                      annotation_text="VOP medida")
    fig.update_layout(height=320, margin=dict(l=10,r=10,t=10,b=10),
                      xaxis_title="VOP (m/s)", yaxis_title="",showlegend=False)
    return fig


def show_audit_table(data: pd.DataFrame):
    model_names={"ePWV_ARG":"Argentina candidata", "ePWV_Europa_sana":"Europa sana",
                 "ePWV_Europa_riesgo":"Europa factores de riesgo"}
    rows=[]
    for col, name in model_names.items():
        m=metrics(data["VOP_medida"], data[col])
        rows.append({"Modelo":name,**m})
    st.dataframe(pd.DataFrame(rows).round(3), hide_index=True, use_container_width=True)
    return rows


st.markdown('<div class="smallcap">UNIDAD DE MECÁNICA VASCULAR · HERRAMIENTA DE INVESTIGACIÓN</div>', unsafe_allow_html=True)
st.title("🫀 VOP ARG · Estimación y validación")
st.caption("Modelo argentino candidato (2026) + ecuaciones europeas + percentiles de Díaz y cols. (2018)")
st.warning("**Uso de investigación:** modelo argentino con validación interna solamente. No diagnostica rigidez arterial ni reemplaza la VOP carótido-femoral tonométrica.",icon="⚠️")

with st.sidebar:
    st.header("Parámetros del proyecto")
    st.info("**ePWV Argentina:** edad, sexo y PAM con factor 0,4.\n\n**Díaz (2018):** referencia normativa basada en edad y sexo.")
    st.caption("Muestra exploratoria documentada: n=1.772 registros; 9–87 años. Deben verificarse sujetos independientes.")
    st.metric("RMSE CV interna", "1,031 m/s")
    st.metric("MAE CV interna", "0,762 m/s")
    st.metric("R² CV interna", "0,595")
    st.caption("Estos números son resultados históricos del informe; no se recalculan desde los datos cargados.")
    st.markdown("---")
    st.caption(MODEL_VERSION)

tab_ind, tab_lotes, tab_pat, tab_conf, tab_val, tab_met = st.tabs([
    "🧮 Paciente", "📂 Carga masiva", "🧬 EVA · Saludable · SUPERNOVA",
    "🔬 Auditoría técnica P90/P95", "📊 Validación", "📚 Metodología"])

with tab_ind:
    st.subheader("Cálculo individual")
    with st.form("individual"):
        a,b,c,d=st.columns(4)
        edad=a.number_input("Edad (años)",min_value=9,max_value=87,value=55,step=1)
        sexo=b.selectbox("Sexo utilizado por el modelo",["Masculino","Femenino"])
        pas=c.number_input("PAS (mmHg)",min_value=70,max_value=260,value=125,step=1)
        pad=d.number_input("PAD (mmHg)",min_value=50,max_value=180,value=75,step=1)
        x,y=st.columns([2,1])
        identifier=x.text_input("Código anónimo del registro (opcional)", value="")
        measured_on=y.checkbox("Tengo VOP cf medida",value=False)
        vop=st.number_input("VOP cf tonométrica (m/s)",min_value=2.0,max_value=30.0,value=7.5,step=0.1) if measured_on else None
        run=st.form_submit_button("Calcular y comparar",type="primary",use_container_width=True)
    if run:
        try:
            st.session_state["individual_result"]=calculate(edad,sexo,pas,pad,vop,identifier)
        except ValueError as err:
            st.error(str(err)); st.session_state.pop("individual_result",None)
    result=st.session_state.get("individual_result")
    if result:
        ca,cb,cc,cd=st.columns(4)
        ca.metric("PAM (0,4)",f'{result["PAM_0_4"]:.1f} mmHg')
        cb.metric("ePWV argentina",f'{result["ePWV_ARG"]:.2f} m/s')
        cc.metric("ePWV europea sana",f'{result["ePWV_Europa_sana"]:.2f} m/s')
        cd.metric("ePWV europea con FR",f'{result["ePWV_Europa_riesgo"]:.2f} m/s')
        st.plotly_chart(make_histogram(result),use_container_width=True)
        st.markdown("#### Intervalo normativo argentino de Díaz (2018)")
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Media de referencia",f'{result["Diaz_media_normativa"]:.2f} m/s')
        m2.metric("DE de referencia",f'{result["Diaz_DE_normativa"]:.2f} m/s')
        m3.metric("P90",f'{result["Diaz_P90"]:.2f} m/s')
        m4.metric("P95",f'{result["Diaz_P95"]:.2f} m/s')
        if result["VOP_medida"] is not None:
            st.success(f'**VOP medida:** {result["VOP_medida"]:.2f} m/s  ·  **Z de Díaz:** {result["Diaz_Z_VOP_medida"]:+.2f}  ·  **Percentil de la VOP medida:** P{result["Diaz_percentil_VOP_medida"]:.1f}')
            st.caption("El percentil corresponde exclusivamente a la VOP medida; no se asigna percentil normativo clínico a la VOP estimada.")
        else:
            st.info("Sin VOP realmente medida, no se informa percentil de VOP medida ni error individual.")
        st.markdown('#### Envejecimiento vascular (clasificación EVA / SUPERNOVA)')
        if result['Fenotipo_VOP_medida'] is not None:
            st.info(f'**Fenotipo por VOP realmente MEDIDA:** {result["Fenotipo_VOP_medida"]} (P10/P90 de Díaz por edad/sexo).')
        else:
            st.warning('**No evaluable:** el fenotipo vascular del paciente requiere VOP cf medida. Las ecuaciones estimadas no determinan EVA, saludable o SUPERNOVA clínica.')
        st.caption('Las estimaciones argentina y europeas se comparan entre sí como simulaciones numéricas. Abra «EVA · Saludable · SUPERNOVA» para comparar fenotipos referenciales y discordancias con la tonometría.')
        st.markdown(f'**Contraste estimado entre modelos:** {result["Concordancia_3_estimados"]} | **Comparación con medición:** {result["Concordancia_medida_estimados"]}.')
        st.download_button("⬇️ Informe PDF individual",patient_pdf(result),
                           file_name="VOP_ARG_informe_exploratorio.pdf",mime="application/pdf")

with tab_lotes:
    st.subheader("Cargar CSV / Excel y calcular todas las fórmulas")
    st.caption("No se publica ni se guarda automáticamente ningún archivo. En una instancia pública de Streamlit, el procesamiento ocurre en el servidor remoto: utilice códigos anónimos, nunca datos identificatorios de pacientes.")
    upload=st.file_uploader("Archivo de investigación (.csv, .xlsx)",type=["csv","xlsx"],key="bulk")
    if upload:
        row=st.number_input("Número de fila que contiene encabezados",1,20,1,help="En el Excel original de Tandil los encabezados están en la fila 2.")
        try:
            source=read_table(upload,int(row))
            if source.empty:
                st.error("No se detectaron registros.")
            else:
                st.caption(f"{len(source):,} registros · {len(source.columns)} columnas detectadas")
                with st.expander("Vista de origen",expanded=False):
                    st.dataframe(source.head(10),use_container_width=True)
                cols=list(source.columns)
                opts=[None]+cols
                columns=st.columns(3)
                mapping={}
                for j,key in enumerate(["Edad","Sexo","PAS","PAD","VOP","ID"]):
                    g=guess(cols,key)
                    mapping[key]=columns[j%3].selectbox(f"Columna {key}",opts,index=opts.index(g) if g is not None else 0,
                                                       format_func=lambda x:"(no disponible)" if x is None else str(x),key=f"map_{key}")
                if st.button("Procesar registros",type="primary"):
                    if any(mapping[k] is None for k in ("Edad","Sexo","PAS","PAD")):
                        st.error("Seleccione Edad, Sexo, PAS y PAD.")
                    else:
                        ok,bad=analyze_rows(source,mapping)
                        st.session_state["batch_ok"]=ok
                        st.session_state["batch_bad"]=bad
                        st.session_state["batch_source_name"]=upload.name
        except Exception as e:
            st.error(f"No pudo leerse el archivo: {e}")
    res=st.session_state.get("batch_ok")
    if isinstance(res,pd.DataFrame):
        bad=st.session_state.get("batch_bad",pd.DataFrame())
        s1,s2=st.columns(2)
        s1.metric("Registros procesados",len(res))
        s2.metric("Registros rechazados",len(bad))
        if not res.empty:
            st.dataframe(res.round(3),use_container_width=True,hide_index=True)
            st.download_button("⬇️ Descargar resultados CSV",csv_data(res),file_name="VOP_ARG_resultados.csv",mime="text/csv")
            if res["VOP_medida"].notna().any():
                st.info("Hay registros con VOP realmente medida. Abra la pestaña Validación para comparar errores.")
        if not bad.empty:
            with st.expander("Registros rechazados y motivos"):
                st.dataframe(bad,hide_index=True,use_container_width=True)
                st.download_button("⬇️ Descargar rechazos CSV",csv_data(bad),file_name="VOP_ARG_rechazados.csv",mime="text/csv")


with tab_pat:
    render_aging()

with tab_conf:
    render_concordance()

with tab_val:
    st.subheader("Validación empírica con VOP cf medida")
    data=st.session_state.get("batch_ok")
    if not isinstance(data,pd.DataFrame) or data.empty:
        st.info("Primero cargue un CSV/XLSX con edad, sexo, PAS, PAD y VOP cf medida en «Carga masiva».")
    else:
        data=data.dropna(subset=["VOP_medida"]).copy()
        if len(data)<2:
            st.info("Se requieren al menos 2 registros con VOP medida para calcular métricas.")
        else:
            st.caption(f"Muestra pareada disponible: {len(data)} registros. Las métricas siguientes se calculan en vivo sobre SU archivo y no sustituyen validación externa independiente.")
            age_range=st.slider("Rango etario",9,87,(9,87))
            sex_filter=st.multiselect("Sexo",["Masculino","Femenino"],default=["Masculino","Femenino"])
            subset=data[data["Edad"].between(*age_range)&data["Sexo"].isin(sex_filter)].copy()
            if len(subset)>=2:
                show_audit_table(subset)
                model=st.selectbox("Modelo para gráficos",["Argentina candidata","Europa sana","Europa factores de riesgo"])
                field={"Argentina candidata":"ePWV_ARG","Europa sana":"ePWV_Europa_sana","Europa factores de riesgo":"ePWV_Europa_riesgo"}[model]
                c1,c2=st.columns(2)
                with c1:
                    f=px.scatter(subset,x="VOP_medida",y=field,color="Sexo",hover_data=["Edad"],
                                 labels={"VOP_medida":"VOP cf medida (m/s)",field:"VOP estimada (m/s)"},
                                 title="Concordancia individual")
                    low=float(min(subset["VOP_medida"].min(),subset[field].min()))
                    high=float(max(subset["VOP_medida"].max(),subset[field].max()))
                    f.add_shape(type="line",x0=low,y0=low,x1=high,y1=high,
                                line=dict(color="gray",dash="dash"))
                    st.plotly_chart(f,use_container_width=True)
                with c2:
                    tmp=subset.assign(Promedio=(subset[field]+subset["VOP_medida"])/2,
                                      Diferencia=subset[field]-subset["VOP_medida"])
                    f=px.scatter(tmp,x="Promedio",y="Diferencia",color="Sexo",title="Bland–Altman (estimada − medida)")
                    m=metrics(tmp["VOP_medida"],tmp[field])
                    for val,color,label in [(m["Sesgo (m/s)"],"#008A80","sesgo"),
                                            (m["LoA inferior (m/s)"],"#D88E45","LoA inf"),
                                            (m["LoA superior (m/s)"],"#D88E45","LoA sup")]:
                        f.add_hline(y=val,line_dash="dash",line_color=color,annotation_text=label)
                    f.update_layout(xaxis_title="Media de medición y estimación (m/s)",yaxis_title="Diferencia (m/s)")
                    st.plotly_chart(f,use_container_width=True)
                error=subset[field]-subset["VOP_medida"]
                f=px.scatter(x=subset["Edad"],y=error,color=subset["Sexo"],
                             labels={"x":"Edad (años)","y":"Estimación − medición (m/s)","color":"Sexo"},
                             title="Sesgo por edad")
                f.add_hline(y=0,line_color="#555555")
                st.plotly_chart(f,use_container_width=True)
                st.markdown("#### Desempeño por grupo etario")
                frames=[]
                for label,lo,hi in AGE_BANDS:
                    group=subset[(subset["Edad"]>=lo)&(subset["Edad"]<hi)]
                    if len(group)>=2:
                        frames.append({"Edad":label,**metrics(group["VOP_medida"],group[field])})
                if frames:
                    st.dataframe(pd.DataFrame(frames).round(3),hide_index=True,use_container_width=True)
            else:
                st.info("No hay pares suficientes en el rango seleccionado.")

with tab_met:
    st.subheader("Ecuaciones, origen y límites de interpretación")
    st.latex(r"PAM=PAD+0.4(PAS-PAD)")
    st.latex(r"\widehat{VOP}_{ARG}=0.180526+0.916427\log_{10}(edad)+0.010667\,edad+0.000396061\,edad^2+0.133136\,sexo_M+0.043184\,PAM")
    st.markdown("**Ecuación europea (sujetos sanos):**")
    st.latex(r"ePWV=4.62-0.13\,edad+0.0018\,edad^2+0.0006\,edad\,PAM+0.0284\,PAM")
    st.markdown("**Ecuación europea (factores de riesgo):**")
    st.latex(r"ePWV=9.587-0.402\,edad+0.004560\,edad^2-2.621\cdot10^{-5}\,edad^2\,PAM+3.176\cdot10^{-3}\,edad\,PAM-0.01832\,PAM")
    st.markdown("**Díaz y cols.:** referencias de media y DE por edad y sexo. Percentil exclusivamente sobre VOP medida: Z = (VOP medida − media Díaz) / DE Díaz.")
    st.markdown("""**Fenotipos de ENVEJECIMIENTO vascular, no simples bandas de rigidez**
- **SUPERNOVA:** VOP medida <P10 (análisis principal) para edad y sexo de Díaz (2018).
- **Saludable/esperado referencial:** desde P10 hasta menos de P90, por VOP **medida**. La etiqueta no implica ausencia de enfermedad cardiovascular ni reemplaza una evaluación de HVA multidimensional.
- **EVA:** VOP **medida** ≥P90; posición extrema superior compatible con envejecimiento vascular acelerado referencial.
- **Sensibilidad P5/P95:** otra especificación seleccionable; todavía no existen umbrales universales de EVA/SUPERNOVA.
- **Sin VOP medida:** fenotipo real **NO EVALUABLE**. Las fórmulas europea y argentina solo ofrecen comparaciones numéricas teóricas, NUNCA diagnósticos con ePWV.
- **Concordancia:** acuerdo de categorías en tres modelos, kappa categórica y matrices frente al fenotipo VOP medido cuando está disponible; no prueba que un modelo prediga riesgo clínico.
- **Comparación previa de P50–P95:** conservada solo como herramienta interna de auditoría de umbrales, no como definición de EVA/SUPERNOVA.
""")
    st.markdown("""**Limitaciones científicas**
- El modelo argentino es **candidato**: coeficientes tomados del informe metodológico (octubre de 2026), no hay validación externa ni calibración prospectiva.
- Muestra de desarrollo aparentemente sana: extrapolación a hipertensión, diabetes o enfermedad cardiovascular no demostrada.
- No se ha confirmado la independencia entre los registros originales de Tandil.
- En ≥70 años el error observado en la validación interna fue considerable; no emplear para decisiones individuales.
- El RMSE histórico de validación interna **no equivale** a precisión garantizada para un nuevo paciente.
- El percentil de Díaz describe una distribución normativa, **no** la incertidumbre individual de ePWV.
- Validar conversiones de distancia, medición y unidades antes de comparar distintas cohortes.
""")
    st.caption("Referencias: " + REFERENCE)
    st.caption("Cálculos disponibles para auditoría científica. Herramienta sin historiales, accesos ni base de datos de pacientes en el código fuente.")
