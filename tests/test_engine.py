from engine import calculate, metrics
def test_example():
    d=calculate(55,'Masculino',125,75)
    assert d['PAM']==95
    assert abs(d['ePWV_ARG']-7.795826883)<1e-6
    assert abs(d['ePWV_Europa_sana']-8.748)<1e-6
def test_percentile_only_measured():
    assert calculate(55,'Femenino',125,75)['Percentil_medida'] is None
    assert calculate(55,'Femenino',125,75,7)['Percentil_medida'] is not None
def test_metrics():
    assert metrics([5,6,7],[6,7,8])['RMSE']==1

from patterns import reference_band, evaluate_patterns, BAND_ORDER

def test_reference_band_boundaries():
    assert reference_band(5.9,6,8,9) == "<P50"
    assert reference_band(6,6,8,9) == "P50–<P90"
    assert reference_band(8,6,8,9) == "P90–<P95"
    assert reference_band(9,6,8,9) == "≥P95"

def test_estimated_patterns_not_measured_percentiles():
    d=calculate(55,'Masculino',125,75)
    assert d['Banda_VOP_medida_Diaz'] is None
    assert d['Modelo_mas_cercano_medida'] is None
    assert d['Delta_Europa_sana_menos_ARG_m_s'] == d['ePWV_Europa_sana']-d['ePWV_ARG']
    assert d['Amplitud_entre_modelos_m_s'] >= 0

def test_measured_high_not_detected():
    d=calculate(55,'Femenino',125,75)
    d['VOP_medida']=d['Diaz_P95']+1
    for k in ('ePWV_ARG','ePWV_Europa_sana','ePWV_Europa_riesgo'):
        d[k]=d['Diaz_media']
    p=evaluate_patterns(d)
    assert p['Banda_VOP_medida_Diaz']=='≥P95'
    assert 'no señalada' in p['Patron_ajuste_con_medida']

def test_exploratory_tolerance():
    d=calculate(60,'Masculino',125,70)
    assert evaluate_patterns(d,0)['Discrepancia_supera_margen']
    assert not evaluate_patterns(d,10)['Discrepancia_supera_margen']
