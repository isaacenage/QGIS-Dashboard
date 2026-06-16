/* QGIS Dashboard — exported runtime.
 *
 * Vanilla JS, no dependencies. Reads the embedded JSON model and reproduces the
 * dashboard offline, including live cross-filtering. The filter/aggregation
 * logic is a direct port of the plugin's bus.py / chart.py / pivot_engine.py so
 * behavior matches the live dashboard. Charts are hand-drawn inline SVG.
 */
(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
  var THEME = DATA.theme || {};
  var DEFAULT_SERIES = ["#2b7de9", "#13a10e", "#c19c00", "#d13438", "#8764b8",
    "#00b7c3", "#ca5010", "#498205", "#a4262c", "#5c2e91"];
  var SERIES = (THEME.series && THEME.series.length) ? THEME.series : DEFAULT_SERIES;
  // global element gap (logical px): each card is inset by this much inside its
  // footprint, mirroring the desktop's GridTile inset. The output can't be
  // re-dragged, so this is the only way the export reflects the spacing.
  var GAP = Math.max(0, Number(DATA.gap || 0));
  var NULL_KEY = "(null)";
  var SEP = String.fromCharCode(1);   // composite (row, col) cell-key separator

  var ELEMENT_LABELS = {
    indicator: "Indicator", chart: "Chart", pivot: "Pivot / matrix",
    list: "List", map: "Map", category_selector: "Category selector",
    text: "Text", image: "Image"
  };
  var FULL_BLEED = { map: true, image: true };

  var CHART_SPECS = {
    bar: { painter: "bar", stat: true, fold: false, cap: 12, inner: 0 },
    barh: { painter: "barh", stat: true, fold: false, cap: 12, inner: 0 },
    line: { painter: "line", stat: true, fold: false, cap: 20, inner: 0 },
    area: { painter: "area", stat: true, fold: false, cap: 20, inner: 0 },
    pie: { painter: "pie", stat: false, fold: true, cap: 7, inner: 0 },
    donut: { painter: "pie", stat: false, fold: true, cap: 7, inner: 0.55 }
  };
  function chartSpec(t) { return CHART_SPECS[t] || CHART_SPECS.bar; }

  // ---- per-page cross-filter state -------------------------------------
  // pageId -> { sourceId: {key: <string>, pairs: [{field, value}]} }
  var STATE = {};
  function selections(pageId) {
    if (!STATE[pageId]) STATE[pageId] = {};
    return STATE[pageId];
  }

  // ---- data helpers -----------------------------------------------------
  function layerOf(tile) { return (tile.layer_id && DATA.layers[tile.layer_id]) || null; }

  function baseRows(tile) {
    var layer = layerOf(tile);
    if (!layer) return [];
    if (tile.base_pass) {
      return tile.base_pass.map(function (i) { return layer.features[i]; });
    }
    return layer.features;
  }

  function eq(a, b) { return String(a) === String(b); }

  // Rows for a TARGET tile: its base rows AND-filtered by every connected
  // source that currently has an active selection (mirror combined_filter_for).
  function filteredRows(tile, page) {
    var rows = baseRows(tile);
    var conns = page.connections || {};
    var sel = selections(page.id);
    var preds = [];
    Object.keys(conns).forEach(function (src) {
      if (conns[src].indexOf(tile.id) >= 0) {
        var s = sel[src];
        if (s && s.pairs && s.pairs.length) preds = preds.concat(s.pairs);
      }
    });
    if (!preds.length) return rows;
    return rows.filter(function (r) {
      return preds.every(function (p) { return eq(r[p.field], p.value); });
    });
  }

  function setSelection(page, sourceId, sel) {
    var s = selections(page.id);
    if (sel === null) delete s[sourceId];
    else s[sourceId] = sel;
    renderPage(page);
  }

  function toggleSelection(page, sourceId, key, pairs) {
    var cur = selections(page.id)[sourceId];
    if (cur && cur.key === key) setSelection(page, sourceId, null);
    else setSelection(page, sourceId, { key: key, pairs: pairs });
  }

  // ---- formatting -------------------------------------------------------
  function fmtNum(v) {
    if (typeof v !== "number") return String(v);
    if (Number.isInteger(v)) return v.toLocaleString();
    return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtIndicator(cfg, v) {
    if (v === null || v === undefined) return cfg.no_value_text || "No data";
    var out = v;
    if (typeof v === "number" && !Number.isInteger(v)) {
      var dp = (cfg.decimals != null) ? cfg.decimals : 0;
      out = Number(v.toFixed(dp));
    }
    var s = (typeof out === "number") ? out.toLocaleString() : String(out);
    return (cfg.prefix || "") + s + (cfg.suffix || "");
  }

  // ---- aggregation (port of chart._aggregate + fold_categories) ---------
  function foldCategories(items, cap, fold) {
    if (!cap || cap <= 0 || items.length <= cap) return items.slice();
    var head = items.slice(0, cap);
    if (fold) {
      var other = items.slice(cap).reduce(function (a, p) { return a + Number(p[1]); }, 0);
      head.push(["Other", other]);
    }
    return head;
  }

  function aggregateChart(tile, rows) {
    var cfg = tile.config;
    var catField = cfg.category_field;
    if (!catField) return [];
    var spec = chartSpec(cfg.chart_type);
    var stat = spec.stat ? (cfg.statistic || "count") : "count";
    var valField = cfg.value_field;
    var buckets = {};
    rows.forEach(function (r) {
      var key = String(r[catField]);
      if (!buckets[key]) buckets[key] = [];
      if (stat === "count") { buckets[key].push(1); }
      else {
        var v = parseFloat(r[valField]);
        if (!isNaN(v)) buckets[key].push(v);
      }
    });
    var out = Object.keys(buckets).map(function (k) {
      var vals = buckets[k];
      if (stat === "sum") return [k, vals.reduce(function (a, b) { return a + b; }, 0)];
      if (stat === "mean") return [k, vals.length ? vals.reduce(function (a, b) { return a + b; }, 0) / vals.length : 0];
      return [k, vals.length];
    });
    out.sort(function (a, b) { return b[1] - a[1]; });
    var cap = parseInt(cfg.max_categories, 10) || spec.cap;
    return foldCategories(out, cap, spec.fold);
  }

  // ---- pivot engine (port of pivot_engine.compute_pivot) ----------------
  var FINALIZERS = {
    count: function (a) { return a.length; },
    sum: function (a) { return a.reduce(function (x, y) { return x + y; }, 0); },
    mean: function (a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : 0; },
    min: function (a) { return Math.min.apply(null, a); },
    max: function (a) { return Math.max.apply(null, a); }
  };
  function keyOf(r, field) {
    var v = r[field];
    return (v === null || v === undefined) ? NULL_KEY : String(v);
  }
  function computePivot(rows, rowField, colField, valueField, statistic, maxRows, maxCols) {
    var fin = FINALIZERS[statistic] || FINALIZERS.count;
    if (!rowField) return { rowField: rowField, colField: colField, statistic: statistic, rowKeys: [], colKeys: [], cells: {}, rowTotals: {}, colTotals: {}, grandTotal: null, truncated: false };
    var cell = {}, rowb = {}, colb = {}, grand = [];
    rows.forEach(function (r) {
      var rk = keyOf(r, rowField);
      var ck = colField ? keyOf(r, colField) : "";
      var v;
      if (statistic === "count") v = 1;
      else { v = parseFloat(r[valueField]); if (isNaN(v)) return; }
      var ckey = rk + SEP + ck;
      (cell[ckey] = cell[ckey] || []).push(v);
      (rowb[rk] = rowb[rk] || []).push(v);
      grand.push(v);
      if (colField) (colb[ck] = colb[ck] || []).push(v);
    });
    var rowKeysAll = Object.keys(rowb).sort(function (a, b) { return fin(rowb[b]) - fin(rowb[a]); });
    var colKeysAll = colField ? Object.keys(colb).sort(function (a, b) { return fin(colb[b]) - fin(colb[a]); }) : [];
    var truncated = rowKeysAll.length > maxRows || colKeysAll.length > maxCols;
    var rowKeys = rowKeysAll.slice(0, maxRows);
    var colKeys = colKeysAll.slice(0, maxCols);
    var rowSet = {}, colSet = {};
    rowKeys.forEach(function (k) { rowSet[k] = 1; });
    colKeys.forEach(function (k) { colSet[k] = 1; });
    var cells = {};
    Object.keys(cell).forEach(function (ckey) {
      var parts = ckey.split(SEP);
      if (rowSet[parts[0]] && (!colField || colSet[parts[1]])) cells[ckey] = fin(cell[ckey]);
    });
    var rowTotals = {}, colTotals = {};
    rowKeys.forEach(function (k) { rowTotals[k] = fin(rowb[k]); });
    colKeys.forEach(function (k) { colTotals[k] = fin(colb[k]); });
    return {
      rowField: rowField, colField: colField, statistic: statistic,
      rowKeys: rowKeys, colKeys: colKeys, cells: cells,
      rowTotals: rowTotals, colTotals: colTotals,
      grandTotal: grand.length ? fin(grand) : null, truncated: truncated
    };
  }

  // ---- indicator aggregate-expression evaluator ------------------------
  // Supports the common QgsExpression aggregate forms; returns undefined for
  // anything else so the caller can fall back to the server-computed value.
  function evalAggregate(rows, expr) {
    expr = (expr || "count(1)").trim();
    if (/^count\s*\(\s*(1|\*)?\s*\)$/i.test(expr)) return rows.length;
    var m = expr.match(/^count\s*\(\s*distinct\s+"?([^")]+)"?\s*\)$/i);
    if (m) {
      var seen = {};
      rows.forEach(function (r) { seen[String(r[m[1]])] = 1; });
      return Object.keys(seen).length;
    }
    m = expr.match(/^(sum|mean|avg|average|min|max|count)\s*\(\s*"?([^")]+)"?\s*\)$/i);
    if (m) {
      var fn = m[1].toLowerCase(), field = m[2];
      var vals = rows.map(function (r) { return parseFloat(r[field]); })
        .filter(function (v) { return !isNaN(v); });
      if (fn === "count") return vals.length;
      if (!vals.length) return null;
      if (fn === "sum") return vals.reduce(function (a, b) { return a + b; }, 0);
      if (fn === "mean" || fn === "avg" || fn === "average") return vals.reduce(function (a, b) { return a + b; }, 0) / vals.length;
      if (fn === "min") return Math.min.apply(null, vals);
      if (fn === "max") return Math.max.apply(null, vals);
    }
    return undefined;
  }

  // ---- DOM helpers ------------------------------------------------------
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  var SVGNS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    var n = document.createElementNS(SVGNS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }
  function color(i) { return SERIES[i % SERIES.length]; }

  // ---- SVG chart painters ----------------------------------------------
  function drawChart(host, tile, page) {
    host.innerHTML = "";
    var rows = filteredRows(tile, page);
    var data = aggregateChart(tile, rows);
    var w = host.clientWidth || 300, h = host.clientHeight || 200;
    if (!data.length) { host.appendChild(el("div", "dash-empty", "No data")); return; }
    var spec = chartSpec(tile.config.chart_type);
    var sel = selections(page.id)[tile.id];
    var selKey = sel ? sel.key : null;
    var onPick = function (cat) {
      if (cat === "Other") return;
      var field = tile.config.category_field;
      toggleSelection(page, tile.id, cat, [{ field: field, value: cat }]);
    };
    var svg = svgEl("svg", { "class": "dash-chart", width: w, height: h, viewBox: "0 0 " + w + " " + h });
    if (spec.painter === "bar") paintBars(svg, w, h, data, selKey, onPick, false);
    else if (spec.painter === "barh") paintBars(svg, w, h, data, selKey, onPick, true);
    else if (spec.painter === "line") paintLine(svg, w, h, data, selKey, onPick, false);
    else if (spec.painter === "area") paintLine(svg, w, h, data, selKey, onPick, true);
    else if (spec.painter === "pie") paintPie(svg, w, h, data, selKey, onPick, spec.inner);
    host.appendChild(svg);
  }

  function paintBars(svg, w, h, data, selKey, onPick, horizontal) {
    var pad = 8, labelH = 16, topPad = 14;
    var maxV = Math.max.apply(null, data.map(function (d) { return Number(d[1]); })) || 1;
    if (!horizontal) {
      var plotBottom = h - pad - labelH, plotTop = pad + topPad;
      var plotH = Math.max(plotBottom - plotTop, 1);
      var slotW = (w - 2 * pad) / data.length, barW = slotW * 0.6;
      data.forEach(function (d, i) {
        var x = pad + i * slotW, bh = plotH * (Number(d[1]) / maxV), y = plotBottom - bh;
        var fill = (d[0] === selKey) ? "var(--muted)" : color(i);
        var rect = svgEl("rect", { x: x + (slotW - barW) / 2, y: y, width: barW, height: bh, fill: fill, cursor: "pointer" });
        rect.addEventListener("click", function () { onPick(d[0]); });
        svg.appendChild(rect);
        addText(svg, x + slotW / 2, y - 3, fmtNum(Number(d[1])), "middle", "var(--text)", 10);
        addText(svg, x + slotW / 2, plotBottom + 12, clip(d[0], slotW), "middle", "var(--muted)", 10);
      });
    } else {
      var labelW = Math.min(w * 0.32, 140), valW = 46;
      var plotLeft = pad + labelW, plotW = Math.max(w - pad - labelW - valW, 1);
      var slotH = (h - 2 * pad) / data.length, barH = Math.min(slotH * 0.6, 26);
      data.forEach(function (d, i) {
        var top = pad + i * slotH, bw = plotW * (Number(d[1]) / maxV), y = top + (slotH - barH) / 2;
        var fill = (d[0] === selKey) ? "var(--muted)" : color(i);
        addText(svg, pad, top + slotH / 2, clip(d[0], labelW - 6), "start", "var(--muted)", 10);
        var rect = svgEl("rect", { x: plotLeft, y: y, width: bw, height: barH, fill: fill, cursor: "pointer" });
        rect.addEventListener("click", function () { onPick(d[0]); });
        svg.appendChild(rect);
        addText(svg, plotLeft + bw + 4, top + slotH / 2, fmtNum(Number(d[1])), "start", "var(--text)", 10);
      });
    }
  }

  function paintLine(svg, w, h, data, selKey, onPick, fill) {
    var pad = 8, labelH = 16, topPad = 14;
    var maxV = Math.max.apply(null, data.map(function (d) { return Number(d[1]); })) || 1;
    var plotBottom = h - pad - labelH, plotTop = pad + topPad;
    var plotH = Math.max(plotBottom - plotTop, 1);
    var slotW = (w - 2 * pad) / data.length;
    var pts = data.map(function (d, i) {
      return { x: pad + slotW * (i + 0.5), y: plotBottom - plotH * (Number(d[1]) / maxV), cat: d[0] };
    });
    if (fill && pts.length) {
      var dPath = "M" + pts[0].x + "," + plotBottom;
      pts.forEach(function (p) { dPath += " L" + p.x + "," + p.y; });
      dPath += " L" + pts[pts.length - 1].x + "," + plotBottom + " Z";
      svg.appendChild(svgEl("path", { d: dPath, fill: color(0), "fill-opacity": 0.22, stroke: "none" }));
    }
    var poly = pts.map(function (p) { return p.x + "," + p.y; }).join(" ");
    svg.appendChild(svgEl("polyline", { points: poly, fill: "none", stroke: color(0), "stroke-width": 2 }));
    pts.forEach(function (p, i) {
      var selp = (p.cat === selKey);
      var c = svgEl("circle", { cx: p.x, cy: p.y, r: selp ? 5 : 3, fill: selp ? "var(--muted)" : color(0), stroke: "var(--chart-bg)", cursor: "pointer" });
      c.addEventListener("click", function () { onPick(p.cat); });
      svg.appendChild(c);
      addText(svg, p.x, plotBottom + 12, clip(p.cat, slotW), "middle", "var(--muted)", 10);
    });
  }

  function paintPie(svg, w, h, data, selKey, onPick, inner) {
    var total = data.reduce(function (a, d) { return a + Number(d[1]); }, 0);
    if (total <= 0) return;
    var legendW = w > 260 ? Math.min(w * 0.4, 180) : 0;
    var pieW = w - legendW;
    var diameter = Math.max(Math.min(pieW, h) - 8, 10);
    var cx = pieW / 2, cy = h / 2, radius = diameter / 2;
    var innerR = inner ? radius * inner : 0;
    var start = -90;
    data.forEach(function (d, i) {
      var span = 360 * Number(d[1]) / total;
      var explode = (d[0] === selKey) ? 8 : 0;
      var mid = (start + span / 2) * Math.PI / 180;
      var ox = Math.cos(mid) * explode, oy = Math.sin(mid) * explode;
      var path = arcPath(cx + ox, cy + oy, radius, start, start + span, innerR);
      var seg = svgEl("path", { d: path, fill: color(i), stroke: "#ffffff", "stroke-width": 1, cursor: "pointer" });
      seg.addEventListener("click", function () { onPick(d[0]); });
      svg.appendChild(seg);
      start += span;
    });
    if (legendW) {
      var ry = 6;
      data.forEach(function (d, i) {
        if (ry + 16 > h) return;
        svg.appendChild(svgEl("rect", { x: pieW + 6, y: ry, width: 11, height: 11, fill: color(i) }));
        addText(svg, pieW + 22, ry + 9, clip(d[0] + " (" + fmtNum(Number(d[1])) + ")", legendW - 24), "start", "var(--text)", 10);
        ry += 18;
      });
    }
  }

  function arcPath(cx, cy, r, a0, a1, innerR) {
    var large = (a1 - a0) > 180 ? 1 : 0;
    var p0 = polar(cx, cy, r, a0), p1 = polar(cx, cy, r, a1);
    if (!innerR) {
      return "M" + cx + "," + cy + " L" + p0.x + "," + p0.y +
        " A" + r + "," + r + " 0 " + large + " 1 " + p1.x + "," + p1.y + " Z";
    }
    var i0 = polar(cx, cy, innerR, a0), i1 = polar(cx, cy, innerR, a1);
    return "M" + p0.x + "," + p0.y +
      " A" + r + "," + r + " 0 " + large + " 1 " + p1.x + "," + p1.y +
      " L" + i1.x + "," + i1.y +
      " A" + innerR + "," + innerR + " 0 " + large + " 0 " + i0.x + "," + i0.y + " Z";
  }
  function polar(cx, cy, r, deg) {
    var rad = deg * Math.PI / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }
  function addText(svg, x, y, text, anchor, fill, size) {
    var t = svgEl("text", { x: x, y: y, "text-anchor": anchor, fill: fill, "font-size": size, "dominant-baseline": "middle" });
    t.textContent = text;
    svg.appendChild(t);
  }
  function clip(text, px) {
    text = String(text);
    var max = Math.max(Math.floor(px / 6), 1);
    return text.length > max ? text.slice(0, max - 1) + "…" : text;
  }

  // ---- indicator value animations (mirror elements/indicator_anim.py) ----
  // The page DOM is rebuilt on every filter change, so the previous numeric
  // value is kept per tile id to drive odometer/rolling transitions.
  var IND_LAST = {};
  function easeOutCubic(t) { return 1 - Math.pow(1 - Math.min(Math.max(t, 0), 1), 3); }

  function animateNumber(node, cfg, from, to, dur) {
    var start = null;
    function frame(ts) {
      if (start === null) start = ts;
      var t = Math.min((ts - start) / dur, 1);
      node.textContent = fmtIndicator(cfg, from + (to - from) * easeOutCubic(t));
      if (t < 1) requestAnimationFrame(frame); else node.textContent = fmtIndicator(cfg, to);
    }
    requestAnimationFrame(frame);
  }
  function animateTypewriter(node, text, dur) {
    var start = null;
    function frame(ts) {
      if (start === null) start = ts;
      var t = Math.min((ts - start) / dur, 1);
      node.textContent = text.slice(0, Math.round(text.length * t));
      if (t < 1) requestAnimationFrame(frame); else node.textContent = text;
    }
    requestAnimationFrame(frame);
  }

  // ---- tile renderers ---------------------------------------------------
  function renderIndicator(body, tile, page) {
    var cfg = tile.config, rows = filteredRows(tile, page);
    var box = el("div", "dash-indicator");
    if (cfg.top_text) box.appendChild(el("div", "dash-ind-top", cfg.top_text));

    var live = evalAggregate(rows, cfg.value_expression || "count(1)");
    var value = (live === undefined) ? tile.indicator_value : live;
    var text = fmtIndicator(cfg, value);

    // value + optional icon (left / right / above)
    var wrap = el("div", "dash-ind-valuewrap pos-" + (cfg.icon_position || "left"));
    if (tile.icon_uri) {
      var img = el("img", "dash-ind-icon");
      img.src = tile.icon_uri;
      var isz = cfg.icon_size || 48;
      img.style.width = isz + "px"; img.style.height = isz + "px";
      wrap.appendChild(img);
    }
    var valNode = el("div", "dash-ind-value");
    if (cfg.value_size) valNode.style.fontSize = cfg.value_size + "px";
    wrap.appendChild(valNode);
    box.appendChild(wrap);

    var mode = (cfg.animation || "").toLowerCase();
    var dur = cfg.animation_duration_ms || 900;
    var last = IND_LAST[tile.id];
    if ((mode === "odometer" || mode === "rolling") && typeof value === "number"
        && typeof last === "number" && last !== value) {
      animateNumber(valNode, cfg, last, value, dur);
    } else if (mode === "typewriter") {
      animateTypewriter(valNode, text, dur);
    } else if (mode === "fade") {
      valNode.textContent = text;
      valNode.classList.add("fade-in");
    } else {
      valNode.textContent = text;
    }
    if (typeof value === "number") IND_LAST[tile.id] = value;

    if (cfg.reference_expression && typeof value === "number") {
      var ref = evalAggregate(rows, cfg.reference_expression);
      if (typeof ref === "number") {
        var delta = value - ref;
        var arrow = delta > 0 ? "▲" : (delta < 0 ? "▼" : "—");
        var cls = "dash-ind-bottom " + (delta > 0 ? "up" : delta < 0 ? "down" : "");
        box.appendChild(el("div", cls, arrow + " " + fmtIndicator(cfg, Math.abs(delta)) + " vs ref"));
      }
    }
    body.appendChild(box);
  }

  function renderList(body, tile, page) {
    var cfg = tile.config, layer = layerOf(tile);
    var fields = (cfg.display_fields && cfg.display_fields.length) ? cfg.display_fields
      : (layer ? layer.fields.slice(0, 3) : []);
    var rows = filteredRows(tile, page).slice(0, cfg.max_rows || 200);
    var wrap = el("div", "dash-table-wrap");
    var table = el("table", "dash-table");
    var thead = el("thead"), htr = el("tr");
    fields.forEach(function (f, i) {
      var th = el("th", i === 0 ? "rowhead" : null, f); htr.appendChild(th);
    });
    thead.appendChild(htr); table.appendChild(thead);
    var tbody = el("tbody");
    rows.forEach(function (r) {
      var tr = el("tr");
      fields.forEach(function (f, i) {
        var td = el("td", i === 0 ? "rowhead" : null, r[f] == null ? "" : String(r[f]));
        tr.appendChild(td);
      });
      tr.addEventListener("click", function () {
        Array.prototype.forEach.call(tbody.children, function (c) { c.classList.remove("selected"); });
        tr.classList.add("selected");
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody); wrap.appendChild(table); body.appendChild(wrap);
  }

  function renderPivot(body, tile, page) {
    var cfg = tile.config, rows = filteredRows(tile, page);
    var res = computePivot(rows, cfg.row_field, cfg.col_field || null,
      cfg.value_field, cfg.statistic || "count",
      parseInt(cfg.max_rows, 10) || 50, parseInt(cfg.max_cols, 10) || 20);
    var hasCols = res.colKeys.length > 0;
    var showTotals = (cfg.show_totals !== false) && res.rowKeys.length > 0;
    var sel = selections(page.id)[tile.id]; var selKey = sel ? sel.key : null;
    var wrap = el("div", "dash-table-wrap");
    var table = el("table", "dash-table");

    var headers = [res.rowField || "(rows)"];
    if (hasCols) headers = headers.concat(res.colKeys);
    else headers.push((cfg.statistic || "count").replace(/^./, function (c) { return c.toUpperCase(); }));
    var totalsCol = hasCols && showTotals;
    if (totalsCol) headers.push("Total");

    var thead = el("thead"), htr = el("tr");
    headers.forEach(function (hLabel, ci) {
      var th = el("th", ci === 0 ? "rowhead" : null, hLabel);
      if (hasCols && ci >= 1 && ci <= res.colKeys.length) {
        var colKey = res.colKeys[ci - 1];
        if (colKey !== NULL_KEY && cfg.col_field) {
          th.className += " clickable";
          if (selKey === "col|" + colKey) th.classList.add("selected");
          th.addEventListener("click", function () {
            toggleSelection(page, tile.id, "col|" + colKey, [{ field: cfg.col_field, value: colKey }]);
          });
        }
      }
      htr.appendChild(th);
    });
    thead.appendChild(htr); table.appendChild(thead);

    var tbody = el("tbody");
    res.rowKeys.forEach(function (rk) {
      var tr = el("tr");
      var rh = el("td", "rowhead", rk);
      if (rk !== NULL_KEY && cfg.row_field) {
        rh.className += " clickable";
        if (selKey === "row|" + rk) rh.classList.add("selected");
        rh.addEventListener("click", function () {
          toggleSelection(page, tile.id, "row|" + rk, [{ field: cfg.row_field, value: rk }]);
        });
      }
      tr.appendChild(rh);
      if (hasCols) {
        res.colKeys.forEach(function (ck) {
          var v = res.cells[rk + SEP + ck];
          var td = el("td", null, v == null ? "" : fmtNum(v));
          if (rk !== NULL_KEY && ck !== NULL_KEY && cfg.row_field && cfg.col_field) {
            var k = "cell|" + rk + SEP + ck;
            td.className = "clickable";
            if (selKey === k) td.classList.add("selected");
            td.addEventListener("click", function () {
              toggleSelection(page, tile.id, k, [
                { field: cfg.row_field, value: rk }, { field: cfg.col_field, value: ck }]);
            });
          }
          tr.appendChild(td);
        });
        if (totalsCol) tr.appendChild(el("td", "rowhead", fmtNum(res.rowTotals[rk])));
      } else {
        tr.appendChild(el("td", null, fmtNum(res.rowTotals[rk])));
      }
      tbody.appendChild(tr);
    });
    if (showTotals) {
      var trt = el("tr");
      trt.appendChild(el("td", "rowhead", "Total"));
      if (hasCols) {
        res.colKeys.forEach(function (ck) { trt.appendChild(el("td", "rowhead", fmtNum(res.colTotals[ck]))); });
        if (totalsCol) trt.appendChild(el("td", "rowhead", res.grandTotal == null ? "" : fmtNum(res.grandTotal)));
      } else {
        trt.appendChild(el("td", "rowhead", res.grandTotal == null ? "" : fmtNum(res.grandTotal)));
      }
      tbody.appendChild(trt);
    }
    table.appendChild(tbody); wrap.appendChild(table); body.appendChild(wrap);
  }

  function renderSelector(body, tile, page) {
    var cfg = tile.config, layer = layerOf(tile), field = cfg.category_field;
    var box = el("div", "dash-selector");
    var select = el("select");
    select.appendChild(new Option("(All)", "(All)"));
    if (layer && field) {
      var seen = {};
      layer.features.forEach(function (r) { seen[String(r[field])] = 1; });
      Object.keys(seen).sort().forEach(function (v) { select.appendChild(new Option(v, v)); });
    }
    var cur = selections(page.id)[tile.id];
    select.value = cur ? cur.key : "(All)";
    select.addEventListener("change", function () {
      if (select.value === "(All)" || !field) setSelection(page, tile.id, null);
      else setSelection(page, tile.id, { key: select.value, pairs: [{ field: field, value: select.value }] });
    });
    box.appendChild(select); body.appendChild(box);
  }

  function renderText(body, tile) {
    var cfg = tile.config;
    var wrap = el("div", "dash-text");
    var inner = el("div", "inner");
    var heading = !!cfg.heading;
    var size = heading ? Math.round((THEME.title_size || 13) * 1.7) : (THEME.font_size || 11);
    inner.textContent = cfg.text || "";
    inner.style.fontSize = size + "px";
    inner.style.fontWeight = heading ? "700" : "400";
    inner.style.textAlign = cfg.align || "left";
    wrap.style.justifyContent = cfg.align === "center" ? "center" : (cfg.align === "right" ? "flex-end" : "flex-start");
    wrap.appendChild(inner); body.appendChild(wrap);
  }

  function renderImage(body, tile) {
    var wrap = el("div", "dash-image-wrap");
    if (tile.image_uri) {
      var img = el("img", "dash-image");
      img.src = tile.image_uri;
      if (tile.config.fit === "stretch") img.style.objectFit = "fill";
      wrap.appendChild(img);
    } else {
      wrap.appendChild(el("div", "dash-note", "Image unavailable"));
    }
    body.appendChild(wrap);
  }

  function renderMap(body, tile) {
    var wrap = el("div", "dash-map-wrap");
    if (tile.map_image) {
      var img = el("img", "dash-map"); img.src = tile.map_image;
      wrap.appendChild(img);
    } else {
      wrap.appendChild(el("div", "dash-note", "Map — view in QGIS"));
    }
    body.appendChild(wrap);
  }

  // ---- tile + page assembly --------------------------------------------
  var CHART_HOSTS = [];   // {host, tile, page} for the post-layout draw pass

  function renderTile(tile, page) {
    var node = el("div", "dash-tile" + (FULL_BLEED[tile.type] ? " full-bleed" : ""));
    var g = tile.grid || {};
    // free-form layout: tiles carry a logical pixel rect (x, y, w, h). The card
    // is inset by GAP on every side inside that footprint (matching the desktop
    // GridTile inset) so adjacent cards always keep their breathing room.
    node.style.position = "absolute";
    node.style.left = (Number(g.x || 0) + GAP) + "px";
    node.style.top = (Number(g.y || 0) + GAP) + "px";
    node.style.width = Math.max(Number(g.w || 120) - 2 * GAP, 1) + "px";
    node.style.height = Math.max(Number(g.h || 120) - 2 * GAP, 1) + "px";

    var showTitle = !FULL_BLEED[tile.type] && tile.type !== "text" && tile.type !== "header";
    if (showTitle) {
      var title = tile.config.title || ELEMENT_LABELS[tile.type] || tile.type;
      node.appendChild(el("div", "dash-tile-title", title));
    }
    var body = el("div", "dash-tile-body");
    node.appendChild(body);

    if (tile.type === "indicator") renderIndicator(body, tile, page);
    else if (tile.type === "list") renderList(body, tile, page);
    else if (tile.type === "pivot") renderPivot(body, tile, page);
    else if (tile.type === "category_selector") renderSelector(body, tile, page);
    else if (tile.type === "text") renderText(body, tile);
    else if (tile.type === "header") renderHeader(body, tile);
    else if (tile.type === "image") renderImage(body, tile);
    else if (tile.type === "map") renderMap(body, tile);
    else if (tile.type === "chart") {
      var host = el("div"); host.style.width = "100%"; host.style.height = "100%";
      body.appendChild(host);
      CHART_HOSTS.push({ host: host, tile: tile, page: page });
    } else {
      body.appendChild(el("div", "dash-note", tile.type));
    }
    return node;
  }

  // ---- header (brand banner) tile --------------------------------------
  // Mirrors theme fallbacks so a chosen family degrades gracefully.
  var FONT_FALLBACK = '"Segoe UI", "Helvetica Neue", Arial, sans-serif';

  function renderHeader(body, tile) {
    var cfg = tile.config || {};
    var inner = el("div", "dash-banner-inner");
    var slot = cfg.logo_slot || "left";
    inner.style.flexDirection = (slot === "above" || slot === "below") ? "column" : "row";
    inner.style.height = "100%";
    var logoFirst = (slot === "left" || slot === "above");

    var logo = null;
    if (tile.logo_uri) {
      logo = el("img", "dash-banner-logo");
      logo.src = tile.logo_uri;
      var sz = Number(cfg.logo_size || 40);
      logo.style.width = sz + "px";
      logo.style.height = sz + "px";
    }
    var title = el("div", "dash-banner-title", cfg.title || "");
    if (cfg.font_family) title.style.fontFamily = '"' + cfg.font_family + '", ' + FONT_FALLBACK;
    title.style.fontSize = Number(cfg.font_size || 22) + "px";
    title.style.textAlign = cfg.align || "left";
    title.style.flex = "1 1 auto";

    if (logo && logoFirst) inner.appendChild(logo);
    inner.appendChild(title);
    if (logo && !logoFirst) inner.appendChild(logo);
    body.appendChild(inner);
  }

  function buildGrid(page) {
    var grid = el("div", "dash-grid");
    // size the surface to the content extent so it scrolls when it overflows
    var maxR = 0, maxB = 0;
    page.tiles.forEach(function (tile) {
      var g = tile.grid || {};
      maxR = Math.max(maxR, Number(g.x || 0) + Math.max(Number(g.w || 0), 0));
      maxB = Math.max(maxB, Number(g.y || 0) + Math.max(Number(g.h || 0), 0));
    });
    grid.style.width = (maxR + 12) + "px";
    grid.style.height = (maxB + 12) + "px";
    page.tiles.forEach(function (tile) { grid.appendChild(renderTile(tile, page)); });
    return grid;
  }

  function renderPage(page) {
    CHART_HOSTS = [];
    var area = document.getElementById("page-area");
    area.innerHTML = "";
    var wrap = el("div", "dash-pagewrap");
    var scroll = el("div", "dash-scroll");
    scroll.appendChild(buildGrid(page));
    wrap.appendChild(scroll);
    area.appendChild(wrap);
    // charts need their host measured after layout
    requestAnimationFrame(function () {
      CHART_HOSTS.forEach(function (c) { drawChart(c.host, c.tile, c.page); });
    });
  }

  // ---- top-level app ----------------------------------------------------
  var ACTIVE_PAGE = null;

  function showPage(page) {
    ACTIVE_PAGE = page;
    Array.prototype.forEach.call(document.querySelectorAll(".dash-tab"), function (t) {
      t.classList.toggle("active", t.getAttribute("data-id") === page.id);
    });
    renderPage(page);
  }

  function build() {
    var app = document.getElementById("app");
    app.innerHTML = "";
    if (DATA.pages.length > 1) {
      var tabs = el("div", "dash-tabs");
      DATA.pages.forEach(function (page) {
        var tab = el("button", "dash-tab", page.title);
        tab.setAttribute("data-id", page.id);
        tab.addEventListener("click", function () { showPage(page); });
        tabs.appendChild(tab);
      });
      app.appendChild(tabs);
    }
    var area = el("div", "dash-page-area");
    area.id = "page-area";
    app.appendChild(area);

    var start = DATA.pages.filter(function (p) { return p.id === DATA.active_page; })[0] || DATA.pages[0];
    if (start) showPage(start);
  }

  var resizeTimer = null;
  window.addEventListener("resize", function () {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      CHART_HOSTS.forEach(function (c) { drawChart(c.host, c.tile, c.page); });
    }, 150);
  });

  if (DATA.pages && DATA.pages.length) build();
  else document.getElementById("app").appendChild(el("div", "dash-note", "Empty dashboard."));
})();
