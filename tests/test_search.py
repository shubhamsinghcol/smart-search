import unittest
from types import SimpleNamespace
from unittest.mock import patch
from smart_relevance_search.engine import Document, SearchIndex, plain, tokens
from smart_relevance_search import combine_search, normalize_smart_search, rank_collection, search_context_is_notes_mode, split_search, smart_search

class SearchTests(unittest.TestCase):
    def search(self, query, texts, **kwargs):
        return SearchIndex([Document(i,t) for i,t in enumerate(texts)]).search(query, **kwargs)

    def test_cloze(self):
        self.assertIn('transmural', plain('{{c1::transmural::hint}}'))
        self.assertNotIn('hint', plain('{{c1::transmural::hint}}'))

    def test_markup(self):
        self.assertEqual(tokens('<style>noise</style>Crohn’s &amp; café [sound:file.mp3]'), ['crohn','cafe'])

    def test_abbreviation_boundary(self):
        self.assertEqual([h.nid for h in self.search('UC', ['mucus production','ulcerative colitis'])], [1])

    def test_short_terms_numbers(self):
        self.assertEqual([h.nid for h in self.search('pH 7.2', ['pH 7.2','unrelated'])], [0])

    def test_typo(self):
        self.assertEqual(self.search('transmurral',['transmural inflammation','cardiology'])[0].nid,0)

    def test_no_numeric_fuzz(self):
        self.assertEqual(self.search('12345',['12346']),[])

    def test_empty(self):
        self.assertEqual(self.search('the and', ['anything']), [])
        self.assertEqual(self.search('crohn', []), [])

    def test_cloze_retrieval(self):
        self.assertEqual(self.search('transmural', ['{{c1::transmural}}','irrelevant'])[0].nid,0)

    def test_multi_concept(self):
        hits=self.search('transmural granulomas fistula', ['transmural granulomas fistula','fistula surgery','granulomas lung','unrelated'])
        self.assertEqual([h.nid for h in hits], [0])

    def test_semantic_alignment(self):
        hits=self.search('alpha', ['alpha one','alpha two','other'],semantic=lambda q,t:[.5,.99,0])
        self.assertEqual(hits[0].nid,1)
        self.assertEqual(hits[0].semantic,.99)

    def test_semantic_only(self):
        hits=self.search('intestinal inflammation',['bowel injury','cardiology'],semantic=lambda q,t:[.9,.1])
        self.assertEqual([h.nid for h in hits],[0])

    def test_nan_semantics(self):
        self.assertTrue(self.search('alpha',['alpha'],semantic=lambda q,t:[float('nan')]))

    def test_duplicate_notes(self):
        index=SearchIndex([Document(1,'alpha'),Document(1,'alpha')])
        self.assertEqual(len(index.docs),1)

    def test_expansion_drift(self):
        texts=['transmural granulomas crohn','transmural granulomas crohn','crohn unrelated']+['generic unrelated']*8
        hits=self.search('transmural granulomas',texts)
        self.assertEqual({h.nid for h in hits},{0,1})
        self.assertIn('crohn',hits[0].expanded)

    def test_repeat_deterministic(self):
        self.assertEqual(self.search('alpha',['alpha','alpha']),self.search('alpha',['alpha','alpha']))

    def test_nested_parentheses(self):
        self.assertEqual(split_search('(smart:IBD (Crohn)) -flag:1'),('IBD (Crohn)','-flag:1'))

    def test_unclosed_group(self):
        with self.assertRaises(ValueError): split_search('(smart:IBD (Crohn)')

    def test_native_filter(self):
        self.assertEqual(split_search('(smart:alpha beta) -flag:1'),('alpha beta','-flag:1'))
        self.assertEqual(split_search('(smart:alpha)'),('alpha',''))

    def test_combines_visible_search_and_persistent_filters(self):
        self.assertEqual(
            combine_search(' (smart:alpha beta) ', ' -tag:g3 is:due '),
            '(smart:alpha beta) -tag:g3 is:due',
        )
        self.assertEqual(combine_search('', 'is:new'), 'is:new')
        self.assertEqual(combine_search('deck:Current', ''), 'deck:Current')

    def test_main_field_requires_explicit_smart_prefix(self):
        self.assertEqual(normalize_smart_search('alpha beta'), 'alpha beta')
        self.assertEqual(normalize_smart_search('smart:alpha beta'), '(smart:alpha beta)')
        self.assertEqual(normalize_smart_search('(smart:alpha beta)'), '(smart:alpha beta)')
        self.assertEqual(normalize_smart_search(''), '')

    def test_ambiguous_search(self):
        for query in ['deck:x (smart:alpha)','(smart:alpha) OR deck:x','(smart:alpha) (smart:beta)']:
            with self.assertRaises(ValueError): split_search(query)

    def test_collection_dedup_and_filters(self):
        note=SimpleNamespace(fields=['alpha'],tags=[])
        cards={1:SimpleNamespace(nid=9,note=lambda:note),2:SimpleNamespace(nid=9,note=lambda:note)}
        filters=[]
        col=SimpleNamespace(find_cards=lambda f:filters.append(f) or [2,1],get_card=cards.get)
        hits,ids=rank_collection(col,'alpha','-flag:1')
        self.assertEqual(filters,['', '-flag:1'])
        self.assertEqual(ids,[1,2])
        self.assertEqual([h.nid for h in hits],[9])

    def test_exclusion_cannot_promote_weak_matches(self):
        texts = {1: 'transmural granulomas fistula', 2: 'transmural granulomas fistula', 3: 'fistula surgery', 4: 'unrelated'}
        cards = {cid: SimpleNamespace(nid=cid, note=lambda text=text: SimpleNamespace(fields=[text], tags=[])) for cid,text in texts.items()}
        choices = {'': [1,2,3,4], '-flag:1': [1,3,4], '-flag:1 -tag:g3': [3,4], '-tag:g3': [2,3,4]}
        col = SimpleNamespace(find_cards=lambda f: choices[f], get_card=cards.get)
        base, ids = rank_collection(col, 'transmural granulomas fistula', '-flag:1')
        narrowed, narrowed_ids = rank_collection(col, 'transmural granulomas fistula', '-flag:1 -tag:g3')
        self.assertEqual(ids, [1])
        self.assertEqual(narrowed_ids, [])
        self.assertEqual(narrowed, [])
        all_hits, _ = rank_collection(col, 'transmural granulomas fistula')
        kept, _ = rank_collection(col, 'transmural granulomas fistula', '-tag:g3')
        self.assertEqual(kept, [h for h in all_hits if h.nid != 1])

    def test_filter_keeps_only_allowed_sibling_cards(self):
        note = SimpleNamespace(fields=['alpha'], tags=[])
        cards = {1: SimpleNamespace(nid=9, note=lambda: note), 2: SimpleNamespace(nid=9, note=lambda: note)}
        col = SimpleNamespace(find_cards=lambda f: [2] if f else [1,2], get_card=cards.get)
        hits, ids = rank_collection(col, 'alpha', '-flag:1')
        self.assertEqual(ids, [2])
        self.assertEqual([h.nid for h in hits], [9])

    def test_notes_mode_hook(self):
        import sys
        from smart_relevance_search.engine import Hit
        mw=SimpleNamespace(col=None,addonManager=SimpleNamespace(getConfig=lambda n:{'last_filter':'stale'}))
        context=SimpleNamespace(search='(smart:alpha)',browser=SimpleNamespace(table=SimpleNamespace(is_notes_mode=lambda:True)),addon_metadata={},ids=None)
        with patch.dict(sys.modules,{'aqt':SimpleNamespace(mw=mw)}),patch('smart_relevance_search.rank_collection',return_value=([Hit(9,1,('alpha',))],[1,2])) as rank:
            smart_search(context)
        self.assertEqual(context.ids,[9])
        self.assertEqual(rank.call_args.args[2],'')

    def test_mode_toggle_uses_active_model_state(self):
        # During toggle_state(), Anki changes DataModel._state before it updates
        # Table._state. The hook must return IDs for the new model state.
        state = SimpleNamespace(is_notes_mode=lambda: True)
        table = SimpleNamespace(
            _model=SimpleNamespace(_state=state),
            is_notes_mode=lambda: False,
        )
        context = SimpleNamespace(browser=SimpleNamespace(table=table))
        self.assertTrue(search_context_is_notes_mode(context))

if __name__=='__main__': unittest.main()
