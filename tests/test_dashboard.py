"""Comprobación de componentes de visualización, si Streamlit está instalado."""
import pytest
st = pytest.importorskip('streamlit')
from aging import case_aging
from aging_ui import make_age_nomogram, make_model_comparison, make_z_map, _pdf_patient
from engine import calculate


def test_nomogram_tracks_reference_per_age():
    r=calculate(55,'Masculino',125,75,8.5)
    a=case_aging(r,10,90)
    fig=make_age_nomogram(r,a,10,90)
    assert list(fig.data[0].x)[0]==9
    assert list(fig.data[0].x)[-1]==87
    assert fig.data[0].y[55-9]==pytest.approx(a['Umbral_SUPERNOVA_m_s'])
    assert fig.data[1].y[55-9]==pytest.approx(a['Umbral_EVA_m_s'])


def test_measured_and_model_points_are_distinct():
    r=calculate(55,'Masculino',125,75,8.7)
    a=case_aging(r)
    f=make_z_map(r,a)
    assert len(f.data)==4
    assert f.data[0].marker.symbol=='diamond'
    assert all(t.marker.symbol=='circle-open' for t in f.data[1:])
    g=make_model_comparison(r)
    assert len(g.data[0].x)==4


def test_no_measured_phenotype_in_chart():
    r=calculate(55,'Masculino',125,75)
    a=case_aging(r)
    assert a['Fenotipo_VOP_medida'] is None
    f=make_z_map(r,a)
    assert len(f.data)==3


def test_pdf_export():
    r=calculate(55,'Masculino',125,75,8.7)
    pdf=_pdf_patient(r,case_aging(r))
    assert pdf[:4]==b'%PDF'
    assert len(pdf)>2000