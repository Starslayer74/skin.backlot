# -*- coding: utf-8 -*-
"""Directory listings for the skin.
?action=art&id=<service id>  a shuffled mix of that service's shows and movies,
                             used for the cycling home-screen artwork."""
import random
import sys
from urllib.parse import parse_qsl, unquote_plus

import xbmcgui
import xbmcplugin

from resources.lib import backlot

PROPS = ["title", "art", "year", "genre", "plot", "mpaa", "studio"]
PER_TYPE = 15


def _filter(values, op):
    """Any of (op=contains) / none of (op=doesnotcontain) these studios; values
    starting with "=" are exact names."""
    exact_op = "is" if op == "contains" else "isnot"
    rules = [{"field": "studio", "operator": exact_op, "value": v[1:]} if v.startswith("=")
             else {"field": "studio", "operator": op, "value": v} for v in values]
    if not rules:
        return None
    if len(rules) == 1:
        return rules[0]
    return {"or" if op == "contains" else "and": rules}


def _items(method, key, flt, kind):
    params = {"properties": PROPS, "sort": {"method": "random"}, "limits": {"start": 0, "end": PER_TYPE}}
    if flt:
        params["filter"] = flt
    out = []
    for it in backlot._rpc(method, params).get(key, []):
        art = it.get("art", {})
        if art.get("fanart"):
            out.append((kind, it, art))
    return out


def art_listing(handle, sid):
    cfg = backlot.load()
    items = []
    if sid in ("movies", "tvshows"):
        used = [v for s in backlot.active_services(cfg) for v in s["matches"]]
        flt = _filter(used, "doesnotcontain")
        if sid == "movies":
            items = _items("VideoLibrary.GetMovies", "movies", flt, "movie")
        else:
            items = _items("VideoLibrary.GetTVShows", "tvshows", flt, "tvshow")
    else:
        svc = next((s for s in backlot.active_services(cfg) if s["id"] == sid), None)
        if svc and svc.get("matches"):
            flt = _filter(svc["matches"], "contains")
            items = (_items("VideoLibrary.GetTVShows", "tvshows", flt, "tvshow") +
                     _items("VideoLibrary.GetMovies", "movies", flt, "movie"))
    random.shuffle(items)
    listing = []
    for kind, it, art in items:
        li = xbmcgui.ListItem(it.get("title") or it.get("label", ""), offscreen=True)
        li.setArt({k: art[k] for k in ("fanart", "clearlogo", "poster", "landscape") if art.get(k)})
        tag = li.getVideoInfoTag()
        tag.setMediaType(kind)
        tag.setTitle(it.get("title", ""))
        if it.get("year"):
            tag.setYear(int(it["year"]))
        tag.setGenres(it.get("genre", []) or [])
        tag.setPlot(it.get("plot", ""))
        tag.setMpaa(it.get("mpaa", ""))
        url = "plugin://script.backlot.helper/?action=none"
        li.setPath(url)
        listing.append((url, li, True))
    xbmcplugin.addDirectoryItems(handle, listing, len(listing))
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


SIM_PROPS = {"movie": ["title", "genre", "set", "studio", "director", "year", "art", "plot", "mpaa", "rating", "file", "runtime"],
             "tvshow": ["title", "genre", "studio", "year", "art", "plot", "mpaa", "rating", "file"]}


def _score(src, it, kind):
    g = len(set(src.get("genre", [])) & set(it.get("genre", [])))
    score = 3 * g
    if kind == "movie":
        if src.get("set") and src.get("set") == it.get("set"):
            score += 6
        score += 2 * len(set(src.get("director", [])) & set(it.get("director", [])))
    score += 2 * len(set(src.get("studio", [])) & set(it.get("studio", [])))
    if src.get("year") and it.get("year") and abs(int(src["year"]) - int(it["year"])) <= 5:
        score += 1
    if score < 2:
        return 0
    return score + float(it.get("rating") or 0) / 10.0


def _library_item(it, kind, idkey):
    li = xbmcgui.ListItem(it.get("title", ""), offscreen=True)
    li.setArt(it.get("art", {}))
    tag = li.getVideoInfoTag()
    tag.setMediaType(kind)
    tag.setDbId(it[idkey])
    tag.setTitle(it.get("title", ""))
    if it.get("year"):
        tag.setYear(int(it["year"]))
    tag.setGenres(it.get("genre", []) or [])
    tag.setPlot(it.get("plot", ""))
    tag.setMpaa(it.get("mpaa", ""))
    path = it.get("file", "") if kind == "movie" else "videodb://tvshows/titles/%d/" % it[idkey]
    li.setPath(path)
    return path, li, kind == "tvshow"


def actor_listing(handle, kind, name):
    """Everything in the library this person appears in, newest first."""
    listing = []
    if kind in SIM_PROPS and name:
        method, key, idkey = (("VideoLibrary.GetMovies", "movies", "movieid") if kind == "movie"
                              else ("VideoLibrary.GetTVShows", "tvshows", "tvshowid"))
        params = {"properties": SIM_PROPS[kind], "filter": {"field": "actor", "operator": "is", "value": name},
                  "sort": {"method": "year", "order": "descending"}}
        listing = [_library_item(it, kind, idkey) for it in backlot._rpc(method, params).get(key, [])]
    xbmcplugin.setContent(handle, "movies" if kind == "movie" else "tvshows")
    xbmcplugin.addDirectoryItems(handle, listing, len(listing))
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def similar_listing(handle, kind, dbid):
    """'More like this' from the user's own library: shared genres, collection,
    director, studio and era, best first."""
    listing = []
    if kind in SIM_PROPS and dbid.isdigit():
        method, key, idkey = (("VideoLibrary.GetMovies", "movies", "movieid") if kind == "movie"
                              else ("VideoLibrary.GetTVShows", "tvshows", "tvshowid"))
        detail = "VideoLibrary.GetMovieDetails" if kind == "movie" else "VideoLibrary.GetTVShowDetails"
        src = backlot._rpc(detail, {idkey: int(dbid), "properties": SIM_PROPS[kind]}).get(
            "moviedetails" if kind == "movie" else "tvshowdetails", {})
        allitems = backlot._rpc(method, {"properties": SIM_PROPS[kind]}).get(key, [])
        scored = [(_score(src, it, kind), it) for it in allitems if it.get(idkey) != int(dbid)]
        scored = sorted([x for x in scored if x[0] > 0], key=lambda x: -x[0])[:20]
        listing = [_library_item(it, kind, idkey) for _s, it in scored]
    xbmcplugin.setContent(handle, "movies" if kind == "movie" else "tvshows")
    xbmcplugin.addDirectoryItems(handle, listing, len(listing))
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def main():
    handle = int(sys.argv[1])
    args = dict(parse_qsl(sys.argv[2].lstrip("?")))
    if args.get("action") == "art":
        art_listing(handle, args.get("id", ""))
    elif args.get("action") == "actor":
        # name comes last and unencoded from the skin, so take everything after "name="
        raw = sys.argv[2]
        name = unquote_plus(raw.split("name=", 1)[1]) if "name=" in raw else ""
        actor_listing(handle, args.get("type", ""), name.strip())
    elif args.get("action") == "similar":
        similar_listing(handle, args.get("dbtype", ""), args.get("dbid", ""))
    else:
        xbmcplugin.endOfDirectory(handle, succeeded=False, updateListing=False, cacheToDisc=False)


main()
