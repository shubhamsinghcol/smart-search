# Smart:Search v2

The Browser has two visible search fields after the add-on loads:

- The original top field accepts normal native Anki searches. Begin it with
  `smart:` to opt into ranked smart search; the add-on supplies the outer
  parentheses automatically.
- The **Filters** field underneath accepts native Anki terms such as
  `-tag:g3 -flag:1 -is:suspended is:due`.

The Filters field is saved in the add-on configuration when it loses focus or
when Enter is pressed, and is restored whenever the Browser is opened. Pressing
Enter in either field runs the two fields as one combined Anki search.

For example, put this in the original search bar:

```
smart:Noncaseating granulomas + Transmural inflammation / thickened bowel wall + Cobblestone mucosa + Linear/deep fissuring + small bowel strictures/fistula
```

and put `-flag:1` (plus any other persistent constraints) in **Filters**.
The parenthesized `(smart:...)` form also remains accepted. Without `smart:`,
the main field is handled as a normal native Anki search.

The single leading smart group accepts natural language/concept lists and nested
parentheses. Native Anki filters follow it and narrow the results after
ranking across the active collection. The visible Filters field is intentionally
reused until you edit or clear it. Cards and Notes modes both work.
This applies to the active profile. No collection content or scheduling is changed.

## Ranking

- Whole-token matching, Unicode normalization and preserved cloze answers.
- Curated synonym groups; conservative correction of absent long words.
- BM25-style rarity and length weighting with nonlinear concept coverage.
- Exact full-query phrase bonus.
- One bounded feedback pass: terms must occur in multiple strong notes and be
  at least twice as prevalent there as in the candidate corpus. At most six terms
  contribute a capped bonus; they cannot admit unrelated notes on their own.
- Scores are computed per note, then mapped to the filtered cards. Sibling cards
  do not count as independent evidence. No deck-wide relevance spillover.
- Results below 15% of the highest score are suppressed; no fixed result count.
- Per-note matched terms, expansion terms and scores are exposed to other add-ons
  in `SearchContext.addon_metadata['smart_search']` (not yet a visible UI).

BM25 reference: https://www.sqlite.org/fts5.html#the_bm25_function
The cutoff and semantic thresholds are heuristics, not relevance probabilities.
Quoted text receives normal phrase scoring, not Google's strict quote semantics.
Negation inside the smart group is not a Boolean operator; use native filters.

## Optional semantics

`semantic_enabled` defaults to false. The previous installation's compiled Python
3.14 dependencies are incompatible with Anki's Python 3.13 environment. Do not
assume a successful system-Python model test verifies Anki compatibility.
Enable only after installing and validating compatible dependencies and the local
`all-MiniLM-L6-v2` model in Anki's runtime. No model downloads occur during search.
The optional layer supports semantic-only matches, correct per-note similarity,
and a bounded 4096-entry in-memory vector cache. Import/model failures fall back
to lexical search and log the failure once per session.

## Install and validate

Copy the Python files and config.json to
`~/Library/Application Support/Anki2/addons21/smart_relevance_search/`, then restart
Anki. Existing local dependencies need not be copied or removed.

Run `python3 -m unittest discover -s tests -v` from the project directory.
Original source is preserved in `backups/luna-original/`.

## Remaining limits

Search builds a collection index synchronously on each invocation. Large collections
and optional first-time embedding generation can pause the Browser. Persistent
incremental indexing and a background indexing UI are the next performance layer.
The embedding model truncates long notes. Ranking quality still needs judged
examples from your own collection; this is not a reproduction of Google's engine.
