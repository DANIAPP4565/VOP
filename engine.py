"""Cálculos reproducibles de ePWV / VOP cf. No es un dispositivo médico validado."""
from __future__ import annotations

from math import log10, sqrt
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from patterns import evaluate_patterns
from concordance import analyze_case
from aging import case_aging

MODEL_VERSION = "ARG-ePWV exploratorio | octubre 2026"
REFERENCE = (
    "Díaz A, Zócalo Y, Bia D, Wray S, Cabrera Fischer E. "
    "J Clin Hypertens. 2018;20:659-671. doi:10.1111/jch.13251"
)


def normalized_sex(value: Any) -> str:
    """Retorna 'Masculino' o 'Femenino'. En la cohorte original 1=M, 2=F."""
    if pd.isna(value):
        raise ValueError("Falta sexo.")
    v = str(value).strip().casefold()
    if v in ("1", "1.0", "m", "masc", "masculino", "h", "hombre", "varón", "varon", "male"):
        return "Masculino"
    if v in ("2", "2.0", "f", "fem", "femenino", "mujer", "female"):
        return "Femenino"
    raise ValueError(f"Sexo no reconocido: {value!r}. Use Masculino/Femenino o 1/2.")


def valid_inputs(edad: float, sexo: Any, pas: float, pad: float, vop: float | None = None):
    vals = [edad, pas, pad] + ([] if vop is None else [vop])
    if any(not np.isfinite(float(x)) for x in vals):
        raise ValueError("Los valores deben ser numéricos y finitos.")
    if not 9 <= edad <= 87:
        raise ValueError("Edad fuera de 9 a 87 años, intervalo de la cohorte de referencia.")
    normalized_sex(sexo)
    if not (50 <= pad <= 180 and 70 <= pas <= 260 and pas > pad):
        raise ValueError("Revisar PAS/PAD: PAS > PAD, PAS 70–260 y PAD 50–180 mmHg.")
    if vop is not None and not 2 <= vop <= 30:
        raise ValueError("VOP medida fuera del rango de control de entrada 2–30 m/s.")


def pam(pas: float, pad: float) -> float:
    """PAM convencional con coeficiente pulsátil 0,4 (no 1/3)."""
    return float(pad + 0.4 * (pas - pad))


def epwv_arg(edad: float, sexo: Any, presion_media: float) -> float:
    male = 1.0 if normalized_sex(sexo) == "Masculino" else 0.0
    return float(
        0.180526 + 0.916427 * log10(edad) + 0.010667 * edad
        + 0.000396061 * edad**2 + 0.133136 * male + 0.043184 * presion_media
    )


def epwv_europe_healthy(edad: float, presion_media: float) -> float:
    return float(
        4.62 - 0.13 * edad + 0.0018 * edad**2
        + 0.0006 * edad * presion_media + 0.0284 * presion_media
    )


def epwv_europe_risk(edad: float, presion_media: float) -> float:
    """Variante 'factores de riesgo' publicada; no usar la columna C errónea del Excel."""
    return float(
        9.587 - 0.402 * edad + 0.004560 * edad**2
        - 2.621e-5 * edad**2 * presion_media
        + 3.176e-3 * edad * presion_media - 1.832e-2 * presion_media
    )


def diaz_normative(edad: float, sexo: Any) -> tuple[float, float]:
    """Media/DE normativas por edad y sexo, no predicción personalizada."""
    if normalized_sex(sexo) == "Femenino":
        mu = 0.062441 + 5.3108 * log10(edad) - 0.09658 * edad + 1.151e-3 * edad**2
        sd = 1.0392 - 0.4128 * sqrt(edad) + 0.08020 * edad - 3.65e-4 * edad**2
    else:
        mu = 1.3942 + 3.4927 * log10(edad) - 0.02436 * edad + 5.698e-4 * edad**2
        sd = -0.04760 + 0.06798 * sqrt(edad) + 0.02987 * edad - 2.091e-4 * edad**2
    if sd <= 0:
        raise ValueError("DE normativa no positiva. Revisar edad y sexo.")
    return float(mu), float(sd)


def calculate(edad: float, sexo: Any, pas: float, pad: float,
              vop_medida: float | None = None, identificador: str = "") -> dict:
    edad, pas, pad = float(edad), float(pas), float(pad)
    if vop_medida is not None:
        vop_medida = float(vop_medida)
    sexo = normalized_sex(sexo)
    valid_inputs(edad, sexo, pas, pad, vop_medida)
    mbp = pam(pas, pad)
    mu, sd = diaz_normative(edad, sexo)
    norm = NormalDist()
    out = {
        "Identificador": str(identificador), "Edad": edad, "Sexo": sexo,
        "PAS": pas, "PAD": pad, "PAM_0_4": mbp,
        "ePWV_ARG": epwv_arg(edad, sexo, mbp),
        "ePWV_Europa_sana": epwv_europe_healthy(edad, mbp),
        "ePWV_Europa_riesgo": epwv_europe_risk(edad, mbp),
        "Diaz_media_normativa": mu, "Diaz_DE_normativa": sd,
        "Diaz_P05": mu + norm.inv_cdf(.05) * sd,
        "Diaz_P10": mu + norm.inv_cdf(.10) * sd,
        "Diaz_P90": mu + norm.inv_cdf(.90) * sd,
        "Diaz_P95": mu + norm.inv_cdf(.95) * sd,
        "VOP_medida": vop_medida,
        "Diaz_Z_VOP_medida": None,
        "Diaz_percentil_VOP_medida": None,
        "Error_ARG": None, "Error_Europa_sana": None, "Error_Europa_riesgo": None,
    }
    if vop_medida is not None:
        z = (vop_medida - mu) / sd
        out["Diaz_Z_VOP_medida"] = z
        out["Diaz_percentil_VOP_medida"] = 100 * norm.cdf(z)
        out["Error_ARG"] = out["ePWV_ARG"] - vop_medida
        out["Error_Europa_sana"] = out["ePWV_Europa_sana"] - vop_medida
        out["Error_Europa_riesgo"] = out["ePWV_Europa_riesgo"] - vop_medida
    out.update(evaluate_patterns(out))
    out.update(case_aging(out))  # Fenotipo de envejecimiento VOP medida vs comparación ePWV
    out.update(analyze_case(out))  # P90 / margen de 1 m/s por defecto
    return out


def metrics(observed: pd.Series | np.ndarray, predicted: pd.Series | np.ndarray) -> dict:
    """Métricas pareadas. Sesgo = estimada - medida."""
    y = np.asarray(observed, dtype=float)
    p = np.asarray(predicted, dtype=float)
    keep = np.isfinite(y) & np.isfinite(p)
    y, p = y[keep], p[keep]
    if len(y) < 2:
        raise ValueError("Se necesitan al menos dos pares medido/estimado.")
    e = p-y
    rmse = float(np.sqrt(np.mean(e**2)))
    sst = float(np.sum((y-y.mean())**2))
    return {
        "N": len(y), "Sesgo (m/s)": float(np.mean(e)),
        "MAE (m/s)": float(np.mean(abs(e))), "RMSE (m/s)": rmse,
        "R²": float(1-np.sum(e**2)/sst) if sst else float("nan"),
        "LoA inferior (m/s)": float(np.mean(e)-1.96*np.std(e, ddof=1)),
        "LoA superior (m/s)": float(np.mean(e)+1.96*np.std(e, ddof=1)),
        "Error ≤1 m/s (%)": float(100*np.mean(abs(e)<=1)),
    }


AGE_BANDS = (
    ("9–20", 9, 21), ("21–39", 21, 40), ("40–59", 40, 60),
    ("60–69", 60, 70), ("≥70", 70, 88),
)


def analyze_rows(df: pd.DataFrame, mapping: dict[str, str | None]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """No modifica la fuente. Mantiene errores de validación por fila."""
    output, rejects = [], []
    for i, row in df.iterrows():
        try:
            def number(key: str) -> float:
                v = row[mapping[key]]
                if isinstance(v, str):
                    v = v.strip().replace(" ", "").replace(",", ".")
                if pd.isna(v) or str(v).strip() == "":
                    raise ValueError(f"Falta {key}")
                return float(v)
            raw_measured = row[mapping["VOP"]] if mapping.get("VOP") else None
            if pd.isna(raw_measured) or str(raw_measured).strip() == "":
                raw_measured = None
            elif isinstance(raw_measured, str):
                raw_measured = float(raw_measured.strip().replace(",", "."))
            name = row[mapping["ID"]] if mapping.get("ID") else f"Registro {i+1}"
            result = calculate(number("Edad"), row[mapping["Sexo"]], number("PAS"),
                               number("PAD"), raw_measured, str(name))
            result["Fila_origen"] = i + 1
            output.append(result)
        except (ValueError, TypeError, OverflowError, KeyError) as e:
            rejects.append({"Fila_origen": i+1, "Motivo": str(e)})
    return pd.DataFrame(output), pd.DataFrame(rejects)
