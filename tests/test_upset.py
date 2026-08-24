"""Tests for the UpSet widget.

The widget's contract has two halves: the intersection maths on the Python
side, and the split between what is synced to the browser and what stays in
the kernel. Both are covered here.
"""

from __future__ import annotations

import doctest
import json

import pytest

import anyupset._upset as upset_module
from anyupset import UpSet


@pytest.fixture
def w() -> UpSet:
    """Three nested sets: 1 is in a only, 2 in a+b, 3 in all three."""
    return UpSet({"a": {1, 2, 3}, "b": {2, 3}, "c": {3}})


# -- construction ---------------------------------------------------------


def test_sets_default_to_largest_first(w: UpSet) -> None:
    assert w.sets == ["a", "b", "c"]


def test_explicit_order_is_respected() -> None:
    assert UpSet({"a": {1}, "b": {1, 2}}, order=["a", "b"]).sets == ["a", "b"]


def test_unknown_name_in_order_is_rejected() -> None:
    with pytest.raises(ValueError, match="not in data"):
        UpSet({"a": {1}}, order=["a", "zz"])


def test_empty_input() -> None:
    empty = UpSet({})
    assert empty.sets == [] and empty._data["n_items"] == 0


# -- intersections are exclusive ------------------------------------------


def test_membership_is_exclusive(w: UpSet) -> None:
    assert w.members("a") == [1]
    assert w.members("a", "b") == [2]
    assert w.members("a", "b", "c") == [3]
    assert w.members("c") == [], "c alone holds nothing; 3 is also in a and b"


def test_argument_order_does_not_matter(w: UpSet) -> None:
    assert w.members("b", "a") == w.members("a", "b")


def test_intersections_covers_every_item(w: UpSet) -> None:
    assert w.intersections == {("a",): [1], ("a", "b"): [2], ("a", "b", "c"): [3]}


def test_unknown_set_is_rejected(w: UpSet) -> None:
    with pytest.raises(ValueError, match="unknown set"):
        w.members("nope")


# -- the inverted input shape ---------------------------------------------


def test_from_memberships_accepts_mapping_pairs_and_generator() -> None:
    pairs = [("Alien", ["scifi", "horror"]), ("Up", ["comedy", "scifi"])]
    from_map = UpSet.from_memberships(dict(pairs))
    assert from_map.sets == ["scifi", "comedy", "horror"]
    assert from_map.members("scifi", "horror") == ["Alien"]
    assert UpSet.from_memberships(pairs).intersections == from_map.intersections
    assert UpSet.from_memberships(p for p in pairs).intersections == from_map.intersections


def test_from_memberships_matches_hand_built_sets() -> None:
    flipped = UpSet.from_memberships({"Alien": ["scifi"], "Up": ["scifi", "comedy"]})
    manual = UpSet({"scifi": {"Alien", "Up"}, "comedy": {"Up"}})
    assert flipped.intersections == manual.intersections


def test_memberships_round_trips() -> None:
    w = UpSet({"a": {1, 2}, "b": {2}})
    assert UpSet.from_memberships(w.memberships).intersections == w.intersections


def test_item_in_no_set_is_absent() -> None:
    assert UpSet.from_memberships({"x": [], "y": ["a"]}).memberships == {"y": ("a",)}


# -- selection ------------------------------------------------------------


def test_select_and_clear(w: UpSet) -> None:
    w.select("a", "b")
    assert w.selected_sets == ["a", "b"]
    assert w.selected_members == [2]
    assert w.selected_mask == 0b011
    w.select()
    assert w.selected_sets == [] and w.selected_members == []


def test_setting_the_mask_directly_stays_consistent(w: UpSet) -> None:
    w.selected_mask = 0b111
    assert w.selected_sets == ["a", "b", "c"] and w.selected_members == [3]


# -- what crosses the wire, and what does not -----------------------------


def test_selected_members_is_not_synced() -> None:
    synced = set(UpSet({"a": {1}}).traits(sync=True))
    assert "selected_members" not in synced, "the full list must stay in the kernel"
    assert {"selected_sets", "selected_values", "selected_mask"} <= synced


def test_examples_are_capped_but_members_are_not() -> None:
    big = UpSet({"x": set(range(500))}, max_examples=10)
    assert len(big._data["intersections"][0]["examples"]) == 10
    big.select("x")
    assert len(big.selected_members) == 500


def test_max_copy_caps_only_the_synced_copy() -> None:
    capped = UpSet({"x": set(range(1000))}, max_copy=10)
    capped.select("x")
    assert len(capped.selected_values) == 10
    assert len(capped.selected_members) == 1000


def test_payload_is_json_serialisable() -> None:
    mixed = UpSet({"s": {1, "two", 3.5}})
    json.dumps(mixed._data)
    mixed.select("s")
    json.dumps(mixed.selected_values)


def test_static_assets_are_loaded(w: UpSet) -> None:
    assert "export default { render }" in w._esm
    assert ".upset-root" in w._css


# -- scalar fidelity for the copy button ----------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("x", "x"),
        (7, 7),
        (True, True),
        (1.5, 1.5),
        (float("nan"), "nan"),
        (float("inf"), "inf"),
        (2**53, str(2**53)),
        (2**53 - 1, 2**53 - 1),
        ((1, 2), "(1, 2)"),
    ],
)
def test_jsonable_keeps_json_safe_scalars(value: object, expected: object) -> None:
    assert UpSet._jsonable(value) == expected


def test_integer_members_survive_as_integers(w: UpSet) -> None:
    w.select("a", "b")
    assert w.selected_values == [2] and isinstance(w.selected_values[0], int)


# -- marimo integration ---------------------------------------------------


def test_value_exposes_the_selection_but_not_the_full_members(w: UpSet) -> None:
    mo = pytest.importorskip("marimo")
    u = mo.ui.anywidget(w)

    keys = set(u.value)
    assert {"selected_sets", "selected_values"} <= keys
    assert "selected_members" not in keys, "unsynced traits must not reach .value"
    assert not any(k.startswith("_") and k != "_data" for k in keys), sorted(keys)

    u.select("a", "b")
    assert u.value["selected_sets"] == ["a", "b"]
    assert u.value["selected_values"] == [2]
    # the wrapper proxies through to the widget, so full fidelity is still there
    assert u.selected_members == [2]
    assert u.members("a", "b") == [2]


# -- docs -----------------------------------------------------------------


def test_docstring_examples() -> None:
    result = doctest.testmod(upset_module)
    assert result.failed == 0, f"{result.failed} of {result.attempted} doctests failed"
