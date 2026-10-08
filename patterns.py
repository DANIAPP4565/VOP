"""Patrones descriptivos de VOP medida y estimada frente a valores normativos de Díaz (2018).

ADVERTENCIA: una ePWV estimada NO tiene un percentil normativo validado.
Las bandas de ePWV son exclusivamente contrastes numéricos con umbrales
basados en VOP carótido-femoral realmente medida.
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

def evaluate_patterns(result: dict, tolerance: float = 1.0) -> dict:
    """Clasificación referencial y contraste descriptivo entre modelos."""
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 10:
        raise ValueError("El margen descriptivo debe ser entre 0 y 10 m/s")
    p50 = float(result.get("Diaz_media_normativa", result.get("Diaz_media")))
    p90 = float(result["Diaz_P90"])
    p95 = float(result["Diaz_P95"])
    values = {key: float(result[key]) for key, _, _ in MODELS}
    bands = {name: reference_band(values[key], p50, p90, p95)
             for key, _, name in MODELS}
    delta_sana = values["ePWV_Europa_sana"] - values["ePWV_ARG"]
    delta_riesgo = values["ePWV_Europa_riesgo"] - values["ePWV_ARG"]
    spread = max(values.values()) - min(values.values())
    out = {
        **bands,
        "Patron_modelos": "Bandas coincidentes" if len(set(bands.values())) == 1 else "Bandas discordantes",
        "Numero_bandas_estimadas": len(set(bands.values())),
        "Amplitud_entre_modelos_m_s": spread,
        "Discrepancia_supera_margen": spread > tolerance,
        "Margen_descriptivo_m_s": tolerance,
        "Delta_Europa_sana_menos_ARG_m_s": delta_sana,
        "Delta_Europa_riesgo_menos_ARG_m_s": delta_riesgo,
        "Delta_Europa_riesgo_menos_sana_m_s": values["ePWV_Europa_riesgo"] - values["ePWV_Europa_sana"],
        "Direccion_Europa_sana_vs_ARG": "Sin diferencia relevante para margen exploratorio"
            if abs(delta_sana) <= tolerance else ("Europa sana mayor" if delta_sana > 0 else "Argentina mayor"),
        "Direccion_Europa_riesgo_vs_ARG": "Sin diferencia relevante para margen exploratorio"
            if abs(delta_riesgo) <= tolerance else ("Europa FR mayor" if delta_riesgo > 0 else "Argentina mayor"),
        "Banda_VOP_medida_Diaz": None,
        "Patron_ajuste_con_medida": None,
        "Modelo_mas_cercano_medida": None,
    }
    measured = result.get("VOP_medida")
    if measured is not None:
        measured = float(measured)
        actual_band = reference_band(measured, p50, p90, p95)
        out["Banda_VOP_medida_Diaz"] = actual_band
        distances = {label: abs(values[key] - measured) for key, label, _ in MODELS}
        nearest = min(distances.values())
        out["Modelo_mas_cercano_medida"] = " / ".join(
            label for label, val in distances.items() if math.isclose(val, nearest, abs_tol=1e-9))
        high_measured = measured >= p90
        high_estimated = [values[key] >= p90 for key, _, _ in MODELS]
        if high_measured and not any(high_estimated):
            pattern = "Elevación referencial medida no señalada por las estimaciones"
        elif not high_measured and all(high_estimated):
            pattern = "Estimaciones elevadas sin elevación referencial medida"
        elif actual_band in bands.values() and len(set(bands.values())) == 1:
            pattern = "Bandas de las tres estimaciones coinciden con la medida"
        else:
            pattern = "Concordancia parcial / discordancia con la medida"
        out["Patron_ajuste_con_medida"] = pattern
        for key, label, band_col in MODELS:
            tag = {"ePWV_ARG":"ARG", "ePWV_Europa_sana":"Europa_sana",
                   "ePWV_Europa_riesgo":"Europa_riesgo"}[key]
            out["Concordancia_banda_" + tag] = bands[band_col] == actual_band
            out["Error_abs_" + tag] = abs(values[key] - measured)
    return out
