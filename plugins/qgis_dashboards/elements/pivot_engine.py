# -*- coding: utf-8 -*-
"""Pivot / cross-tab engine — pandas-free and layer-backed.

``compute_pivot`` buckets an iterable of feature-like mappings (anything that
supports ``f[field]`` — a ``QgsFeature`` in production, a plain dict in tests)
into a cross-tab: rows = unique values of ``row_field``, columns = unique values
of ``col_field`` (optional), each cell the aggregate of ``value_field``.

Totals are computed from the raw values per row/column/grand bucket (not by
summing cell aggregates), so ``mean``/``min``/``max`` totals are correct.

This module is intentionally Qt-free so it can be unit-tested without a QGIS
runtime.
"""

from collections import defaultdict, namedtuple

NULL_KEY = "(null)"

PivotResult = namedtuple(
    "PivotResult",
    "row_field col_field statistic row_keys col_keys cells "
    "row_totals col_totals grand_total truncated",
)


def _is_null(v):
    if v is None:
        return True
    isnull = getattr(v, "isNull", None)
    if callable(isnull):
        try:
            return bool(v.isNull())
        except Exception:
            return False
    return False


def _key(feature, field):
    v = feature[field]
    return NULL_KEY if _is_null(v) else str(v)


def _num(feature, field):
    if not field:
        return None
    try:
        return float(feature[field])
    except (TypeError, ValueError):
        return None


def _mean(vals):
    return sum(vals) / len(vals) if vals else 0


_FINALIZERS = {
    "count": len,
    "sum": sum,
    "mean": _mean,
    "min": min,
    "max": max,
}

STATISTICS = ("count", "sum", "mean", "min", "max")


def compute_pivot(features, row_field, col_field=None, value_field=None,
                  statistic="count", max_rows=50, max_cols=20):
    """Return a :class:`PivotResult` cross-tab over ``features``."""
    fin = _FINALIZERS.get(statistic, len)
    if not row_field:
        return PivotResult(row_field, col_field, statistic,
                           [], [], {}, {}, {}, None, False)

    cell = defaultdict(list)
    rowb = defaultdict(list)
    colb = defaultdict(list)
    grand = []
    for f in features:
        r = _key(f, row_field)
        c = _key(f, col_field) if col_field else ""
        if statistic == "count":
            v = 1.0
        else:
            v = _num(f, value_field)
            if v is None:
                continue
        cell[(r, c)].append(v)
        rowb[r].append(v)
        grand.append(v)
        if col_field:
            colb[c].append(v)

    row_keys_all = sorted(rowb, key=lambda k: fin(rowb[k]), reverse=True)
    col_keys_all = (sorted(colb, key=lambda k: fin(colb[k]), reverse=True)
                    if col_field else [])
    truncated = len(row_keys_all) > max_rows or len(col_keys_all) > max_cols
    row_keys = row_keys_all[:max_rows]
    col_keys = col_keys_all[:max_cols]

    row_set, col_set = set(row_keys), set(col_keys)
    cells = {(r, c): fin(vals) for (r, c), vals in cell.items()
             if r in row_set and (not col_field or c in col_set)}
    row_totals = {r: fin(rowb[r]) for r in row_keys}
    col_totals = {c: fin(colb[c]) for c in col_keys}
    grand_total = fin(grand) if grand else None

    return PivotResult(row_field, col_field, statistic, row_keys, col_keys,
                       cells, row_totals, col_totals, grand_total, truncated)
