# anyupset

Interactive [UpSet plots](https://upset.app/) as an
[anywidget](https://anywidget.dev), for marimo and Jupyter.

An UpSet plot shows how items are distributed across combinations of sets.
The point of this one is **seeing the actual items**: hover any bar and its
members appear in the side panel; click to pin the selection and pull it back
into Python.

## Install

```sh
uv add anyupset
```

## Use

```python
from anyupset import UpSet

upset = UpSet({
    "drama":   {"Titanic", "Casablanca", "Whiplash"},
    "romance": {"Titanic", "Casablanca", "Notting Hill"},
    "comedy":  {"Notting Hill"},
})
upset
```

Columns are *exclusive* intersections: each item belongs to exactly one
column, the one matching the full set of sets it is in.

### Reading the selection

```python
upset.selected_sets      # ['drama', 'romance']
upset.selected_members   # ['Casablanca', 'Titanic'] — original Python objects
upset.selected_values    # the same, reduced to JSON-safe scalars
```

In marimo, wrap it so downstream cells re-run on interaction:

```python
upset = mo.ui.anywidget(UpSet(...))
upset.value["selected_sets"]     # ['drama', 'romance']
upset.value["selected_values"]   # ['Casablanca', 'Titanic']
```

`.value` carries only *synced* traits. `selected_members` is deliberately not
synced — it holds the original objects, uncapped, and never crosses the wire —
but the wrapper proxies attribute access, so `upset.selected_members` still
works. Use `.value` for reactivity, the attribute when you need fidelity.

### Without clicking

```python
upset.sets                          # ['drama', 'romance', 'comedy']
upset.members("drama", "romance")   # ['Casablanca', 'Titanic']
upset.intersections                 # every non-empty combination, largest first
upset.select("drama", "romance")    # pin it, as a click would
upset.select()                      # clear
```

### Controls

`sort_by` (`"size"` / `"degree"`), `min_size`, `max_degree`, and
`max_intersections` are synced traitlets — settable from the toolbar or from
Python, and they stay in step either way.

```python
upset.min_size = 3          # hide the long tail of singletons
upset.max_degree = 2        # only single sets and pairs
```

## Examples

Both demos build the same plot from the same 156-film dataset.

```sh
# marimo — reactive: clicking a bar re-runs the cells below it
uv run --group dev marimo edit examples/marimo_demo.py

# Jupyter — re-run the reading cell yourself after clicking
uv run --group jupyter jupyter lab examples/jupyter_demo.ipynb
```

## Notes

`max_examples` (default 200) caps how many members of each intersection are
sent to the browser for the panel. `selected_members` is always complete — it
is deliberately not synced, so a large intersection never crosses the wire.
