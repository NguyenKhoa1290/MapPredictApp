"""CV-03 read-only source survey. No CRS selection, label repair or data joins."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

# Allow direct execution from tools without changing the application import path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ezdxf
from shapely import STRtree, normalize
from shapely.geometry import Point, Polygon

from cad_to_geojson import _entity_features
from prediction_grid import read_dxf_grid

SOURCES = (
    ("hcm", "luoi_hcm.dxf", "DTL-1D", "MTEXT"),
    ("bac-kan", "bắc kan.dxf", "00.Ranh gioi", "MTEXT"),
    ("phu-quoc", "phú quốc.dxf", "Docao", "TEXT"),
)
FOLDER = ROOT / "Tailieuthamkhao/Giaodienfrontend/luoi"


def geometry_summary(polygons, handles):
    groups = defaultdict(list)
    for index, polygon in enumerate(polygons):
        groups[normalize(polygon).wkb].append(handles[index])
    duplicates = [items for items in groups.values() if len(items) > 1]
    tree = STRtree(polygons)
    overlaps = []
    for index, polygon in enumerate(polygons):
        for other in tree.query(polygon, predicate="intersects").tolist():
            if other <= index:
                continue
            area = polygon.intersection(polygons[other]).area
            # Ignore numerical slivers, not a legal/topographic tolerance.
            if area > 1e-5:
                overlaps.append({"handles": [handles[index], handles[other]], "area_raw_units2": area})
    bounds = [min(p.bounds[0] for p in polygons), min(p.bounds[1] for p in polygons),
              max(p.bounds[2] for p in polygons), max(p.bounds[3] for p in polygons)] if polygons else None
    sizes = Counter((round(p.bounds[2] - p.bounds[0], 6),
                     round(p.bounds[3] - p.bounds[1], 6), round(p.area, 6)) for p in polygons)
    return {"polygons": len(polygons), "unique_exact_geometries": len(groups),
            "duplicate_geometry_groups": duplicates,
            "duplicate_extra_polygons": sum(len(group) - 1 for group in duplicates),
            "overlap_pairs_above_raw_area_1e_minus_5": overlaps, "bounds_raw": bounds,
            "sizes_raw_units": [{"width": width, "height": height, "area": area, "count": count}
                                for (width, height, area), count in sizes.most_common()]}


def label_summary(polygons, labels):
    """Strict insertion point containment only, deliberately no nearest fallback."""
    tree = STRtree(polygons)
    counts = Counter()
    assigned = defaultdict(list)
    problematic = []
    for label in labels:
        point = Point(label["position"][:2])
        candidates = tree.query(point, predicate="intersects").tolist()
        if len(candidates) == 1 and polygons[candidates[0]].contains(point):
            state = "unique_inside"
            assigned[candidates[0]].append(label["text"])
        elif candidates:
            state = "boundary_or_overlap"
        else:
            state = "outside"
        counts[state] += 1
        if state != "unique_inside":
            diagnostic = {**label, "status": state, "intersecting_polygons": len(candidates)}
            if state == "outside" and polygons:
                diagnostic["distance_to_grid_raw_units_diagnostic_only"] = min(
                    polygon.distance(point) for polygon in polygons)
            problematic.append(diagnostic)
    code_counts = Counter(label["text"] for label in labels)
    numbers = sorted({int(label["text"]) for label in labels})
    return {"labels": len(labels), "code_count": len(code_counts),
            "duplicate_label_codes": {code: count for code, count in code_counts.items() if count > 1},
            "numeric_code_extent": [numbers[0], numbers[-1]] if numbers else None,
            "numeric_code_gaps": sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers)) if numbers else [],
            "strict_insert_statuses": {state: counts[state] for state in
                                       ("unique_inside", "boundary_or_overlap", "outside")},
            "cells_without_unique_insert_label": len(polygons) - len(assigned),
            "cells_with_multiple_unique_insert_labels": sum(len(items) > 1 for items in assigned.values()),
            "problem_examples": problematic[:5],
            "outside_labels": [item for item in problematic if item["status"] == "outside"],
            "mtext_attachments": dict(Counter(str(label["attachment_point"]) for label in labels
                                              if label["kind"] == "MTEXT"))}


def audit_source(path, grid_layer, label_kind):
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    document = ezdxf.readfile(path)  # No save, recovery rewrite, or external XREF loading.
    entities = list(document.modelspace())
    layers = defaultdict(Counter)
    for entity in entities:
        layers[entity.dxf.layer][entity.dxftype()] += 1
    selected = [entity for entity in entities if entity.dxftype() == "LWPOLYLINE"
                and entity.dxf.layer == grid_layer]
    polygons, handles, invalid = [], [], []
    for entity in selected:
        if not entity.is_closed:
            invalid.append({"handle": entity.dxf.handle, "reason": "open"})
            continue
        parts = list(_entity_features(entity, warnings=Counter()))
        if len(parts) != 1 or parts[0]["geometry"]["type"] != "LineString":
            invalid.append({"handle": entity.dxf.handle, "reason": "unsupported_boundary"})
            continue
        polygon = Polygon(parts[0]["geometry"]["coordinates"])
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
            invalid.append({"handle": entity.dxf.handle, "reason": "invalid_geometry"})
            continue
        polygons.append(polygon)
        handles.append(entity.dxf.handle)
    labels = []
    for entity in entities:
        if entity.dxftype() != label_kind or entity.dxf.layer != "0":
            continue
        text = entity.plain_text() if label_kind == "MTEXT" else entity.dxf.text
        if not re.fullmatch(r"\d+", text.strip()):
            continue
        label = {"text": text.strip(), "handle": entity.dxf.handle, "kind": label_kind,
                 "position": list(entity.dxf.insert)}
        if label_kind == "MTEXT":
            label.update(attachment_point=entity.dxf.attachment_point, width=entity.dxf.width,
                         char_height=entity.dxf.char_height, rotation=entity.get_rotation())
        labels.append(label)
    baseline = read_dxf_grid(path)["metadata"]
    result = {"file": path.name, "sha256": before,
              "modelspace_entity_types": dict(Counter(entity.dxftype() for entity in entities)),
              "modelspace_layers": {layer: dict(kinds) for layer, kinds in layers.items()},
              "header": {name: str(document.header.get(name)) for name in
                         ("$ACADVER", "$INSUNITS", "$MEASUREMENT", "$INSBASE", "$EXTMIN", "$EXTMAX",
                          "$UCSORG", "$UCSXDIR", "$UCSYDIR")},
              "geodata_count": sum(entity.dxftype() == "GEODATA" for entity in document.objects),
              "crs_status": "not_confirmed", "applied_transform": None,
              "xrefs": [{"name": block.name, "path": block.block.dxf.get("xref_path"),
                         "embedded_entities": len(block)} for block in document.blocks
                        if block.block.dxf.get("xref_path", "")],
              "selection": {"geometry_layer": grid_layer, "geometry_type": "LWPOLYLINE",
                            "label_layer": "0", "label_type": label_kind, "label_regex": r"\d+"},
              "geometry": geometry_summary(polygons, handles), "invalid_selected_boundaries": invalid,
              "labels": label_summary(polygons, labels),
              "current_unfiltered_reader": {name: baseline[name] for name in
                                            ("cell_count", "identified_count", "id_status_counts", "raw_bounds")}}
    if before != hashlib.sha256(path.read_bytes()).hexdigest():
        raise RuntimeError("DXF changed during survey")
    result["source_unchanged"] = True
    return result


def audit():
    return {project: audit_source(FOLDER / name, layer, kind) for project, name, layer, kind in SOURCES}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=True, indent=2))
