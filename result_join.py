"""Conservative, request-local result matching for uploaded prediction grids."""
from collections import Counter, defaultdict
import math
from numbers import Real
import re


PALETTE = {0: "#ff0000", 1: "#ffa500", 2: "#008000"}


def exact_key(value):
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, Real):
        if not math.isfinite(value):
            return ""
        return str(int(value)) if value == int(value) else str(value)
    return str(value).strip().casefold()


def numeric_key(value):
    if isinstance(value, Real) and not isinstance(value, bool):
        return str(int(value)) if math.isfinite(value) and value == int(value) else None
    key = exact_key(value)
    match = re.fullmatch(r"[^0-9]*([0-9]+)[^0-9]*", key)
    return (match[1].lstrip("0") or "0") if match else None


def result_label(value):
    key = exact_key(value)
    return int(key) if key in ("0", "1", "2") else None


def match_results(values, rows, csv_join, mode="exact"):
    """Never reuse a duplicate/fallback key or guess by row order/proximity.

    Call separately per selected file so collisions in another uploaded grid do
    not affect this grid. Original key values remain untouched in the features.
    """
    if mode not in ("exact", "numeric"):
        raise ValueError("Chế độ ghép phải là exact hoặc numeric")
    exact, numeric = defaultdict(list), defaultdict(list)
    for index, row in enumerate(rows):
        key = exact_key(row.get(csv_join))
        if key:
            exact[key].append(index)
        number = numeric_key(row.get(csv_join))
        if number is not None:
            numeric[number].append(index)
    cell_exact = Counter(exact_key(value) for value in values if exact_key(value))
    cell_numeric = Counter(number for value in values if (number := numeric_key(value)) is not None)
    output, samples, counts = [], [], Counter()
    used = set()
    for value in values:
        key, number = exact_key(value), numeric_key(value)
        candidates, method, status = [], None, "unmatched"
        if not key:
            status = "missing_key"
        elif cell_exact[key] != 1:
            status = "ambiguous"
        elif key in exact:
            candidates, method = exact[key], "exact"
        elif mode == "numeric" and number is not None:
            if number in numeric and (cell_numeric[number] != 1 or len(numeric[number]) != 1):
                status = "ambiguous"
            else:
                candidates, method = numeric.get(number, []), "numeric"
        label, row_index = None, None
        if candidates:
            if len(candidates) != 1:
                status = "ambiguous"
            else:
                row_index = candidates[0]
                label = result_label(rows[row_index].get("Y"))
                if label is not None:
                    status = "matched"
                    used.add(row_index)
                    counts[method] += 1
                else:
                    status = "no_data" if not exact_key(rows[row_index].get("Y")) else "invalid_y"
        counts[status] += 1
        output.append({"Y": label, "status": status, "method": method if status == "matched" else None,
                       "result_key": rows[row_index].get(csv_join) if row_index is not None else None})
        if len(samples) < 20 and (status != "matched" or method == "numeric"):
            samples.append({"layer_key": value, "result_key": output[-1]["result_key"],
                            "status": status, "method": output[-1]["method"]})
    total = len(values)
    return output, {"total": total, "matched": counts["matched"], "unmatched": total - counts["matched"],
                    "exact": counts["exact"], "numeric": counts["numeric"],
                    "ambiguous": counts["ambiguous"], "missing_key": counts["missing_key"],
                    "no_data": counts["no_data"], "invalid_y": counts["invalid_y"],
                    "unused_results": len(rows) - len(used),
                    "duplicate_result_keys": sum(len(items) > 1 for items in exact.values()),
                    "results_applied": bool(rows), "mode": mode, "samples": samples}


def apply_results(collection, rows, layer_join, csv_join, mode="exact", values=None):
    features = collection["features"]
    values = values if values is not None else [item["properties"].get(layer_join) for item in features]
    matches, summary = match_results(values, rows, csv_join, mode)
    for feature, match in zip(features, matches):
        label = match["Y"]
        feature["properties"].update(Y=label, fillColor=PALETTE.get(label, "#cccccc"),
                                      fillOpacity=0.6 if label is not None else 0,
                                      join_status=match["status"], join_method=match["method"],
                                      result_key=match["result_key"])
    collection["join_summary"] = {**summary, "layer_join": layer_join, "csv_join": csv_join}
    return collection
