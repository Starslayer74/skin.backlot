# -*- coding: utf-8 -*-
"""Show Kodi's info screen for a library movie or TV show by its database id."""
import xbmc
import xbmcgui

from . import backlot

FIELDS = {"movie": ("VideoLibrary.GetMovieDetails", "movieid", "moviedetails",
                    ["title", "genre", "year", "rating", "director", "plot", "tagline", "mpaa", "studio",
                     "runtime", "set", "cast", "art", "file", "playcount", "resume", "uniqueid", "premiered"]),
          "tvshow": ("VideoLibrary.GetTVShowDetails", "tvshowid", "tvshowdetails",
                     ["title", "genre", "year", "rating", "plot", "mpaa", "studio", "cast", "art", "file",
                      "playcount", "uniqueid", "premiered", "season", "episode", "watchedepisodes"])}


def show(kind, dbid):
    if kind not in FIELDS or not str(dbid).isdigit():
        return
    method, idkey, key, props = FIELDS[kind]
    it = backlot._rpc(method, {idkey: int(dbid), "properties": props}).get(key)
    if not it:
        return
    li = xbmcgui.ListItem(it.get("title", ""), offscreen=True)
    li.setArt(it.get("art", {}))
    tag = li.getVideoInfoTag()
    tag.setMediaType(kind)
    tag.setDbId(int(dbid))
    tag.setTitle(it.get("title", ""))
    if it.get("year"):
        tag.setYear(int(it["year"]))
    tag.setGenres(it.get("genre", []) or [])
    tag.setStudios(it.get("studio", []) or [])
    tag.setPlot(it.get("plot", ""))
    tag.setMpaa(it.get("mpaa", ""))
    tag.setRating(float(it.get("rating") or 0))
    tag.setPremiered(it.get("premiered", ""))
    tag.setUniqueIDs(it.get("uniqueid", {}) or {}, "tmdb" if "tmdb" in (it.get("uniqueid") or {}) else "")
    if kind == "movie":
        tag.setDirectors(it.get("director", []) or [])
        tag.setTagLine(it.get("tagline", ""))
        tag.setDuration(int(it.get("runtime") or 0))
        if it.get("set"):
            tag.setSet(it["set"])
        tag.setPlaycount(int(it.get("playcount") or 0))
        li.setPath(it.get("file", ""))
    else:
        li.setPath("videodb://tvshows/titles/%s/" % dbid)
        li.setIsFolder(True)
    cast = []
    for c in it.get("cast", [])[:30]:
        cast.append(xbmc.Actor(c.get("name", ""), c.get("role", ""), c.get("order", 0), c.get("thumbnail", "")))
    tag.setCast(cast)
    xbmc.executebuiltin("Dialog.Close(movieinformation,true)")
    xbmc.sleep(150)
    xbmcgui.Dialog().info(li)
