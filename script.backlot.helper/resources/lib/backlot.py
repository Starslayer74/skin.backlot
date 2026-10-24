# -*- coding: utf-8 -*-
"""Core of the Backlot helper: config storage, playlist generation and the
Home-window properties the Backlot skin reads.

A service is a dict:
    id, name, enabled, color (AARRGGBB), matches [studio/network names],
    banner, icon (optional custom art paths), preset (bool)
"""
import json
import os
import re
import time
import uuid
from xml.sax.saxutils import escape

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon("script.backlot.helper")
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_PATH = ADDON.getAddonInfo("path")
PROFILE = xbmcvfs.translatePath("special://profile/addon_data/%s/" % ADDON_ID)
CONFIG = os.path.join(PROFILE, "config.json")
PLAYLISTS = os.path.join(PROFILE, "playlists")
PLAYLIST_URL = "special://profile/addon_data/%s/playlists/" % ADDON_ID
ART_URL = "special://home/addons/%s/resources/media/services/" % ADDON_ID
HOME = xbmcgui.Window(10000)
MAX_SLOTS = 40
FALLBACK_COLOR = "FF2A2F3A"


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[%s] %s" % (ADDON_ID, msg), level)


# ------------------------------------------------------------------ presets / config
def load_presets():
    with open(os.path.join(ADDON_PATH, "resources", "presets.json"), encoding="utf-8") as f:
        return json.load(f)


def palette():
    return load_presets()["palette"]


def _preset_service(p):
    return {"id": p["id"], "name": p["name"], "enabled": p.get("enabled", False),
            "color": p.get("color", FALLBACK_COLOR), "matches": list(p.get("matches", [])),
            "banner": "", "icon": "", "logo": p.get("logo", ""), "preset": True,
            "android_app": p.get("android_app", ""), "website": p.get("website", ""), "launch": "",
            "network": p.get("network", ""), "auto_hide": bool(p.get("auto_hide"))}


# preset logos replaced in later versions; saved configs still holding these get the new one
OLD_LOGOS = {"max": ("HBO Max",), "british": ("BBC",), "telemundo": ("",), "pbs": ("",), "crunchyroll": ("",), "mgmplus": ("",)}
# preset studio lists from before presets_version 2; saved services still using
# exactly these get the fuller lists (anything the user customized is left alone)
OLD_MATCHES = {"peacock": ["NBC", "Universal"], "max": ["HBO", "Cinemax"], "netflix": ["Netflix"], "paramount": ["CBS", "Showtime"], "disney": ["ABC"], "cw": ["The CW", "Paramount Network", "The WB"], "amc": ["AMC", "Shudder"], "british": ["BBC"], "prime": ["Amazon", "MGM"], "appletv": ["Apple TV+", "Apple Studios", "Apple Original Films"], "hulu": ["Hulu", "FX"], "discovery": ["Discovery", "TLC", "HGTV", "Food Network"]}


def load():
    """Saved config merged with presets (new presets are appended)."""
    presets = load_presets()["services"]
    cfg = None
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError) as e:
            log("config unreadable, using defaults: %s" % e, xbmc.LOGWARNING)
    if not cfg:
        cfg = {"version": 1, "show_fallbacks": True, "services": [_preset_service(p) for p in presets]}
    by_id = {p["id"]: p for p in presets}
    for s in cfg["services"]:
        if s.get("preset") and s["id"] in by_id and ("logo" not in s or s.get("logo") in OLD_LOGOS.get(s["id"], ())):
            s["logo"] = by_id[s["id"]].get("logo", "")
        # Max went back to being HBO Max; rename it unless the user renamed it themselves
        if s.get("preset") and s["id"] == "max" and s.get("name") == "Max":
            s["name"] = "HBO Max"
        if s.get("preset") and s["id"] in by_id and s.get("matches") in _old_lists(s["id"]):
            s["matches"] = list(by_id[s["id"]].get("matches", []))
        if s.get("preset") and s["id"] == "british" and s.get("name") == "British":
            s["name"] = "UK TV"
        if s.get("preset") and s["id"] in by_id:
            # network presets added later: keep their roll-up parent and auto-hide flag current
            for k in ("network", "auto_hide"):
                if by_id[s["id"]].get(k):
                    s[k] = by_id[s["id"]][k]
        if s.get("preset") and s["id"] in by_id:
            for k in ("android_app", "website"):
                s.setdefault(k, by_id[s["id"]].get(k, ""))
        s.setdefault("launch", "")
    known = {s["id"] for s in cfg["services"]}
    for p in presets:
        if p["id"] not in known:
            cfg["services"].append(_preset_service(p))
    cfg.setdefault("show_fallbacks", True)
    for _child, (_parent, key, default) in MERGES.items():
        cfg.setdefault(key, default)
    cfg.setdefault("group_sets", True)
    cfg.setdefault("keep_sets_together", True)
    cfg.setdefault("show_collections", True)
    cfg.setdefault("networks", {})
    return cfg


# saved services still holding one of these exact studio lists get the current preset's list
OLD_MATCH_LISTS = {
    "british": [["BBC"], ["BBC", "ITV", "Channel 4", "Sky UK", "Sky Atlantic", "Sky Studios"]],
    "prime": [["Amazon", "MGM", "Metro-Goldwyn-Mayer", "United Artists", "Orion Pictures", "Epix"]],
}


def _old_lists(sid):
    lists = list(OLD_MATCH_LISTS.get(sid, []))
    if sid in OLD_MATCHES:
        lists.append(OLD_MATCHES[sid])
    return lists


NETWORK_MODES = ("both", "inside", "own")


def network_mode(cfg, sid):
    """both = its own tile and inside its streaming service, inside = only
    inside the service, own = only its own tile."""
    mode = cfg.get("networks", {}).get(sid, "both")
    return mode if mode in NETWORK_MODES else "both"


# services that can live inside another one: child id -> (parent id, config key, default)
MERGES = {
    "hulu": ("disney", "hulu_in_disney", True),         # Hulu's US app is folding into Disney+
    "discovery": ("max", "discovery_in_max", True),     # both Warner Bros. Discovery; Max carries Discovery+ shows
}


def active_services(cfg):
    """Enabled services as the home screen uses them. Merged services (Hulu
    inside Disney+, Discovery+ inside HBO Max) add their studios to the parent
    and get no tile of their own."""
    svcs = [dict(s, matches=list(s.get("matches", []))) for s in cfg["services"]]
    by_id = {x["id"]: x for x in svcs}
    # networks first (NBC into Peacock, FOX into Hulu ...), so a network inside
    # Hulu follows Hulu into Disney+ below
    for net in svcs:
        parent = by_id.get(net.get("network") or "")
        if not parent:
            continue
        mode = network_mode(cfg, net["id"])
        if mode in ("both", "inside"):
            parent["matches"] += [m for m in net["matches"] if m not in parent["matches"]]
        else:
            parent["matches"] = [m for m in parent["matches"] if m not in net["matches"]]
        net["enabled"] = mode in ("both", "own")
    for child_id, (parent_id, key, default) in MERGES.items():
        if not cfg.get(key, default):
            continue
        child = next((x for x in svcs if x["id"] == child_id), None)
        parent = next((x for x in svcs if x["id"] == parent_id), None)
        if child and parent:
            parent["matches"] += [m for m in child["matches"] if m not in parent["matches"]]
            child["enabled"] = False
    return [s for s in svcs if s.get("enabled") and s.get("matches")]


def save(cfg):
    os.makedirs(PROFILE, exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG)


def reset_service(svc):
    for p in load_presets()["services"]:
        if p["id"] == svc["id"]:
            fresh = _preset_service(p)
            fresh["enabled"] = svc.get("enabled", fresh["enabled"])
            return fresh
    return svc


def new_custom(name, matches, color):
    slug = re.sub(r"[^a-z0-9]+", "", name.lower())[:16] or "service"
    return {"id": "c_%s_%s" % (slug, uuid.uuid4().hex[:6]), "name": name, "enabled": True,
            "color": color, "matches": matches, "banner": "", "icon": "", "logo": "", "preset": False}


def first_run():
    """One-time Android TV style defaults: no '..' parent item or 'All seasons' entry in lists."""
    cfg = load()
    if cfg.get("defaults_applied", 0) >= 2:
        return
    _rpc("Settings.SetSettingValue", {"setting": "filelists.showparentdiritems", "value": False})
    # no "* All seasons" entry ahead of Season 1
    _rpc("Settings.SetSettingValue", {"setting": "videolibrary.showallitems", "value": False})
    cfg["defaults_applied"] = 2
    save(cfg)
    log("applied first-run defaults")


TMDBH = "plugin.video.themoviedb.helper"


def tmdbhelper_installed():
    return xbmc.getCondVisibility("System.HasAddon(%s)" % TMDBH)


def tune_tmdbhelper():
    """Turn on TMDb Helper's "Get additional details from the local Kodi
    library database" (setting id local_db; use_kodi_local_db in older
    versions). Without it TMDb Helper can't tell which titles you own, so
    "In library" badges never appear."""
    if not tmdbhelper_installed():
        return False
    cfg = load()
    if cfg.get("tmdbhelper_tuned") == 2:
        return True
    try:
        import xbmcaddon as _xa
        th = _xa.Addon(TMDBH)
        done = False
        try:
            if not th.getSettingBool("local_db"):
                th.setSettingBool("local_db", True)
            done = True
        except Exception:  # noqa: BLE001
            pass
        if not done:
            try:
                if th.getSettingInt("use_kodi_local_db") == 0:
                    th.setSettingInt("use_kodi_local_db", 1)
                done = True
            except Exception:  # noqa: BLE001
                pass
        if done:
            cfg["tmdbhelper_tuned"] = 2
            save(cfg)
            log("TMDb Helper set to use the local Kodi library")
    except Exception as e:  # noqa: BLE001
        log("couldn't adjust TMDb Helper: %s" % e, xbmc.LOGWARNING)
    return True


# ------------------------------------------------------------------ open the real service
def launch_target(svc):
    """(kind, value) for opening the service's own app or site on this device.
    svc["launch"] = "" (automatic), "android", "web", "exec:<command>" or "none"."""
    mode = svc.get("launch", "")
    android = xbmc.getCondVisibility("System.Platform.Android")
    if mode == "none":
        return ("", "")
    if mode.startswith("exec:"):
        return ("exec", mode[5:])
    if mode == "web":
        return ("web", svc.get("website", ""))
    if mode == "android" or (not mode and android and svc.get("android_app")):
        if android and svc.get("android_app"):
            return ("android", svc["android_app"])
    if svc.get("website"):
        return ("web", svc["website"])
    return ("", "")


def launch(sid):
    cfg = load()
    svc = next((s for s in cfg["services"] if s["id"] == sid), None)
    if not svc:
        return
    kind, value = launch_target(svc)
    if not kind or not value:
        xbmcgui.Dialog().notification(svc["name"], "No app or website set. Add one in Manage services.", ADDON.getAddonInfo("icon"))
        return
    log("opening %s: %s %s" % (svc["name"], kind, value))
    if kind == "android":
        xbmc.executebuiltin("StartAndroidActivity(%s)" % value)
    elif kind == "web":
        if xbmc.getCondVisibility("System.Platform.Android"):
            xbmc.executebuiltin('StartAndroidActivity("",android.intent.action.VIEW,"",%s)' % value)
        else:
            import webbrowser
            opened = False
            try:
                opened = webbrowser.open(value)
            except Exception:  # noqa: BLE001
                opened = False
            if not opened:
                # e.g. LibreELEC / OSMC: Kodi-only systems with no web browser
                xbmcgui.Dialog().ok(svc["name"], "There's no web browser on this device to open %s.[CR][CR]%s" % (svc["name"], value))
    elif kind == "exec":
        xbmc.executebuiltin('System.Exec("%s")' % value.replace('"', '\\"'))


# ------------------------------------------------------------------ art
LOGOS = "resource://resource.images.studios.coloured/"


def art_for(svc, kind):
    """Custom full-tile art the user picked, else '' (the skin draws the logo
    on the service color)."""
    return svc.get(kind) or ""


def logo_for(svc):
    """Logo for the tile: a dropped-in file, the logo the user picked, the
    preset's logo from Kodi's official studio pack, else the first matching
    studio name that the pack has."""
    # a file dropped into addon_data/script.backlot.helper/logos/<service id>.png wins
    for ext in (".png", ".jpg"):
        drop = os.path.join(PROFILE, "logos", svc.get("id", "") + ext)
        if svc.get("id") and os.path.exists(drop):
            return drop
    names = [svc.get("logo")] if svc.get("logo") else []
    names += svc.get("matches", [])
    for n in names:
        if not n:
            continue
        if n.startswith(("special://", "resource://", "/", "http")) or re.match(r"^[A-Za-z]:\\", n):
            return n
        if xbmcvfs.exists(LOGOS + n + ".png"):
            return LOGOS + n + ".png"
    return ""


def tint(color, amount=0.32):
    """Brand color pulled toward the skin's dark surface so full-color logos
    stay readable on it (e.g. a green logo on a green tile)."""
    try:
        r, g, b = int(color[2:4], 16), int(color[4:6], 16), int(color[6:8], 16)
    except (ValueError, TypeError):
        return FALLBACK_COLOR
    base = (0x16, 0x18, 0x1E)
    mix = [int(c * amount + bc * (1 - amount)) for c, bc in zip((r, g, b), base)]
    return "FF%02X%02X%02X" % tuple(mix)


# ------------------------------------------------------------------ playlists
def _playlist(fname, ptype, name, rules, order=("ascending", "sorttitle"), limit=None, group_sets=False, match="all"):
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
             '<smartplaylist type="%s">' % ptype, "    <name>%s</name>" % escape(name), "    <match>%s</match>" % match]
    for field, op, values in rules:
        lines.append('    <rule field="%s" operator="%s">' % (field, op))
        lines += ["        <value>%s</value>" % escape(v) for v in values]
        lines.append("    </rule>")
    if group_sets:
        # collections (movie sets) show as one entry; movies not in a set stay as they are
        lines.append('    <group mixed="true">sets</group>')
    if limit:
        lines.append("    <limit>%d</limit>" % limit)
    lines.append('    <order direction="%s">%s</order>' % order)
    lines.append("</smartplaylist>")
    with open(os.path.join(PLAYLISTS, fname), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return PLAYLIST_URL + fname


RECENT = ("descending", "dateadded")


def build_slots(cfg):
    """Write every playlist and return the ordered list of home tiles."""
    os.makedirs(PLAYLISTS, exist_ok=True)
    for f in os.listdir(PLAYLISTS):
        if f.endswith(".xsp"):
            os.remove(os.path.join(PLAYLISTS, f))
    slots, used_values = [], []
    active = active_services(cfg)
    # networks (NBC, FOX ...) list everything from that network; collections are
    # only kept together across the streaming services
    fixes = set_fixes([a for a in active if not a.get("network")]) if cfg.get("keep_sets_together", True) else {}
    lib = None
    for svc in active:
        sid, name = svc["id"], svc["name"]
        rule, match = studio_rules(svc["matches"])
        if svc.get("auto_hide"):
            # network and niche service tiles only show up once the library has something for them
            if lib is None:
                lib = library_items()
            if not any(matches_any(st, svc["matches"]) for _k, _t, st in lib):
                continue
        used_values += svc["matches"]
        mine, theirs = fixes.get(sid, ([], []))
        if mine or theirs:
            mpath = _movies_url(svc["matches"], mine, theirs, ("ascending", "sorttitle"))
            rpath = _movies_url(svc["matches"], mine, theirs, RECENT, 20)
        else:
            mpath = _playlist("%s_movies.xsp" % sid, "movies", "Movies", rule, group_sets=cfg.get("group_sets", True), match=match)
            rpath = _playlist("%s_movies_recent.xsp" % sid, "movies", "New %s movies" % name, rule, RECENT, 20, match=match)
        slots.append({
            "id": sid, "label": name, "color": svc.get("color") or FALLBACK_COLOR,
            "banner": art_for(svc, "banner"), "icon": art_for(svc, "icon"), "logo": logo_for(svc),
            "tint": tint(svc.get("color") or FALLBACK_COLOR),
            "can_launch": "true" if all(launch_target(svc)) else "",
            "tab1_label": "TV Shows", "tab1_path": _playlist("%s_tvshows.xsp" % sid, "tvshows", "TV Shows", rule, match=match),
            "tab2_label": "Movies", "tab2_path": mpath,
            "row1_label": "New %s shows" % name,
            "row1_path": _playlist("%s_tvshows_recent.xsp" % sid, "tvshows", "New %s shows" % name, rule, RECENT, 20, match=match),
            "row2_label": "New %s movies" % name,
            "row2_path": rpath,
        })
    if cfg.get("show_fallbacks", True):
        # Movies / TV Shows open the whole library directly (no hub)
        fb = {"color": FALLBACK_COLOR, "tint": FALLBACK_COLOR, "banner": "", "icon": "", "tab2_label": "", "tab2_path": ""}
        slots.append(dict(fb, id="movies", label="Movies",
                          logo=ART_URL + "movies_logo.png",
                          direct="videodb://movies/titles/",
                          tab1_label="Movies", tab1_path="videodb://movies/titles/",
                          row1_label="Recently added movies",
                          row1_path=_playlist("all_movies_recent.xsp", "movies", "Recently added", [], RECENT, 20),
                          row2_label="Continue watching",
                          row2_path=_playlist("all_movies_inprogress.xsp", "movies", "Continue watching",
                                              [("inprogress", "true", [])], ("descending", "lastplayed"), 20)))
        if cfg.get("show_collections", True):
            slots.append(dict(fb, id="collections", label="Collections",
                              logo=ART_URL + "collections_logo.png",
                              direct="videodb://movies/sets/",
                              tab1_label="Collections", tab1_path="videodb://movies/sets/",
                              row1_label="Collections",
                              row1_path="videodb://movies/sets/",
                              row2_label="", row2_path=""))
        slots.append(dict(fb, id="tvshows", label="TV Shows",
                          logo=ART_URL + "tvshows_logo.png",
                          direct="videodb://tvshows/titles/",
                          tab1_label="TV Shows", tab1_path="videodb://tvshows/titles/",
                          row1_label="Recently updated shows",
                          row1_path=_playlist("all_tvshows_recent.xsp", "tvshows", "Recently updated", [], RECENT, 20),
                          row2_label="Shows in progress",
                          row2_path=_playlist("all_tvshows_inprogress.xsp", "tvshows", "Shows in progress",
                                              [("inprogress", "true", [])], ("descending", "lastplayed"), 20)))
    return slots[:MAX_SLOTS]


def set_fixes(active):
    """Keep each movie collection under one service: the one holding most of
    its movies (ties go to the service listed first), so every Blade or Alien
    film sits together even when their studios differ.
    Returns {service id: (collections to pull in, collections to leave out)},
    listing only collections that actually need moving."""
    order = [s["id"] for s in active]
    members = {}
    for m in _rpc("VideoLibrary.GetMovies", {"properties": ["set", "studio"]}).get("movies", []):
        if m.get("set"):
            studios = m.get("studio", []) or []
            members.setdefault(m["set"], []).append({s["id"] for s in active if matches_any(studios, s["matches"])})
    fixes = {}
    for name, ms in members.items():
        counts = {}
        for hit in ms:
            for sid in hit:
                counts[sid] = counts.get(sid, 0) + 1
        if not counts:
            continue
        owner = sorted(counts, key=lambda sid: (-counts[sid], order.index(sid)))[0]
        if any(owner not in hit for hit in ms):
            fixes.setdefault(owner, ([], []))[0].append(name)
        for sid in counts:
            if sid != owner:
                fixes.setdefault(sid, ([], []))[1].append(name)
    return fixes


def _movies_url(matches, mine, theirs, order, limit=None):
    """A library movie list for a service as a videodb URL with a JSON filter
    (smart playlist files can't say "this studio OR this collection, but not
    those collections")."""
    from urllib.parse import quote
    contains, exact = split_values(matches)
    anyof = []
    if contains:
        anyof.append({"field": "studio", "operator": "contains", "value": contains})
    if exact:
        anyof.append({"field": "studio", "operator": "is", "value": exact})
    if mine:
        anyof.append({"field": "set", "operator": "is", "value": sorted(mine)})
    rules = [{"or": anyof} if len(anyof) > 1 else anyof[0]]
    if theirs:
        rules.append({"field": "set", "operator": "isnot", "value": sorted(theirs)})
    xsp = {"type": "movies", "rules": {"and": rules}, "order": {"direction": order[0], "method": order[1]}}
    if limit:
        xsp["limit"] = limit
    return "videodb://movies/titles/?xsp=" + quote(json.dumps(xsp, separators=(",", ":"), ensure_ascii=False), safe="")


SLOT_KEYS = ("id", "label", "color", "tint", "logo", "banner", "icon", "direct", "can_launch", "tab1_label", "tab1_path", "tab2_label", "tab2_path",
             "row1_label", "row1_path", "row2_label", "row2_path")


def publish(cfg=None):
    """Regenerate playlists and push the tile list to the skin."""
    # the service and the skin can both ask at startup; let one finish first
    mon = xbmc.Monitor()
    for _ in range(50):
        if not HOME.getProperty("backlot.busy"):
            break
        if mon.waitForAbort(0.1):
            return []
    HOME.setProperty("backlot.busy", "true")
    try:
        return _publish(cfg or load())
    finally:
        HOME.clearProperty("backlot.busy")


def _publish(cfg):
    # Kodi's own movie lists (e.g. Movies > All movies) follow this setting
    _rpc("Settings.SetSettingValue", {"setting": "videolibrary.groupmoviesets",
                                      "value": bool(cfg.get("group_sets", True))})
    slots = build_slots(cfg)
    for n in range(1, MAX_SLOTS + 1):
        slot = slots[n - 1] if n <= len(slots) else None
        for k in SLOT_KEYS:
            prop = "backlot.svc.%d.%s" % (n, k)
            if slot:
                HOME.setProperty(prop, slot.get(k, ""))
            else:
                HOME.clearProperty(prop)
    HOME.setProperty("backlot.svc.count", str(len(slots)))
    HOME.setProperty("backlot.ready", "true")
    HOME.setProperty("backlot.updated", str(time.time()))
    log("published %d tiles" % len(slots))
    return slots


# ------------------------------------------------------------------ library
def _rpc(method, params):
    req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    res = json.loads(xbmc.executeJSONRPC(json.dumps(req)))
    return res.get("result", {})


def library_items():
    """[(type, title, [studios])] for every movie and TV show."""
    out = []
    for method, key, kind in (("VideoLibrary.GetMovies", "movies", "movie"),
                              ("VideoLibrary.GetTVShows", "tvshows", "tvshow")):
        for item in _rpc(method, {"properties": ["studio"]}).get(key, []):
            out.append((kind, item.get("label", ""), item.get("studio", []) or []))
    return out


# Kodi art type -> file names tinyMediaManager (and others) write into each movie's folder
SET_ART_FILES = {
    "poster": ("movieset-poster",),
    "fanart": ("movieset-fanart",),
    "clearlogo": ("movieset-clearlogo", "movieset-logo"),
    "banner": ("movieset-banner",),
    "landscape": ("movieset-landscape", "movieset-thumb"),
    "clearart": ("movieset-clearart",),
    "discart": ("movieset-discart", "movieset-disc"),
    "keyart": ("movieset-keyart",),
}


def _movie_folder(path):
    if path.startswith("stack://"):
        path = path[8:].split(" , ")[0]
    cut = max(path.rfind("/"), path.rfind("\\"))
    return path[:cut + 1] if cut >= 0 else ""


SET_ART_CACHE = os.path.join(PROFILE, "setart.json")


def collection_art(overwrite=False):
    """Give each movie collection the artwork saved next to its movies
    (movieset-poster.jpg, movieset-clearlogo.png ...). Kodi only looks in a
    separate "movie set information folder", so without this collections
    show no artwork. Returns how many collections were updated.

    Each collection's folders are remembered once checked, so later runs only
    look at new or changed collections instead of every file on every disk.
    overwrite=True (the Manage services button) re-checks everything."""
    if xbmc.getCondVisibility("Library.IsScanningVideo") and not overwrite:
        return 0  # runs again when the scan finishes
    sets = _rpc("VideoLibrary.GetMovieSets", {"properties": ["art"]}).get("sets", [])
    if not sets:
        return 0
    folders = {}
    for m in _rpc("VideoLibrary.GetMovies", {"properties": ["setid", "file"]}).get("movies", []):
        if m.get("setid"):
            folder = _movie_folder(m.get("file", ""))
            if folder and folder not in folders.setdefault(m["setid"], []):
                folders[m["setid"]].append(folder)
    cache = {}
    if not overwrite:
        try:
            with open(SET_ART_CACHE, encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, ValueError):
            cache = {}
    mon = xbmc.Monitor()
    updated = 0
    for st in sets:
        if mon.abortRequested():
            break
        sid = str(st["setid"])
        have = st.get("art", {}) or {}
        sig = "|".join(sorted(folders.get(st["setid"], [])))
        # unchanged collection that already got its poster: nothing to look for
        if not overwrite and cache.get(sid) == sig and have.get("poster"):
            continue
        new = {}
        for kind, names in SET_ART_FILES.items():
            if have.get(kind) and not overwrite:
                continue
            found = ""
            for folder in folders.get(st["setid"], []):
                for name in names:
                    for ext in (".jpg", ".png"):
                        if xbmcvfs.exists(folder + name + ext):
                            found = folder + name + ext
                            break
                    if found:
                        break
                if found:
                    break
            if found and found != have.get(kind):
                new[kind] = found
        if new:
            _rpc("VideoLibrary.SetMovieSetDetails", {"setid": st["setid"], "art": new})
            updated += 1
        cache[sid] = sig
    try:
        os.makedirs(PROFILE, exist_ok=True)
        with open(SET_ART_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except OSError:
        pass
    if updated:
        log("collection artwork added to %d collections" % updated)
    return updated


def studio_counts(items=None):
    counts = {}
    for _kind, _title, studios in items if items is not None else library_items():
        for s in studios:
            counts[s] = counts.get(s, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))


def matches_any(studios, values):
    """A value matches when it appears inside a studio name; a value starting
    with "=" must equal the studio name (so FOX doesn't catch 20th Century Fox)."""
    low = [s.lower() for s in studios]
    for v in values:
        v = v.lower()
        if v.startswith("="):
            if v[1:] in low:
                return True
        elif any(v in s for s in low):
            return True
    return False


def split_values(values):
    """(contains values, exact values) for building library filters."""
    return [v for v in values if not v.startswith("=")], [v[1:] for v in values if v.startswith("=")]


def studio_rules(values):
    """Smart playlist rules for "any of these studios"; returns (rules, match)."""
    contains, exact = split_values(values)
    rules = []
    if contains:
        rules.append(("studio", "contains", contains))
    if exact:
        rules.append(("studio", "is", exact))
    return rules, ("one" if len(rules) > 1 else "all")


def unmatched_studios(cfg):
    values = [v for s in active_services(cfg) for v in s["matches"]]
    items = [i for i in library_items() if not matches_any(i[2], values)]
    return studio_counts(items), len(items)
