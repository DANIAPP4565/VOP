"""Casos frontera y verificaciones de cohortes sin datos clínicos reales."""
import pandas as pd
import pytest
from engine import calculate
from concordance import analyze_case, enrich, confusion, summarize


def synthetic(measured=None, ref=9.0, vals=(7.0,8.0,10.0)):
    return {'Diaz_P90':ref,'Diaz_P95':ref+1, 'VOP_medida':measured,
            'ePWV_ARG':vals[0], 'ePWV_Europa_sana':vals[1], 'ePWV_Europa_riesgo':vals[2],
            'Edad':55,'Sexo':'Masculino'}


def test_no_measured_is_not_diagnosed():
    a=analyze_case(synthetic())
    assert a['VOP_medida_elevada_ref'] is None
    assert a['Patron_medida_estimadas'].startswith('Sin VOP medida')
    assert a['Acuerdo_binario_ARG'] is None
    assert a['Conteo_modelos_elevados']==1


def test_measured_ge_p90_and_p95_boundaries():
    assert analyze_case(synthetic(measured=9.0))['VOP_medida_elevada_ref'] is True
    assert analyze_case(synthetic(measured=9.0),cutoff=95)['VOP_medida_elevada_ref'] is False
    assert analyze_case(synthetic(measured=10.0),cutoff=95)['VOP_medida_elevada_ref'] is True


def test_real_high_all_models_miss():
    a=analyze_case(synthetic(measured=10.8, vals=(7,8,8)))
    assert a['Patron_medida_estimadas']=='Elevación medida omitida por los tres modelos'
    assert a['Conteo_modelos_elevados']==0
    assert a['Coincide_mayoria_con_medida'] is False


def test_real_low_all_models_overpredict():
    a=analyze_case(synthetic(measured=8, vals=(9,10,11)))
    assert a['Patron_medida_estimadas']=='Sin elevación medida: alertas de los tres modelos'
    assert a['Conteo_modelos_elevados']==3
    assert a['Coincide_mayoria_con_medida'] is False


def test_majority_partial_concordance_and_errors():
    a=analyze_case(synthetic(measured=9.5, vals=(7.0,10.0,10.5)),margin=1.0)
    assert a['Conteo_modelos_elevados']==2
    assert a['Coincide_mayoria_con_medida'] is True
    assert a['Modelo_menor_error']=='Europa sana'
    assert a['Error_firmado_ARG_m_s']==pytest.approx(-2.5)
    assert a['Diferencia_mayor_margen_ARG'] is True
    assert a['Diferencia_mayor_margen_EU_SANA'] is False


def test_invalid_cutoff_and_tolerance():
    with pytest.raises(ValueError):analyze_case(synthetic(),cutoff=92)
    with pytest.raises(ValueError):analyze_case(synthetic(),margin=-1)


def test_confusion_counts_and_zero_denominators():
    out=confusion([True,True,False,False],[True,False,True,False])
    assert [out[k] for k in ('VP','FN','FP','VN')]==[1,1,1,1]
    assert out['Sensibilidad_%']==50 and out['Especificidad_%']==50
    absent=confusion([False,False],[False,False])
    assert absent['Sensibilidad_%'] is None and absent['VPP_%'] is None
    assert absent['Especificidad_%']==100


def test_summary_only_measured_in_denominator():
    a=synthetic(measured=9.2,vals=(7,8,8))
    b=synthetic(measured=8,vals=(7,9.2,9.5))
    c=synthetic(measured=None,vals=(10,10,10))
    data=pd.DataFrame([a,b,c]);e,summary,pairs,strata=summarize(data)
    assert len(e)==3 and len(pairs)==3 and len(strata)>=1
    assert summary.loc[summary['Modelo']=='Argentina candidata','N'].iloc[0]==2
    assert summary.loc[0,'FN']==1
    assert summary.loc[0,'VN']==1
    assert e['Coincidencia_3_modelos'].sum()==2
    assert strata.iloc[0]['N_medidos']==2


def test_calculate_includes_concordance_default():
    r=calculate(55,'Masculino',125,75,10)
    assert r['Umbral_Diaz_usado']=='P90'
    assert r['VOP_medida_disponible'] is True
    assert r['VOP_medida_elevada_ref']==(r['VOP_medida']>=r['Diaz_P90'])


def test_enrich_without_measurement():
    r1=calculate(30,'Femenino',114,73)
    r2=calculate(70,'Masculino',120,75)
    e=enrich(pd.DataFrame([r1,r2]),cutoff=95)
    assert e['Umbral_Diaz_usado'].tolist()==['P95','P95']
    assert e['VOP_medida_disponible'].sum()==0
