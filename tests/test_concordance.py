"""Pruebas del módulo exploratorio de concordancia."""
import pandas as pd
import pytest
from engine import calculate
from concordance import analyze_case,confusion,enrich,summarize

def synthetic(measured=None, vals=(7,8,10)):
    return {'Diaz_P90':9.,'Diaz_P95':10.,'VOP_medida':measured,
            'ePWV_ARG':vals[0],'ePWV_Europa_sana':vals[1],'ePWV_Europa_riesgo':vals[2],
            'Edad':55,'Sexo':'Masculino'}

def test_no_medicion_no_diagnosticar():
    d=analyze_case(synthetic())
    assert d['VOP_medida_elevada_ref'] is None
    assert d['Acuerdo_binario_ARG'] is None
    assert d['Conteo_modelos_elevados']==1

def test_p90_y_p95_limites():
    assert analyze_case(synthetic(9.))['VOP_medida_elevada_ref'] is True
    assert analyze_case(synthetic(9.),cutoff=95)['VOP_medida_elevada_ref'] is False
    assert analyze_case(synthetic(10.),cutoff=95)['VOP_medida_elevada_ref'] is True

def test_elevacion_medida_omitida():
    d=analyze_case(synthetic(10.8,(7,8,8)))
    assert d['Conteo_modelos_elevados']==0
    assert d['Patron_medida_estimadas']=='Elevación medida omitida por los tres modelos'

def test_alertas_estimada_sin_medida():
    d=analyze_case(synthetic(8.,(9,10,11)))
    assert d['Conteo_modelos_elevados']==3
    assert 'alertas de los tres' in d['Patron_medida_estimadas']

def test_concordancia_parcial_errores():
    d=analyze_case(synthetic(9.5,(7,10,10.5)),margin=1.)
    assert d['Conteo_modelos_elevados']==2
    assert d['Coincide_mayoria_con_medida'] is True
    assert d['Modelo_menor_error']=='Europa sana'
    assert d['Error_firmado_ARG_m_s']==pytest.approx(-2.5)
    assert d['Diferencia_mayor_margen_EU_SANA'] is False

def test_confusion_y_division_por_cero():
    d=confusion([True,True,False,False],[True,False,True,False])
    assert [d[k] for k in ('VP','FN','FP','VN')]==[1,1,1,1]
    assert d['Sensibilidad_%']==50
    e=confusion([False,False],[False,False])
    assert e['Sensibilidad_%'] is None
    assert e['VPP_%'] is None

def test_summary_excluye_sin_medicion():
    inputs=pd.DataFrame([synthetic(9.2,(7,8,8)),synthetic(8,(7,9.2,9.5)),synthetic(None,(10,10,10))])
    e,table,pairs,ages=summarize(inputs)
    assert len(e)==3 and len(pairs)==3
    assert table.iloc[0]['N']==2
    assert table.iloc[0]['FN']==1
    assert table.iloc[0]['VN']==1
    assert ages.iloc[0]['N_medidos']==2
    assert e['Coincidencia_3_modelos'].sum()==2

def test_engine_incorpora_campos():
    r=calculate(55,'Masculino',125,75,10)
    assert r['Umbral_Diaz_usado']=='P90'
    assert r['VOP_medida_disponible'] is True

def test_enrich_sin_columnas_duplicadas():
    r1=calculate(30,'Femenino',115,73)
    r2=calculate(70,'Masculino',120,75)
    e=enrich(pd.DataFrame([r1,r2]),cutoff=95)
    assert e.columns.is_unique
    assert e['Umbral_Diaz_usado'].tolist()==['P95','P95']
    assert not e['VOP_medida_disponible'].any()

def test_invalid_parameters():
    with pytest.raises(ValueError):analyze_case(synthetic(),cutoff=92)
    with pytest.raises(ValueError):analyze_case(synthetic(),margin=-1)
