const NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
const fmt = (n) => n.toLocaleString();
const popcount = (m) => { let c = 0; while (m) { m &= m - 1; c++; } return c; };

// Members arrive as JSON scalars; render each as the equivalent Python literal.
// JSON string escaping is a subset of Python's, so stringify is safe for text.
function pyLiteral(x) {
  if (x === null || x === undefined) return "None";
  if (typeof x === "boolean") return x ? "True" : "False";
  if (typeof x === "number") return Number.isFinite(x) ? String(x) : JSON.stringify(String(x));
  return JSON.stringify(String(x));
}

function pyList(values) {
  const parts = values.map(pyLiteral);
  const oneLine = "[" + parts.join(", ") + "]";
  if (oneLine.length <= 80) return oneLine;
  return "[\n" + parts.map((p) => "    " + p + ",").join("\n") + "\n]";
}
const namesOf = (mask, sets) => sets.filter((_, i) => mask & (1 << i));

// layout constants
const BAR_H = 110, ROW_H = 22, COL_W = 26, DOT_R = 6.5;
// Cap DOM rows in the panel: a pinned group can hold tens of thousands.
const RENDER_CAP = 300;
const SIZEBAR_W = 54, GAP = 10, PAD_T = 14, LABEL_MAX = 120;

function render({ model, el: host }) {
  const ac = new AbortController();
  const signal = ac.signal;

  const root = el("div", "upset-root");
  const controls = el("div", "upset-controls");
  const body = el("div", "upset-body");
  const plotWrap = el("div", "upset-plot");
  const panel = el("div", "upset-panel");
  const tip = el("div", "upset-tip");
  body.append(plotWrap, panel);
  root.append(controls, body, tip);
  host.appendChild(root);

  // ---------- controls ----------
  const sortSel = el("select", "upset-input");
  for (const [v, t] of [["size", "size"], ["degree", "degree"]]) {
    const o = el("option", null, t); o.value = v; sortSel.appendChild(o);
  }
  const minInp = el("input", "upset-input upset-num"); minInp.type = "number"; minInp.min = "1";
  const degInp = el("input", "upset-input upset-num"); degInp.type = "number"; degInp.min = "0";
  degInp.title = "0 = no limit";
  const topInp = el("input", "upset-input upset-num"); topInp.type = "number"; topInp.min = "0";
  topInp.title = "0 = show all";
  const clearBtn = el("button", "upset-btn", "clear");
  const status = el("span", "upset-status");

  const field = (label, node) => {
    const w = el("label", "upset-field");
    w.append(el("span", "upset-field-label", label), node);
    return w;
  };
  controls.append(
    field("sort by", sortSel), field("min size", minInp),
    field("max degree", degInp), field("top n", topInp), clearBtn, status,
  );

  sortSel.addEventListener("change", () => {
    model.set("sort_by", sortSel.value); model.save_changes(); drawAll();
  }, { signal });
  minInp.addEventListener("change", () => {
    model.set("min_size", Math.max(1, +minInp.value || 1)); model.save_changes(); drawAll();
  }, { signal });
  degInp.addEventListener("change", () => {
    model.set("max_degree", Math.max(0, +degInp.value || 0)); model.save_changes(); drawAll();
  }, { signal });
  topInp.addEventListener("change", () => {
    model.set("max_intersections", Math.max(0, +topInp.value || 0)); model.save_changes(); drawAll();
  }, { signal });
  clearBtn.addEventListener("click", () => select(-1), { signal });

  // ---------- state ----------
  let hoverMask = null;
  let query = "";
  let viewCache = null;   // memoized filter+sort of the intersection list
  let maskIndex = null;   // mask -> intersection, built once per dataset
  let panelFrame = 0;     // rAF handle, coalesces panel redraws while moving

  const selMask = () => model.get("selected_mask");
  function select(mask) {
    model.set("selected_mask", mask); model.save_changes();
    drawAll();
  }

  function rowsView() {
    if (viewCache) return viewCache;
    const d = model.get("_data") || {};
    const sets = d.sets || [];
    const minSize = model.get("min_size"), maxDeg = model.get("max_degree");
    const cap = model.get("max_intersections");
    let rows = (d.intersections || []).filter(
      (r) => r.size >= minSize && (maxDeg <= 0 || r.degree <= maxDeg)
    );
    if (model.get("sort_by") === "degree") {
      rows.sort((a, b) => a.degree - b.degree || b.size - a.size);
    } else {
      rows.sort((a, b) => b.size - a.size || a.degree - b.degree);
    }
    const total = rows.length;
    if (cap > 0 && rows.length > cap) rows = rows.slice(0, cap);
    viewCache = { sets, setSizes: d.set_sizes || [], rows, total, all: d.intersections || [] };
    return viewCache;
  }

  function byMask(mask) {
    if (!maskIndex) {
      maskIndex = new Map();
      for (const r of model.get("_data")?.intersections || []) maskIndex.set(r.mask, r);
    }
    return maskIndex.get(mask) || null;
  }

  // Hover fires far faster than the eye can read; render at most once a frame.
  function schedulePanel() {
    if (panelFrame) return;
    panelFrame = requestAnimationFrame(() => {
      panelFrame = 0;
      drawPanel();
    });
  }

  async function copyText(text) {
    // writeText can hang rather than reject when the document lacks focus or
    // user activation, so never await it unbounded — the button must always
    // report something back.
    const limit = (promise, ms) => Promise.race([
      promise,
      new Promise((_, rej) => setTimeout(() => rej(new Error("clipboard timeout")), ms)),
    ]);
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await limit(navigator.clipboard.writeText(text), 1500);
        return true;
      }
    } catch (err) { /* fall through to the legacy path */ }
    const ta = el("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;top:-1000px;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
    ta.remove();
    return ok;
  }

  // ---------- plot ----------
  function drawPlot() {
    const { sets, setSizes, rows, total, all } = rowsView();
    plotWrap.replaceChildren();

    const labelW = Math.min(
      LABEL_MAX,
      Math.max(40, ...sets.map((s) => s.length * 7 + 6))
    );
    // gutter wide enough for the largest set count, e.g. "16,223"
    const countW = fmt(Math.max(1, ...setSizes)).length * 6.5 + 4;
    const barX = countW + 8;
    const left = barX + SIZEBAR_W + GAP + labelW + GAP;
    const matrixTop = PAD_T + BAR_H + 18;
    const width = left + Math.max(rows.length, 1) * COL_W + 8;
    const height = matrixTop + sets.length * ROW_H + 6;

    // Bound the examples panel to the plot's own height. Without this a large
    // intersection stretches the flex row — and so the whole widget — to
    // thousands of pixels instead of scrolling inside the panel.
    panel.style.maxHeight = Math.max(height, 200) + "px";

    const svg = svgEl("svg", { width, height, viewBox: `0 0 ${width} ${height}`, class: "upset-svg" });

    if (!rows.length) {
      svg.appendChild(svgEl("text", { x: 8, y: 24, class: "upset-empty-text" })).textContent =
        "no intersections match the filters";
      plotWrap.appendChild(svg);
      return;
    }

    const maxSize = Math.max(...rows.map((r) => r.size));
    const maxSet = Math.max(1, ...setSizes);
    const barY = (v) => PAD_T + BAR_H - (v / maxSize) * BAR_H;

    // y axis for the intersection bars. Drawn as a real axis — upright, with
    // tick marks at 0 and the maximum — so the top number cannot be mistaken
    // for a count of sets.
    const axisX = left - 8;
    const baseY = PAD_T + BAR_H;
    svg.appendChild(svgEl("line", {
      x1: axisX, x2: width - 4, y1: baseY, y2: baseY, class: "upset-axis",
    }));
    svg.appendChild(svgEl("line", {
      x1: axisX, x2: axisX, y1: PAD_T - 2, y2: baseY, class: "upset-axis",
    }));
    for (const [value, y] of [[maxSize, PAD_T], [0, baseY]]) {
      svg.appendChild(svgEl("line", {
        x1: axisX - 4, x2: axisX, y1: y, y2: y, class: "upset-axis",
      }));
      const lbl = svgEl("text", {
        x: axisX - 7, y: y + 3.5, class: "upset-tick", "text-anchor": "end",
      });
      lbl.textContent = fmt(value);
      svg.appendChild(lbl);
    }
    const titleX = axisX - 13 - fmt(maxSize).length * 6.5;
    if (titleX > 8) {
      const title = svgEl("text", {
        x: titleX, y: PAD_T + BAR_H / 2, class: "upset-axis-title", "text-anchor": "middle",
        transform: `rotate(-90 ${titleX} ${PAD_T + BAR_H / 2})`,
      });
      title.textContent = "intersection size";
      svg.appendChild(title);
    }

    // ----- left block: per-set bars + labels + row stripes
    sets.forEach((name, i) => {
      const cy = matrixTop + i * ROW_H + ROW_H / 2;
      svg.appendChild(svgEl("rect", {
        x: 0, y: cy - ROW_H / 2, width, height: ROW_H,
        class: i % 2 ? "upset-stripe" : "upset-stripe upset-stripe-alt",
      }));
      const w = (setSizes[i] / maxSet) * SIZEBAR_W;
      svg.appendChild(svgEl("rect", {
        x: barX + SIZEBAR_W - w, y: cy - 6, width: Math.max(w, 1), height: 12,
        class: "upset-setbar", rx: 2,
      }));
      const c = svgEl("text", {
        x: countW, y: cy + 4, class: "upset-setcount",
        "text-anchor": "end", "data-set": i,
      });
      c.textContent = fmt(setSizes[i]);
      svg.appendChild(c);
      const t = svgEl("text", {
        x: barX + SIZEBAR_W + GAP + labelW, y: cy + 4,
        class: "upset-setlabel", "text-anchor": "end", "data-set": i,
      });
      t.textContent = name;
      const title = svgEl("title", {});
      title.textContent = `${name} — ${fmt(setSizes[i])} items`;
      t.appendChild(title);
      svg.appendChild(t);
    });

    // ----- columns
    const showNums = rows.length <= 26;
    rows.forEach((r, j) => {
      const cx = left + j * COL_W + COL_W / 2;
      const g = svgEl("g", { class: "upset-col", "data-mask": r.mask });
      const active = r.mask === selMask();
      if (active) g.classList.add("is-selected");

      g.appendChild(svgEl("rect", {
        x: cx - COL_W / 2, y: PAD_T - 6, width: COL_W,
        height: BAR_H + 6 + 18 + sets.length * ROW_H, class: "upset-colbg", rx: 3,
      }));

      const h = Math.max((r.size / maxSize) * BAR_H, 2);
      g.appendChild(svgEl("rect", {
        x: cx - (COL_W - 9) / 2, y: PAD_T + BAR_H - h,
        width: COL_W - 9, height: h, class: "upset-bar", rx: 2,
      }));
      if (showNums) {
        const n = svgEl("text", { x: cx, y: barY(r.size) - 4, class: "upset-barnum", "text-anchor": "middle" });
        n.textContent = fmt(r.size);
        g.appendChild(n);
      }

      const idx = [];
      sets.forEach((_, i) => { if (r.mask & (1 << i)) idx.push(i); });
      if (idx.length > 1) {
        g.appendChild(svgEl("line", {
          x1: cx, x2: cx,
          y1: matrixTop + idx[0] * ROW_H + ROW_H / 2,
          y2: matrixTop + idx[idx.length - 1] * ROW_H + ROW_H / 2,
          class: "upset-link",
        }));
      }
      sets.forEach((_, i) => {
        g.appendChild(svgEl("circle", {
          cx, cy: matrixTop + i * ROW_H + ROW_H / 2, r: DOT_R,
          class: (r.mask & (1 << i)) ? "upset-dot is-on" : "upset-dot",
        }));
      });

      // hit target on top
      g.appendChild(svgEl("rect", {
        x: cx - COL_W / 2, y: PAD_T - 6, width: COL_W,
        height: BAR_H + 6 + 18 + sets.length * ROW_H, class: "upset-hit",
      }));
      svg.appendChild(g);
    });

    svg.addEventListener("mousemove", (ev) => {
      const g = ev.target.closest(".upset-col");
      const mask = g ? +g.dataset.mask : null;
      if (mask !== hoverMask) {
        hoverMask = mask;
        svg.querySelectorAll(".upset-col").forEach((n) =>
          n.classList.toggle("is-hover", +n.dataset.mask === mask)
        );
        highlightSetLabels(svg, mask ?? selMask(), sets);
        schedulePanel();
      }
      if (mask == null) { tip.style.display = "none"; return; }
      const r = byMask(mask);
      const rect = root.getBoundingClientRect();
      tip.innerHTML = "";
      tip.append(
        el("div", "upset-tip-title", namesOf(mask, sets).join(" ∩ ") || "—"),
        el("div", "upset-tip-sub",
           `${fmt(r.size)} items · ${(100 * r.size / (model.get("_data").n_items || 1)).toFixed(1)}% · degree ${r.degree}`),
        el("div", "upset-tip-hint", mask === selMask() ? "click to unpin" : "click to pin"),
      );
      tip.style.display = "block";
      const tw = tip.offsetWidth;
      tip.style.left = Math.min(ev.clientX - rect.left + 14, rect.width - tw - 6) + "px";
      tip.style.top = (ev.clientY - rect.top + 16) + "px";
    }, { signal });

    svg.addEventListener("mouseleave", () => {
      hoverMask = null;
      tip.style.display = "none";
      svg.querySelectorAll(".upset-col").forEach((n) => n.classList.remove("is-hover"));
      highlightSetLabels(svg, selMask(), sets);
      schedulePanel();
    }, { signal });

    svg.addEventListener("click", (ev) => {
      const g = ev.target.closest(".upset-col");
      if (!g) return;
      const mask = +g.dataset.mask;
      select(mask === selMask() ? -1 : mask);
    }, { signal });

    highlightSetLabels(svg, hoverMask ?? selMask(), sets);
    plotWrap.appendChild(svg);

    status.textContent =
      `${fmt(rows.length)}${rows.length < total ? ` of ${fmt(total)}` : ""} intersections · ` +
      `${fmt(all.length)} total · ${fmt(model.get("_data").n_items || 0)} items`;
  }

  function highlightSetLabels(svg, mask, sets) {
    svg.querySelectorAll(".upset-setlabel, .upset-setcount").forEach((t) => {
      const i = +t.dataset.set;
      t.classList.toggle("is-active", mask > 0 && !!(mask & (1 << i)));
    });
  }

  // ---------- examples panel ----------
  function drawPanel() {
    const { sets } = rowsView();
    const mask = hoverMask ?? selMask();
    const pinned = selMask() > 0 && (hoverMask == null || hoverMask === selMask());
    panel.replaceChildren();

    if (!(mask > 0)) {
      const empty = el("div", "upset-panel-empty");
      empty.append(
        el("div", "upset-panel-empty-icon", "◍"),
        el("div", null, "Hover a bar to peek at its members."),
        el("div", "upset-panel-empty-sub", "Click to pin the selection for Python."),
      );
      panel.appendChild(empty);
      return;
    }

    const r = byMask(mask);
    if (!r) {
      const none = el("div", "upset-panel-empty");
      none.append(
        el("div", "upset-panel-empty-icon", "\u25cc"),
        el("div", null, "No items belong to exactly " + (namesOf(mask, sets).join(" \u2229 ") || "these sets") + "."),
      );
      panel.appendChild(none);
      return;
    }
    const head = el("div", "upset-panel-head");
    const titleRow = el("div", "upset-panel-titlerow");
    titleRow.appendChild(el("div", "upset-panel-title", namesOf(mask, sets).join(" ∩ ")));
    titleRow.appendChild(el("span", pinned ? "upset-pin is-on" : "upset-pin", pinned ? "pinned" : "preview"));
    head.appendChild(titleRow);
    const pct = (100 * r.size / (model.get("_data").n_items || 1)).toFixed(1);
    head.appendChild(el("div", "upset-panel-sub",
      `${fmt(r.size)} item${r.size === 1 ? "" : "s"} · ${pct}% · exactly these ${r.degree} set${r.degree === 1 ? "" : "s"}`));

    // The panel only holds `examples` (capped), but the pinned intersection
    // also has its full member list synced, so copy can be complete.
    const full = mask === selMask() ? model.get("selected_values") || [] : [];
    const copyList = full.length ? full : r.examples;

    const actions = el("div", "upset-actions");
    const search = el("input", "upset-input upset-search");
    search.type = "search"; search.placeholder = "filter examples…"; search.value = query;
    search.addEventListener("input", () => { query = search.value; renderList(); }, { signal });

    const copyBtn = el("button", "upset-btn upset-copy");
    const copyLabel = copyList.length >= r.size
      ? `copy ${fmt(r.size)}`
      : `copy ${fmt(copyList.length)} of ${fmt(r.size)}`;
    copyBtn.textContent = copyLabel;
    copyBtn.title = "Copy these members to the clipboard as a Python list";
    copyBtn.addEventListener("click", async () => {
      const q = query.trim().toLowerCase();
      const out = q ? copyList.filter((x) => String(x).toLowerCase().includes(q)) : copyList;
      const ok = await copyText(pyList(out));
      copyBtn.textContent = ok ? `copied ${fmt(out.length)} ✓` : "copy failed";
      copyBtn.classList.toggle("is-done", ok);
      setTimeout(() => {
        copyBtn.textContent = copyLabel;
        copyBtn.classList.remove("is-done");
      }, 1400);
    }, { signal });

    actions.append(search, copyBtn);
    head.appendChild(actions);
    panel.appendChild(head);

    const list = el("div", "upset-list");
    panel.appendChild(list);

    function renderList() {
      const q = query.trim().toLowerCase();
      const source = full.length ? full : r.examples;
      const matched = q ? source.filter((x) => String(x).toLowerCase().includes(q)) : source;
      const shown = matched.slice(0, RENDER_CAP);
      const frag = document.createDocumentFragment();
      for (const x of shown) frag.appendChild(el("div", "upset-item", String(x)));
      if (!matched.length) {
        frag.appendChild(el("div", "upset-item upset-item-muted", "no match"));
      }
      const hidden = matched.length - shown.length;
      if (hidden > 0) {
        frag.appendChild(el("div", "upset-more",
          `+ ${fmt(hidden)} more not listed — copy takes all ${fmt(matched.length)}`));
      } else if (!q && source.length < r.size) {
        frag.appendChild(el("div", "upset-more",
          `+ ${fmt(r.size - source.length)} more — pin this bar to reach them all`));
      }
      list.replaceChildren(frag);
    }
    renderList();
    // keep focus while typing
    if (query) { search.focus(); search.setSelectionRange(query.length, query.length); }
  }

  function drawAll() {
    viewCache = null;
    maskIndex = null;
    sortSel.value = model.get("sort_by");
    minInp.value = model.get("min_size");
    degInp.value = model.get("max_degree");
    topInp.value = model.get("max_intersections");
    drawPlot();
    drawPanel();
  }

  for (const t of ["_data", "sort_by", "min_size", "max_degree", "max_intersections", "selected_mask"]) {
    model.on("change:" + t, drawAll);
  }
  drawAll();

  return () => {
    if (panelFrame) cancelAnimationFrame(panelFrame);
    ac.abort();
  };
}

export default { render };
