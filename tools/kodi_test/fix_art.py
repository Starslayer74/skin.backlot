"""Point library art at the local image files next to each title (the test
media has no network), and set dateadded from the premiere date so the
"New ..." rows show the newest releases first."""
import os, kodictl as k
MAP = {"poster": ["poster.jpg", "poster.png"], "fanart": ["fanart.jpg"], "clearlogo": ["clearlogo.png"],
       "landscape": ["landscape.jpg", "thumb.jpg"], "banner": ["banner.jpg"], "keyart": ["keyart.jpg"], "clearart": ["clearart.png"]}
def local(folder, base=""):
    art = {}
    for kind, names in MAP.items():
        for n in names:
            for cand in ([base + "-" + n] if base else []) + [n]:
                p = os.path.join(folder, cand)
                if os.path.exists(p):
                    art[kind] = p; break
            if kind in art: break
    return art
ms = k.rpc("VideoLibrary.GetMovies", {"properties": ["file", "art", "premiered"]})["movies"]
for m in ms:
    f = m["file"]; folder = os.path.dirname(f); base = os.path.splitext(os.path.basename(f))[0]
    art = local(folder, base)
    drop = {kk: None for kk in m["art"] if kk in MAP and kk not in art and not kk.startswith("set.")}
    params = {"movieid": m["movieid"], "art": dict(drop, **art)}
    if m.get("premiered"): params["dateadded"] = m["premiered"] + " 20:00:00"
    k.rpc("VideoLibrary.SetMovieDetails", params)
shows = k.rpc("VideoLibrary.GetTVShows", {"properties": ["file", "art", "premiered"]})["tvshows"]
for s in shows:
    art = local(s["file"])
    drop = {kk: None for kk in s["art"] if kk in MAP and kk not in art}
    k.rpc("VideoLibrary.SetTVShowDetails", {"tvshowid": s["tvshowid"], "art": dict(drop, **art)})
print(len(ms), "movies", len(shows), "shows")
