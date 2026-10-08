"""Concordancia descriptiva de ePWV versus VOP medida. NO diagnóstico clínico."""
from itertools import combinations
from math import isfinite
import numpy as np
import pandas as pd

MODEL_FIELDS = {
    'ARG': ('ePWV_ARG', 'Argentina candidata'),
    'EU_SANA': ('ePWV_Europa_sana', 'Europa sana'),
    'EU_FR': ('ePWV_Europa_riesgo', 'Europa factores de riesgo'),
}
MODEL_KEYS = tuple(MODEL_FIELDS)
AGE_GROUPS = (('9–20',9,21),('21–39',21,40),('40–59',40,60),('60–69',60,70),('≥70',70,88))

def _has_number(v):
    try: return v is not None and isfinite(float(v))
    except (TypeError,ValueError): return False

def _percent(n,d):
    return 100*n/d if d else None

def analyze_case(record: dict, cutoff: int=90, margin: float=1.0) -> dict:
    """Compara P90 o P95 de Díaz para VOP medida con señales NUMÉRICAS de ePWV."""
    if cutoff not in (90,95): raise ValueError('Percentil de comparación: P90 o P95.')
    if not _has_number(margin) or not 0<=margin<=10: raise ValueError('Margen descriptivo 0–10 m/s.')
    threshold = float(record[f'Diaz_P{cutoff}'])
    if not isfinite(threshold): raise ValueError('Umbral de referencia no válido.')
    values={k:float(record[v[0]]) for k,v in MODEL_FIELDS.items()}
    if not all(isfinite(v) for v in values.values()): raise ValueError('Valores estimados no válidos.')
    flags={k:v>=threshold for k,v in values.items()}
    count=sum(flags.values())
    spread=max(values.values())-min(values.values())
    raw=record.get('VOP_medida')
    measured=float(raw) if _has_number(raw) else None
    if measured is None:
        high_measured=None
        state='Sin VOP medida: no evaluable'
    else:
        high_measured=measured>=threshold
        if high_measured and count==0: state='Elevación medida omitida por los tres modelos'
        elif high_measured and count<3: state='Elevación medida: identificación parcial de modelos'
        elif high_measured: state='Elevación medida: coincidencia de los tres modelos'
        elif count==0: state='Sin elevación medida: coincidencia de los tres modelos'
        elif count<3: state='Sin elevación medida: alertas estimadas parciales'
        else: state='Sin elevación medida: alertas de los tres modelos'
    out={
       'Umbral_Diaz_usado':f'P{cutoff}','Valor_umbral_m_s':threshold,
       'VOP_medida_disponible':measured is not None,
       'VOP_medida_elevada_ref':high_measured,
       'Conteo_modelos_elevados':count,'Voto_mayoria_estimados':count>=2,
       'Consenso_binario_estimados':'3/3 elevada' if count==3 else '3/3 no elevada' if count==0 else 'Sin consenso 3/3',
       'Coincidencia_3_modelos':count in (0,3),
       'Amplitud_estimaciones_m_s':spread,
       'Dispersión_supera_margen':spread>margin,
       'Patron_medida_estimadas':state,
       'Coincide_mayoria_con_medida':(count>=2)==high_measured if measured is not None else None,
    }
    for k,v in values.items():
        out[f'Eleva_num_{k}']=flags[k]
        out[f'Delta_{k}_a_P{cutoff}_m_s']=v-threshold
        out[f'Error_firmado_{k}_m_s']=v-measured if measured is not None else None
        out[f'Error_absoluto_{k}_m_s']=abs(v-measured) if measured is not None else None
        out[f'Diferencia_mayor_margen_{k}']=abs(v-measured)>margin if measured is not None else None
        out[f'Acuerdo_binario_{k}']=flags[k]==high_measured if measured is not None else None
        out[f'Estado_comparativo_{k}']='No evaluable (sin medición)' if measured is None else (
          'Coincide con medición (referencial)' if flags[k]==high_measured else (
          'Elevación medida no señalada' if high_measured else 'Elevación estimada no observada en medición'))
    if measured is None:
        out['Modelo_menor_error']=None
    else:
        errors={k:abs(v-measured) for k,v in values.items()}
        best=min(errors.values())
        out['Modelo_menor_error']=', '.join(MODEL_FIELDS[k][1] for k,v in errors.items() if abs(v-best)<=1e-9)
    return out

def enrich(data:pd.DataFrame, cutoff:int=90, margin:float=1.0)->pd.DataFrame:
    if data.empty:return data.copy()
    extra=pd.DataFrame([analyze_case(r,cutoff,margin) for r in data.to_dict('records')],index=data.index)
    return pd.concat([data.drop(columns=extra.columns,errors='ignore').copy(),extra],axis=1)

def confusion(measured,predicted)->dict:
    y=np.asarray(measured,dtype=bool); p=np.asarray(predicted,dtype=bool)
    if len(y)!=len(p): raise ValueError('Longitudes diferentes.')
    tp=int(np.sum(y&p));fn=int(np.sum(y&~p));fp=int(np.sum(~y&p));tn=int(np.sum(~y&~p))
    return {'N':len(y),'VP':tp,'FN':fn,'FP':fp,'VN':tn,
            'Acuerdo_%':_percent(tp+tn,len(y)),
            'Sensibilidad_%':_percent(tp,tp+fn),
            'Especificidad_%':_percent(tn,tn+fp),
            'VPP_%':_percent(tp,tp+fp),
            'VPN_%':_percent(tn,tn+fn)}

def _kappa(a,b):
    a=np.asarray(a,dtype=bool);b=np.asarray(b,dtype=bool)
    if not len(a):return None
    po=float(np.mean(a==b))
    pa=float(np.mean(a));pb=float(np.mean(b))
    pe=pa*pb+(1-pa)*(1-pb)
    return (po-pe)/(1-pe) if (1-pe)>1e-12 else None

def summarize(data:pd.DataFrame,cutoff:int=90,margin:float=1.0):
    enriched=enrich(data,cutoff,margin)
    if enriched.empty:return enriched,pd.DataFrame(),pd.DataFrame(),pd.DataFrame()
    paired=enriched.loc[enriched['VOP_medida_disponible']].copy()
    rows=[]
    for key,(field,name) in MODEL_FIELDS.items():
        counts=confusion(paired['VOP_medida_elevada_ref'],paired[f'Eleva_num_{key}']) if len(paired) else {
           'N':0,'VP':None,'FN':None,'FP':None,'VN':None,
           'Acuerdo_%':None,'Sensibilidad_%':None,'Especificidad_%':None,'VPP_%':None,'VPN_%':None}
        rows.append({'Modelo':name,'Estudios_con_medida':len(paired),**counts,
           'Sesgo_m_s':float(paired[f'Error_firmado_{key}_m_s'].mean()) if len(paired) else None,
           'MAE_m_s':float(paired[f'Error_absoluto_{key}_m_s'].mean()) if len(paired) else None,
           'Fraccion_error_mayor_margen_%':_percent(int(paired[f'Diferencia_mayor_margen_{key}'].sum()),len(paired)) if len(paired) else None})
    between=[]
    for ka,kb in combinations(MODEL_KEYS,2):
        a=enriched[f'Eleva_num_{ka}'];b=enriched[f'Eleva_num_{kb}']
        between.append({'Pareja':f'{MODEL_FIELDS[ka][1]} vs {MODEL_FIELDS[kb][1]}',
            'N':len(enriched),'Acuerdo_binario_%':float(100*(a==b).mean()),
            'Kappa_binaria':_kappa(a,b),
            'Diferencia_media_m_s':float((enriched[MODEL_FIELDS[ka][0]]-enriched[MODEL_FIELDS[kb][0]]).mean())})
    groups=[('Total',enriched)]
    for label,lo,hi in AGE_GROUPS:
        groups.append((f'Edad {label}',enriched[enriched.Edad.ge(lo)&enriched.Edad.lt(hi)]))
    for sex in ('Masculino','Femenino'):
        groups.append((f'Sexo {sex}',enriched[enriched.Sexo==sex]))
    strata=[]
    for label,group in groups:
        if group.empty:continue
        med=group[group['VOP_medida_disponible']]
        strata.append({'Estrato':label,'N':len(group),'N_medidos':len(med),
            'VOP_medida_elevada_%':_percent(int(med['VOP_medida_elevada_ref'].sum()),len(med)) if len(med) else None,
            'Modelos_consenso_3_3_%':float(100*group['Coincidencia_3_modelos'].mean()),
            'Elevacion_medida_omitida_todos_N':int((med['Patron_medida_estimadas']=='Elevación medida omitida por los tres modelos').sum()) if len(med) else 0,
            'Alertas_3_modelos_sin_elevacion_medida_N':int((med['Patron_medida_estimadas']=='Sin elevación medida: alertas de los tres modelos').sum()) if len(med) else 0})
    return enriched,pd.DataFrame(rows),pd.DataFrame(between),pd.DataFrame(strata)
