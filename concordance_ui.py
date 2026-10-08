"""Interfaz de investigación: comparación de ePWV estimada y VOP realmente medida."""
from io import BytesIO
from xml.sax.saxutils import escape
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from concordance import analyze_case,summarize,MODEL_FIELDS

def _csv(data):
    return data.to_csv(index=False,sep=';',decimal=',').encode('utf-8-sig')

def _pdf_report(r,a):
    buf=BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=42,rightMargin=42)
    styles=getSampleStyleSheet()
    story=[Paragraph('VOP ARG - Concordancia referencial',styles['Title']),Spacer(1,14),
        Paragraph('<b>INVESTIGACIÓN; NO USO DIAGNÓSTICO. Sin validación externa.</b>',styles['BodyText']),Spacer(1,15)]
    mv=r.get('VOP_medida')
    rows=[
      ('Edad/sexo',f'{r["Edad"]:.0f} años / {r["Sexo"]}'),
      ('PA',f'{r["PAS"]:.0f}/{r["PAD"]:.0f} mmHg'),
      ('Umbral elegido',f'{a["Umbral_Diaz_usado"]} = {a["Valor_umbral_m_s"]:.2f} m/s'),
      ('VOP MEDIDA',f'{mv:.2f} m/s' if mv is not None else 'Sin dato'),
      ('Patrón frente a medida',a['Patron_medida_estimadas']),
      ('Acuerdo entre 3 estimaciones',a['Consenso_binario_estimados']),
    ]
    for key,(field,label) in MODEL_FIELDS.items():
        delta=a[f'Error_firmado_{key}_m_s']
        rows.append((label,f'{r[field]:.2f} m/s; numéricamente {"≥" if a[f"Eleva_num_{key}"] else "<"} límite'
           +(f'; estimada-medida {delta:+.2f} m/s' if delta is not None else '')))
    table=Table([[Paragraph('<b>Variable</b>',styles['BodyText']),Paragraph('<b>Resultado</b>',styles['BodyText'])]]+
         [[Paragraph(escape(str(k)),styles['BodyText']),Paragraph(escape(str(v)),styles['BodyText'])] for k,v in rows],
         colWidths=[168,335],repeatRows=1)
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.whitesmoke,colors.white]),
        ('LINEBELOW',(0,0),(-1,0),.8,colors.HexColor('#006E70')),
        ('BOTTOMPADDING',(0,0),(-1,-1),9)]))
    story.extend([table,Spacer(1,13),Paragraph(
      'Los percentiles de Díaz et al. se refieren a VOP carótido-femoral realmente medida en sujetos sanos. '
      'Las coincidencias de ePWV con el umbral son contrastes aritméticos y no diagnósticos.',styles['BodyText']),
      Spacer(1,8),Paragraph('Díaz A et al. J Clin Hypertens. 2018;20:659–671. DOI:10.1111/jch.13251.',styles['BodyText'])])
    doc.build(story)
    return buf.getvalue()

def render():
    st.subheader('Rigidez vascular referencial y concordancia medida-estimada')
    st.warning('**Solo la VOP cf medida** se interpreta directamente frente a los P90/P95 de Díaz (2018). '
       'Una ePWV por encima de esos valores es únicamente una comparación numérica, '
       '**no un percentil de ePWV validado ni un diagnóstico**.')
    left,right=st.columns([1,2])
    cutoff=left.radio('Referencia para VOP medida',[90,95],index=0,horizontal=True,
        format_func=lambda x:f'P{x} Díaz',key='advanced_cutoff')
    margin=right.slider('Margen de error absoluto (m/s), exploratorio',0.0,4.0,1.0,0.1,key='advanced_margin')
    st.caption('≥P90 o ≥P95: elevación respecto de distribución normativa saludable. '
       'El margen no es corte clínico.')
    r=st.session_state.get('result') or st.session_state.get('individual_result')
    if r:
        st.markdown('### Análisis individual')
        c=analyze_case(r,cutoff,margin)
        measured=r.get('VOP_medida')
        a,b,d,e=st.columns(4)
        a.metric('VOP realmente medida',f'{measured:.2f} m/s' if measured is not None else 'No disponible')
        b.metric(f'Umbral Díaz P{cutoff}',f'{c["Valor_umbral_m_s"]:.2f} m/s')
        d.metric('Estimaciones ≥ umbral',f'{c["Conteo_modelos_elevados"]}/3')
        e.metric('Acuerdo estimaciones',c['Consenso_binario_estimados'])
        if measured is None:
            st.info('No se puede establecer elevación referencial medida ni su discordancia con estimaciones: falta tonometría.')
        elif c['VOP_medida_elevada_ref']:
            st.error(f'**Elevación referencial de VOP medida** (≥P{cutoff}). {c["Patron_medida_estimadas"]}. '
                     'No implica por sí sola enfermedad vascular.')
        else:
            st.info(f'VOP medida <P{cutoff}. {c["Patron_medida_estimadas"]}.')
        display=[]
        for k,(field,name) in MODEL_FIELDS.items():
            display.append({'Modelo':name,'ePWV (m/s)':r[field],
              'Contraste con umbral':'≥ umbral' if c[f'Eleva_num_{k}'] else '< umbral',
              'Error firmado vs medida (m/s)':c[f'Error_firmado_{k}_m_s'],
              'Error absoluto (m/s)':c[f'Error_absoluto_{k}_m_s'],
              'Contraste referencial':c[f'Estado_comparativo_{k}']})
        st.dataframe(pd.DataFrame(display).round(3),hide_index=True,use_container_width=True)
        f=go.Figure(go.Bar(x=[r[MODEL_FIELDS[k][0]] for k in MODEL_FIELDS],
                y=[MODEL_FIELDS[k][1] for k in MODEL_FIELDS],orientation='h',
                marker_color='#008A80'))
        f.add_vline(x=c['Valor_umbral_m_s'],line_dash='dash',line_color='#B67B35',annotation_text=f'P{cutoff}')
        if measured is not None:
            f.add_vline(x=measured,line_color='#B3434A',line_width=3,annotation_text='Medida')
            st.caption(f'Menor error absoluto para este caso: {c["Modelo_menor_error"]}. '
                       'No acredita mejor desempeño poblacional.')
        f.update_layout(xaxis_title='m/s',height=290,margin=dict(t=20,b=20,l=0,r=10))
        st.plotly_chart(f,use_container_width=True)
        st.download_button('Descargar concordancia individual (PDF)',_pdf_report(r,c),
            file_name='VOP_concordancia_individual.pdf',mime='application/pdf')
    else:
        st.info('Ingrese primero un registro en la pestaña Paciente.')
    st.markdown('### Cohorte y concordancia por modelo')
    data=st.session_state.get('batch') if 'batch' in st.session_state else st.session_state.get('batch_ok')
    if not isinstance(data,pd.DataFrame) or data.empty:
        st.info('Cargue CSV/XLSX en Carga masiva para análisis pareado y por estratos.')
        return
    enriched,model_table,pairs,strata=summarize(data,cutoff,margin)
    med=enriched[enriched['VOP_medida_disponible']].copy()
    a,b,c,d=st.columns(4)
    a.metric('Registros',len(enriched))
    b.metric('Con VOP medida',len(med))
    c.metric('Elevación referencial MEDIDA',int(med['VOP_medida_elevada_ref'].sum()) if len(med) else '—')
    d.metric('Consenso de 3 estimaciones',f'{100*enriched["Coincidencia_3_modelos"].mean():.1f}%')
    if len(med):
        st.markdown('#### Discordancia medida-estimada')
        st.dataframe(med['Patron_medida_estimadas'].value_counts().rename_axis('Patrón').reset_index(name='N'),
                     hide_index=True,use_container_width=True)
        mat=pd.crosstab(pd.Series(np.where(med['VOP_medida_elevada_ref'],'≥ umbral','< umbral'),
                          index=med.index,name='VOP medida'),
                         med['Conteo_modelos_elevados'].astype(str))
        for x in ('0','1','2','3'):
            if x not in mat.columns:mat[x]=0
        mat=mat[['0','1','2','3']]
        f=go.Figure(go.Heatmap(z=mat.to_numpy(),x=mat.columns.tolist(),y=mat.index.tolist(),
                 text=mat.to_numpy(),texttemplate='%{text}',colorscale='Teal',showscale=False))
        f.update_layout(title='Cantidad de estimaciones que coincide con el umbral de Díaz',
             xaxis_title='Número de ePWV estimadas ≥ umbral',yaxis_title='VOP cf medida',
             height=320)
        st.plotly_chart(f,use_container_width=True)
        st.markdown('#### Matrices 2×2 y métricas descriptivas')
        st.caption('VP/FN/FP/VN: positivo = ≥ límite de Díaz medido. Sensibilidad y especificidad '
          'se refieren SOLO a esa etiqueta, no a eventos cardiovasculares ni diagnóstico de enfermedad.')
        st.dataframe(model_table.round(2),hide_index=True,use_container_width=True)
        cols=st.columns(3)
        for idx,rr in model_table.iterrows():
            with cols[idx]:
                st.markdown('**'+rr['Modelo']+'**')
                st.dataframe(pd.DataFrame({'Estimación ≥ límite':[rr['VP'],rr['FP']],
                 'Estimación < límite':[rr['FN'],rr['VN']]},
                 index=['VOP medida ≥ límite','VOP medida < límite']),use_container_width=True)
    else:
        st.info('Sin mediciones tonométricas: no se computan sensibilidad/especificidad ni matrices con referencia medida.')
    st.markdown('#### Acuerdo entre ecuaciones estimadas')
    st.dataframe(pairs.round(3),hide_index=True,use_container_width=True)
    st.caption('La kappa es indefinida si no hay variabilidad suficiente. '
       'La concordancia de modelos entre sí no demuestra exactitud.')
    st.markdown('#### Desglose por edad y sexo')
    st.dataframe(strata.round(2),hide_index=True,use_container_width=True)
    if len(med):
        f=go.Figure()
        for key,(_,label) in MODEL_FIELDS.items():
            f.add_trace(go.Scatter(x=med.Edad,y=med[f'Error_absoluto_{key}_m_s'],
                            mode='markers',name=label,opacity=.48))
        f.add_hline(y=margin,line_dash='dot',annotation_text='Margen')
        f.update_layout(xaxis_title='Edad (años)',yaxis_title='Error absoluto (m/s)',height=330)
        st.plotly_chart(f,use_container_width=True)
    x,y,z=st.columns(3)
    x.download_button('Resultados por registro CSV',_csv(enriched),'VOP_concordancia_registros.csv','text/csv')
    y.download_button('Resumen por modelo CSV',_csv(model_table),'VOP_concordancia_modelos.csv','text/csv')
    z.download_button('Estratos CSV',_csv(strata),'VOP_concordancia_estratos.csv','text/csv')
    st.caption('Datos solo en la sesión actual: no se envían a GitHub automáticamente. En un despliegue público, '
       'no cargar nombres, DNI ni otros datos identificatorios. Valide externamente antes de uso clínico.')
