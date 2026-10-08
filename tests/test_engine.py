import math
import pandas as pd
import pytest
from engine import calculate, metrics, normalized_sex, analyze_rows


def test_reference_example():
    out = calculate(55, "Masculino", 125, 75)
    assert out["PAM_0_4"] == 95
    assert out["ePWV_ARG"] == pytest.approx(7.795826883, abs=1e-8)
    assert out["ePWV_Europa_sana"] == pytest.approx(8.748, abs=1e-8)
    assert out["Diaz_percentil_VOP_medida"] is None


def test_input_sex_codes():
    assert normalized_sex(1) == "Masculino"
    assert normalized_sex(2) == "Femenino"
    assert normalized_sex("M") == "Masculino"


def test_measured_percentile_distinct():
    a = calculate(50, "Femenino", 120, 75, vop_medida=7.2)
    assert a["Diaz_percentil_VOP_medida"] > 0
    assert a["Diaz_percentil_VOP_medida"] < 100
    assert a["Error_ARG"] == pytest.approx(a["ePWV_ARG"] - 7.2)


def test_invalid_age_and_pressure():
    with pytest.raises(ValueError):
        calculate(92, "Masculino", 120, 80)
    with pytest.raises(ValueError):
        calculate(40, "Masculino", 95, 100)


def test_bland_altman_metrics():
    m = metrics([5, 6, 7], [6, 7, 8])
    assert m["Sesgo (m/s)"] == 1
    assert m["MAE (m/s)"] == 1
    assert m["RMSE (m/s)"] == 1
    assert m["R²"] == pytest.approx(-.5)


def test_batch_rejections():
    df = pd.DataFrame({"edad":[55,200], "sexo":[1,2], "pas":[125,125],"pad":[75,75]})
    ok,bad=analyze_rows(df,{"Edad":"edad","Sexo":"sexo","PAS":"pas","PAD":"pad","VOP":None,"ID":None})
    assert len(ok)==1 and len(bad)==1

from patterns import reference_band, evaluate_patterns, BAND_ORDER


def test_bandas_en_limites():
    assert reference_band(5.99,6,8,9)=="<P50"
    assert reference_band(6,6,8,9)=="P50–<P90"
    assert reference_band(8,6,8,9)=="P90–<P95"
    assert reference_band(9,6,8,9)=="≥P95"


def test_patrones_sin_medicion():
    r=calculate(55,"Masculino",125,75)
    assert r["Banda_VOP_medida_Diaz"] is None
    assert r["Modelo_mas_cercano_medida"] is None
    assert r["Amplitud_entre_modelos_m_s"] >= 0
    assert r["Delta_Europa_sana_menos_ARG_m_s"] == pytest.approx(r["ePWV_Europa_sana"]-r["ePWV_ARG"])
    assert r["Patron_modelos"] in ("Bandas coincidentes", "Bandas discordantes")


def test_patron_subestimacion_hipotetica():
    r=calculate(55,"Femenino",125,75)
    r["VOP_medida"] = r["Diaz_P95"] + 1
    for key in ["ePWV_ARG","ePWV_Europa_sana","ePWV_Europa_riesgo"]:
        r[key]=r["Diaz_media_normativa"]
    p=evaluate_patterns(r)
    assert p["Banda_VOP_medida_Diaz"] == "≥P95"
    assert "no señalada" in p["Patron_ajuste_con_medida"]
    assert all(p[k] for k in ["Concordancia_banda_ARG", "Concordancia_banda_Europa_sana", "Concordancia_banda_Europa_riesgo"]) is False


def test_signo_diferencias_y_margen():
    r=calculate(60,"Masculino",125,70)
    a=evaluate_patterns(r,0.0)
    b=evaluate_patterns(r,10.0)
    assert a["Discrepancia_supera_margen"]
    assert not b["Discrepancia_supera_margen"]


def test_pdf_individual_con_patrones():
    # ReportLab output smoke test from app is not imported here (Streamlit top-level).
    r=calculate(55,"Femenino",123,76,9.1)
    assert isinstance(r["Banda_VOP_medida_Diaz"],str)
