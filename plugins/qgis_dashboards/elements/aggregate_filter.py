# -*- coding: utf-8 -*-
"""Inject the live dashboard filter into aggregate expressions.

QGIS aggregate functions (``count``/``sum``/``mean``/...) compute over the
*whole* layer and ignore the ``QgsFeatureRequest`` filter that iterate-based
elements (chart/list/pivot) honor. An indicator therefore never reacts to a
cross-filter connection unless the filter is fed to each aggregate explicitly
via its ``filter:=`` argument.

The ``filter:=`` argument expects an *expression node*, not a string, so the
documented ``count(1, filter:=@dashboard_filter)`` form never worked (a string
variable is truthy for every feature). The robust fix is to splice the combined
filter's *literal expression text* into every aggregate call:

    sum("pop")  ->  sum("pop", filter:=("region" = 'A'))

This module is pure (no QGIS / Qt) so it is unit-tested standalone.
"""

# QGIS shorthand aggregate functions whose final argument can be ``filter:=``.
# Scalar functions like ``min``/``max``/``round`` are element-wise over their
# arguments (not aggregates) and are deliberately excluded.
AGGREGATE_FUNCS = frozenset({
    "count", "count_distinct", "count_missing",
    "minimum", "maximum", "sum", "mean", "median",
    "stdev", "range", "minority", "majority",
    "q1", "q3", "iqr", "min_length", "max_length",
    "concatenate", "concatenate_unique", "array_agg",
    "aggregate",
})


def _is_ident_char(c):
    return c.isalnum() or c == "_"


def inject_filter(expr, filt):
    """Return *expr* with ``filter:=(filt)`` added to each aggregate call.

    A call that already specifies a top-level ``filter:=`` is left untouched.
    Returns *expr* unchanged when either *expr* or *filt* is empty.
    """
    if not expr or not filt:
        return expr
    filt = filt.strip()
    if not filt:
        return expr

    clause = ", filter:=({})".format(filt)
    out = []
    stack = []           # one frame per open paren currently being scanned
    last_ident = None    # identifier seen immediately before (only ws between)
    i, n = 0, len(expr)

    while i < n:
        c = expr[i]

        # --- string literal ('...') or quoted identifier ("...") ---
        if c == "'" or c == '"':
            q = c
            out.append(c)
            i += 1
            while i < n:
                ch = expr[i]
                out.append(ch)
                if ch == q:
                    # a doubled quote is an escaped quote, not a terminator
                    if i + 1 < n and expr[i + 1] == q:
                        out.append(expr[i + 1])
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            if stack:
                stack[-1]["content"] = True
            last_ident = None
            continue

        # --- identifier / function name / keyword ---
        if c.isalpha() or c == "_":
            j = i
            while j < n and _is_ident_char(expr[j]):
                j += 1
            ident = expr[i:j]
            out.append(ident)
            # detect a top-level ``filter:=`` so we don't add a second one
            k = j
            while k < n and expr[k] in " \t\r\n":
                k += 1
            if ident.lower() == "filter" and expr[k:k + 2] == ":=" and stack:
                stack[-1]["has_filter"] = True
            if stack:
                stack[-1]["content"] = True
            last_ident = ident
            i = j
            continue

        # --- open paren: a function call if an identifier precedes it ---
        if c == "(":
            is_agg = (last_ident is not None
                      and last_ident.lower() in AGGREGATE_FUNCS)
            stack.append({"is_agg": is_agg, "has_filter": False,
                          "content": False})
            out.append(c)
            last_ident = None
            i += 1
            continue

        # --- close paren: splice the filter into a bare aggregate call ---
        if c == ")":
            if stack:
                fr = stack.pop()
                if fr["is_agg"] and not fr["has_filter"] and fr["content"]:
                    out.append(clause)
                if stack:           # this call is content of its parent call
                    stack[-1]["content"] = True
            out.append(c)
            last_ident = None
            i += 1
            continue

        # --- any other character ---
        if not c.isspace():
            if stack:
                stack[-1]["content"] = True
            last_ident = None
        out.append(c)
        i += 1

    return "".join(out)
