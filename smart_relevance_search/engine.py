"""Pure, local note retrieval; no Anki or ML imports required."""
from __future__ import annotations
import html
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from difflib import get_close_matches

STOPWORDS = {"the", "and", "or", "with", "of", "in", "to", "a", "an", "is", "are", "this", "that", "these", "those", "which", "what", "does", "shown"}
SYNONYMS = {
    "granuloma": {"granuloma", "granulomas", "granulomatous"},
    "transmural": {"transmural", "full-thickness", "full thickness"},
    "thickened bowel wall": {"thickened bowel wall", "bowel wall thickening"},
    "cobblestone": {"cobblestone", "cobblestoning"},
    "fissure": {"fissure", "fissures", "fissuring", "deep fissure", "linear fissure"},
    "stricture": {"stricture", "strictures", "stenosis", "stenoses"},
    "fistula": {"fistula", "fistulas", "fistulae", "fistulization"},
    "crohn disease": {"crohn", "crohn's", "crohn disease", "crohn's disease"},
    "inflammatory bowel disease": {"ibd", "inflammatory bowel disease"},
    "ulcerative colitis": {"ulcerative colitis", "uc"},
}


STOPWORDS |= {"patient", "question", "answer", "disease", "following", "most", "can", "has"}

def plain(text):
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[sound:[^]]+\]", " ", text)
    while re.search(r"\{\{c\d+::([^{}]*?)(?:::[^{}]*?)?\}\}", text):
        text = re.sub(r"\{\{c\d+::([^{}]*?)(?:::[^{}]*?)?\}\}", r"\1", text)
    return html.unescape(text)

def tokens(text):
    text = unicodedata.normalize("NFKD", plain(text).casefold()).replace("’", "'")
    text = re.sub(r"'s\b", "", text)
    return re.findall(r"[^\W_]+", "".join(c for c in text if not unicodedata.combining(c)))

def normalized(text):
    return " ".join(tokens(text))

@dataclass
class Document:
    nid: int
    text: str
    tags: str = ""

@dataclass
class Hit:
    nid: int
    score: float
    matched: tuple[str, ...]
    expanded: tuple[str, ...] = ()
    semantic: float = 0.0

class SearchIndex:
    def __init__(self, docs):
        self.docs = list({d.nid: d for d in docs}.values())
        self.body = [normalized(d.text) for d in self.docs]
        self.tags = [normalized(d.tags) for d in self.docs]
        self.counts = [Counter(t.split()) for t in self.body]
        self.df = Counter()
        for body, tags in zip(self.counts, self.tags):
            self.df.update(set(body) | set(tags.split()))
        self.avglen = sum(map(lambda c: sum(c.values()), self.counts)) / max(1, len(self.docs)) or 1
        self.aliases = [tuple(sorted({normalized(v) for v in vs})) for vs in SYNONYMS.values()]

    def concepts(self, query):
        words = tokens(query)
        groups, consumed = [], set()
        q = " " + " ".join(words) + " "
        for aliases in self.aliases:
            if any(" " + a + " " in q for a in aliases):
                groups.append(aliases)
                for a in aliases:
                    if " " + a + " " in q:
                        consumed.update(a.split())
        for word in dict.fromkeys(words):
            if word in STOPWORDS or word in consumed:
                continue
            variants = [word]
            # Correct only absent long alphabetic words; never numbers or abbreviations.
            if word not in self.df and len(word) >= 5 and word.isalpha():
                choices = [w for w in self.df if w.isalpha() and abs(len(w)-len(word)) <= 1 and w[:1] == word[:1]]
                variants += get_close_matches(word, sorted(choices), n=1, cutoff=.84)
            groups.append(tuple(variants))
        return groups

    def search(self, query, semantic=None, expand=True):
        groups = self.concepts(query)
        if not groups or not self.docs:
            return []
        matches = []
        for aliases in groups:
            matches.append([max((self.counts[i].get(a, 0) if " " not in a else float(" " + a + " " in " " + body + " ")) + .4 * float(" " + a + " " in " " + self.tags[i] + " ") for a in aliases) for i, body in enumerate(self.body)])
        weights = [math.log(1 + (len(self.docs)-sum(v > 0 for v in m)+.5)/(sum(v > 0 for v in m)+.5)) for m in matches]
        base, labels = [], []
        for i, counts in enumerate(self.counts):
            matched = tuple(g[0] for g,m in zip(groups,matches) if m[i] > 0)
            coverage = sum(w for w,m in zip(weights,matches) if m[i] > 0) / sum(weights)
            bm25 = sum(w * m[i] * 2.2 / (m[i] + 1.2 * (.25 + .75*sum(counts.values())/self.avglen)) for w,m in zip(weights,matches) if m[i])
            phrase = normalized(query)
            bonus = .2 if len(phrase.split()) > 1 and " " + phrase + " " in " " + self.body[i] + " " else 0
            base.append(bm25 * (.15 + .85*coverage**2) * (1+bonus))
            labels.append(matched)
        top = max(base, default=0)
        seeds = [i for i,s in enumerate(base) if top and s >= top*.2 and len(labels[i]) >= min(2,len(groups))][:30]
        expansion = []
        if expand and len(seeds) >= 2:
            freq = Counter()
            for i in seeds:
                freq.update(set(self.counts[i]))
            original = set(tokens(query))
            candidates = [(count/len(seeds) / (self.df[w]/len(self.docs)), w) for w,count in freq.items() if count >= 2 and w not in original and w not in STOPWORDS and len(w) > 3 and count/len(seeds) >= .5]
            expansion = [w for lift,w in sorted(candidates, reverse=True) if lift >= 2][:6]
        sims = semantic(query, [d.text for d in self.docs]) if semantic else [0.0]*len(self.docs)
        if len(sims) != len(self.docs):
            sims = [0.0]*len(self.docs)
        hits = []
        for i,d in enumerate(self.docs):
            sim = float(sims[i])
            sim = sim if math.isfinite(sim) else 0.0
            extra = tuple(w for w in expansion if w in self.counts[i])
            # Expansion supports original evidence; cannot recruit unrelated cards by itself.
            score = base[i] + min(base[i]*.2, top*.1*len(extra))
            if sim >= .45:
                score += max(top,1)*.35*((sim-.45)/.55)
            if score > 0 and (base[i] > 0 or sim >= .65):
                hits.append(Hit(d.nid, score, labels[i], extra, sim))
        ceiling = max((h.score for h in hits), default=0)
        return sorted((h for h in hits if h.score >= ceiling*.15), key=lambda h:(-h.score,h.nid))
