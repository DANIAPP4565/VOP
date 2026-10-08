"""Fenotipos de envejecimiento vascular basados en referencia argentina de cfPWV.

Marco de INVESTIGACIÓN, no diagnóstico: fenotipo medido solo cuando existe
cfPWV carótido-femoral tonométrica. Una ePWV estimada NO es equivalente.
Estratificación exploratoria P10/P90; alternativa sensibilidad P5/P95.
Referencias: Díaz et al. J Clin Hypertens 2018 doi:10.1111/jch.13251;
concepto SUPERNOVA / EVA: Bruno et al. Hypertension 2020;
las definiciones de fenotipo no están internacionalmente estandarizadas.
"""
from __future__ import annotations
from itertools import combinations
from math import isfinite
from statistics import NormalDist
from typing import Any
import pandas as pd
import numpy as np

PHENOTYPES = ('SUPERNOVA', 'Saludable/esperado', 'EVA')
MODEL_FIELDS = {
    'ARG': ('ePWV_ARG', 'Argentina candidata'),
    'EU_SANA': ('ePWV_Europa_sana', 'Europa sana'),
    'EU_FR': ('ePWV_Europa_riesgo', 'Europa factores de riesgo'),
}
AGE_GROUPS = [('9–20',9,21),('21–39',21,40),('40–59',40,60),('60–69',60,70),('≥70',70,88)]


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, str) and not value.strip():
        return None
    try:
        v=float(value)
        return v if isfinite(v) else None
    except (ValueError,TypeError):
        return None


def percentile_cutoffs(mu: float, sd: float, lower: int = 10, upper: int = 90) -> tuple[float,float]:
    """Límites por edad/sexo usando media/DE publicadas; no edad vascular invertida."""
    if (lower,upper) not in ((10,90),(5,95)):
        raise ValueError('Solo se admiten P10/P90 o P5/P95 para sensibilidad.')
    if not (isfinite(float(mu)) and isfinite(float(sd)) and float(sd)>0):
        raise ValueError('Media/DE normativas inválidas.')
    return (float(mu)+NormalDist().inv_cdf(lower/100)*float(sd),
            float(mu)+NormalDist().inv_cdf(upper/100)*float(sd))


def classify(value: Any, p_lower: float, p_upper: float) -> str | None:
    """SUPERNOVA: < límite inferior; HVA/esperado: intermedio; EVA: >= superior."""
    v=_number(value)
    if not isfinite(float(p_lower)) or not isfinite(float(p_upper)) or p_lower>=p_upper:
        raise ValueError('Límites normativos inválidos.')
    if v is None:
        return None
    if v < p_lower:return PHENOTYPES[0]
    if v >= p_upper:return PHENOTYPES[2]
    return PHENOTYPES[1]


def case_aging(record: dict, lower: int = 10, upper: int = 90) -> dict:
    """El fenotipo real solamente se asigna a cfPWV MEDIDA.

    Etiquetas para ePWV: simulaciones numéricas sin validación clínica.
    """
    mu=_number(record.get('Diaz_media_normativa',record.get('Diaz_media')))
    sd=_number(record.get('Diaz_DE_normativa',record.get('Diaz_DE')))
    if mu is None or sd is None:raise ValueError('Se requiere referencia Díaz (media y DE).')
    p_lo,p_hi=percentile_cutoffs(mu,sd,lower,upper)
    m=_number(record.get('VOP_medida'))
    actual=classify(m,p_lo,p_hi)
    out={
      'Criterio_EVA':f'P{lower}/P{upper}',
      'Umbral_SUPERNOVA_m_s':p_lo,
      'Umbral_EVA_m_s':p_hi,
      'Fenotipo_VOP_medida':actual,
      'Fenotipo_ePWV_estado':'SIMULACIÓN NO VALIDADA',
      'N_estimados_coinciden_medida':None,
      'Concordancia_3_estimados':'',
      'Concordancia_medida_estimados':'No evaluable: sin cfPWV medida',
      'Acuerdo_fenotipo_3_modelos':None,
      'Modelo_menor_error_fenotipo':None,
    }
    preds={}
    for key,(field,name) in MODEL_FIELDS.items():
        val=_number(record.get(field))
        if val is None:raise ValueError(f'Falta estimación {field}')
        category=classify(val,p_lo,p_hi)
        preds[key]=category
        out[f'Fenotipo_teorico_{key}']=category
        out[f'Fenotipo_teorico_{key}_coincide_medida']=(category==actual) if actual is not None else None
        out[f'Error_{key}_estimada_menos_medida']=val-m if m is not None else None
        out[f'Error_abs_{key}_m_s']=abs(val-m) if m is not None else None
    labels=list(preds.values()); n_unique=len(set(labels))
    out['Concordancia_3_estimados']='3/3 en la misma categoría' if n_unique==1 else ('2/3 en la misma categoría' if n_unique==2 else '3/3 categorías diferentes')
    out['Acuerdo_fenotipo_3_modelos']=(n_unique==1)
    if actual is not None:
        n_matching=sum(v==actual for v in preds.values())
        out['N_estimados_coinciden_medida']=n_matching
        out['Concordancia_medida_estimados']=(
            'Coincidencia categórica 3/3' if n_matching==3 else
            'Coincidencia categórica parcial 2/3' if n_matching==2 else
            'Coincidencia categórica parcial 1/3' if n_matching==1 else
            'Discordancia categórica 0/3')
        errors={key:out[f'Error_abs_{key}_m_s'] for key in MODEL_FIELDS}
        min_err=min(errors.values())
        out['Modelo_menor_error_fenotipo']=', '.join(MODEL_FIELDS[k][1] for k,e in errors.items() if abs(e-min_err)<1e-9)
    return out


def evaluate_cohort(df:pd.DataFrame, lower:int=10,upper:int=90) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    """Datos por sujeto y matrices de acuerdo 3 categorías (sin fuga de datos)."""
    if df.empty:
        return df.copy(),pd.DataFrame(),pd.DataFrame(),pd.DataFrame()
    extra=pd.DataFrame([case_aging(r,lower,upper) for r in df.to_dict('records')],index=df.index)
    data=pd.concat([df.drop(columns=extra.columns,errors='ignore').copy(),extra],axis=1)
    measured=data.loc[data['Fenotipo_VOP_medida'].notna()].copy()
    models=[]; matrices=[]; strata=[]
    if not measured.empty:
        actual=measured['Fenotipo_VOP_medida']
        for key,(field,name) in MODEL_FIELDS.items():
            theor=measured[f'Fenotipo_teorico_{key}']
            agreement=(actual==theor)
            ct=pd.crosstab(pd.Categorical(actual,categories=PHENOTYPES),
                           pd.Categorical(theor,categories=PHENOTYPES),dropna=False)
            ct=ct.reindex(index=PHENOTYPES,columns=PHENOTYPES,fill_value=0)
            for idx in PHENOTYPES:
                for col in PHENOTYPES:
                    matrices.append({'Modelo':name,'Fenotipo medido':idx,'Fenotipo estimado (simulado)':col,'N':int(ct.loc[idx,col])})
            pe=sum(ct.sum(axis=1).iloc[j]*ct.sum(axis=0).iloc[j] for j in range(3))/(len(measured)**2)
            po=float(agreement.mean())
            kappa=(po-pe)/(1-pe) if (1-pe)>1e-12 else None
            n_eva=int((actual=='EVA').sum());eva_missed=int(((actual=='EVA')&(theor!='EVA')).sum())
            n_super=int((actual=='SUPERNOVA').sum()); super_missed=int(((actual=='SUPERNOVA')&(theor!='SUPERNOVA')).sum())
            models.append({'Modelo':name,'N con medición':len(measured),
                           'Coincidencia referencial %':po*100,
                           'Kappa 3 categorías':kappa,
                           'EVA medida N':n_eva,'EVA omitida N':eva_missed,
                           'SUPERNOVA medida N':n_super,'SUPERNOVA omitida N':super_missed,
                           'MAE vs medida (m/s)':float(measured[f'Error_abs_{key}_m_s'].mean()),
                           'Sesgo ePWV – cfPWV (m/s)':float(measured[f'Error_{key}_estimada_menos_medida'].mean())})
    groups=[('Total',data)]
    groups.extend((lab,data[(data['Edad']>=lo)&(data['Edad']<hi)]) for lab,lo,hi in AGE_GROUPS)
    groups.extend((f'Sexo: {lab}',data[data['Sexo']==lab]) for lab in ('Masculino','Femenino'))
    for lab,part in groups:
        if part.empty: continue
        med=part[part.Fenotipo_VOP_medida.notna()]
        strata.append({'Estrato':lab,'N':len(part),'N con medición':len(med),
                       'SUPERNOVA medida N':int((med.Fenotipo_VOP_medida=='SUPERNOVA').sum()),
                       'Saludable/esperado medida N':int((med.Fenotipo_VOP_medida=='Saludable/esperado').sum()),
                       'EVA medida N':int((med.Fenotipo_VOP_medida=='EVA').sum()),
                       'Concordancia 3 estimados %':float(100*part.Acuerdo_fenotipo_3_modelos.mean()),
                       'Concordancia 3/3 vs medida %':float(100*(med.N_estimados_coinciden_medida==3).mean()) if len(med) else None})
    return data,pd.DataFrame(models),pd.DataFrame(matrices),pd.DataFrame(strata)
