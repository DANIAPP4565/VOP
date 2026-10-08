"""Concordancia EXPLORATORIA de ePWV con VOP carótido-femoral medida.

Los umbrales de Díaz (2018) provienen de sujetos saludables y describen
la distribución de VOP *medida*. Aplicarlos a ePWV estimada sirve SOLO
como contraste numérico: no produce diagnósticos ni predicción validada.
"""
from __future__ import annotations
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
AGE_GROUPS = (("9–20", 9, 21), ("21–39", 21, 40), ("40–59", 40, 60),
              ("60–69", 60, 70), ("≥70", 70, 88))


def _has_number(v):
    try:
        return v is not None and isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _percent(num, denom):
    return 100 * num / denom if denom else None


def analyze_case(record: dict, cutoff: int = 90, margin: float = 1.0) -> dict:
    """Retorna banderas de acuerdo descriptivo y discrepancias con medida.

    cutoff: P90 o P95 de Díaz, diferente en cada paciente por edad/sexo.
    margin: diferencia absoluta exploratoria en m/s; no umbral diagnóstico.
    """
    if cutoff not in (90, 95):
        raise ValueError('Percentil de comparación: 90 o 95.')
    if not _has_number(margin) or not 0 <= float(margin) <= 10:
        raise ValueError('Margen exploratorio entre 0 y 10 m/s.')
    threshold = float(record[f'Diaz_P{cutoff}'])
    if not isfinite(threshold):
        raise ValueError('Umbral de Díaz ausente.')
    estimated = {key: float(record[field]) for key, (field, _) in MODEL_FIELDS.items()}
    if not all(isfinite(v) for v in estimated.values()):
        raise ValueError('Alguna estimación no es numérica.')
    flags = {k: v >= threshold for k, v in estimated.items()}
    count = sum(flags.values())
    max_spread = max(estimated.values()) - min(estimated.values())
    measured_raw = record.get('VOP_medida')
    measured = float(measured_raw) if _has_number(measured_raw) else None
    if measured is None:
        status = 'Sin VOP medida: no evaluable'
        high_measured = None
    else:
        high_measured = measured >= threshold
        if high_measured and count == 0:
            status = 'Elevación medida omitida por los tres modelos'
        elif high_measured and count in (1, 2):
            status = 'Elevación medida: identificación parcial de modelos'
        elif high_measured and count == 3:
            status = 'Elevación medida: coincidencia de los tres modelos'
        elif not high_measured and count == 0:
            status = 'Sin elevación medida: coincidencia de los tres modelos'
        elif not high_measured and count in (1, 2):
            status = 'Sin elevación medida: alertas estimadas parciales'
        else:
            status = 'Sin elevación medida: alertas de los tres modelos'
    row = {
        'Umbral_Diaz_usado': f'P{cutoff}',
        'Valor_umbral_m_s': threshold,
        'VOP_medida_disponible': measured is not None,
        'VOP_medida_elevada_ref': high_measured,
        'Conteo_modelos_elevados': count,
        'Voto_mayoria_estimados': count >= 2,
        'Consenso_binario_estimados': '3/3 elevada' if count == 3 else '3/3 no elevada' if count == 0 else 'Sin consenso 3/3',
        'Coincidencia_3_modelos': count in (0, 3),
        'Amplitud_estimaciones_m_s': max_spread,
        'Dispersión_supera_margen': max_spread > margin,
        'Patron_medida_estimadas': status,
        'Coincide_mayoria_con_medida': (count >= 2) == high_measured if measured is not None else None,
    }
    for key, val in estimated.items():
        row[f'Eleva_num_{key}'] = flags[key]
        row[f'Delta_{key}_a_P{cutoff}_m_s'] = val - threshold
        row[f'Error_firmado_{key}_m_s'] = val - measured if measured is not None else None
        row[f'Error_absoluto_{key}_m_s'] = abs(val - measured) if measured is not None else None
        row[f'Diferencia_mayor_margen_{key}'] = abs(val - measured) > margin if measured is not None else None
        row[f'Acuerdo_binario_{key}'] = flags[key] == high_measured if measured is not None else None
        row[f'Estado_comparativo_{key}'] = (
            'No evaluable (sin medición)' if measured is None else
            'Coincide con medición (referencial)' if flags[key] == high_measured else
            'Elevación medida no señalada' if high_measured else
            'Elevación estimada no observada en medición'
        )
    if measured is not None:
        differences = {k: abs(val - measured) for k, val in estimated.items()}
        best = min(differences.values())
        row['Modelo_menor_error'] = ', '.join(MODEL_FIELDS[k][1] for k,v in differences.items() if abs(v-best) <= 1e-9)
    else:
        row['Modelo_menor_error'] = None
    return row


def enrich(data: pd.DataFrame, cutoff: int = 90, margin: float = 1.0) -> pd.DataFrame:
    """No altera origen. Resultados para todas las filas con umbrales por sujeto."""
    if data.empty:
        return data.copy()
    extra = pd.DataFrame([analyze_case(rec, cutoff, margin) for rec in data.to_dict(orient='records')],
                         index=data.index)
    return pd.concat([data.drop(columns=extra.columns, errors="ignore").copy(), extra], axis=1)


def confusion(measured: pd.Series, predicted: pd.Series) -> dict:
    """Tabla 2x2: positivo significa >=P90/P95, NO diagnóstico clínico.

    Sensibilidad/especificidad son descriptivas frente a etiqueta referencial medida.
    """
    y = np.asarray(measured, dtype=bool)
    p = np.asarray(predicted, dtype=bool)
    if len(y) != len(p):
        raise ValueError('Tamaño de arreglos diferente.')
    tp=int(np.sum(y&p));fn=int(np.sum(y&~p));fp=int(np.sum(~y&p));tn=int(np.sum(~y&~p))
    return {'N':len(y),'VP':tp,'FN':fn,'FP':fp,'VN':tn,
            'Acuerdo_%':_percent(tp+tn,len(y)),
            'Sensibilidad_%':_percent(tp,tp+fn),
            'Especificidad_%':_percent(tn,tn+fp),
            'VPP_%':_percent(tp,tp+fp),
            'VPN_%':_percent(tn,tn+fn)}


def _kappa(a: pd.Series, b: pd.Series):
    """Kappa de Cohen para acuerdo binario, indefinido si pe=1."""
    aa = np.asarray(a, dtype=bool);bb = np.asarray(b, dtype=bool)
    if not len(aa):return None
    po=np.mean(aa==bb)
    pa=float(np.mean(aa));pb=float(np.mean(bb))
    pe=pa*pb+(1-pa)*(1-pb)
    return (float((po-pe)/(1-pe)) if (1-pe)>1e-12 else None)


def summarize(data: pd.DataFrame, cutoff: int = 90, margin: float = 1.0):
    """Devuelve enriquecida, tabla de modelos, concordancia par a par y estratos.

    Denominadores de diagnóstico aparente incluyen SOLO filas con VOP medida.
    No existe prueba de validación externa implicada por estos resultados.
    """
    enriched = enrich(data, cutoff, margin)
    if enriched.empty:
        return enriched, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    paired = enriched.loc[enriched['VOP_medida_disponible']].copy()
    rows=[]
    for key,(field,name) in MODEL_FIELDS.items():
        counts=confusion(paired['VOP_medida_elevada_ref'],paired[f'Eleva_num_{key}']) if len(paired) else None
        rows.append({'Modelo':name,'Estudios_con_medida':len(paired),
                     **(counts or {'N':0,'VP':None,'FN':None,'FP':None,'VN':None,'Acuerdo_%':None,
                                    'Sensibilidad_%':None,'Especificidad_%':None,'VPP_%':None,'VPN_%':None}),
                     'Sesgo_m_s':float(paired[f'Error_firmado_{key}_m_s'].mean()) if len(paired) else None,
                     'MAE_m_s':float(paired[f'Error_absoluto_{key}_m_s'].mean()) if len(paired) else None,
                     'Fraccion_error_mayor_margen_%':_percent(
                         int(paired[f'Diferencia_mayor_margen_{key}'].sum()),len(paired)) if len(paired) else None})
    between=[]
    for ka,kb in combinations(MODEL_KEYS,2):
        a=enriched[f'Eleva_num_{ka}'];b=enriched[f'Eleva_num_{kb}']
        between.append({'Pareja':f'{MODEL_FIELDS[ka][1]} vs {MODEL_FIELDS[kb][1]}',
                        'N':len(enriched),'Acuerdo_binario_%':float(100*(a==b).mean()),
                        'Kappa_binaria':_kappa(a,b),
                        'Diferencia_media_m_s':float((enriched[MODEL_FIELDS[ka][0]]-enriched[MODEL_FIELDS[kb][0]]).mean())})
    subgroup=[]
    groups=[('Total',enriched)]
    for label,lo,hi in AGE_GROUPS:
        groups.append((f'Edad {label}',enriched[enriched.Edad.ge(lo)&enriched.Edad.lt(hi)]))
    for sex in ('Masculino','Femenino'):
        groups.append((f'Sexo {sex}',enriched[enriched.Sexo==sex]))
    for label,group in groups:
        if group.empty:continue
        with_meas=group[group['VOP_medida_disponible']]
        subgroup.append({'Estrato':label,'N':len(group),'N_medidos':len(with_meas),
                         'VOP_medida_elevada_%':_percent(int(with_meas['VOP_medida_elevada_ref'].sum()),len(with_meas)) if len(with_meas) else None,
                         'Modelos_consenso_3_3_%':float(100*group['Coincidencia_3_modelos'].mean()),
                         'Elevacion_medida_omitida_todos_N':int((with_meas['Patron_medida_estimadas']=='Elevación medida omitida por los tres modelos').sum()) if len(with_meas) else 0,
                         'Alertas_3_modelos_sin_elevacion_medida_N':int((with_meas['Patron_medida_estimadas']=='Sin elevación medida: alertas de los tres modelos').sum()) if len(with_meas) else 0})
    return enriched,pd.DataFrame(rows),pd.DataFrame(between),pd.DataFrame(subgroup)
