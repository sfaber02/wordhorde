#!/usr/bin/env python3
"""
General-purpose author dictionary builder for Word Horde.
Usage: python3 build_author_dict.py
Builds one dictionary per author defined in AUTHORS below.
Outputs: {key}_dictionary.json and {key}_words.json
"""

import zipfile
import os
import re
import json
from collections import defaultdict
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

EBOOK_DIR = "/Users/shawn/Desktop/E-BOOKS"
OUT_DIR = "/Users/shawn/dev/wordswarm"
WORDS_ENRICHMENT_PATH = os.path.join(OUT_DIR, "words.json")

# --- Author definitions ---
AUTHORS = {
    "camus": {
        "name": "Albert Camus",
        "epubs": [
            "The Stranger (Albert Camus) (z-lib.org).epub",
            "The Fall (Albert Camus) (z-lib.org).epub",
            "The First Man (Albert Camus) (z-lib.org).epub",
        ],
    },
    "mccarthy": {
        "name": "Cormac McCarthy",
        "epubs": [
            "Blood Meridian (Cormac McCarthy) (z-lib.org).epub",
        ],
    },
    "dick": {
        "name": "Philip K. Dick",
        "epubs": [
            "The Man in the High Castle (Philip K. Dick) (z-lib.org).epub",
            "The Minority Report (The Collected Stories Of Philip K. Dick Volume 4) (Philip K. Dick) (z-lib.org).epub",
        ],
    },
}

# --- Stopwords ---
STOPWORDS = set("""
a about above after again against all am an and any are aren't as at be because
been before being below between both but by can't cannot could couldn't did didn't
do does doesn't doing don't down during each few for from further get got had hadn't
has hasn't have haven't having he he'd he'll he's her here here's hers herself him
himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself
let's me more most mustn't my myself no nor not of off on once only or other ought
our ours ourselves out over own same shan't she she'd she'll she's should shouldn't
so some such than that that's the their theirs them themselves then there there's
these they they'd they'll they're they've this those through to too under until up
very was wasn't we we'd we'll we're we've were weren't what what's when when's
where where's which while who who's whom why why's will with won't would wouldn't
you you'd you'll you're you've your yours yourself yourselves
t s m d re ve ll just like get got go went said know one two three
also back still well even just much
dont cant wont wouldnt couldnt shouldnt
""".split())

# --- Helpers ---
def extract_text_from_epub(epub_path):
    texts = []
    try:
        with zipfile.ZipFile(epub_path, 'r') as z:
            for name in sorted(z.namelist()):
                if name.endswith(('.html', '.htm', '.xhtml')):
                    try:
                        data = z.read(name).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(data, 'lxml')
                        for tag in soup(['script', 'style', 'head']):
                            tag.decompose()
                        texts.append(soup.get_text(separator=' '))
                    except Exception:
                        pass
    except Exception as e:
        print(f"  Error reading {epub_path}: {e}")
    return ' '.join(texts)

def sentence_split(text):
    text = re.sub(r'\s+', ' ', text)
    return re.split(r'(?<=[.!?])\s+(?=[A-Z"\'])', text)

def clean_sentence(s):
    return re.sub(r'\s+', ' ', s.strip())

def is_good_sentence(s):
    words = s.split()
    if len(words) < 5 or len(words) > 50:
        return False
    if re.match(r'^(Chapter|Part|Book|Copyright|ISBN|Published|All rights)', s, re.I):
        return False
    if sum(1 for w in words if re.search(r'\d', w)) > 3:
        return False
    alpha_words = [w for w in words if re.match(r'^[a-zA-Z]+$', w)]
    if len(alpha_words) < len(words) * 0.6:
        return False
    cap_words = [w for w in words if w and w[0].isupper() and len(w) > 1]
    if len(cap_words) > len(words) * 0.5 and len(words) > 6:
        return False
    return True

def get_word_key(token):
    return re.sub(r"[^a-z']", '', token.lower()).strip("'")

def score_sentence(s):
    words = s.split()
    length_score = 1.0 - abs(len(words) - 15) / 30.0
    punct_score = len(re.findall(r'[,;:\-"\'—]', s)) * 0.1
    return length_score + punct_score

# --- Load enrichment data once ---
print("Loading enrichment data...")
words_enrichment = {}
try:
    with open(WORDS_ENRICHMENT_PATH) as f:
        words_enrichment = json.load(f)
    print(f"  Loaded {len(words_enrichment)} enriched words\n")
except Exception as e:
    print(f"  Could not load words.json: {e}\n")

# --- Process each author ---
for key, author in AUTHORS.items():
    print(f"{'='*50}")
    print(f"Building: {author['name']}")
    print(f"{'='*50}")

    all_sentences = []
    seen_sentence_hashes = set()

    for epub_name in author['epubs']:
        epub_path = os.path.join(EBOOK_DIR, epub_name)
        if not os.path.exists(epub_path):
            print(f"  WARNING: not found: {epub_name}")
            continue
        print(f"  {epub_name[:60]}...")
        text = extract_text_from_epub(epub_path)
        for s in sentence_split(text):
            s = clean_sentence(s)
            if not is_good_sentence(s):
                continue
            h = re.sub(r'\s+', ' ', s.lower().strip())
            if h in seen_sentence_hashes:
                continue
            seen_sentence_hashes.add(h)
            all_sentences.append(s)

    print(f"  Total sentences: {len(all_sentences)}")

    # Build word index
    word_sentences = defaultdict(list)
    word_counts = defaultdict(int)

    for sentence in all_sentences:
        words_in_sentence = set()
        for token in sentence.split():
            w = get_word_key(token)
            if w and len(w) >= 3 and w not in STOPWORDS:
                word_counts[w] += 1
                if w not in words_in_sentence:
                    word_sentences[w].append(sentence)
                    words_in_sentence.add(w)

    # Select best sentence per word
    author_dict = {}
    for word, sentences in word_sentences.items():
        if len(sentences) < 2:
            continue
        if len(word) < 3 or len(word) > 20:
            continue
        if not re.match(r"^[a-z']+$", word):
            continue
        best = sorted(sentences, key=score_sentence, reverse=True)[0]
        author_dict[word] = best

    # Build words metadata
    author_words = {}
    for word in author_dict:
        entry = {}
        enriched = words_enrichment.get(word) or words_enrichment.get(word.capitalize())
        if enriched:
            if 'e' in enriched: entry['e'] = enriched['e']
            if 's' in enriched: entry['s'] = enriched['s']
            if 'p' in enriched: entry['p'] = enriched['p']
        entry['c'] = word_counts[word]
        author_words[word] = entry

    # Stats
    has_emotion = sum(1 for e in author_words.values() if 'e' in e)
    has_syllable = sum(1 for e in author_words.values() if 's' in e)
    has_pos = sum(1 for e in author_words.values() if 'p' in e)
    top10 = sorted(author_words, key=lambda x: author_words[x]['c'], reverse=True)[:10]

    print(f"  Dictionary: {len(author_dict)} words")
    print(f"  Emotions: {has_emotion}  Syllables: {has_syllable}  POS: {has_pos}")
    print(f"  Top words: {[(w, author_words[w]['c']) for w in top10]}")

    # Write output
    dict_path = os.path.join(OUT_DIR, f"{key}_dictionary.json")
    words_path = os.path.join(OUT_DIR, f"{key}_words.json")

    dict_json = json.dumps(author_dict, separators=(',', ':'), ensure_ascii=False)
    with open(dict_path, 'w') as f:
        f.write(dict_json)

    words_json = json.dumps(author_words, separators=(',', ':'), ensure_ascii=False)
    with open(words_path, 'w') as f:
        f.write(words_json)

    print(f"  Wrote {dict_path.split('/')[-1]} ({len(dict_json)/1024:.0f} KB)")
    print(f"  Wrote {words_path.split('/')[-1]} ({len(words_json)/1024:.0f} KB)")
    print()

print("Done.")
