"""Pruebas de fenotipos EVA/Saludable/SUPERNOVA (datos sintéticos)."""
import pandas as pd
import pytest
from statistics import NormalDist
from aging import classify,case_aging,percentile_cutoffs,evaluate_cohort
from engine import calculate, analyze_rows


def test_percentile_formula_matches_reference():
    a,b=percentile_cutoffs(7,1,10,90)
    assert a==pytest.approx(7+NormalDist().inv_cdf(.1))
    assert b==pytest.approx(7+NormalDist().inv_cdf(.9))
    assert b>a


def test_boundaries_and_order():
    lo,hi=5,9
    assert classify(4.9,lo,hi)=='SUPERNOVA'
    assert classify(5,lo,hi)=='Saludable/esperado'
    assert classify(8.9,lo,hi)=='Saludable/esperado'
    assert classify(9,lo,hi)=='EVA'
    assert classify(None,lo,hi) is None
    assert classify(float('nan'),lo,hi) is None


def test_use_measured_only_for_patient():
    r=calculate(55,'Masculino',125,75)
    assert r['Fenotipo_VOP_medida'] is None
    assert r['Concordancia_medida_estimados'].startswith('No evaluable')
    assert r['Fenotipo_ePWV_estado']=='SIMULACIÓN NO VALIDADA'
    assert r['Umbral_SUPERNOVA_m_s']<r['Umbral_EVA_m_s']


def test_eva_measured():
    r=calculate(55,'Masculino',125,75)
    r=calculate(55,'Masculino',125,75,r['Diaz_P90'])
    assert r['Fenotipo_VOP_medida']=='EVA'
    assert r['Diaz_percentil_VOP_medida']==pytest.approx(90,abs=1e-7)


def test_supernova_measured():
    r=calculate(55,'Femenino',125,75)
    r=calculate(55,'Femenino',125,75,r['Umbral_SUPERNOVA_m_s']-0.1)
    assert r['Fenotipo_VOP_medida']=='SUPERNOVA'


def test_selected_sensitivity_cutoffs():
    r=calculate(60,'Masculino',120,75)
    five=case_aging(r,5,95)
    ten=case_aging(r,10,90)
    assert five['Umbral_SUPERNOVA_m_s']<ten['Umbral_SUPERNOVA_m_s']
    assert five['Umbral_EVA_m_s']>ten['Umbral_EVA_m_s']
    with pytest.raises(ValueError):case_aging(r,25,75)


def test_cohort_measured_only_comparison():
    base=calculate(55,'Masculino',125,75)
    rows=[calculate(55,'Masculino',125,75,base['Umbral_SUPERNOVA_m_s']-0.1),
          calculate(55,'Masculino',125,75,base['Diaz_media_normativa']),
          calculate(55,'Masculino',125,75,base['Diaz_P90']+0.2),
          calculate(55,'Masculino',125,75)]
    data,summary,matrix,strata=evaluate_cohort(pd.DataFrame(rows))
    assert len(data)==4
    assert len(summary)==3
    assert summary['N con medición'].tolist()==[3,3,3]
    assert len(matrix)==27 # 3x3 para cada uno de 3 modelos
    assert set(data['Fenotipo_VOP_medida'].dropna())=={'SUPERNOVA','Saludable/esperado','EVA'}
    assert data.iloc[-1]['N_estimados_coinciden_medida'] is None or pd.isna(data.iloc[-1]['N_estimados_coinciden_medida'])
    assert strata.iloc[0]['N con medición']==3


def test_cohort_without_measured_no_validation():
    r1=calculate(30,'Femenino',115,72)
    r2=calculate(65,'Masculino',124,77)
    _,summary,matrix,strata=evaluate_cohort(pd.DataFrame([r1,r2]))
    assert summary.empty and matrix.empty
    assert strata.iloc[0]['N con medición']==0


def test_sample_excel_batch_has_phenotypes():
    df=pd.DataFrame({'EDAD':[40,50],'SEXO':[1,2],'PAS':[120,140],'PAD':[80,85],
                     'VOP':[None,12.0]})
    mapping={'Edad':'EDAD','Sexo':'SEXO','PAS':'PAS','PAD':'PAD','VOP':'VOP','ID':None}
    okay,bad=analyze_rows(df,mapping)
    assert bad.empty
    assert len(okay)==2
    assert okay.iloc[0]['Fenotipo_VOP_medida'] is None or pd.isna(okay.iloc[0]['Fenotipo_VOP_medida'])
    assert okay.iloc[1]['Fenotipo_VOP_medida']=='EVA'
