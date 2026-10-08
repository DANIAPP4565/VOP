"""Panel visual de envejecimiento vascular para Streamlit.

Fenotipo referencial SOLO con cfPWV realmente medida; las ePWV de cada
modelo reciben categorías numéricas TEÓRICAS, NO VALIDADAS clínicamente.
Los umbrales operativos P10/P90 o P5/P95 provienen de las distribuciones
por edad y sexo de Díaz y col. (2018). No representan diagnósticos.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from math import isfinite
from statistics import NormalDist
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

from aging import AGE_GROUPS, MODEL_FIELDS, PHENOTYPES, case_aging, evaluate_cohort

C = {
    'super': '#087A69', 'healthy': '#2670AD', 'eva': '#BA4E51',
    'navy': '#162D46', 'muted': '#64778A', 'grid': '#E7ECF1',
    'arg': '#087F79', 'eu': '#6686C1', 'fr': '#AF825A', 'actual': '#172D48',
    'bg': '#FAFCFF'
}
COLORS = {'SUPERNOVA': C['super'], 'Saludable/esperado': C['healthy'], 'EVA': C['eva']}
NAMES = {'SUPERNOVA': 'SUPERNOVA', 'Saludable/esperado': 'SALUDABLE / ESPERADO', 'EVA': 'EVA'}
MODEL_SHORT = {'ARG': 'Argentina candidata', 'EU_SANA': 'Europa sana', 'EU_FR': 'Europa con FR'}


def _esc(text):
    return escape(str(text), {'"': '&quot;'})


def _fmt(x, suffix=''):
    if x is None or not isfinite(float(x)):
        return '—'
    return f'{float(x):.2f}{suffix}'


def _plot_style(fig, height=370, bottom=36):
    fig.update_layout(
        template='plotly_white', height=height,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, Arial, sans-serif', color=C['navy'], size=12),
        margin=dict(l=20, r=18, t=44, b=bottom),
        legend=dict(orientation='h', yanchor='top', y=-.22, xanchor='left', x=0, font=dict(size=11)),
        hoverlabel=dict(bgcolor='white',font_size=12),
        xaxis=dict(showgrid=True, gridcolor=C['grid'], zeroline=False, linecolor=C['grid']),
        yaxis=dict(showgrid=True, gridcolor=C['grid'], zeroline=False, linecolor=C['grid']),
    )
    return fig


def _normative(age, sex):
    """Media y DE publicadas; nunca derivadas de una presión ficticia."""
    from math import log10, sqrt
    male = str(sex).strip().lower().startswith('mas')
    a = float(age)
    if male:
        mu = 1.3942 + 3.4927*log10(a) - .02436*a + 5.698e-4*a*a
        sd = -.04760 + .06798*sqrt(a) + .02987*a - 2.091e-4*a*a
    else:
        mu = .062441 + 5.3108*log10(a) - .09658*a + 1.151e-3*a*a
        sd = 1.0392 - .4128*sqrt(a) + .08020*a - 3.65e-4*a*a
    return mu, sd


@lru_cache(maxsize=8)
def _reference_table(sex, lower, upper):
    nd = NormalDist()
    zl = nd.inv_cdf(lower / 100)
    zh = nd.inv_cdf(upper / 100)
    rows=[]
    for age in range(9,88):
        mu, sd = _normative(age, sex)
        rows.append({'Edad':age,'Inferior':mu+zl*sd,'Media':mu,'Superior':mu+zh*sd})
    return pd.DataFrame(rows)


def make_age_nomogram(record, analysis, lower=10, upper=90):
    """Curvas de referencia por sexo + marcadores de estimación y medición."""
    sex=record['Sexo']; age=float(record['Edad']); data=_reference_table(sex,lower,upper)
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=data.Edad, y=data.Inferior, mode='lines', name=f'P{lower} Díaz',
                             line=dict(color=C['super'],width=2), hovertemplate='Edad %{x}: %{y:.2f} m/s<extra>P inferior</extra>'))
    fig.add_trace(go.Scatter(x=data.Edad, y=data.Superior, mode='lines', name=f'P{upper} Díaz',
                             fill='tonexty', fillcolor='rgba(38,112,173,.095)',
                             line=dict(color=C['eva'],width=2), hovertemplate='Edad %{x}: %{y:.2f} m/s<extra>P superior</extra>'))
    fig.add_trace(go.Scatter(x=data.Edad, y=data.Media, mode='lines', name='Media Díaz',
                             line=dict(color=C['healthy'], width=2.1, dash='dot'),
                             hovertemplate='Edad %{x}: %{y:.2f} m/s<extra>Media</extra>'))
    if record.get('VOP_medida') is not None:
        fig.add_trace(go.Scatter(x=[age],y=[record['VOP_medida']],name='VOP medida',mode='markers',
                 marker=dict(symbol='diamond',size=17,color=C['actual'],line=dict(color='white',width=2)),
                 hovertemplate='TONOMETRÍA: %{y:.2f} m/s<extra></extra>'))
    for key,(field,name) in MODEL_FIELDS.items():
        fig.add_trace(go.Scatter(x=[age],y=[record[field]],mode='markers',name=f'{MODEL_SHORT[key]} · estimada',
                  marker=dict(symbol='circle-open',size=13,color={'ARG':C['arg'],'EU_SANA':C['eu'],'EU_FR':C['fr']}[key],line=dict(width=3)),
                  hovertemplate=f'{name} (teórico): %{{y:.2f}} m/s<extra></extra>'))
    fig.add_vline(x=age, line=dict(color='rgba(39,62,87,.32)',dash='dash',width=1))
    fig.update_layout(title=dict(text=f'Curvas argentinas de referencia por edad · {sex}',font=dict(size=15)),
                      xaxis_title='Edad (años)',yaxis_title='VOP cf (m/s)')
    fig.update_xaxes(range=[9,87])
    return _plot_style(fig, 390, 60)


def make_z_map(record, analysis, lower=10, upper=90):
    mu=float(record['Diaz_media_normativa']); sd=float(record['Diaz_DE_normativa'])
    zlo=NormalDist().inv_cdf(lower/100); zhi=NormalDist().inv_cdf(upper/100)
    labels=[]; observations=[]
    if record.get('VOP_medida') is not None:
        labels.append('VOP medida · tonometría'); observations.append(('MED',float(record['VOP_medida'])))
    for key,(field,name) in MODEL_FIELDS.items():
        labels.append(f'{MODEL_SHORT[key]} · ePWV');observations.append((key,float(record[field])))
    z_scores=[(k,(v-mu)/sd) for k,v in observations]
    lo=min([-3.2,zlo-.35]+[v-.35 for _,v in z_scores]);hi=max([3.2,zhi+.35]+[v+.35 for _,v in z_scores]);lo=max(-8,lo);hi=min(8,hi)
    fig=go.Figure()
    for a,b,fill in [(lo,zlo,'rgba(8,122,105,.12)'),(zlo,zhi,'rgba(38,112,173,.065)'),(zhi,hi,'rgba(186,78,81,.11)')]:
        fig.add_vrect(x0=a,x1=b,fillcolor=fill,line_width=0,layer='below')
    for z,label in [(zlo,f'P{lower}'),(zhi,f'P{upper}')]:
        fig.add_vline(x=z,line=dict(color='#7C8A96',dash='dash',width=1))
        fig.add_annotation(x=z,y=1.10,yref='paper',text=label,showarrow=False,font=dict(size=11,color=C['muted']))
    for i,(key,z) in enumerate(z_scores):
        color = C['actual'] if key=='MED' else {'ARG':C['arg'],'EU_SANA':C['eu'],'EU_FR':C['fr']}[key]
        fig.add_trace(go.Scatter(x=[z],y=[i],mode='markers+text',
             marker=dict(size=19 if key=='MED' else 15, symbol='diamond' if key=='MED' else 'circle-open',
                         color=color,line=dict(width=2.7)),
             text=[f'{observations[i][1]:.2f} m/s'], textposition='middle right',
             textfont=dict(color=color,size=11), showlegend=False,
             hovertemplate=f'{labels[i]}<br>z = %{{x:.2f}}<br>VOP = {observations[i][1]:.2f} m/s<extra></extra>'))
    fig.update_layout(title=dict(text='Mapa de posicionamiento vascular · puntaje Z',font=dict(size=15)),
         xaxis=dict(title='Desvíos estándar respecto de la referencia Díaz · no equivale a edad vascular',range=[lo,hi]),
         yaxis=dict(tickvals=list(range(len(labels))),ticktext=labels,autorange='reversed',range=[len(labels)-.25,-.65]),
         showlegend=False)
    fig.add_annotation(x=(lo+zlo)/2,y=-.29,text='SUPERNOVA',showarrow=False,font=dict(size=10,color=C['super']))
    fig.add_annotation(x=(zlo+zhi)/2,y=-.29,text='INTERVALO ESPERADO',showarrow=False,font=dict(size=10,color=C['healthy']))
    fig.add_annotation(x=(zhi+hi)/2,y=-.29,text='EVA',showarrow=False,font=dict(size=10,color=C['eva']))
    return _plot_style(fig, 335, 32)


def make_model_comparison(record):
    names=[]; values=[]; color=[]; flags=[]
    if record.get('VOP_medida') is not None:
        names.append('VOP medida (referencia)');values.append(float(record['VOP_medida']));color.append(C['actual']);flags.append(False)
    for key,(field,_) in MODEL_FIELDS.items():
        names.append(MODEL_SHORT[key]);values.append(float(record[field]));flags.append(True)
        color.append({'ARG':C['arg'],'EU_SANA':C['eu'],'EU_FR':C['fr']}[key])
    fig=go.Figure()
    fig.add_trace(go.Bar(x=values,y=names,orientation='h',marker=dict(color=color),text=[f'{v:.2f}' for v in values],
        textposition='outside',hovertemplate='%{y}: %{x:.2f} m/s<extra></extra>',showlegend=False))
    if record.get('VOP_medida') is not None:
        fig.add_vline(x=float(record['VOP_medida']),line=dict(color=C['actual'],width=1.3,dash='dot'))
    fig.update_layout(title=dict(text='Medición y estimaciones · m/s',font=dict(size=15)),
        xaxis_title='Velocidad (m/s)',yaxis_title='',bargap=.38)
    fig.update_xaxes(range=[0, max(values)*1.17])
    fig.update_yaxes(autorange='reversed')
    return _plot_style(fig,305,30)


def _pdf_patient(r, a):
    buf=BytesIO();doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=40,rightMargin=40)
    sty=getSampleStyleSheet()
    parts=[Paragraph('VOP ARG | Panel de fenotipos EVA · SUPERNOVA',sty['Title']),Spacer(1,12),
           Paragraph('<b>Investigación, clasificación operativa sin validación clínica independiente.</b>',sty['BodyText']),Spacer(1,14)]
    rows=[('Edad / sexo',f'{r["Edad"]:.0f} años / {r["Sexo"]}'),
          ('PAS / PAD',f'{r["PAS"]:.0f}/{r["PAD"]:.0f} mmHg'),
          ('Referencia Díaz',a['Criterio_EVA']),
          ('Límite inferior',f'{a["Umbral_SUPERNOVA_m_s"]:.2f} m/s'),
          ('Límite superior EVA',f'{a["Umbral_EVA_m_s"]:.2f} m/s'),
          ('VOP medida',_fmt(r.get('VOP_medida'),' m/s')),
          ('Fenotipo medido',a['Fenotipo_VOP_medida'] or 'NO EVALUABLE · sin medición'),
          ('Concordancia 3 estimaciones',a['Concordancia_3_estimados']),
          ('Concordancia contra medida',a['Concordancia_medida_estimados'])]
    for key,(field,name) in MODEL_FIELDS.items():
        rows.append((name+' · SOLO TEÓRICO',f'{r[field]:.2f} m/s / {a[f"Fenotipo_teorico_{key}"]}'))
    tab=Table([['Indicador','Resultado']]+[[escape(str(k)),escape(str(v))] for k,v in rows],colWidths=[240,270],repeatRows=1)
    tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(C['navy'])),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#EDF3F8')]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8)]))
    parts.extend([tab,Spacer(1,13),Paragraph(
       'Solo la VOP cf tonométrica recibe fenotipo referencial. Las categorías de ePWV son simulaciones numéricas sin validación, no diagnósticos ni evaluación pronóstica. '
       'SUPERNOVA y EVA se definen aquí por P10/P90 (o P5/P95 en sensibilidad) de la distribución de referencia por edad y sexo. '
       'Díaz et al., J Clin Hypertens. 2018;20:659–671. DOI 10.1111/jch.13251.',sty['BodyText'])])
    doc.build(parts);return buf.getvalue()


def _badge(cat):
    return {'SUPERNOVA':('super','✦'),'Saludable/esperado':('healthy','●'),'EVA':('eva','▲')}.get(cat,('empty','—'))


def _patient_hero(r,a,lower,upper):
    cat=a['Fenotipo_VOP_medida'];sty,icon=_badge(cat)
    if cat is None:
        desc='Para asignar un fenotipo referencial, ingresá una VOP carótido-femoral realmente medida.'
        phenotype='NO EVALUABLE';value='—';per='Sin percentil medido'
    else:
        desc={'SUPERNOVA':'VOP medida por debajo del límite inferior de referencia para edad y sexo.',
             'Saludable/esperado':'VOP medida dentro del intervalo de referencia para edad y sexo.',
             'EVA':'VOP medida igual o superior al límite superior de referencia para edad y sexo.'}[cat]
        phenotype=NAMES[cat];value=f'{r["VOP_medida"]:.2f}';per=f'P{float(r["Diaz_percentil_VOP_medida"]):.1f} · Z {float(r["Diaz_Z_VOP_medida"]):+.2f}'
    st.markdown(f'''<section class="vop-result vop-{sty}" aria-label="Resultado de envejecimiento vascular">
      <div class="vop-result-main"><div class="vop-eyebrow">FENOTIPO DE ENVEJECIMIENTO VASCULAR · TONOMETRÍA</div>
      <div class="vop-phenotype"><span class="vop-symbol">{icon}</span>{_esc(phenotype)}</div>
      <div class="vop-desc">{_esc(desc)}</div><span class="vop-tag">CLASIFICACIÓN REFERENCIAL · P{lower}/P{upper}</span></div>
      <div class="vop-value"><div class="vop-val-label">VOP CF MEDIDA</div><div class="vop-big">{value} <small>m/s</small></div>
      <div class="vop-percentile">{_esc(per)}</div></div>
    </section>''',unsafe_allow_html=True)
    x=st.columns(4)
    x[0].metric('Límite SUPERNOVA', f'< {_fmt(a["Umbral_SUPERNOVA_m_s"])} m/s')
    x[1].metric('Media normativa Díaz', f'{_fmt(r["Diaz_media_normativa"])} m/s')
    x[2].metric('Umbral EVA', f'≥ {_fmt(a["Umbral_EVA_m_s"])} m/s')
    x[3].metric('Acuerdo entre estimaciones',a['Concordancia_3_estimados'].split(' en ')[0])


def _demo_record():
    from engine import calculate
    return calculate(55,'Masculino',125,75,8.7)


def render():
    st.markdown('''<div class="vop-section-label">FENOTIPOS VASCULARES · DASHBOARD</div>
    <h2 class="vop-panel-title">EVA · Saludable · SUPERNOVA</h2>
    <p class="vop-panel-sub">Interpretación visual de la VOP medida y comparación de los modelos de estimación, con referencias argentinas por edad y sexo.</p>''',unsafe_allow_html=True)
    if 'aging_alt' not in st.session_state: st.session_state['aging_alt']=False
    top1,top2=st.columns([2.4,1])
    with top1:
        st.info('**Referencia:** Díaz y cols. (2018). Fenotipo **solo con tonometría real**. Las etiquetas de ePWV son **simulaciones no validadas**, no diagnósticos.')
    with top2:
        st.toggle('Sensibilidad P5 / P95',key='aging_alt',help='Principal P10/P90; sensibilidad P5/P95, sin umbral clínico universal.')
    lower,upper=(5,95) if st.session_state['aging_alt'] else (10,90)

    actual=st.session_state.get('individual_result')
    demo=actual is None
    if demo:
        st.warning('**Modo demostración:** no hay un cálculo de paciente cargado. Se muestran datos **ficticios**, para visualizar la interfaz. Ingresá un paciente en «Paciente» para reemplazarlos.')
        r=_demo_record()
    else:
        r=actual
    a=case_aging(r,lower,upper)
    _patient_hero(r,a,lower,upper)

    left,right=st.columns([1.12,1],gap='large')
    with left:
        st.plotly_chart(make_z_map(r,a,lower,upper),use_container_width=True,key='vop_z_map')
    with right:
        st.plotly_chart(make_model_comparison(r),use_container_width=True,key='vop_model_comparison')
    st.plotly_chart(make_age_nomogram(r,a,lower,upper),use_container_width=True,key='vop_nomogram')
    st.caption('Diamante sólido: **tonometría real**. Círculos vacíos: **ePWV estimadas**. Las franjas se basan en la distribución de VOP medida de Díaz y cols. por edad y sexo. Los rangos P10/P90 constituyen una clasificación operativa de investigación.')

    with st.container(border=True):
        st.markdown('#### Concordancia del fenotipo entre las tres ecuaciones')
        k1,k2,k3=st.columns(3)
        k1.metric('Entre ePWV (teórico)',a['Concordancia_3_estimados'])
        k2.metric('Contra tonometría',a['Concordancia_medida_estimados'])
        k3.metric('Mejor aproximación individual',a['Modelo_menor_error_fenotipo'] or 'No evaluable')
        rows=[]
        if r.get('VOP_medida') is not None:
            rows.append({'Origen':'VOP CF MEDIDA','Valor (m/s)':r['VOP_medida'],
                   'Categoría':'MEDIDA: '+(a['Fenotipo_VOP_medida'] or '—'), 'Diferencia vs medida (m/s)':0.0})
        for key,(field,name) in MODEL_FIELDS.items():
            rows.append({'Origen':name,'Valor (m/s)':r[field],
                   'Categoría':'TEÓRICA: '+a[f'Fenotipo_teorico_{key}'],
                   'Diferencia vs medida (m/s)':a[f'Error_{key}_estimada_menos_medida']})
        st.dataframe(pd.DataFrame(rows),column_config={
            'Valor (m/s)':st.column_config.NumberColumn(format='%.2f'),
            'Diferencia vs medida (m/s)':st.column_config.NumberColumn(format='%+.2f')},
            hide_index=True,use_container_width=True)
        if not demo:
            st.download_button('⬇️ Informe EVA / SUPERNOVA (PDF)',_pdf_patient(r,a),
                       file_name='VOP_ARG_panel_envejecimiento.pdf',mime='application/pdf',key='vop_pdf_visual')
        else:
            st.caption('El informe clínico se habilita únicamente cuando ingresás los datos de un paciente en «Paciente».')

    st.markdown('### Panorama poblacional de fenotipos')
    batch=st.session_state.get('batch_ok')
    if not isinstance(batch,pd.DataFrame) or batch.empty:
        st.info('Para visualizar prevalencias, concordancia y gráficos de cohortes, importá una base de datos **anonimizada** en «Carga masiva».')
        return
    data,summary,matrix,strata=evaluate_cohort(batch,lower,upper)
    measured=data.loc[data['Fenotipo_VOP_medida'].notna()].copy()
    n=len(measured)
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Registros cargados',len(data))
    c2.metric('Con cfPWV medida',n)
    if n:
        c3.metric('EVA referencial',f'{int((measured.Fenotipo_VOP_medida=="EVA").sum())} ({100*(measured.Fenotipo_VOP_medida=="EVA").mean():.1f}%)')
        c4.metric('SUPERNOVA referencial',f'{int((measured.Fenotipo_VOP_medida=="SUPERNOVA").sum())} ({100*(measured.Fenotipo_VOP_medida=="SUPERNOVA").mean():.1f}%)')
    else:
        c3.metric('EVA medida','No evaluable');c4.metric('SUPERNOVA medida','No evaluable')
    if not n:
        st.warning('La cohorte no incluye VOP cf medida. **No se puede determinar prevalencia de EVA o SUPERNOVA reales**. Las ecuaciones pueden compararse solo de forma teórica.')
        pool=data
    else:
        pool=measured

    dist=[]
    sources=[('Fenotipo_VOP_medida','TONOMETRÍA REAL')]+[(f'Fenotipo_teorico_{k}',f'{MODEL_SHORT[k]} · ePWV') for k in MODEL_FIELDS]
    if not n: sources=sources[1:]
    for field,label in sources:
        for cat in PHENOTYPES:
            count=int((pool[field]==cat).sum())
            dist.append({'Fuente':label,'Fenotipo':cat,'Porcentaje':100*count/len(pool),'N':count})
    plot=pd.DataFrame(dist)
    l,rcol=st.columns([1.1,1],gap='large')
    with l:
        fig=px.bar(plot, x='Fuente',y='Porcentaje',color='Fenotipo',barmode='stack',
                   category_orders={'Fenotipo':list(PHENOTYPES)},
                   color_discrete_map=COLORS, custom_data=['N'],
                   title='Distribución porcentual · misma cohorte pareada' if n else 'Solo estimaciones teóricas · sin tonometría')
        fig.update_traces(hovertemplate='%{x}<br>%{fullData.name}: %{y:.1f}%<br>N=%{customdata[0]}<extra></extra>')
        fig.update_layout(yaxis_title='Porcentaje (%)',xaxis_title='',legend_title='',bargap=.35)
        fig.update_yaxes(range=[0,100])
        st.plotly_chart(_plot_style(fig,380,94),use_container_width=True,key='vop_cohort_distribution')
    with rcol:
        if n:
            cnt=measured['Fenotipo_VOP_medida'].value_counts().reindex(PHENOTYPES,fill_value=0)
            fig=go.Figure(go.Pie(labels=list(cnt.index),values=list(cnt.values),hole=.71,
                     marker=dict(colors=[COLORS[c] for c in PHENOTYPES]),sort=False,
                     textinfo='percent',hovertemplate='%{label}<br>N = %{value} (%{percent})<extra></extra>'))
            fig.add_annotation(x=.5,y=.5,text=f'<b>{n}</b><br>medidos',showarrow=False,font=dict(size=18,color=C['navy']))
            fig.update_layout(title=dict(text='Fenotipo de VOP realmente medida',font=dict(size=15)),showlegend=True)
            st.plotly_chart(_plot_style(fig,380,80),use_container_width=True,key='vop_cohort_donut')
        else:
            st.info('La composición de EVA / SUPERNOVA medida requiere una cohorte con tonometría.')
    st.caption('Las barras de comparación utilizan el **mismo subconjunto con VOP medida** cuando está disponible. Los resultados teóricos de ePWV no sustituyen una prevalencia observada.')

    if n:
        st.markdown('#### Concordancia y discordancia con el fenotipo medido')
        choice=st.selectbox('Seleccionar ecuación',list(MODEL_SHORT.keys()),format_func=lambda k:MODEL_SHORT[k],key='vop_heat_model')
        mat=pd.crosstab(pd.Categorical(measured['Fenotipo_VOP_medida'],categories=PHENOTYPES),
                        pd.Categorical(measured[f'Fenotipo_teorico_{choice}'],categories=PHENOTYPES),dropna=False)
        mat=mat.reindex(index=PHENOTYPES,columns=PHENOTYPES,fill_value=0)
        heat=go.Figure(data=go.Heatmap(z=mat.values,x=list(PHENOTYPES),y=list(PHENOTYPES),
                colorscale=[[0,'#F1F5FA'],[.35,'#A6C7C4'],[1,C['arg']]],
                text=mat.values,texttemplate='%{text}',textfont=dict(size=16),showscale=False,
                hovertemplate='VOP medida: %{y}<br>Estimación teórica: %{x}<br>N=%{z}<extra></extra>'))
        heat.update_layout(title=f'Matriz de 3 fenotipos · {MODEL_SHORT[choice]}',
                           xaxis_title='Estimación teórica',yaxis_title='VOP medida')
        heat.update_yaxes(autorange='reversed')
        left,right=st.columns([1.07,1],gap='large')
        with left:
            st.plotly_chart(_plot_style(heat,365,68),use_container_width=True,key='vop_heatmap')
        with right:
            st.markdown('**Coincidencia categórica y errores**')
            st.dataframe(summary.round(2),hide_index=True,use_container_width=True)
            st.caption('Kappa: acuerdo descriptivo de etiquetas construidas con umbrales de VOP medida; no valida los puntos de corte de ePWV.')
        ages=[]
        for label,low,high in AGE_GROUPS:
            sub=measured[measured.Edad.between(low,high-1)]
            for cat in PHENOTYPES:
                ages.append({'Edad':label,'Fenotipo':cat,'Porcentaje':100*(sub.Fenotipo_VOP_medida==cat).mean() if len(sub) else 0,
                             'N':int((sub.Fenotipo_VOP_medida==cat).sum()),'Total':len(sub)})
        fig=px.bar(pd.DataFrame(ages),x='Edad',y='Porcentaje',color='Fenotipo',barmode='stack',
            color_discrete_map=COLORS,category_orders={'Fenotipo':list(PHENOTYPES)},
            custom_data=['N','Total'],title='Fenotipos de tonometría por grupo de edad')
        fig.update_traces(hovertemplate='Edad %{x}<br>%{fullData.name}: %{y:.1f}%<br>N=%{customdata[0]} / %{customdata[1]}<extra></extra>')
        fig.update_layout(yaxis_title='Porcentaje (%)',xaxis_title='Edad (años)',legend_title='')
        fig.update_yaxes(range=[0,100])
        st.plotly_chart(_plot_style(fig,340,76),use_container_width=True,key='vop_age_strata')
    with st.expander('Tabla completa de estratos y auditoría',expanded=False):
        st.dataframe(strata.round(2),use_container_width=True,hide_index=True)
        if n:st.dataframe(summary.round(2),use_container_width=True,hide_index=True)
    st.download_button('⬇️ Descargar fenotipos y concordancia (CSV)',
           data.to_csv(index=False,sep=';',decimal=',').encode('utf-8-sig'),
           file_name='VOP_ARG_fenotipos_y_concordancia.csv',mime='text/csv',key='vop_aging_csv')
    st.caption('Esta clasificación en tres grupos es un criterio de investigación, no una definición universal de EVA/SUPERNOVA ni edad vascular en años. No validar la exactitud de las ecuaciones usando la misma cohorte con la que se entrenaron.')