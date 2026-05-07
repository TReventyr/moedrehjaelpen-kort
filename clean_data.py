#!/usr/bin/env python3
"""
Merges activity name variants in data.json into canonical names.
Overwrites data.json in place.
"""

import json
import re

MERGES = [
    # (canonical, matcher_fn)
    ("Babystartpakker",          lambda a: bool(re.search(r'startpakke', a, re.I))),
    ("Den rullende kagemand",    lambda a: bool(re.search(r'den rullende kagemand', a, re.I))),
    ("Gravidcafé",               lambda a: bool(re.search(r'gravid(itets)?.*caf|barselscaf', a, re.I))),
    ("Legestue",                 lambda a: bool(re.search(r'leg og (bevægelse|tumle)', a, re.I))),
    ("Oplevelser og udflugter",  lambda a: a.strip().lower() == "oplevelser og ture"),
    ("Ønsketræet",               lambda a: bool(re.search(r'ønsketræ', a, re.I))),
]


def canonicalise(activity: str) -> str:
    for canonical, matches in MERGES:
        if matches(activity):
            return canonical
    return activity


with open("data.json", encoding="utf-8") as f:
    data = json.load(f)

total_changed = 0
for entry in data:
    new_acts = []
    seen = set()
    for act in entry["activities"]:
        canon = canonicalise(act)
        if act != canon:
            total_changed += 1
            print(f"  {entry['name']}: {act!r} → {canon!r}")
        if canon.lower() not in seen:
            seen.add(canon.lower())
            new_acts.append(canon)
    entry["activities"] = new_acts

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✓ {total_changed} activity names normalised across {len(data)} entries.")

# Summary of unique activities after merge
all_acts = set()
for e in data:
    all_acts.update(e["activities"])
print(f"✓ Unique activities after merge: {len(all_acts)}")
for a in sorted(all_acts):
    count = sum(1 for e in data if a in e["activities"])
    print(f"  {count:2d}x  {a}")
