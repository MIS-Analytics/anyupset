import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    import polars as pl

    from anyupset import UpSet


@app.cell(hide_code=True)
def _():
    mo.md("""
    # UpSet — interactive

    An UpSet plot answers *"which combinations of sets do my items fall into?"*.
    The twist here: **click (or just hover) a bar to see actual examples from that
    intersection**, and pull the selection back into Python.

    The widget itself lives in `src/anyupset/` — this notebook just uses it.
    Data goes in either shape: `UpSet({set_name: members})`, or
    `UpSet.from_memberships({item: sets_it_is_in})` as used below.
    """)
    return


@app.cell(hide_code=True)
def _():
    import random

    MOVIES = [
        ("Alien", ["sci-fi", "horror", "thriller"]),
        ("Aliens", ["sci-fi", "action", "horror"]),
        ("Blade Runner", ["sci-fi", "thriller", "drama"]),
        ("Blade Runner 2049", ["sci-fi", "drama", "thriller"]),
        ("The Thing", ["sci-fi", "horror", "thriller"]),
        ("Jurassic Park", ["sci-fi", "action", "adventure"]),
        ("Back to the Future", ["sci-fi", "comedy", "adventure"]),
        ("E.T.", ["sci-fi", "drama", "adventure"]),
        ("Close Encounters", ["sci-fi", "drama"]),
        ("Contact", ["sci-fi", "drama"]),
        ("Ex Machina", ["sci-fi", "thriller", "drama"]),
        ("Annihilation", ["sci-fi", "horror", "thriller"]),
        ("District 9", ["sci-fi", "action", "thriller"]),
        ("Children of Men", ["sci-fi", "thriller", "drama"]),
        ("Snowpiercer", ["sci-fi", "action", "thriller"]),
        ("Looper", ["sci-fi", "action", "thriller"]),
        ("Edge of Tomorrow", ["sci-fi", "action", "adventure"]),
        ("Minority Report", ["sci-fi", "action", "thriller"]),
        ("Total Recall", ["sci-fi", "action", "thriller"]),
        ("RoboCop", ["sci-fi", "action", "thriller"]),
        ("The Terminator", ["sci-fi", "action", "thriller"]),
        ("Terminator 2", ["sci-fi", "action", "thriller"]),
        ("Predator", ["sci-fi", "action", "horror"]),
        ("Starship Troopers", ["sci-fi", "action", "comedy"]),
        ("The Fifth Element", ["sci-fi", "action", "adventure", "comedy"]),
        ("Ghost in the Shell", ["sci-fi", "animation", "action"]),
        ("Akira", ["sci-fi", "animation", "action"]),
        ("Ghostbusters", ["comedy", "horror", "action"]),
        ("Shaun of the Dead", ["comedy", "horror"]),
        ("Zombieland", ["comedy", "horror", "action"]),
        ("What We Do in the Shadows", ["comedy", "horror"]),
        ("Get Out", ["horror", "thriller"]),
        ("Us", ["horror", "thriller"]),
        ("Hereditary", ["horror", "drama"]),
        ("Midsommar", ["horror", "drama"]),
        ("The Witch", ["horror", "drama"]),
        ("The Babadook", ["horror", "drama"]),
        ("A Quiet Place", ["horror", "thriller", "sci-fi"]),
        ("The Shining", ["horror", "thriller", "drama"]),
        ("Psycho", ["horror", "thriller"]),
        ("The Exorcist", ["horror", "drama"]),
        ("Jaws", ["horror", "thriller", "adventure"]),
        ("The Silence of the Lambs", ["horror", "thriller", "drama"]),
        ("Se7en", ["thriller", "drama"]),
        ("Zodiac", ["thriller", "drama"]),
        ("Prisoners", ["thriller", "drama"]),
        ("Gone Girl", ["thriller", "drama"]),
        ("Nightcrawler", ["thriller", "drama"]),
        ("No Country for Old Men", ["thriller", "drama"]),
        ("Sicario", ["thriller", "action", "drama"]),
        ("Heat", ["action", "thriller", "drama"]),
        ("Collateral", ["action", "thriller", "drama"]),
        ("Die Hard", ["action", "thriller"]),
        ("Mad Max: Fury Road", ["action", "adventure", "sci-fi"]),
        ("The Matrix", ["sci-fi", "action"]),
        ("Inception", ["sci-fi", "action", "thriller"]),
        ("Interstellar", ["sci-fi", "drama", "adventure"]),
        ("Arrival", ["sci-fi", "drama"]),
        ("Gravity", ["sci-fi", "thriller", "drama"]),
        ("The Martian", ["sci-fi", "drama", "comedy", "adventure"]),
        ("Her", ["sci-fi", "drama", "romance"]),
        ("Eternal Sunshine", ["sci-fi", "romance", "drama"]),
        ("WALL-E", ["animation", "sci-fi", "romance", "adventure"]),
        ("Up", ["animation", "adventure", "comedy", "drama"]),
        ("Inside Out", ["animation", "comedy", "drama"]),
        ("Toy Story", ["animation", "comedy", "adventure"]),
        ("Toy Story 3", ["animation", "comedy", "adventure", "drama"]),
        ("Finding Nemo", ["animation", "adventure", "comedy"]),
        ("Ratatouille", ["animation", "comedy", "drama"]),
        ("Monsters, Inc.", ["animation", "comedy", "adventure"]),
        ("Spirited Away", ["animation", "adventure"]),
        ("My Neighbor Totoro", ["animation", "adventure"]),
        ("Princess Mononoke", ["animation", "adventure", "action"]),
        ("Howl's Moving Castle", ["animation", "adventure", "romance"]),
        ("Spider-Verse", ["animation", "action", "adventure", "sci-fi"]),
        ("The Incredibles", ["animation", "action", "comedy", "adventure"]),
        ("Shrek", ["animation", "comedy", "adventure", "romance"]),
        ("Coco", ["animation", "drama", "adventure"]),
        ("Kung Fu Panda", ["animation", "action", "comedy"]),
        ("How to Train Your Dragon", ["animation", "adventure", "action"]),
        ("The Lion King", ["animation", "drama", "adventure"]),
        ("Klaus", ["animation", "comedy", "adventure"]),
        ("The Princess Bride", ["adventure", "comedy", "romance"]),
        ("Indiana Jones", ["adventure", "action"]),
        ("The Goonies", ["adventure", "comedy"]),
        ("Pirates of the Caribbean", ["adventure", "action", "comedy"]),
        ("The Mummy", ["adventure", "action", "comedy", "horror"]),
        ("National Treasure", ["adventure", "action", "thriller"]),
        ("The Lord of the Rings", ["adventure", "action", "drama"]),
        ("Star Wars", ["sci-fi", "adventure", "action"]),
        ("The Empire Strikes Back", ["sci-fi", "adventure", "action"]),
        ("Rogue One", ["sci-fi", "adventure", "action", "drama"]),
        ("Guardians of the Galaxy", ["sci-fi", "action", "comedy", "adventure"]),
        ("Thor: Ragnarok", ["action", "comedy", "adventure", "sci-fi"]),
        ("Black Panther", ["action", "adventure", "drama", "sci-fi"]),
        ("Iron Man", ["action", "adventure", "sci-fi"]),
        ("The Avengers", ["action", "adventure", "sci-fi"]),
        ("Groundhog Day", ["comedy", "romance", "sci-fi"]),
        ("When Harry Met Sally", ["comedy", "romance"]),
        ("Notting Hill", ["comedy", "romance"]),
        ("Four Weddings and a Funeral", ["comedy", "romance"]),
        ("Bridget Jones's Diary", ["comedy", "romance"]),
        ("10 Things I Hate About You", ["comedy", "romance"]),
        ("Crazy Rich Asians", ["comedy", "romance", "drama"]),
        ("Palm Springs", ["comedy", "romance", "sci-fi"]),
        ("About Time", ["comedy", "romance", "sci-fi", "drama"]),
        ("La La Land", ["romance", "drama", "comedy"]),
        ("Titanic", ["romance", "drama"]),
        ("Casablanca", ["romance", "drama"]),
        ("Before Sunrise", ["romance", "drama"]),
        ("Call Me by Your Name", ["romance", "drama"]),
        ("Brokeback Mountain", ["romance", "drama"]),
        ("Moonlight", ["romance", "drama"]),
        ("Carol", ["romance", "drama"]),
        ("Portrait of a Lady on Fire", ["romance", "drama"]),
        ("The Godfather", ["drama"]),
        ("There Will Be Blood", ["drama"]),
        ("12 Angry Men", ["drama"]),
        ("Schindler's List", ["drama"]),
        ("Manchester by the Sea", ["drama"]),
        ("Nomadland", ["drama"]),
        ("Whiplash", ["drama"]),
        ("The Social Network", ["drama"]),
        ("Spotlight", ["drama", "thriller"]),
        ("Goodfellas", ["drama", "thriller"]),
        ("The Departed", ["drama", "thriller", "action"]),
        ("Parasite", ["thriller", "drama", "comedy"]),
        ("Knives Out", ["comedy", "thriller"]),
        ("Fargo", ["comedy", "thriller", "drama"]),
        ("Burn After Reading", ["comedy", "thriller"]),
        ("In Bruges", ["comedy", "thriller", "drama"]),
        ("The Big Lebowski", ["comedy"]),
        ("Airplane!", ["comedy"]),
        ("Anchorman", ["comedy"]),
        ("Superbad", ["comedy"]),
        ("Booksmart", ["comedy"]),
        ("Bridesmaids", ["comedy"]),
        ("Hot Fuzz", ["comedy", "action", "thriller"]),
        ("The Nice Guys", ["comedy", "action", "thriller"]),
        ("21 Jump Street", ["comedy", "action"]),
        ("Kingsman", ["comedy", "action", "adventure"]),
        ("Deadpool", ["comedy", "action", "sci-fi"]),
        ("Kill Bill", ["action", "thriller"]),
        ("John Wick", ["action", "thriller"]),
        ("Mission: Impossible", ["action", "thriller", "adventure"]),
        ("Speed", ["action", "thriller"]),
        ("Point Break", ["action", "thriller"]),
        ("Casino Royale", ["action", "thriller", "adventure"]),
        ("Skyfall", ["action", "thriller", "drama"]),
        ("The Bourne Identity", ["action", "thriller"]),
        ("Top Gun", ["action", "drama"]),
        ("Gladiator", ["action", "drama", "adventure"]),
        ("The Dark Knight", ["action", "thriller", "drama"]),
        ("Logan", ["action", "drama", "sci-fi"]),
        ("Everything Everywhere", ["sci-fi", "comedy", "action", "drama"]),
        ("The Truman Show", ["drama", "comedy", "sci-fi"]),
    # ] + [
    #     ( "".join( [random.choice("abc") for i in range(15)] ), random.sample(["action", "drama", "sci-fi"], 2) ) for _ in range(1_000) 
    ]
    return (MOVIES,)


@app.cell
def _(MOVIES):
    # MOVIES is item -> tags, so flip it on the way in. The plain
    # UpSet({set_name: members}) constructor takes the other shape.
    #
    # mo.ui.anywidget makes this a marimo UI element, so cells referencing
    # `upset` re-run on interaction. It proxies attribute access through to the
    # widget, so `.selected_members` still hands back the real Python objects —
    # `.value` only ever carries the synced traits.
    upset = mo.ui.anywidget(UpSet.from_memberships(MOVIES))
    upset
    return (upset,)


@app.cell
def _(upset):
    upset.value
    return


@app.cell
def _(MOVIES, upset):
    # Read through .value, the marimo convention: it is the synced state of the
    # UI element. `selected_values` is thewha JSON-safe copy of the members, capped
    # at max_copy — reach for `upset.selected_members` when you need the
    # original Python objects, uncapped.
    _sel = upset.value  # recomputed on each access, so read it once
    _sets = _sel["selected_sets"]
    _members = _sel["selected_values"]
    if not _members:
        _out = mo.md("*Click an intersection above to pull it into Python.*")
    else:
        _genres = dict(MOVIES)
        _df = pl.DataFrame(
            {
                "title": _members,
                "all genres": [", ".join(sorted(_genres[t])) for t in _members],
            }
        )
        _out = mo.vstack(
            [
                mo.md(f"### `{' ∩ '.join(_sets)}` — {len(_members)} films"),
                mo.ui.table(_df, selection=None, page_size=8),
            ]
        )
    _out
    return


if __name__ == "__main__":
    app.run()
