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
