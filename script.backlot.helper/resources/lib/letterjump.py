# -*- coding: utf-8 -*-
"""Jump a library list to the first item starting with a letter.
RunScript(script.backlot.helper,jump,<container id>,<letter or #>)

Reads the list's own sort letters (so "The" handling and sort titles match
what Kodi shows), binary-searches them when the list is sorted A-Z or Z-A,
and falls back to a straight scan when it isn't."""
import xbmc


def _key(ch):
    ch = (ch or "").upper()[:1]
    # digits and symbols all count as "#", which sorts before A
    return ch if "A" <= ch <= "Z" else "#"


def _rank(k):
    return 0 if k == "#" else ord(k) - 64


def jump(cid, letter):
    cid = str(int(cid))
    target = _rank(_key(letter))
    total = int(xbmc.getInfoLabel("Container(%s).NumItems" % cid) or 0)
    if total <= 0:
        return
    # a ".." parent row (if shown) has no sort letter; skip past it
    first = 1 if xbmc.getCondVisibility("Container(%s).HasParent" % cid) else 0
    ranks = {}

    def rank_at(i):
        if i not in ranks:
            ranks[i] = _rank(_key(xbmc.getInfoLabel("Container(%s).ListItemAbsolute(%d).SortLetter" % (cid, i))))
        return ranks[i]

    lo, hi = first, total + first - 1
    descending = rank_at(lo) > rank_at(hi)
    sorted_ok = True
    # spot-check that the letters really run in order before trusting a binary search
    step = max(1, (hi - lo) // 8)
    prev = rank_at(lo)
    for i in range(lo + step, hi + 1, step):
        r = rank_at(i)
        if (r < prev) if not descending else (r > prev):
            sorted_ok = False
            break
        prev = r

    if sorted_ok:
        a, b = lo, hi + 1
        while a < b:
            m = (a + b) // 2
            r = rank_at(m)
            if (r < target) if not descending else (r > target):
                a = m + 1
            else:
                b = m
        pos = min(a, hi)
    else:
        pos = next((i for i in range(lo, hi + 1) if rank_at(i) >= target), hi)
    xbmc.executebuiltin("SetFocus(%s,%d,absolute)" % (cid, pos))
