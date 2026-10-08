"""Panel Streamlit para concordancia numérica ePWV vs medición tonométrica."""
from __future__ import annotations
from io import BytesIO
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from concordance import analyze_case, summarize, MODEL_FIELDS


def _csv(data):
    return data.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')


def _pdf_report(r, a):
    mem = BytesIO()
    doc=SimpleDocTemplate(mem,pagesize=A4,leftMargin=42,rightMargin=42)
    styles=getSampleStyleSheet()
    story=[Paragraph('VOP ARG · Concordancia referencial medida y estimada', styles['Title']),
           Spacer(1,14),Paragraph('<b>USO DE INVESTIGACIÓN. Sin validación externa. Estas etiquetas NO son diagnósticos.</b>',styles['BodyText']),Spacer(1,12)]
    threshold=a['Umbral_Diaz_usado'];measured=r.get('VOP_medida')
    summary=[('Edad / sexo',f'{r["Edad"]:.0f} años · {r["Sexo"]}'),
             ('PAS / PAD',f'{r["PAS"]:.0f} / {r["PAD"]:.0f} mmHg'),
             (f'Umbral {threshold} Díaz', f'{a["Valor_umbral_m_s"]:.2f} m/s'),
             ('VOP cf medida',f'{measured:.2f} m/s' if measured is not None else 'No disponible'),
             ('Evaluación de medida','Elevada respecto de referencia' if a['VOP_medida_elevada_ref'] else 'Inferior a referencia' if measured is not None else 'No evaluable'),
             ('Resultado de contraste',a['Patron_medida_estimadas']),
             ('Concordancia entre estimaciones', a['Consenso_binario_estimados'])]
    for k,(col,name) in MODEL_FIELDS.items():
        error=a[f'Error_firmado_{k}_m_s']
        summary.append((name, f'{r[col]:.2f} m/s | umbral: {"supera/iguala" if a[f"Eleva_num_{k}"] else "inferior"}' + (f' | error estimada - medida: {error:+.2f} m/s' if error is not None else '')))
    table=Table([[Paragraph('<b>Indicador</b>',styles['BodyText']),Paragraph('<b>Resultado</b>',styles['BodyText'])]] +
            [[Paragraph(escape(str(k)),styles['BodyText']), Paragraph(escape(str(v)),styles['BodyText'])] for k,v in summary],
            colWidths=[160,350],repeatRows=1)
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.whitesmoke,colors.white]),
                              ('LINEBELOW',(0,0),(-1,0),.8,colors.HexColor('#006E70')),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.extend([table,Spacer(1,16),Paragraph(
        'La referencia de Díaz y cols. (2018) describe la distribución de VOP cf realmente medida en población aparentemente saludable. '
        'La comparación de estimaciones con el mismo umbral es solo aritmética; sensibilidad/especificidad calculadas contra esta etiqueta no prueban validez diagnóstica.',
        styles['BodyText']), Spacer(1,10),Paragraph('Díaz A y cols. J Clin Hypertens. 2018;20:659-671. DOI: 10.1111/jch.13251.',styles['BodyText'])])
    doc.build(story)
    return mem.getvalue()


def render():
    st.subheader('Rigidez vascular referencial y concordancia medida–estimada')
    st.warning('**Referencia normativa:** solo la VOP carótido-femoral **medida** puede clasificarse directamente según Díaz (2018). Para las ePWV estimadas, superar P90/P95 constituye únicamente una **señal aritmética exploratoria**, no diagnóstico de rigidez vascular.')
    s1,s2=st.columns([1,2])
    threshold=s1.radio('Límite referencial de VOP medida',options=[90,95],index=0,format_func=lambda v:f'P{v} Díaz',horizontal=True,key='concord_threshold')
    margin=s2.slider('Margen de error absoluto (m/s) — exploratorio, no clínico',min_value=0.0,max_value=4.0,value=1.0,step=.1,key='concord_margin')
    st.caption('Se consideran valores elevados respecto del límite elegido cuando VOP medida ≥ límite. Coincidencias entre ePWV y dicho umbral son solamente contrastes numéricos descriptivos.')

    r=st.session_state.get('individual_result')
    if r:
        st.markdown('### 1. Caso individual')
        a=analyze_case(r,threshold,margin)
        measured=r.get('VOP_medida')
        c1,c2,c3,c4=st.columns(4)
        c1.metric('VOP cf realmente medida',f'{measured:.2f} m/s' if measured is not None else 'Sin dato')
        c2.metric(f'Límite Díaz P{threshold}',f'{a["Valor_umbral_m_s"]:.2f} m/s')
        c3.metric('Estimaciones ≥ límite',f'{a["Conteo_modelos_elevados"]} de 3')
        c4.metric('Consenso estimaciones', a['Consenso_binario_estimados'])
        if measured is not None:
            if a['VOP_medida_elevada_ref']:
                st.error(f'**Elevación referencial en VOP MEDIDA ≥P{threshold}.** {a["Patron_medida_estimadas"]}. No equivale por sí sola a un diagnóstico de enfermedad arterial.')
            else:
                st.info(f'**VOP MEDIDA <P{threshold}.** {a["Patron_medida_estimadas"]}.')
        else:
            st.info('**Sin VOP medida.** No es posible establecer elevación referencial medida ni concordancia frente a tonometría; solo puede describirse el acuerdo entre ecuaciones estimadas.')
        report=[]
        for key,(field,name) in MODEL_FIELDS.items():
            report.append({'Modelo':name,'ePWV (m/s)':r[field],
                f'Comparación numérica con P{threshold}':'≥ límite' if a[f'Eleva_num_{key}'] else '< límite',
                'Error vs medida (m/s)':a[f'Error_firmado_{key}_m_s'],
                'Error absoluto (m/s)':a[f'Error_absoluto_{key}_m_s'],
                'Etiqueta vs medida':a[f'Estado_comparativo_{key}']})
        st.dataframe(pd.DataFrame(report).round(3),hide_index=True,use_container_width=True)
        fig=go.Figure()
        labels=[MODEL_FIELDS[k][1] for k in MODEL_FIELDS]
        vals=[r[MODEL_FIELDS[k][0]] for k in MODEL_FIELDS]
        fig.add_trace(go.Bar(y=labels,x=vals,orientation='h',name='VOP estimada',marker_color='#0A8991'))
        fig.add_vline(x=a['Valor_umbral_m_s'],line_color='#CC8435',line_dash='dash',annotation_text=f'P{threshold} Díaz')
        if measured is not None:
            fig.add_vline(x=measured,line_color='#A53A44',line_width=3,annotation_text='VOP medida')
        fig.update_layout(xaxis_title='Velocidad (m/s)',height=290,margin=dict(l=0,r=15,t=25,b=20))
        st.plotly_chart(fig,use_container_width=True)
        if measured is not None:
            st.caption(f'Modelo de menor error absoluto para **este caso**: {a["Modelo_menor_error"]}. Esto no demuestra cuál modelo es mejor en la población.')
        st.download_button('⬇️ Informe individual de concordancia (PDF)',_pdf_report(r,a),
                           file_name='VOP_ARG_concordancia_individual.pdf',mime='application/pdf')
    else:
        st.info('Calcule primero un paciente en la pestaña «Paciente» para mostrar su patrón individual.')

    data=st.session_state.get('batch_ok')
    st.markdown('### 2. Concordancia en una cohorte')
    if not isinstance(data,pd.DataFrame) or data.empty:
        st.info('Cargue registros anónimos en «Carga masiva» para estudiar concordancia, omisiones, falsas señales y estratos por edad/sexo.')
        return
    enriched,summary,pairs,strata=summarize(data,threshold,margin)
    measured=enriched.loc[enriched['VOP_medida_disponible']].copy()
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Registros procesados',len(enriched))
    c2.metric('Con VOP medida',len(measured))
    c3.metric('Medida elevada (referencial)',int(measured['VOP_medida_elevada_ref'].sum()) if len(measured) else '—')
    c4.metric('Consenso entre 3 modelos',f'{100*enriched["Coincidencia_3_modelos"].mean():.1f}%')
    if len(measured):
        st.markdown('#### Resultados según presencia de VOP medida elevada')
        counts=measured['Patron_medida_estimadas'].value_counts(dropna=False)
        st.dataframe(counts.rename_axis('Patrón').reset_index(name='N'),hide_index=True,use_container_width=True)
        heat=pd.crosstab(pd.Series(np.where(measured['VOP_medida_elevada_ref'],'≥ umbral','< umbral'),index=measured.index,name='VOP medida'),
                         measured['Conteo_modelos_elevados'].astype(str).rename('Cantidad estimaciones ≥ umbral'))
        for col in ('0','1','2','3'):
            if col not in heat.columns:heat[col]=0
        heat=heat[['0','1','2','3']]
        fig=go.Figure(go.Heatmap(z=heat.to_numpy(),x=heat.columns.tolist(),y=heat.index.tolist(),text=heat.to_numpy(),texttemplate='%{text}',colorscale='Teal',showscale=False))
        fig.update_layout(title=f'Coincidencia de señales estimadas con VOP medida (P{threshold} Díaz)',height=310,
                          xaxis_title='Cantidad de ecuaciones estimadas ≥ umbral',yaxis_title='VOP realmente medida')
        st.plotly_chart(fig,use_container_width=True)
        st.markdown('#### Matrices de clasificación descriptiva frente a medición')
        st.caption('VP/VN/FP/FN y porcentajes son resultados comparativos frente al umbral de referencia medida, **no métricas de precisión diagnóstica clínica**. Los indicadores sin denominador se muestran vacíos.')
        st.dataframe(summary.round(2),hide_index=True,use_container_width=True)
        st.markdown('**Tablas 2 × 2 por modelo:**')
        cols=st.columns(3)
        for idx,row in summary.iterrows():
            with cols[idx]:
                st.markdown(f'**{row["Modelo"]}**')
                matrix=pd.DataFrame({'Estimada ≥ límite':[row['VP'],row['FP']],
                                     'Estimada < límite':[row['FN'],row['VN']]},
                                    index=['VOP medida ≥ límite','VOP medida < límite'])
                st.dataframe(matrix,use_container_width=True)
    else:
        st.info('No hay VOP medida en la cohorte. No se calculan sensibilidad, especificidad ni coincidencia con medición.')

    st.markdown('#### Concordancia entre las tres ecuaciones estimadas')
    st.dataframe(pairs.round(3),hide_index=True,use_container_width=True)
    st.caption('La kappa binaria puede ser indefinida cuando una o ambas ecuaciones siempre asignan la misma categoría. El acuerdo entre ecuaciones NO demuestra que ninguna sea correcta.')
    st.markdown('#### Análisis por edad y sexo')
    st.dataframe(strata.round(2),hide_index=True,use_container_width=True)
    st.markdown('#### Diferencia absoluta vs edad (solo registros con VOP medida)')
    if len(measured):
        fig=go.Figure()
        for key,(_,name) in MODEL_FIELDS.items():
            fig.add_trace(go.Scatter(x=measured['Edad'],y=measured[f'Error_absoluto_{key}_m_s'],
                                    mode='markers',name=name,opacity=.45))
        fig.add_hline(y=margin,line_dash='dot',annotation_text='Margen seleccionado')
        fig.update_layout(height=360,xaxis_title='Edad (años)',yaxis_title='Error absoluto (m/s)')
        st.plotly_chart(fig,use_container_width=True)
    st.markdown('#### Descargar análisis reproducible')
    st.caption('Los archivos contienen únicamente los registros anonimizados que usted haya ingresado y sus cálculos; no se graban automáticamente en GitHub.')
    c1,c2,c3=st.columns(3)
    c1.download_button('⬇️ Resultados individuales CSV',_csv(enriched),file_name=f'VOP_concordancia_P{threshold}_individual.csv',mime='text/csv')
    c2.download_button('⬇️ Tabla por modelos CSV',_csv(summary),file_name=f'VOP_concordancia_P{threshold}_modelos.csv',mime='text/csv')
    c3.download_button('⬇️ Estratos CSV',_csv(strata),file_name=f'VOP_concordancia_P{threshold}_estratos.csv',mime='text/csv')
    st.info('Para validar científicamente estas observaciones son necesarios sujetos independientes, estandarización tonométrica y una cohorte externa. La VOP estimada no debe reemplazar la medida.')
