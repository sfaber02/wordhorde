#!/usr/bin/env python3
"""
Build a Bukowski dictionary for Word Horde.
Extracts all text from Bukowski EPUBs, then for each interesting word,
stores the best sentence from Bukowski's writing as its "definition".
Output: bukowski_dictionary.json (word -> sentence)
        bukowski_words.json (word -> {e, s, p}) using existing enrichment data
"""

import zipfile
import os
import re
import json
import random
from collections import defaultdict
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

EPUB_BASE = "/Users/shawn/Desktop/Charles Bukowski"

# --- Stopwords (words too common to be interesting) ---
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

# Common German words to exclude (from the one German-language book)
GERMAN_WORDS = set("""
und ich die der das ist nicht mit ein eine einen einem einer des dem den
hat hatte war waren wird wurde haben sein aber auch wenn dann als wie
sie er wir ihr man sie uns zum zur auf aus bei nach von zu für über
noch mehr sehr alle kann muss soll will doch nur noch mal wieder
mich mir ihm ihr uns euch ihnen sich selbst schon oder durch
dieser diese dieses diesen diesem welche welcher welches
eines eines etwa doch nun mal her hin fort
sowie also sodass damit dabei daher darum davon dazu daran darunter
worden werden wurden konnte musste sollte wollte
meiner meinem meinen meine mein dein deiner deinem deinen deine
sein seiner seinem seinen seine unser unsere unseren unserem unserer
ihr ihrer ihrem ihren ihre
warum weil obwohl obwohl während trotz trotzdem
viel viele vielen vielem vieles wenig wenige
ihm ihnen ihren ihrer ihrem
etwas nichts jemand niemand alles alle
zwischen neben hinter unter neben vor nach seit
worden werden wurden wäre würde könnte müsste sollte
marlon mauritius
""".split())

def extract_text_from_epub(epub_path):
    """Extract all plain text from an EPUB file."""
    texts = []
    try:
        with zipfile.ZipFile(epub_path, 'r') as z:
            for name in sorted(z.namelist()):
                if name.endswith(('.html', '.htm', '.xhtml')):
                    try:
                        data = z.read(name).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(data, 'lxml')
                        # Remove script/style
                        for tag in soup(['script', 'style', 'head']):
                            tag.decompose()
                        text = soup.get_text(separator=' ')
                        texts.append(text)
                    except Exception:
                        pass
    except Exception as e:
        print(f"  Error reading {epub_path}: {e}")
    return ' '.join(texts)

def sentence_split(text):
    """Split text into sentences."""
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'])', text)
    return sentences

def clean_sentence(s):
    """Clean a sentence for display."""
    s = s.strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def is_good_sentence(s):
    """Filter for sentences that make good Bukowski quotes."""
    words = s.split()
    if len(words) < 5 or len(words) > 50:
        return False
    # Skip sentences that look like metadata/headers
    if re.match(r'^(Chapter|Part|Book|Copyright|ISBN|Published|All rights)', s, re.I):
        return False
    # Skip if too many numbers
    if sum(1 for w in words if re.search(r'\d', w)) > 3:
        return False
    # Skip sentences that are mostly non-English (< 60% ASCII alpha words)
    alpha_words = [w for w in words if re.match(r'^[a-zA-Z]+$', w)]
    if len(alpha_words) < len(words) * 0.6:
        return False
    # Skip lists/credits (many capitalized words in a row suggests proper nouns/index)
    cap_words = [w for w in words if w and w[0].isupper() and len(w) > 1]
    if len(cap_words) > len(words) * 0.5 and len(words) > 6:
        return False
    return True

def get_word_key(w):
    """Normalize a word for lookup."""
    return re.sub(r"[^a-z']", '', w.lower()).strip("'")

def normalize_title(name):
    """Strip trailing (id) and normalize for dedup comparison."""
    title = re.sub(r'\s*\(\d+\)\s*$', '', name)
    # Also strip subtitles after ': ' or '_ ' for fuzzy dedup
    title = re.split(r'[_:]', title)[0].strip().lower()
    title = re.sub(r'[^a-z0-9 ]', '', title)
    return title

# --- Step 1: Extract all text (dedup books by normalized title) ---
print("Extracting text from EPUBs...")
all_sentences = []
seen_sentence_hashes = set()
seen_titles = set()
book_dirs = [d for d in os.listdir(EPUB_BASE) if os.path.isdir(os.path.join(EPUB_BASE, d))]

skipped_books = []
for book_dir in sorted(book_dirs):
    norm = normalize_title(book_dir)
    # Skip books with non-English titles (e.g. German editions)
    first_word = book_dir.split()[0].lower().rstrip('_')
    if first_word in {'das', 'die', 'der', 'ein', 'eine', 'le', 'la', 'les', 'un', 'une'}:
        skipped_books.append(f"{book_dir} [non-English title, skipped]")
        continue
    if norm in seen_titles:
        skipped_books.append(book_dir)
        continue
    seen_titles.add(norm)

    path = os.path.join(EPUB_BASE, book_dir)
    epubs = [f for f in os.listdir(path) if f.endswith('.epub')]
    if not epubs:
        continue
    epub_path = os.path.join(path, epubs[0])
    print(f"  {book_dir[:60]}...")
    text = extract_text_from_epub(epub_path)
    sentences = sentence_split(text)
    new_count = 0
    for s in sentences:
        s = clean_sentence(s)
        if not is_good_sentence(s):
            continue
        # Deduplicate sentences by exact normalized text
        key = re.sub(r'\s+', ' ', s.lower().strip())
        if key in seen_sentence_hashes:
            continue
        seen_sentence_hashes.add(key)
        all_sentences.append(s)
        new_count += 1

if skipped_books:
    print(f"\nSkipped duplicate editions:")
    for b in skipped_books:
        print(f"  {b}")

print(f"\nTotal good sentences: {len(all_sentences)}")

# --- Step 2: Build word -> sentences map and occurrence counts ---
print("Building word->sentence index...")
word_sentences = defaultdict(list)
word_counts = defaultdict(int)

for sentence in all_sentences:
    words_in_sentence = set()
    for token in sentence.split():
        w = get_word_key(token)
        if w and len(w) >= 3 and w not in STOPWORDS and w not in GERMAN_WORDS:
            word_counts[w] += 1  # count every occurrence
            if w not in words_in_sentence:
                word_sentences[w].append(sentence)
                words_in_sentence.add(w)

print(f"Unique words found: {len(word_sentences)}")

# --- Step 3: Filter to words with enough coverage & pick best sentence ---
# "Best" = medium length, has some interesting content
def score_sentence(s):
    words = s.split()
    length_score = 1.0 - abs(len(words) - 15) / 30.0  # prefer ~15 words
    # Prefer sentences with punctuation variety (more natural prose)
    punct_score = len(re.findall(r'[,;:\-"\'—]', s)) * 0.1
    return length_score + punct_score

print("Selecting best sentences...")
bukowski_dict = {}

for word, sentences in word_sentences.items():
    # Skip very rare words (likely OCR artifacts)
    if len(sentences) < 2:
        continue
    # Skip very short or very long words
    if len(word) < 3 or len(word) > 20:
        continue
    # Skip words with non-alpha chars (except apostrophe)
    if not re.match(r"^[a-z']+$", word):
        continue

    # Pick best sentence
    scored = sorted(sentences, key=score_sentence, reverse=True)
    best = scored[0]
    bukowski_dict[word] = best

print(f"Dictionary size: {len(bukowski_dict)} words")

# --- Step 4: Load existing enrichment data (emotions, syllables, POS) ---
print("Loading existing enrichment data...")
words_enrichment = {}
try:
    with open("/Users/shawn/dev/wordswarm/words.json") as f:
        words_enrichment = json.load(f)
    print(f"  Loaded {len(words_enrichment)} enriched words")
except Exception as e:
    print(f"  Could not load words.json: {e}")

# --- Step 5: Build bukowski_words.json ---
bukowski_words = {}
for word in bukowski_dict:
    entry = {}
    # Try exact match, then capitalized
    enriched = words_enrichment.get(word) or words_enrichment.get(word.capitalize())
    if enriched:
        if 'e' in enriched:
            entry['e'] = enriched['e']
        if 's' in enriched:
            entry['s'] = enriched['s']
        if 'p' in enriched:
            entry['p'] = enriched['p']
    entry['c'] = word_counts[word]  # occurrence count across all texts
    bukowski_words[word] = entry

has_emotion = sum(1 for e in bukowski_words.values() if 'e' in e)
has_syllable = sum(1 for e in bukowski_words.values() if 's' in e)
has_pos = sum(1 for e in bukowski_words.values() if 'p' in e)
counts = sorted([e['c'] for e in bukowski_words.values()], reverse=True)

print(f"\nBukowski words index: {len(bukowski_words)} words")
print(f"  With emotions: {has_emotion}")
print(f"  With syllables: {has_syllable}")
print(f"  With POS: {has_pos}")
print(f"  Top 10 by count: {[(w, bukowski_words[w]['c']) for w in sorted(bukowski_words, key=lambda x: bukowski_words[x]['c'], reverse=True)[:10]]}")
print(f"  Median count: {counts[len(counts)//2]}")

# --- Step 6: Write output ---
out_base = "/Users/shawn/dev/wordswarm"

dict_json = json.dumps(bukowski_dict, separators=(',', ':'), ensure_ascii=False)
with open(os.path.join(out_base, "bukowski_dictionary.json"), "w") as f:
    f.write(dict_json)
print(f"\nbukowski_dictionary.json: {len(dict_json) / 1024 / 1024:.1f} MB")

words_json = json.dumps(bukowski_words, separators=(',', ':'), ensure_ascii=False)
with open(os.path.join(out_base, "bukowski_words.json"), "w") as f:
    f.write(words_json)
print(f"bukowski_words.json: {len(words_json) / 1024 / 1024:.1f} MB")

# --- Sample output ---
print("\n--- Sample entries ---")
samples = random.sample(list(bukowski_dict.keys()), min(10, len(bukowski_dict)))
for w in sorted(samples):
    print(f"  {w}: {bukowski_dict[w][:80]}...")
