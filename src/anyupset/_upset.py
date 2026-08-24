"""An interactive UpSet plot, built as an anywidget."""

from __future__ import annotations

import pathlib
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import anywidget
import traitlets

_STATIC = pathlib.Path(__file__).parent / "static"


class UpSet(anywidget.AnyWidget):
    """Interactive UpSet plot over a mapping of set name -> members.

    An UpSet plot shows how items are distributed across combinations of sets.
    Each column is one *exclusive* intersection: the items belonging to exactly
    that combination of sets and no others.

    Hover a bar to preview that intersection's members in the side panel; click
    to pin it. The pinned selection is exposed to Python as ``selected_sets``
    and ``selected_members``.

    Parameters
    ----------
    data:
        Mapping of set name to its members. Members must be hashable, and are
        compared by equality across sets.
    order:
        Set names, top to bottom. Defaults to largest set first.
    max_examples:
        How many members of each intersection to send to the browser for the
        examples panel. ``selected_members`` is never truncated.
    max_copy:
        Upper bound on how many members of the *pinned* intersection are synced
        as ``selected_values``. Guards against shipping a runaway group to the
        browser; ``selected_members`` still holds everything.

    Examples
    --------
    >>> w = UpSet({"a": {1, 2, 3}, "b": {2, 3}, "c": {3}})
    >>> w.members("a", "b")          # in a and b, but not c
    [2]
    >>> w.select("a", "b")           # pin it, as if clicked
    >>> w.selected_members
    [2]
    """

    # Beyond this a float64 — and so a JS number — cannot hold an int exactly.
    _JS_SAFE_INT = 2**53 - 1
    _INF = float("inf")

    _esm = _STATIC / "upset.js"
    _css = _STATIC / "upset.css"

    _data = traitlets.Dict().tag(sync=True)

    #: "size" or "degree" — how intersections are ordered left to right.
    sort_by = traitlets.Unicode("size").tag(sync=True)
    #: Hide intersections smaller than this.
    min_size = traitlets.Int(1).tag(sync=True)
    #: Hide intersections of more than this many sets; 0 means no limit.
    max_degree = traitlets.Int(0).tag(sync=True)
    #: Show at most this many columns; 0 means all.
    max_intersections = traitlets.Int(25).tag(sync=True)

    #: Bitmask of the pinned intersection; -1 when nothing is pinned.
    selected_mask = traitlets.Int(-1).tag(sync=True)
    # Not synced: the browser only needs the capped `examples` list, so a large
    # intersection never has to cross the wire.
    #: Names of the pinned sets. Small and JSON-safe, so it is synced and shows
    #: up in ``mo.ui.anywidget(...).value``.
    selected_sets = traitlets.List(traitlets.Unicode(), default_value=[]).tag(sync=True)
    #: The pinned members as the original Python objects. NOT synced — this is
    #: the full-fidelity, uncapped view, and it never crosses the wire.
    selected_members = traitlets.List(default_value=[])
    #: The same members reduced to JSON-safe scalars and capped at ``max_copy``.
    #: Synced, because the panel's copy button needs them in the browser — which
    #: also makes them the member list available through ``.value``.
    selected_values = traitlets.List(default_value=[]).tag(sync=True)

    def __init__(
        self,
        data: Mapping[str, Iterable[Any]],
        *,
        order: Sequence[str] | None = None,
        max_examples: int = 200,
        max_copy: int = 50_000,
        **kwargs: Any,
    ) -> None:
        members = {str(name): set(items) for name, items in data.items()}

        if order is not None:
            names = [str(n) for n in order]
            missing = set(names) - set(members)
            if missing:
                raise ValueError(f"order names not in data: {sorted(missing)}")
        else:
            names = sorted(members, key=lambda n: (-len(members[n]), n))

        masks: dict[Any, int] = {}
        for i, name in enumerate(names):
            bit = 1 << i
            for item in members[name]:
                masks[item] = masks.get(item, 0) | bit

        groups: dict[int, list[Any]] = {}
        for item, mask in masks.items():
            groups.setdefault(mask, []).append(item)
        for items in groups.values():
            items.sort(key=str)

        self._names = names
        self._groups = groups
        self._max_copy = max_copy

        payload = {
            "sets": names,
            "set_sizes": [len(members[n]) for n in names],
            "n_items": len(masks),
            "intersections": [
                {
                    "mask": mask,
                    "degree": bin(mask).count("1"),
                    "size": len(items),
                    "examples": [self._jsonable(x) for x in items[:max_examples]],
                }
                for mask, items in sorted(
                    groups.items(), key=lambda kv: (-len(kv[1]), kv[0])
                )
            ],
        }
        super().__init__(_data=payload, **kwargs)
        self._sync_selection()

    @classmethod
    def from_memberships(
        cls,
        data: Mapping[Any, Iterable[str]] | Iterable[tuple[Any, Iterable[str]]],
        **kwargs: Any,
    ) -> "UpSet":
        """Build from the inverted mapping: each item to the sets it is in.

        The plain constructor takes set name -> members. Data often arrives the
        other way round — one row per item, listing its tags — so this flips it
        for you. Accepts a mapping or any iterable of ``(item, sets)`` pairs.

        Examples
        --------
        >>> w = UpSet.from_memberships({"Alien": ["scifi", "horror"],
        ...                             "Up": ["comedy", "scifi"]})
        >>> w.sets
        ['scifi', 'comedy', 'horror']
        >>> w.members("scifi", "horror")
        ['Alien']
        """
        pairs = data.items() if isinstance(data, Mapping) else data
        sets: dict[str, set[Any]] = {}
        for item, names in pairs:
            for name in names:
                sets.setdefault(str(name), set()).add(item)
        return cls(sets, **kwargs)

    # -- read-only views -------------------------------------------------

    @property
    def sets(self) -> list[str]:
        """Set names, in the order they are drawn top to bottom."""
        return list(self._names)

    @property
    def intersections(self) -> dict[tuple[str, ...], list[Any]]:
        """Every non-empty exclusive intersection, largest first."""
        return {
            self._names_for(mask): list(items)
            for mask, items in sorted(
                self._groups.items(), key=lambda kv: (-len(kv[1]), kv[0])
            )
        }

    @property
    def memberships(self) -> dict[Any, tuple[str, ...]]:
        """Each item mapped to the sets it is in — the inverse of ``data``.

        >>> UpSet({"a": {1}, "b": {1, 2}}).memberships
        {1: ('b', 'a'), 2: ('b',)}
        """
        return {
            item: self._names_for(mask)
            for mask, items in self._groups.items()
            for item in items
        }

    def members(self, *names: str) -> list[Any]:
        """Members belonging to exactly ``names`` and no other set."""
        return list(self._groups.get(self._mask_for(names), []))

    def select(self, *names: str) -> None:
        """Pin an intersection, as clicking it would. No arguments clears."""
        self.selected_mask = self._mask_for(names) if names else -1

    # -- internals -------------------------------------------------------

    def _mask_for(self, names: Iterable[str]) -> int:
        mask = 0
        for name in names:
            if name not in self._names:
                raise ValueError(
                    f"unknown set {name!r}; known sets: {self._names}"
                )
            mask |= 1 << self._names.index(name)
        return mask

    def _names_for(self, mask: int) -> tuple[str, ...]:
        return tuple(n for i, n in enumerate(self._names) if mask & (1 << i))

    @classmethod
    def _jsonable(cls, value: Any) -> Any:
        """Keep JSON-safe scalars intact, so copy can emit real Python literals.

        Members reach the browser as JSON. Anything that survives that trip
        unchanged is passed through, so integer ids copy back as ``[1, 2]``
        rather than ``["1", "2"]``. Everything else falls back to its string
        form.
        """
        if isinstance(value, (str, bool)):
            return value
        if isinstance(value, int):
            return value if abs(value) <= cls._JS_SAFE_INT else str(value)
        if isinstance(value, float):
            # NaN fails every comparison, so this rejects NaN and both infinities.
            return value if -cls._INF < value < cls._INF else str(value)
        return str(value)

    @traitlets.observe("selected_mask")
    def _on_selected_mask(self, _change: Any) -> None:
        self._sync_selection()

    def _sync_selection(self) -> None:
        mask = self.selected_mask
        if mask is None or mask <= 0:
            self.selected_sets = []
            self.selected_members = []
            self.selected_values = []
        else:
            members = list(self._groups.get(mask, []))
            self.selected_sets = list(self._names_for(mask))
            self.selected_members = members
            self.selected_values = [
                self._jsonable(x) for x in members[: self._max_copy]
            ]
