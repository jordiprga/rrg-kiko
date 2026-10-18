"""Validate a market snapshot before deploying it; never modify it."""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from scripts.market import ROOT


def validate(path: Path, max_age_days: int = 14) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1 and data["method"] in ("relative-ema-v1", "relative-models-v2"), "Esquema incompatible"
    generated = datetime.fromisoformat(data["generatedAt"])
    assert 0 <= (datetime.now(timezone.utc) - generated).total_seconds() <= max_age_days * 86400, "Dataset fuera del límite de antigüedad"
    assert (datetime.now(timezone.utc).date() - datetime.fromisoformat(data["latestSession"]).date()).days <= max_age_days, "Sesiones demasiado antiguas"
    assert data["groups"], "Sin universos"
    for group in data["groups"].values():
        assert len(group["defaults"]) >= 4, "Se requieren cuatro activos iniciales"
        for benchmark in group["benchmarks"]:
            for timeframe, expected in [("daily", data["latestSession"]), ("weekly", data["expectedWeeklySession"])]:
                view = data["views"][benchmark][timeframe]
                method = view.get("method", data["method"])
                sma = method == "relative-sma-10-30-9-v2"
                assert method == "relative-ema-v1" or (sma and benchmark == "GSPC" and timeframe == "weekly"), "Método de vista incompatible"
                assert view.get("calculationVersion", 1) == (2 if sma else 1), "Versión de cálculo incompatible"
                expected_parameters = dict(short=10, long=30, m=9) if sma else (dict(n=50, m=20) if timeframe == "daily" else dict(n=10, m=4))
                assert view["parameters"] == expected_parameters, "Parámetros incompatibles"
                reference = view["benchmark"]
                assert len(reference) >= 31 and reference[-1][0] == expected, "Benchmark incompleto"
                assert set(group["defaults"]) <= set(view["assets"]), "Faltan activos iniciales"
                for rows in [reference, *view["assets"].values()]:
                    dates = [row[0] for row in rows]
                    assert len(rows) >= 31 and dates == sorted(set(dates)), "Fechas inválidas"
                    assert dates[-1] == expected, "Instrumento incompleto"
                    assert all(all(isinstance(v, (float, int)) and math.isfinite(v) and v > 0 for v in row[1:]) for row in rows), "Valores inválidos"
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=ROOT / "public/data/market.json")
    parser.add_argument("--max-age-days", type=int, default=14)
    args = parser.parse_args()
    result = validate(args.path, args.max_age_days)
    print(f"Dataset verificado: {result['latestSession']}, {len(result['catalog'])} instrumentos")
