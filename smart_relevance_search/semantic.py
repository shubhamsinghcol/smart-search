"""Optional offline embeddings with a bounded in-memory document cache."""
from __future__ import annotations
from collections import OrderedDict
from pathlib import Path
import logging
import sys

_model = None
_failed = False
_cache = OrderedDict()
CACHE_SIZE = 4096

def scores(query, texts):
    global _model, _failed
    if not texts or _failed:
        return [0.0] * len(texts)
    try:
        if _model is None:
            deps = Path(__file__).parent / 'semantic_deps'
            if deps.exists() and str(deps) not in sys.path:
                sys.path.append(str(deps))
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True)
        from sentence_transformers import util
        # Keep each request's vectors independent of LRU eviction.
        vectors = {}
        missing = list(dict.fromkeys(t for t in texts if t not in _cache))
        for start in range(0, len(missing), 32):
            batch = missing[start:start+32]
            encoded = _model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
            vectors.update(zip(batch, encoded))
        docs = [vectors[t] if t in vectors else _cache[t] for t in texts]
        for t,v in zip(texts, docs):
            _cache[t] = v
            _cache.move_to_end(t)
            if len(_cache) > CACHE_SIZE:
                _cache.popitem(last=False)
        q = _model.encode(query, normalize_embeddings=True, show_progress_bar=False)
        import numpy as np
        return [float(v) for v in util.cos_sim(q, np.asarray(docs))[0]]
    except Exception:
        _failed = True
        logging.getLogger(__name__).exception('Local semantic runtime unavailable; using lexical search')
        return [0.0]*len(texts)
