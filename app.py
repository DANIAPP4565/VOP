import io
from xml.sax.saxutils import escape
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from engine import calculate, metrics
from patterns import evaluate_patterns, MODELS, BAND_ORDER
from concordance_ui import render as render_concordance

st.set_page_config(page_title="VOP ARG | Mecánica Vascular",page_icon="🫀",layout="wide")
st.title("🫀 VOP ARG · Estimación y validación")
st.caption("Modelo candidato argentino (2026) · ecuaciones europeas · referencias de Díaz et al. (2018)")
st.warning("Herramienta de investigación, sin validación externa. No reemplaza la VOP cf medida ni establece diagnósticos.")
tabs=st.tabs(["🧮 Paciente","📂 Base de datos","🧬 Patrones por modelos","🔬 Rigidez medida y concordancia","📊 Validación","📚 Metodología"])
def pdf_report(r):
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=A4); styles=getSampleStyleSheet()
    story=[Paragraph("VOP ARG - Informe exploratorio",styles['Title']),Spacer(1,16),
       Paragraph("Sin validación externa. No sustituye tonometría ni diagnóstico clínico.",styles['BodyText']),Spacer(1,14)]
    for k,v in r.items():
        if v is not None: story.append(Paragraph(escape(f"{k}: {v:.3f}" if isinstance(v,(int,float)) else f"{k}: {v}"), styles["BodyText"]))
    story += [Spacer(1,16),Paragraph("Díaz et al. J Clin Hypertens. 2018;20:659-671; doi:10.1111/jch.13251",styles["BodyText"])]
    story.append(Spacer(1,12));story.append(Paragraph("Advertencia: para ePWV, las bandas se basan en un contraste numérico con umbrales de VOP medida de Díaz. No representan percentiles de ePWV validados ni diagnósticos.",styles["BodyText"]))
    doc.build(story);return out.getvalue()

with tabs[0]:
    with st.form('calc'):
        c1,c2,c3,c4=st.columns(4)
        age=c1.number_input("Edad",9,87,55)
        sex=c2.selectbox("Sexo",['Masculino','Femenino'])
        pas=c3.number_input("PAS",70,260,125)
        pad=c4.number_input("PAD",50,180,75)
        measured=st.checkbox("Incluir VOP cf realmente medida")
        vop=st.number_input("VOP medida (m/s)",2.0,30.0,7.5) if measured else None
        submit=st.form_submit_button("Calcular",type="primary")
    if submit:
        try: st.session_state['result']=calculate(age,sex,pas,pad,vop)
        except ValueError as e: st.error(str(e));st.session_state.pop('result',None)
    r=st.session_state.get('result')
    if r:
        a,b,c,d=st.columns(4)
        a.metric("PAM (factor 0,4)",f"{r['PAM']:.1f} mmHg")
        b.metric("ePWV argentina",f"{r['ePWV_ARG']:.2f} m/s")
        c.metric("ePWV Europa sana",f"{r['ePWV_Europa_sana']:.2f} m/s")
        d.metric("ePWV Europa FR",f"{r['ePWV_Europa_riesgo']:.2f} m/s")
        fig=px.bar(pd.DataFrame({'Modelo':['Argentina candidata','Europa sana','Europa FR','Díaz media (normativa)'],
          'VOP':[r['ePWV_ARG'],r['ePWV_Europa_sana'],r['ePWV_Europa_riesgo'],r['Diaz_media']]}),
          x='VOP',y='Modelo',orientation='h',title='Comparación (m/s)')
        if vop is not None: fig.add_vline(x=r['VOP_medida'],line_dash='dash',annotation_text='VOP medida')
        st.plotly_chart(fig,use_container_width=True)
        a,b,c=st.columns(3)
        a.metric("Media Díaz",f"{r['Diaz_media']:.2f} m/s")
        b.metric("P90 Díaz",f"{r['Diaz_P90']:.2f} m/s")
        c.metric("P95 Díaz",f"{r['Diaz_P95']:.2f} m/s")
        if r['VOP_medida'] is not None:
            st.info(f"Percentil de VOP MEDIDA: P{r['Percentil_medida']:.1f} | Z {r['Z_medida']:.2f} | Error argentina {r['Error_ARG']:+.2f} m/s")
        else: st.info("Percentil de VOP medida no disponible sin tonometría.")
        st.markdown("#### Patrones de rigidez referencial por ecuación")
        st.caption("Las bandas de ePWV representan una comparación NUMÉRICA con valores de VOP MEDIDA de Díaz; no son percentiles clínicos de ePWV ni un diagnóstico.")
        rows=[{"Fuente":lab,"VOP (m/s)":r[key],"Banda vs Díaz":r[band]}
              for key,lab,band in MODELS]
        if r["VOP_medida"] is not None:
            rows.append({"Fuente":"VOP cf realmente medida","VOP (m/s)":r["VOP_medida"],"Banda vs Díaz":r["Banda_VOP_medida_Diaz"]})
        st.dataframe(pd.DataFrame(rows).round(2),hide_index=True,use_container_width=True)
        k1,k2,k3=st.columns(3)
        k1.metric("Europa sana – Argentina",f'{r["Delta_Europa_sana_menos_ARG_m_s"]:+.2f} m/s')
        k2.metric("Europa FR – Argentina",f'{r["Delta_Europa_riesgo_menos_ARG_m_s"]:+.2f} m/s')
        k3.metric("Amplitud de 3 modelos",f'{r["Amplitud_entre_modelos_m_s"]:.2f} m/s')
        if r["VOP_medida"] is not None:
            st.info(f'Patrón medido: **{r["Banda_VOP_medida_Diaz"]}**. **{r["Patron_ajuste_con_medida"]}**. Modelo más próximo: {r["Modelo_mas_cercano_medida"]}.')
        else:
            st.info("No se puede determinar patrón de rigidez medido sin tonometría.")
        st.download_button('Informe PDF individual',pdf_report(r),file_name='vop_arg_informe.pdf',mime='application/pdf')
with tabs[1]:
    st.subheader("Carga de CSV / XLSX")
    st.caption("Procesamiento en servidor Streamlit; NO subir nombres, DNI ni información clínica identificable a servidores públicos.")
    f=st.file_uploader("Seleccionar archivo",type=['csv','xlsx'])
    if f:
        hdr=st.number_input("Fila con encabezados",1,20,1)
        try:
            if f.name.lower().endswith('xlsx'):
                df=pd.read_excel(f,header=hdr-1)
            else:
                try: df=pd.read_csv(f,sep=None,engine='python',header=hdr-1,encoding='utf-8-sig')
                except UnicodeDecodeError:
                    f.seek(0);df=pd.read_csv(f,sep=None,engine='python',header=hdr-1,encoding='latin-1')
            st.caption(f"{len(df)} registros")
            cols=[None]+list(df.columns)
            guesses={'Edad':['edad','age'],'Sexo':['sexo','sex'],'PAS':['pas','sistolica','sbp'],
                     'PAD':['pad','diastolica','dbp'],'VOP':['vop','vopmedida','cfpwv','cfpwvmedida']}
            mapping={}
            c=st.columns(5)
            for n,key in enumerate(guesses):
                default=next((col for col in df if str(col).lower().strip().replace(' ','') in guesses[key]),None)
                mapping[key]=c[n].selectbox(key,cols,index=cols.index(default) if default is not None else 0,
                      format_func=lambda v:"Sin asignar" if v is None else str(v))
            if st.button("Procesar",type="primary"):
                results=[]; errors=[]
                if any(mapping[k] is None for k in ['Edad','Sexo','PAS','PAD']):
                    st.error('Debe asignar Edad, Sexo, PAS y PAD')
                else:
                    for i,row in df.iterrows():
                        try:
                            def num(k):
                                v=row[mapping[k]]
                                return float(v.replace(',','.') if isinstance(v,str) else v)
                            mv=num('VOP') if mapping['VOP'] is not None and pd.notna(row[mapping['VOP']]) else None
                            results.append({'Fila':i+1,**calculate(num('Edad'),row[mapping['Sexo']],num('PAS'),num('PAD'),mv)})
                        except Exception as e: errors.append({'Fila':i+1,'Motivo':str(e)})
                    st.session_state['batch']=pd.DataFrame(results)
                    st.session_state['bad']=pd.DataFrame(errors)
        except Exception as e: st.error(f"No se pudo leer la base: {e}")
    if 'batch' in st.session_state:
        data=st.session_state['batch'];bad=st.session_state.get('bad',pd.DataFrame())
        st.metric("Registros válidos",len(data));st.caption(f"Rechazados: {len(bad)}")
        if not data.empty:
            st.dataframe(data.round(3),use_container_width=True)
            st.download_button('Resultados CSV',data.to_csv(index=False,sep=';',decimal=',').encode('utf-8-sig'),'resultados_vop_arg.csv')
        if not bad.empty: st.dataframe(bad,use_container_width=True)
with tabs[2]:
    st.subheader("Patrones de rigidez vascular referencial por modelos")
    st.warning("La clasificación de VOP cf MEDIDA utiliza referencias de Díaz por edad/sexo. Aplicar bandas normativas de VOP medida a ePWV estimadas es un CONTRASTE DESCRIPTIVO, sin validación clínica.")
    st.markdown("Bandas: **<P50**, **P50–<P90**, **P90–<P95**, **≥P95**. P50 corresponde aproximadamente a la media de Díaz (modelo normal).")
    margin=st.slider("Margen de discrepancia exploratorio (m/s). No es punto de corte clínico.",0.0,3.0,1.0,0.1)
    result=st.session_state.get("result")
    if result:
        p=evaluate_patterns(result,tolerance=margin)
        st.markdown("#### Patrón individual")
        st.info(f'Argentina: **{p["Banda_ARG_vs_Diaz"]}** | Europa sana: **{p["Banda_Europa_sana_vs_Diaz"]}** | Europa con factores: **{p["Banda_Europa_riesgo_vs_Diaz"]}** — {p["Patron_modelos"]}.')
        st.write(f'Europa sana – Argentina: **{p["Delta_Europa_sana_menos_ARG_m_s"]:+.2f} m/s**; Europa FR – Argentina: **{p["Delta_Europa_riesgo_menos_ARG_m_s"]:+.2f} m/s**; dispersión máxima: **{p["Amplitud_entre_modelos_m_s"]:.2f} m/s**.')
        if p["Discrepancia_supera_margen"]:
            st.warning("Las estimaciones difieren más que el margen descriptivo seleccionado.")
        else:
            st.success("Las estimaciones están dentro del margen descriptivo seleccionado.")
        if result.get("VOP_medida") is not None:
            st.info(f'Medida: **{p["Banda_VOP_medida_Diaz"]}**. {p["Patron_ajuste_con_medida"]}.')
    data=st.session_state.get("batch")
    if not isinstance(data,pd.DataFrame) or data.empty:
        st.info("Cargue una base para estudiar distribución de patrones y diferencias según edad.")
    else:
        st.markdown("#### Bandas por modelo en la cohorte cargada")
        counts=[]
        names=[("Banda_ARG_vs_Diaz","Argentina"),("Banda_Europa_sana_vs_Diaz","Europa sana"),
               ("Banda_Europa_riesgo_vs_Diaz","Europa con FR")]
        for field,label in names:
            for band in BAND_ORDER:
                counts.append({"Modelo":label,"Banda":band,"N":int((data[field]==band).sum())})
        fig=px.bar(pd.DataFrame(counts),x="Modelo",y="N",color="Banda",
                   category_orders={"Banda":list(BAND_ORDER)},barmode="stack",
                   title="Posición numérica de las estimaciones respecto a referencias medidas")
        st.plotly_chart(fig,use_container_width=True)
        c1,c2,c3=st.columns(3)
        c1.metric("Bandas discordantes",str(int((data["Patron_modelos"]=="Bandas discordantes").sum())))
        c2.metric(f"Amplitud >{margin:.1f} m/s",f'{(data["Amplitud_entre_modelos_m_s"]>margin).mean()*100:.1f}%')
        c3.metric("Amplitud mediana",f'{data["Amplitud_entre_modelos_m_s"].median():.2f} m/s')
        diffs=pd.concat([
            data[["Edad","Delta_Europa_sana_menos_ARG_m_s"]].rename(columns={"Delta_Europa_sana_menos_ARG_m_s":"Diferencia"}).assign(Contraste="Europa sana – Argentina"),
            data[["Edad","Delta_Europa_riesgo_menos_ARG_m_s"]].rename(columns={"Delta_Europa_riesgo_menos_ARG_m_s":"Diferencia"}).assign(Contraste="Europa FR – Argentina"),
        ],ignore_index=True)
        fig=px.scatter(diffs,x="Edad",y="Diferencia",color="Contraste",opacity=0.4,
                       title="Diferencias de estimación por edad (m/s)")
        fig.add_hline(y=0,line_color="#888888")
        st.plotly_chart(fig,use_container_width=True)
        bands=[]
        for lab,lo,hi in [("9–20",9,21),("21–39",21,40),("40–59",40,60),("60–69",60,70),("≥70",70,88)]:
            part=data[(data["Edad"]>=lo)&(data["Edad"]<hi)]
            if len(part):
                bands.append({"Edad":lab,"N":len(part),
                    "Delta sana – ARG (m/s)":part["Delta_Europa_sana_menos_ARG_m_s"].mean(),
                    "Delta FR – ARG (m/s)":part["Delta_Europa_riesgo_menos_ARG_m_s"].mean(),
                    "Bandas discordantes (%)":100*(part["Patron_modelos"]=="Bandas discordantes").mean()})
        st.dataframe(pd.DataFrame(bands).round(2),hide_index=True,use_container_width=True)
        paired=data.dropna(subset=["VOP_medida"])
        if not paired.empty:
            st.markdown("#### Con VOP medida: concordancia frente a referencia real")
            st.dataframe(paired["Patron_ajuste_con_medida"].value_counts().rename_axis("Patrón").reset_index(name="N"),
                         hide_index=True,use_container_width=True)
            for field,label in names:
                with st.expander("Tabla cruzada de bandas: medida vs " + label):
                    ct=pd.crosstab(pd.Categorical(paired["Banda_VOP_medida_Diaz"],categories=BAND_ORDER),
                        pd.Categorical(paired[field],categories=BAND_ORDER),dropna=False)
                    ct.index.name="VOP medida";ct.columns.name="Modelo estimado"
                    st.dataframe(ct,use_container_width=True)
        st.caption("Ninguna banda de estimación se debe interpretar como diagnóstico. Las discrepancias se computan como Europa menos Argentina.")
with tabs[4]:
    st.subheader("Validación con VOP medida")
    if 'batch' not in st.session_state: st.info('Cargue una base con VOP medida en la pestaña anterior.')
    else:
        data=st.session_state['batch'].dropna(subset=['VOP_medida'])
        if len(data)<2:st.info('Se necesitan al menos 2 pares medido/estimado.')
        else:
            lo,hi=st.slider('Edad',9,87,(9,87))
            sub=data[data.Edad.between(lo,hi)]
            if len(sub)>=2:
                rows=[]
                for key,lab in [('ePWV_ARG','Argentina'),('ePWV_Europa_sana','Europa sana'),('ePWV_Europa_riesgo','Europa FR')]:
                    rows.append({'Modelo':lab,**metrics(sub.VOP_medida,sub[key])})
                st.dataframe(pd.DataFrame(rows).round(3),hide_index=True,use_container_width=True)
                field=st.selectbox('Modelo',['ePWV_ARG','ePWV_Europa_sana','ePWV_Europa_riesgo'])
                c1,c2=st.columns(2)
                fig=px.scatter(sub,x='VOP_medida',y=field,color='Sexo',title='Estimada vs medida')
                low=min(sub.VOP_medida.min(),sub[field].min());high=max(sub.VOP_medida.max(),sub[field].max())
                fig.add_shape(type='line',x0=low,y0=low,x1=high,y1=high,line=dict(color='grey',dash='dash'))
                c1.plotly_chart(fig,use_container_width=True)
                plot=sub.assign(Promedio=(sub.VOP_medida+sub[field])/2,Diferencia=sub[field]-sub.VOP_medida)
                fig=px.scatter(plot,x='Promedio',y='Diferencia',color='Sexo',title='Bland–Altman')
                m=metrics(sub.VOP_medida,sub[field])
                for y in (m['Sesgo'],m['LoA_inf'],m['LoA_sup']):fig.add_hline(y=y,line_dash='dash')
                c2.plotly_chart(fig,use_container_width=True)
                st.plotly_chart(px.scatter(plot,x='Edad',y='Diferencia',title='Sesgo por edad'),use_container_width=True)
            else:st.info('Rango etario sin pares suficientes.')
with tabs[5]:
    st.subheader('Fundamento científico y limitaciones')
    st.latex(r'PAM = PAD + 0.4(PAS-PAD)')
    st.latex(r'ePWV_{ARG}=0.180526+0.916427\log_{10}(edad)+0.010667edad+0.000396061edad^2+0.133136sexo_M+0.043184PAM')
    st.markdown('**ePWV argentina candidata:** ajuste Ridge (alpha=10); validación cruzada interna de 10 particiones, RMSE 1,031 m/s, MAE 0,762 m/s, R² 0,595 documentados previamente.')
    st.markdown('**Referencias de Díaz:** percentiles de VOP cf **medida**, calculados por media y DE según edad y sexo; no son predicciones de ePWV individual.')
    st.warning('No hay validación externa, no se ha confirmado que 1.772 registros representen personas independientes. El error es mayor en mayores de 70 años. No utilizar para diagnóstico o decisiones clínicas independientes.')
    st.markdown("**Taxonomía exploratoria de patrones:** se comparan las tres estimaciones con P50, P90 y P95 de Díaz (medida real) para misma edad y sexo. Solo la VOP TONOMÉTRICA se interpreta normativamente. Concordancia de bandas estimadas no prueba rigidez real, y el margen de dispersión 1 m/s es arbitrario.")
    st.caption('Díaz A, Zócalo Y, Bia D et al. J Clin Hypertens. 2018;20:659–671. DOI: 10.1111/jch.13251.')

with tabs[3]:
    render_concordance()
