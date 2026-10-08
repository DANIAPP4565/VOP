"""Pantalla principal de fenotipos EVA / Saludable / SUPERNOVA.

Importante: solo la cfPWV realmente MEDIDA recibe etiqueta normativa. En ePWV
calculamos posición TEÓRICA numérica, explícitamente marcada no validada.
"""
from __future__ import annotations
from io import BytesIO
from xml.sax.saxutils import escape
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib import colors
from aging import PHENOTYPES,MODEL_FIELDS,case_aging,evaluate_cohort


def _csv(df):
    return df.to_csv(index=False,sep=';',decimal=',').encode('utf-8-sig')


def _phenotype_pdf(r, analysis):
    b=BytesIO()
    d=SimpleDocTemplate(b,pagesize=A4,leftMargin=40,rightMargin=40)
    styles=getSampleStyleSheet()
    items=[Paragraph('VOP ARG | Fenotipos de envejecimiento vascular',styles['Title']),Spacer(1,12),
        Paragraph('<b>Investigación – no validado para diagnóstico. Solo se asigna fenotipo referencial real cuando existe VOP cf tonométrica.</b>',styles['BodyText']),Spacer(1,14)]
    fields=[('Edad, sexo',f'{r["Edad"]:.0f} años, {r["Sexo"]}'),
            ('Presión arterial',f'{r["PAS"]:.0f}/{r["PAD"]:.0f} mmHg'),
            ('Umbral SUPERNOVA',f'< P{analysis["Criterio_EVA"].split("/")[0][1:]} = {analysis["Umbral_SUPERNOVA_m_s"]:.2f} m/s'),
            ('Umbral EVA',f'≥ P{analysis["Criterio_EVA"].split("/")[1][1:]} = {analysis["Umbral_EVA_m_s"]:.2f} m/s'),
            ('VOP realmente medida',f'{r["VOP_medida"]:.2f} m/s' if r['VOP_medida'] is not None else 'No disponible'),
            ('Fenotipo medido',analysis['Fenotipo_VOP_medida'] or 'NO EVALUABLE (sin VOP medida)'),
            ('Concordancia simulada',analysis['Concordancia_3_estimados']),
            ('Concordancia con medida',analysis['Concordancia_medida_estimados'])]
    for key,(field,label) in MODEL_FIELDS.items():
        fields.append((label+' (ESTIMACIÓN)',f'{r[field]:.2f} m/s; categoría teórica NO VALIDADA: {analysis[f"Fenotipo_teorico_{key}"]}'))
    t=Table([[Paragraph('<b>Campo</b>',styles['BodyText']),Paragraph('<b>Valor</b>',styles['BodyText'])]]+[
        [Paragraph(escape(k),styles['BodyText']),Paragraph(escape(str(v)),styles['BodyText'])] for k,v in fields],colWidths=[170,340],repeatRows=1)
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.whitesmoke,colors.white]),
                         ('LINEBELOW',(0,0),(-1,0),.8,colors.HexColor('#008A80')),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    items.extend([t,Spacer(1,12),Paragraph(
        'Criterios operativos exploratorios: valor medido &lt;P10 SUPERNOVA; desde P10 hasta &lt;P90 Saludable/esperado; ≥P90 EVA. '
        'Existe variación de criterios en la literatura; no se deduce riesgo individual ni edad biológica vascular por esta clasificación. '
        'Referencias normativas: Díaz et al. (2018), J Clin Hypertens, doi:10.1111/jch.13251. '
        'Fenotipos EVA y SUPERNOVA: Bruno y cols., Hypertension (2020).',styles['BodyText'])])
    d.build(items)
    return b.getvalue()


def render():
    st.subheader('Fenotipos de envejecimiento vascular · EVA / Saludable / SUPERNOVA')
    st.markdown('''**Clasificación corregida:** a partir de referencias argentinas de **VOP carótido-femoral medida**, ajustadas por edad y sexo (Díaz 2018):

- **SUPERNOVA (envejecimiento vascular supernormal):** VOP medida **<P10**.
- **Saludable / esperado (categoría referencial):** VOP medida **≥P10 y <P90**.
- **EVA (envejecimiento vascular acelerado):** VOP medida **≥P90**.

La denominación «saludable» indica una **posición en una distribución de referencia**; no demuestra ausencia de enfermedad ni equivale por sí sola a una definición clínica integral de HVA.''')
    st.warning('**Sin VOP medida NO asignamos EVA, saludable ni SUPERNOVA al paciente.** Para las tres ecuaciones ePWV se muestra únicamente la **categoría teórica NO VALIDADA** que resultaría de comparar sus valores con percentiles de VOP medida.')
    use_alt=st.toggle('Análisis de sensibilidad: utilizar P5/P95 en lugar de P10/P90',value=False,key='aging_alt')
    lo,hi=(5,95) if use_alt else (10,90)
    st.caption(f'Protocolo seleccionado: P{lo}/P{hi}. Elección exploratoria, sin umbrales universales aceptados. Cambiarlo NO altera las estimaciones de ePWV.')

    r=st.session_state.get('individual_result')
    if r:
        a=case_aging(r,lo,hi)
        st.markdown('### Fenotipo del paciente')
        cols=st.columns(4)
        cols[0].metric('VOP realmente medida',f'{r["VOP_medida"]:.2f} m/s' if r['VOP_medida'] is not None else 'No medida')
        cols[1].metric('Umbral SUPERNOVA',f'<{a["Umbral_SUPERNOVA_m_s"]:.2f} m/s')
        cols[2].metric('Umbral EVA',f'≥{a["Umbral_EVA_m_s"]:.2f} m/s')
        cols[3].metric('Fenotipo real referencial',a['Fenotipo_VOP_medida'] or 'No evaluable')
        if a['Fenotipo_VOP_medida']=='EVA':st.error('**EVA referencial** con VOP cf tonométrica. Requiere correlación clínica; no constituye diagnóstico autónomo.')
        elif a['Fenotipo_VOP_medida']=='SUPERNOVA':st.success('**SUPERNOVA referencial**: rigidez inferior al límite bajo para edad y sexo en la población de referencia.')
        elif a['Fenotipo_VOP_medida']:st.info('**Envejecimiento vascular saludable/esperado según VOP medida** (sin inferir ausencia de factores de riesgo).')
        else:st.info('**No evaluable:** ingrese VOP cf tonométrica en la pestaña «Paciente» para definir el fenotipo referencial medido.')
        rows=[{'Origen':'TONOMETRÍA (referencia medida)','VOP m/s':r['VOP_medida'],
               'Categoría':a['Fenotipo_VOP_medida'] or 'NO EVALUABLE','Naturaleza':'Referencial medida'}]
        for key,(col,lab) in MODEL_FIELDS.items():
            rows.append({'Origen':lab,'VOP m/s':r[col],
                        'Categoría':a[f'Fenotipo_teorico_{key}'],'Naturaleza':'TEÓRICA — NO VALIDADA'})
        st.dataframe(pd.DataFrame(rows).round(3),hide_index=True,use_container_width=True)
        fig=go.Figure()
        fig.add_hrect(y0=0,y1=a['Umbral_SUPERNOVA_m_s'],line_width=0,fillcolor='rgba(0,140,100,.14)',annotation_text='SUPERNOVA ref.',annotation_position='top left')
        fig.add_hrect(y0=a['Umbral_SUPERNOVA_m_s'],y1=a['Umbral_EVA_m_s'],line_width=0,fillcolor='rgba(150,160,160,.13)',annotation_text='Esperado ref.',annotation_position='top left')
        ymax=max([a['Umbral_EVA_m_s'],r['ePWV_ARG'],r['ePWV_Europa_sana'],r['ePWV_Europa_riesgo'],r['VOP_medida'] or 0])+1.2
        fig.add_hrect(y0=a['Umbral_EVA_m_s'],y1=ymax,line_width=0,fillcolor='rgba(180,60,50,.12)',annotation_text='EVA ref.',annotation_position='top left')
        if r['VOP_medida'] is not None:
            fig.add_trace(go.Scatter(x=['VOP medida'],y=[r['VOP_medida']],mode='markers',marker=dict(size=17,symbol='diamond'),name='Tonometría real'))
        for key,(col,name) in MODEL_FIELDS.items():
            fig.add_trace(go.Scatter(x=[name],y=[r[col]],mode='markers',marker=dict(size=13,symbol='circle-open'),name=f'{name} (estimación)'))
        fig.update_layout(yaxis_title='VOP (m/s)',xaxis_title='',height=400,showlegend=True,
                          title='Posición respecto de referencias argentinas por edad y sexo (estimaciones = simulación)',margin=dict(l=10,r=10,t=48,b=20))
        st.plotly_chart(fig,use_container_width=True)
        st.markdown(f'**Concordancia entre estimaciones:** {a["Concordancia_3_estimados"]}. **Frente a VOP medida:** {a["Concordancia_medida_estimados"]}.')
        if r['VOP_medida'] is not None:
            st.caption(f'Modelo con menor error ABSOLUTO en este caso: {a["Modelo_menor_error_fenotipo"]}. Esta proximidad individual no demuestra validez ni precisión poblacional.')
        st.download_button('⬇️ Informe EVA / saludable / SUPERNOVA (PDF)',_phenotype_pdf(r,a),file_name='VOP_ARG_fenotipos_EVA_SUPERNOVA.pdf',mime='application/pdf')
    else:
        st.info('Calcule un paciente en la pestaña «Paciente» para mostrar su fenotipo o la ausencia de medición.')

    st.markdown('### Análisis de una cohorte')
    batch=st.session_state.get('batch_ok')
    if not isinstance(batch,pd.DataFrame) or batch.empty:
        st.info('Importe una planilla anónima en «Carga masiva» para analizar prevalencia referencial, concordancia y discordancia.')
        return
    data, summary, matrix, strata=evaluate_cohort(batch,lo,hi)
    measured=data[data['Fenotipo_VOP_medida'].notna()].copy()
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Registros',len(data))
    c2.metric('Con tonometría',len(measured))
    c3.metric('EVA medida',int((measured.Fenotipo_VOP_medida=='EVA').sum()))
    c4.metric('SUPERNOVA medida',int((measured.Fenotipo_VOP_medida=='SUPERNOVA').sum()))
    labels=[('Fenotipo_VOP_medida','VOP medida')]+[(f'Fenotipo_teorico_{k}',lab+' (estimación)') for k,(_,lab) in MODEL_FIELDS.items()]
    plot=[]
    for field,name in labels:
        selected=measured if field=='Fenotipo_VOP_medida' else data
        for cat in PHENOTYPES:
            plot.append({'Fuente':name,'Categoría':cat,'Registros':int((selected[field]==cat).sum()),
                         'N con etiqueta':len(selected)})
    fig=px.bar(pd.DataFrame(plot),x='Fuente',y='Registros',color='Categoría',barmode='stack',
               category_orders={'Categoría':list(PHENOTYPES)},title='Frecuencia por fenotipo (estimaciones solo numéricas, no clínicas)')
    st.plotly_chart(fig,use_container_width=True)
    st.caption('Denominadores distintos: la barra «VOP medida» utiliza solo quienes tienen tonometría; las ePWV usan todos los registros.')
    if not measured.empty:
        st.markdown('#### Concordancia categórica con tonometría (3 fenotipos)')
        st.dataframe(summary.round(2),hide_index=True,use_container_width=True)
        st.markdown('#### Matrices de confusión según modelo — etiqueta referencia medida')
        for name in summary.Modelo:
            with st.expander(name):
                m=matrix[matrix.Modelo==name].pivot(index='Fenotipo medido',columns='Fenotipo estimado (simulado)',values='N')
                m=m.reindex(index=list(PHENOTYPES),columns=list(PHENOTYPES)).fillna(0).astype(int)
                st.dataframe(m,use_container_width=True)
        st.markdown('#### Discordancia por edad y sexo')
        st.dataframe(strata.round(2),hide_index=True,use_container_width=True)
        errors=[]
        for k,(col,lab) in MODEL_FIELDS.items():
            errors.append(measured[['Edad',f'Error_{k}_estimada_menos_medida']].rename(columns={f'Error_{k}_estimada_menos_medida':'Error (m/s)'}).assign(Modelo=lab))
        scatter=px.scatter(pd.concat(errors),x='Edad',y='Error (m/s)',color='Modelo',opacity=.4,
                           title='Error firmado de estimación vs tonometría por edad')
        scatter.add_hline(y=0,line_dash='dash',line_color='gray')
        st.plotly_chart(scatter,use_container_width=True)
        st.caption('Kappa y porcentajes describen acuerdo con el fenotipo referencial de la VOP medida; NO constituyen validación prospectiva de una decisión clínica.')
    else:
        st.info('No hay mediciones reales: no se calculan matrices contra tonometría ni se reportan EVA/SUPERNOVA reales.')
        st.dataframe(strata.round(2),hide_index=True,use_container_width=True)
    c1,c2,c3=st.columns(3)
    c1.download_button('Resultados individuales (CSV)',_csv(data),file_name=f'vop_fenotipos_P{lo}_P{hi}.csv',mime='text/csv')
    c2.download_button('Resumen por modelo (CSV)',_csv(summary),file_name='vop_fenotipos_modelos.csv',mime='text/csv',disabled=summary.empty)
    c3.download_button('Estratos (CSV)',_csv(strata),file_name='vop_fenotipos_estratos.csv',mime='text/csv')
    st.caption('La referencia Díaz proviene de personas aparentemente saludables; transferibilidad de esta clasificación a pacientes de alto riesgo y a ePWV requiere estudios independientes.')
