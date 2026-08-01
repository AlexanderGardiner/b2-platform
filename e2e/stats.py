from __future__ import annotations

from typing import Any


def calculate_stats(results: list[dict[str, Any]]) -> dict[str, Any]:
    countries = sorted({str(result["country"]) for result in results})
    by_country = {
        country: _stats_for([result for result in results if result["country"] == country])
        for country in countries
    }
    return {
        "overall": _stats_for(results),
        "by_country": by_country,
    }


def _stats_for(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"TP": 0, "TN": 0, "FP": 0, "FN": 0, "UNKNOWN": 0}
    for result in results:
        cls = str(result.get("classification", "UNKNOWN"))
        counts[cls if cls in counts else "UNKNOWN"] += 1

    classified = counts["TP"] + counts["TN"] + counts["FP"] + counts["FN"]
    total = classified + counts["UNKNOWN"]
    accuracy = (counts["TP"] + counts["TN"]) / classified if classified else None
    false_positive_rate = counts["FP"] / (counts["FP"] + counts["TN"]) if counts["FP"] + counts["TN"] else None
    false_negative_rate = counts["FN"] / (counts["FN"] + counts["TP"]) if counts["FN"] + counts["TP"] else None

    return {
        "total": total,
        "classified": classified,
        "accuracy": accuracy,
        "false_positives": counts["FP"],
        "false_negatives": counts["FN"],
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
        "unknown": counts["UNKNOWN"],
        "tp": counts["TP"],
        "tn": counts["TN"],
        "fp": counts["FP"],
        "fn": counts["FN"],
    }

