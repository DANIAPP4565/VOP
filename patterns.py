"""Patrones DESCRIPTIVOS: referencia saludable de VOP MEDIDA vs estimaciones.

No asigna diagnóstico de rigidez arterial a una ePWV ni valida equivalencia
entre percentiles de VOP medida y bandas de ePWV estimada.
"""
from __future__ import annotations

import math

MODELS = (
    ("ePWV_ARG", "Argentina candidata", "Banda_ARG_vs_Diaz"),
    ("ePWV_Europa_sana", "Europa sana", "Banda_Europa_sana_vs_Diaz"),
    ("ePWV_Europa_riesgo", "Europa factores de riesgo", "Banda_Europa_riesgo_vs_Diaz"),
)
BAND_ORDER = ("<P50", "P50–<P90", "P90–<P95", "≥P95")


def reference_band(value: float, median: float, p90: float, p95: float) -> str:
    """Ubicación numérica frente a referencias de Díaz, no diagnóstico."""
    vals = [value, median, p90, p95]
    if not all(math.isfinite(float(v)) for v in vals) or not median < p90 < p95:
        raise ValueError("Valores de referencia inválidos")
    if value < median:
        return BAND_ORDER[0]
    if value < p90:
        return BAND_ORDER[1]
    if value < p95:
        return BAND_ORDER[2]
    return BAND_ORDER[3]


def direction(delta: float, tolerance: float, higher: str, lower: str) -> str:
    if abs(delta) <= tolerance:
        return "Diferencia dentro del margen descriptivo"
    return higher if delta > 0 else lower


def evaluate_patterns(result: dict, tolerance: float = 1.0) -> dict:
    """Bandas basadas en valores de VOP medida de Díaz (2018).

    Para ePWV son SOLO una comparación de magnitudes con umbrales normativos.
    No produce un verdadero percentil de rigidez de una ePWV estimada.
    """
    if not 0 <= tolerance <= 10 or not math.isfinite(tolerance):
        raise ValueError("El margen descriptivo debe ser de 0 a 10 m/s")
    p50 = float(result.get("Diaz_media_normativa", result.get("Diaz_media")))
    p90 = float(result["Diaz_P90"])
    p95 = float(result["Diaz_P95"])
    values = {key: float(result[key]) for key, _, _ in MODELS}
    bands = {band_col: reference_band(values[key], p50, p90, p95)
             for key, _, band_col in MODELS}
    level_spread = len(set(bands.values()))
    delta_sana = values["ePWV_Europa_sana"] - values["ePWV_ARG"]
    delta_riesgo = values["ePWV_Europa_riesgo"] - values["ePWV_ARG"]
    spread = max(values.values()) - min(values.values())
    out = {
        **bands,
        "Patron_modelos": "Bandas coincidentes" if level_spread == 1 else "Bandas discordantes",
        "Numero_bandas_estimadas": level_spread,
        "Amplitud_entre_modelos_m_s": spread,
        "Discrepancia_supera_margen": spread > tolerance,
        "Margen_descriptivo_m_s": tolerance,
        "Delta_Europa_sana_menos_ARG_m_s": delta_sana,
        "Delta_Europa_riesgo_menos_ARG_m_s": delta_riesgo,
        "Delta_Europa_riesgo_menos_sana_m_s": values["ePWV_Europa_riesgo"] - values["ePWV_Europa_sana"],
        "Direccion_Europa_sana_vs_ARG": direction(delta_sana, tolerance,
            "Europa sana mayor", "Argentina candidata mayor"),
        "Direccion_Europa_riesgo_vs_ARG": direction(delta_riesgo, tolerance,
            "Europa con FR mayor", "Argentina candidata mayor"),
        "Banda_VOP_medida_Diaz": None,
        "Patron_ajuste_con_medida": None,
        "Modelo_mas_cercano_medida": None,
    }
    measured = result.get("VOP_medida")
    if measured is not None:
        measured = float(measured)
        actual_band = reference_band(measured, p50, p90, p95)
        out["Banda_VOP_medida_Diaz"] = actual_band
        distances = {label: abs(value - measured)
                     for (key, label, _), value in zip(MODELS, values.values())}
        nearest = min(distances.values())
        out["Modelo_mas_cercano_medida"] = " / ".join(
            label for label, val in distances.items() if math.isclose(val, nearest, abs_tol=1e-9))
        above_measured = measured >= p90
        estimated_above = [values[key] >= p90 for key, _, _ in MODELS]
        if above_measured and not any(estimated_above):
            out["Patron_ajuste_con_medida"] = "Elevación referencial medida no señalada por las estimaciones"
        elif not above_measured and all(estimated_above):
            out["Patron_ajuste_con_medida"] = "Estimaciones elevadas sin elevación referencial medida"
        elif actual_band in bands.values() and len(set(bands.values())) == 1:
            out["Patron_ajuste_con_medida"] = "Bandas de las tres estimaciones coinciden con la medida"
        else:
            out["Patron_ajuste_con_medida"] = "Concordancia parcial / discordancia con la medida"
        for key, label, band_col in MODELS:
            model_tag = {"ePWV_ARG":"ARG", "ePWV_Europa_sana":"Europa_sana", "ePWV_Europa_riesgo":"Europa_riesgo"}[key]
            out["Concordancia_banda_" + model_tag] = (bands[band_col] == actual_band)
            out["Error_abs_" + model_tag] = abs(values[key] - measured)
    return out
