#!/usr/bin/env python3
"""
Build an enriched dictionary JSON for Word Horde.
Combines:
  - Original dictionary (word -> definition)
  - NRC Emotion Lexicon (word -> emotions)
  - CMU Pronouncing Dictionary (word -> syllable count)
  - Part of speech extracted from definitions
"""

import json
import re
from collections import defaultdict

# --- Load original dictionary ---
with open("dictionary.json") as f:
    orig_dict = json.load(f)

print(f"Original dictionary: {len(orig_dict)} words")

# --- Load NRC Emotion Lexicon ---
nrc_path = "data/NRC-Suite-of-Sentiment-Emotion-Lexicons/NRC-Sentiment-Emotion-Lexicons/NRC-Emotion-Lexicon-v0.92/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt"
emotions_data = defaultdict(list)

with open(nrc_path) as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) != 3:
            continue
        word, emotion, score = parts[0], parts[1], int(parts[2])
        if score == 1:
            emotions_data[word].append(emotion)

print(f"NRC emotion lexicon: {len(emotions_data)} words with at least one tag")

# --- Load CMU Pronouncing Dictionary ---
syllable_data = {}

with open("data/cmudict.dict") as f:
    for line in f:
        if line.startswith(';;;'):
            continue
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        word = parts[0].lower()
        # Skip alternate pronunciations like "read(2)"
        if '(' in word:
            word = word.split('(')[0]
            if word in syllable_data:
                continue
        phonemes = parts[1:]
        # Count syllables = number of phonemes with stress markers (digits)
        syllables = sum(1 for p in phonemes if p[-1].isdigit())
        syllable_data[word] = syllables

print(f"CMU dictionary: {len(syllable_data)} words with syllable counts")

# --- Extract Part of Speech from definitions ---
def extract_pos(definition):
    """Extract part of speech using definition text heuristics."""
    defn = definition.strip()
    # Strip leading "1. " numbered prefix
    if re.match(r'^\d+\.\s', defn):
        defn = re.sub(r'^\d+\.\s*', '', defn)

    # Explicit POS abbreviations (rare but precise)
    if re.match(r'^(v\.\s*[ti]\.|v\.)\s', defn, re.I):
        return 'verb'
    if re.match(r'^(n|sb)\.\s', defn, re.I):
        return 'noun'
    if re.match(r'^(adj|a)\.\s', defn, re.I):
        return 'adjective'
    if re.match(r'^adv\.\s', defn, re.I):
        return 'adjective'
    if re.match(r'^(imp|p\.\s*p)\.\s', defn, re.I):
        return 'verb'
    if re.match(r'^(superl|compar)\.\s', defn, re.I):
        return 'adjective'

    # Heuristic: "To <verb>" pattern
    if re.match(r'^To\s+[a-z]', defn):
        return 'verb'

    # Heuristic: "A/An <noun>" or "The <noun>" pattern
    if re.match(r'^(A|An|The)\s+', defn):
        return 'noun'

    # Heuristic: "One who/that..." -> noun (agent noun)
    if re.match(r'^One\s+(who|that|which)\s', defn):
        return 'noun'

    # Heuristic: adjective-like definitions
    if re.match(r'^(Of or pertaining|Pertaining|Relating|Resembling|Having the|Like a|Full of|Without|Not|Containing|Consisting of|Made of|Capable of|Inclined to)\s', defn, re.I):
        return 'adjective'

    return None

pos_count = defaultdict(int)
pos_data = {}

for word, defn in orig_dict.items():
    pos = extract_pos(defn)
    if pos:
        pos_data[word] = pos
        pos_count[pos] += 1

print(f"POS extracted: {len(pos_data)} words")
for pos, count in sorted(pos_count.items(), key=lambda x: -x[1]):
    print(f"  {pos}: {count}")

# --- Build enriched dictionary ---
# Format: { word: { d: definition, e: [emotions], s: syllables, p: pos } }
# Only include fields that have data, to keep size down.

enriched = {}
for word, defn in orig_dict.items():
    entry = {"d": defn}

    w_lower = word.lower()

    if w_lower in emotions_data:
        entry["e"] = emotions_data[w_lower]

    if w_lower in syllable_data:
        entry["s"] = syllable_data[w_lower]

    if word in pos_data:
        entry["p"] = pos_data[word]

    enriched[word] = entry

# Stats
has_emotion = sum(1 for e in enriched.values() if "e" in e)
has_syllable = sum(1 for e in enriched.values() if "s" in e)
has_pos = sum(1 for e in enriched.values() if "p" in e)

print(f"\nEnriched dictionary: {len(enriched)} words")
print(f"  With emotions: {has_emotion}")
print(f"  With syllables: {has_syllable}")
print(f"  With POS: {has_pos}")

# Write output
with open("enriched_dictionary.json", "w") as f:
    json.dump(enriched, f, separators=(',', ':'))

size_mb = len(json.dumps(enriched, separators=(',', ':'))) / 1024 / 1024
print(f"\nOutput: enriched_dictionary.json ({size_mb:.1f} MB)")
