"""Native Browser integration for local ranked note search."""
from __future__ import annotations
import logging
import re
from .engine import Document, SearchIndex
from .semantic import scores as semantic_scores

log = logging.getLogger(__name__)

FILTER_CONFIG_KEY = 'persistent_filter'

def combine_search(search, filters):
    """Combine the visible query and persistent native-filter fields."""
    return ' '.join(part.strip() for part in (search, filters) if part.strip())

def normalize_smart_search(search):
    """Normalize an explicitly requested smart search for the parser."""
    search = search.strip()
    if not search:
        return ''
    if re.match(r'(?i)^\(\s*smart\s*:', search):
        return search
    if re.match(r'(?i)^smart\s*:', search):
        search = re.sub(r'(?i)^smart\s*:', '', search, count=1).strip()
        return f'(smart:{search})'
    return search

def split_search(search):
    # A single leading smart group, followed by native AND filters. Reject
    # ambiguous Boolean placement rather than silently changing its meaning.
    match = re.match(r'\s*\(\s*smart:\s*', search, re.I)
    if not match:
        raise ValueError('Use (smart:concepts) followed by native filters.')
    depth, quoted, end = 1, False, None
    for pos in range(match.end(), len(search)):
        char = search[pos]
        if char == '"' and (pos == 0 or search[pos-1] != "\\"):
            quoted = not quoted
        if not quoted:
            depth += (char == '(') - (char == ')')
            if depth == 0:
                end = pos
                break
    if end is None:
        raise ValueError('Close the (smart:...) group.')
    query = search[match.end():end]
    filters = search[end+1:].strip()
    if re.search(r'\bsmart:', filters, re.I):
        raise ValueError('Only one smart group is supported.')
    if re.match(r'(?i)^(OR|AND)\b', filters):
        raise ValueError('Place native filters directly after the smart group.')
    return query, filters

def rank_collection(col, query, filters='', semantic=None):
    # Keep corpus statistics, expansion and cutoff independent of native filters.
    # Filtering is an intersection: exclusions must never promote weaker hits.
    cards = col.find_cards('')
    allowed = set(col.find_cards(filters)) if filters.strip() else set(cards)
    docs, card_notes = {}, {}
    for cid in cards:
        card = col.get_card(cid)
        card_notes[cid] = card.nid
        if card.nid not in docs:
            note = card.note()
            docs[card.nid] = Document(card.nid, ' '.join(note.fields), ' '.join(note.tags))
    hits = SearchIndex(docs.values()).search(query, semantic=semantic)
    by_note = {}
    for cid,nid in card_notes.items():
        if cid in allowed:
            by_note.setdefault(nid, []).append(cid)
    hits = [h for h in hits if h.nid in by_note]
    return hits, [cid for h in hits for cid in sorted(by_note[h.nid])]

def search_context_is_notes_mode(context):
    """Return the mode of the model currently executing this search.

    While Anki toggles Cards/Notes, DataModel switches first and Table updates
    its mirrored state only after the search completes. Reading Table during
    the hook therefore returns the old mode and makes IDs look deleted.
    """
    table = context.browser.table
    model = getattr(table, '_model', None)
    state = getattr(model, '_state', None)
    if state is not None:
        return state.is_notes_mode()
    return table.is_notes_mode()

def smart_search(context):
    if not re.match(r'(?i)^\s*\(?\s*smart\s*:', context.search):
        return
    from aqt import mw
    try:
        query, filters = split_search(context.search)
        config = mw.addonManager.getConfig(__name__) or {}
        hits, cards = rank_collection(mw.col, query, filters, semantic_scores if config.get('semantic_enabled', False) else None)
        context.ids = [h.nid for h in hits] if search_context_is_notes_mode(context) else cards
        context.reverse = False
        context.addon_metadata = context.addon_metadata or {}
        context.addon_metadata['smart_search'] = {h.nid: {'score': h.score, 'matched': h.matched, 'expanded': h.expanded, 'semantic': h.semantic} for h in hits}
    except Exception as error:
        context.ids = []
        log.exception('Smart search failed')
        from aqt.utils import tooltip
        tooltip('Smart Search: ' + str(error), parent=context.browser)

def apply_persistent_filter(context):
    """Normalize explicit smart syntax and append the native-filter field."""
    if context.ids is not None:
        return
    filter_edit = getattr(context.browser, '_smart_filter_edit', None)
    if filter_edit is not None:
        context.search = combine_search(normalize_smart_search(context.search), filter_edit.text())

def setup_filter_bar(browser):
    """Add a persistent native-filter row to Anki's Browser search area."""
    if getattr(browser, '_smart_filter_edit', None) is not None:
        return

    from aqt import mw
    from aqt.qt import QLabel, QLineEdit, qconnect

    config = mw.addonManager.getConfig(__name__) or {}
    label = QLabel('Filters', browser)
    filter_edit = QLineEdit(browser)
    filter_edit.setObjectName('smartSearchPersistentFilter')
    filter_edit.setAccessibleName('Persistent Anki search filters')
    filter_edit.setPlaceholderText('Persistent filters, e.g. -tag:g3 -flag:1 -is:suspended is:due')
    filter_edit.setToolTip(
        'Native Anki filters stored between Browser sessions. '
        'They are combined with the main search when you press Enter.'
    )
    filter_edit.setText(str(config.get(FILTER_CONFIG_KEY, '')))
    browser.form.gridLayout.addWidget(label, 1, 0)
    browser.form.gridLayout.addWidget(filter_edit, 1, 1)
    browser._smart_filter_label = label
    browser._smart_filter_edit = filter_edit

    def save_filter():
        current = mw.addonManager.getConfig(__name__) or {}
        current[FILTER_CONFIG_KEY] = filter_edit.text().strip()
        mw.addonManager.writeConfig(__name__, current)

    def search_with_filter():
        save_filter()
        browser.onSearchActivated()

    qconnect(filter_edit.editingFinished, save_filter)
    qconnect(filter_edit.returnPressed, search_with_filter)

try:
    from aqt import gui_hooks
except ImportError:
    pass  # Pure engine/tests can run without Qt or Anki.
else:
    gui_hooks.browser_will_show.append(setup_filter_bar)
    gui_hooks.browser_will_search.append(apply_persistent_filter)
    gui_hooks.browser_will_search.append(smart_search)
