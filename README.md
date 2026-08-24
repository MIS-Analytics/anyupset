# anyupset

Interactive [UpSet plots](https://upset.app/) as an
[anywidget](https://anywidget.dev), for marimo and Jupyter.

An UpSet plot shows how items are distributed across combinations of sets.
The point of this one is **seeing the actual items**: hover any bar and its
members appear in the side panel; click to pin the selection and pull it back
into Python.

![anyupset in action](https://raw.githubusercontent.com/MIS-Analytics/anyupset/main/docs/demo.gif)

**[Try it in your browser →](https://mis-analytics.github.io/anyupset/)** —
a live notebook running on WebAssembly, nothing to install.

> [!WARNING]
> **Early days.** This is a `0.1` release. The API may still change, and the
> widget has seen little use beyond its own test suite and demos — pin an exact
> version if you build on it, and please report anything that breaks.
>
> **Written with AI assistance.** Nearly all of this project — the widget, the
> tests, the demos and the CI — was written by Claude in a pair-programming
> session, then reviewed and directed by a human. It is tested, but it has not
> had the scrutiny of a codebase grown by hand over time. Read the source
> before you depend on it.

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

Data often arrives the other way round — one row per item, listing what it
belongs to. `from_memberships` flips it for you, and builds the same plot:

```python
upset = UpSet.from_memberships({
    "Titanic":      ["drama", "romance"],
    "Casablanca":   ["drama", "romance"],
    "Whiplash":     ["drama"],
    "Notting Hill": ["romance", "comedy"],
})
```

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

## Examples

Both demos build the same plot from the same 156-film dataset.

```sh
# marimo — reactive: clicking a bar re-runs the cells below it
uv run --group dev marimo edit examples/marimo_demo.py

# Jupyter — re-run the reading cell yourself after clicking
uv run --group jupyter jupyter lab examples/jupyter_demo.ipynb
```
