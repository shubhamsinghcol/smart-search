# Smart Relevance Search

An Anki Browser add-on that ranks notes by relevance to a natural-language query. The default release uses local lexical ranking and requires no external packages or model download.

## Install

In Anki, open **Tools → Add-ons → Get Add-ons** and install the add-on using its AnkiWeb code once published. Restart Anki, open Browse, and prefix the main search with `smart:`. For example:

```text
smart:Noncaseating granulomas + transmural inflammation + cobblestone mucosa
```

The **Filters** field accepts regular Anki search terms such as `-flag:1` and is saved between Browser sessions. Without `smart:`, the main field keeps normal Anki search behavior.

## Search behavior

- Ranks the active collection and then intersects results with native Anki filters.
- Scores notes rather than treating sibling cards as separate evidence.
- Uses whole-token matching, curated synonyms, conservative typo correction, rarity weighting, and a bounded feedback pass.
- Suppresses results below 15% of the top score. Scores are heuristics, not probabilities.
- Does not modify notes, cards, or scheduling.

## Optional semantic search

The AnkiWeb package ships with semantic search disabled and without its third-party dependencies or model. Its code retains an optional semantic integration point, but semantic search is not currently part of the supported public install flow. The normal lexical search works without it.

## Compatibility and limits

This add-on targets current Anki desktop builds. Search indexes the collection synchronously each time, which may pause the Browser for large collections. Long notes may exceed the embedding model's input limit if semantic search is enabled in a separate local setup.

## Development

The add-on package is built from the runtime files in `smart_relevance_search/`. See [smart_relevance_search/README.md](smart_relevance_search/README.md) for implementation and validation notes. Tests are in `tests/`.

To build the AnkiWeb upload archive from the repository root:

```sh
mkdir -p release
(cd smart_relevance_search && zip -X -j ../release/smart-relevance-search.ankiaddon __init__.py engine.py semantic.py config.json)
```

The archive must contain the add-on files at its root; do not include the enclosing folder, `__pycache__`, backups, tests, or semantic dependencies. Then sign in to [AnkiWeb's shared add-ons page](https://ankiweb.net/shared/addons/), choose **Upload**, and upload the `.ankiaddon` file with the title, description, and compatibility details.

To publish the source on GitHub, create an empty repository on GitHub, then connect this folder as its Git remote and push the `main` branch. No GitHub remote is configured in this checkout yet.

No software license has been selected. Until one is added, the source is public for viewing, but reuse and redistribution are not granted.
