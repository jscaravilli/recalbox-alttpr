#!/usr/bin/env python3
"""Generate a random, kid-friendly "nickname" for an ALTTPR seed.

Format: (random Adjective OR random Verb) + random Noun, title-cased.
  e.g. "Stinky Lemming", "Cackling Wiener", "Quizzical Trombone".

The nickname is COSMETIC display metadata only — it is written into the seed's
gamelist <genre> field (relabeled "Nickname" in the ALTTPR theme) so it shows in
EmulationStation next to Last Played / Play Count. It never touches the ROM
filename, so game saves (keyed off the filename) are completely unaffected.

Word lists live next to this script in words/ (adjectives.txt, verbs.txt,
nouns.txt), one lowercase word per line. If a list is missing/empty the script
falls back to a tiny built-in set so generation never fails.

    usage: alttpr-name.py            -> prints one nickname
"""
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = os.path.join(HERE, "words")

FALLBACK_ADJ = ["silly", "wobbly", "grumpy", "sneaky", "stinky", "goofy"]
FALLBACK_VERB = ["giggling", "wobbling", "zooming", "snoozing", "burping"]
FALLBACK_NOUN = ["wombat", "noodle", "pickle", "muffin", "goblin", "wiener"]


def _load(name, fallback):
    path = os.path.join(WORDS, name)
    try:
        with open(path, encoding="utf-8") as f:
            words = [w.strip() for w in f if w.strip()]
        return words or fallback
    except OSError:
        return fallback


def nickname(rng=random):
    adj = _load("adjectives.txt", FALLBACK_ADJ)
    verb = _load("verbs.txt", FALLBACK_VERB)
    noun = _load("nouns.txt", FALLBACK_NOUN)
    first = rng.choice(adj if rng.random() < 0.5 else verb)
    second = rng.choice(noun)
    return "%s %s" % (first.capitalize(), second.capitalize())


if __name__ == "__main__":
    print(nickname())
