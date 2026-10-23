# -*- coding: utf-8 -*-
"""Remote-friendly menus for managing Backlot services."""
import json
import os
import shutil

import xbmc
import xbmcgui
import xbmcvfs

import backlot

DIALOG = xbmcgui.Dialog()
HEADING = "Backlot services"


def notify(msg):
    DIALOG.notification(HEADING, msg, backlot.ADDON.getAddonInfo("icon"), 3000)


def commit(cfg, msg):
    backlot.save(cfg)
    backlot.publish(cfg)
    notify(msg)


def label(svc):
    state = "" if svc.get("enabled") else "  (off)"
    return "%s%s" % (svc["name"], state)


def pick_service(cfg, heading):
    svcs = cfg["services"]
    i = DIALOG.select(heading, [label(s) for s in svcs])
    return svcs[i] if i >= 0 else None


# ------------------------------------------------------------------ main menu
def main():
    while True:
        cfg = backlot.load()
        fb = "on" if cfg.get("show_fallbacks", True) else "off"
        options = [
            ("Turn services on or off", toggle_services),
            ("Change order", reorder),
            ("Add a custom service", add_custom),
            ("Edit a service", edit_service),
            ("Studios not in any service", unmatched_report),
            ("Movies and TV Shows tiles: %s" % fb, toggle_fallbacks),
            ("Group collections into one tile: %s" % ("on" if cfg.get("group_sets", True) else "off"), toggle_sets),
            ("Hulu: %s" % merge_label(cfg, "hulu"), lambda: choose_merge("hulu")),
            ("Discovery+: %s" % merge_label(cfg, "discovery"), lambda: choose_merge("discovery")),
            ("Reload collection artwork from movie folders", reload_set_art),
            ("Export setup", export_config),
            ("Import setup", import_config),
            ("Reset everything to defaults", reset_all),
        ]
        i = DIALOG.select(HEADING, [o[0] for o in options])
        if i < 0:
            return
        options[i][1]()


# ------------------------------------------------------------------ actions
def toggle_services(quiet=False):
    cfg = backlot.load()
    svcs = cfg["services"]
    pre = [n for n, s in enumerate(svcs) if s.get("enabled")]
    chosen = DIALOG.multiselect("Services on the home screen", [s["name"] for s in svcs], preselect=pre)
    if chosen is None:
        return
    for n, s in enumerate(svcs):
        was = s.get("enabled")
        s["enabled"] = n in chosen
        if s["id"] in backlot.MERGES and s["enabled"] and not was:
            cfg[backlot.MERGES[s["id"]][1]] = False  # turning Hulu/Discovery+ on means its own tile
    if quiet:
        backlot.save(cfg)
        backlot.publish(cfg)
    else:
        commit(cfg, "%d services on" % len(chosen))


def reorder():
    from reorder_ui import arrange
    cfg = backlot.load()
    if arrange(cfg):
        commit(cfg, "Order saved")


def choose_matches(current, title):
    """Pick studios/networks from the library and/or type them."""
    matches = list(current)
    while True:
        opts = ["Pick from studios in my library", "Type names (comma separated)",
                "Done  -  %s" % (", ".join(matches) if matches else "nothing chosen")]
        i = DIALOG.select(title, opts, preselect=2 if matches else 0)
        if i in (-1, 2):
            return matches
        if i == 0:
            counts = backlot.studio_counts()
            names = [n for n, _c in counts]
            extra = [m for m in matches if m not in names]
            names = extra + names
            labels = ["%s  (%d)" % (n, dict(counts).get(n, 0)) if n in dict(counts) else n for n in names]
            pre = [n for n, name in enumerate(names) if name in matches]
            chosen = DIALOG.multiselect("Studios and networks", labels, preselect=pre)
            if chosen is not None:
                matches = [names[n] for n in chosen]
        elif i == 1:
            typed = DIALOG.input("Studios / networks, separated by commas", ", ".join(matches))
            if typed is not None:
                matches = [t.strip() for t in typed.split(",") if t.strip()]


def choose_color(current=None):
    pal = backlot.palette()
    pre = next((n for n, (_name, c) in enumerate(pal) if c == current), 0)
    i = DIALOG.select("Tile color", [p[0] for p in pal], preselect=pre)
    return pal[i][1] if i >= 0 else current


def browse_image(title):
    path = DIALOG.browse(2, title, "files", ".png|.jpg|.jpeg")
    return path if path and not path.endswith(("/", "\\")) else ""


def quick_service(cfg, studio):
    """One-step service for a studio: named after it, next unused palette
    color, logo from Kodi's studio pack when there is one."""
    used = {s.get("color") for s in cfg["services"]}
    pal = [c for _n, c in backlot.palette()]
    color = next((c for c in pal if c not in used), pal[len(cfg["services"]) % len(pal)])
    svc = backlot.new_custom(studio, [studio], color)
    cfg["services"].append(svc)
    commit(cfg, "%s is now a service" % studio)
    DIALOG.ok(studio, "%s now has its own tile at the end of your services.[CR][CR]Rename it, change its logo or color, or add more studios to it in Manage services > Edit a service. Move it with Arrange services." % studio)


def add_custom(name="", matches=None):
    name = DIALOG.input("Service name", name)
    if not name:
        return
    matches = choose_matches(matches or [], "What belongs to %s?" % name)
    if not matches:
        notify("No studios chosen, nothing added")
        return
    color = choose_color(backlot.FALLBACK_COLOR)
    cfg = backlot.load()
    svc = backlot.new_custom(name, matches, color)
    if not backlot.logo_for(svc) and DIALOG.yesno(
            name, "Kodi's studio logo pack has no logo for %s.[CR]Add your own logo image now? Without one, the tile shows the name." % name,
            nolabel="Later", yeslabel="Add logo"):
        path = browse_image("Logo (transparent PNG works best)")
        if path:
            svc["logo"] = keep_image(path, "%s_logo" % svc["id"])
    cfg["services"].append(svc)
    commit(cfg, "%s added" % name)


def keep_image(path, name):
    """Copy a chosen image into Backlot's own folder so it still works if the
    original is moved or lives on a share that isn't always connected."""
    folder = os.path.join(backlot.PROFILE, "logos")
    os.makedirs(folder, exist_ok=True)
    ext = os.path.splitext(path)[1].lower() or ".png"
    dest = os.path.join(folder, name + ext)
    if xbmcvfs.copy(path, dest):
        return dest
    return path


def choose_logo(svc):
    """Logo drawn on the service tile: your own image, one from Kodi's studio
    logo pack by name, or the preset's default."""
    opts = ["Choose an image file", "Use a logo from Kodi's studio pack", "Use default"]
    j = DIALOG.select("Logo for %s" % svc["name"], opts)
    if j == 0:
        path = browse_image("Logo (transparent PNG works best)")
        if path:
            svc["logo"] = keep_image(path, "%s_logo" % svc["id"])
    elif j == 1:
        name = DIALOG.input("Studio or network name as Kodi's pack spells it (e.g. HBO Max)",
                            svc.get("logo", "") if not os.path.isabs(svc.get("logo", "")) else "")
        if name:
            if xbmcvfs.exists(backlot.LOGOS + name + ".png"):
                svc["logo"] = name
            else:
                DIALOG.ok(svc["name"], "Kodi's studio logo pack has no logo called \"%s\"." % name)
    elif j == 2:
        svc["logo"] = backlot.reset_service(dict(svc)).get("logo", "") if svc.get("preset") else ""


def launch_label(svc):
    kind, value = backlot.launch_target(svc)
    if not kind:
        return "none"
    return {"android": "app %s", "web": "website %s", "exec": "program %s"}[kind] % value


def choose_launch(svc):
    """What the service page's "Open <service>" button starts, so you can jump
    to the real app or site when you have a subscription."""
    opts = [("auto", "Automatic", "The Android TV app on Android boxes, the website everywhere else"),
            ("android", "Android TV app", "Package: %s" % (svc.get("android_app") or "not set")),
            ("web", "Website", svc.get("website") or "not set"),
            ("exec", "Program on this computer", "Run a program or shortcut (Windows, Linux, Mac)"),
            ("none", "No button", "Hide the Open button for this service")]
    i = DIALOG.select("%s: Open button" % svc["name"], [xbmcgui.ListItem(a, b) for _k, a, b in opts], useDetails=True)
    if i < 0:
        return
    k = opts[i][0]
    if k == "auto":
        svc["launch"] = ""
    elif k == "android":
        pkg = DIALOG.input("Android package name (e.g. com.netflix.ninja)", svc.get("android_app", ""))
        if pkg:
            svc["android_app"] = pkg.strip()
            svc["launch"] = "android"
    elif k == "web":
        url = DIALOG.input("Website address", svc.get("website", "") or "https://")
        if url:
            svc["website"] = url.strip()
            svc["launch"] = "web"
    elif k == "exec":
        cur = svc.get("launch", "")[5:] if svc.get("launch", "").startswith("exec:") else ""
        prog = DIALOG.browse(1, "Choose the program or shortcut", "files", "", False, False, cur)
        if prog and not prog.endswith(("/", "\\")):
            svc["launch"] = "exec:" + prog
    elif k == "none":
        svc["launch"] = "none"


def edit_service():
    cfg = backlot.load()
    svc = pick_service(cfg, "Edit which service?")
    if not svc:
        return
    while True:
        preset = svc.get("preset")
        logo = svc.get("logo", "")
        opts = [("name", "Name: %s" % svc["name"]),
                ("matches", "Studios / networks: %s" % ", ".join(svc.get("matches", []))),
                ("color", "Tile color"),
                ("logo", "Logo: %s" % (os.path.basename(logo) if logo else "none (shows the name)")),
                ("banner", "Full banner image: %s" % (os.path.basename(svc["banner"]) if svc.get("banner") else "none")),
                ("icon", "Full circle image: %s" % (os.path.basename(svc["icon"]) if svc.get("icon") else "none")),
                ("launch", "Open button: %s" % launch_label(svc)),
                ("enabled", "Turn %s" % ("off" if svc.get("enabled") else "on")),
                ("reset", "Reset to preset" if preset else "Delete this service"),
                ("done", "Done")]
        i = DIALOG.select(svc["name"], [o[1] for o in opts])
        key = opts[i][0] if i >= 0 else "done"
        if key == "done":
            break
        if key == "name":
            new = DIALOG.input("Service name", svc["name"])
            if new:
                svc["name"] = new
        elif key == "matches":
            svc["matches"] = choose_matches(svc.get("matches", []), "What belongs to %s?" % svc["name"])
        elif key == "color":
            svc["color"] = choose_color(svc.get("color"))
        elif key == "logo":
            choose_logo(svc)
        elif key in ("banner", "icon"):
            j = DIALOG.select(opts[i][1], ["Choose an image (replaces the logo tile)", "None"])
            if j == 0:
                path = browse_image("Banner (16:9)" if key == "banner" else "Circle icon (square)")
                if path:
                    svc[key] = keep_image(path, "%s_%s" % (svc["id"], key))
            elif j == 1:
                svc[key] = ""
        elif key == "launch":
            choose_launch(svc)
        elif key == "enabled":
            svc["enabled"] = not svc.get("enabled")
        elif key == "reset":
            if preset:
                if DIALOG.yesno(svc["name"], "Put this service back to its original settings?"):
                    idx = cfg["services"].index(svc)
                    svc = backlot.reset_service(svc)
                    cfg["services"][idx] = svc
            elif DIALOG.yesno(svc["name"], "Delete this service?"):
                cfg["services"].remove(svc)
                commit(cfg, "%s deleted" % svc["name"])
                return
    commit(cfg, "%s saved" % svc["name"])


def unmatched_report():
    """Studios and networks in the library that no service claims. Their
    titles land in the Movies / TV Shows tiles; pick one to give it a home."""
    cfg = backlot.load()
    DIALOG.notification(HEADING, "Reading your library...", backlot.ADDON.getAddonInfo("icon"), 1500)
    counts, total = backlot.unmatched_studios(cfg)
    if not counts:
        DIALOG.ok(HEADING, "Every movie and show in your library belongs to a service." if total == 0
                  else "%d titles have no studio listed, so they go to Movies / TV Shows." % total)
        return
    items = [xbmcgui.ListItem(n, "%d title%s now under Movies / TV Shows" % (c, "" if c == 1 else "s")) for n, c in counts]
    i = DIALOG.select("Studios with no service: pick one to give it a home", items, useDetails=True)
    if i < 0:
        return
    studio = counts[i][0]
    active = [s for s in cfg["services"] if s.get("enabled")]
    opts = [xbmcgui.ListItem("Make %s its own service" % studio, "Adds a new tile to the home screen")]
    opts += [xbmcgui.ListItem("Add to %s" % s["name"], "%s titles will show up under %s" % (studio, s["name"])) for s in active]
    j = DIALOG.select(studio, opts, useDetails=True)
    if j == 0:
        quick_service(cfg, studio)
    elif j > 0:
        svc = active[j - 1]
        if studio not in svc["matches"]:
            svc["matches"].append(studio)
        commit(cfg, "%s added to %s" % (studio, svc["name"]))


def toggle_fallbacks():
    cfg = backlot.load()
    cfg["show_fallbacks"] = not cfg.get("show_fallbacks", True)
    commit(cfg, "Movies / TV Shows tiles %s" % ("on" if cfg["show_fallbacks"] else "off"))


MERGE_TEXT = {
    "hulu": ("Hulu", "Disney+", "Hulu's US app is moving into Disney+, so Hulu shows appear there"),
    "discovery": ("Discovery+", "Max", "Max and Discovery+ are both Warner Bros. Discovery, and Max carries Discovery+ shows"),
}


def merge_label(cfg, sid):
    parent_id, key, default = backlot.MERGES[sid]
    svc = next((s for s in cfg["services"] if s["id"] == sid), {})
    if cfg.get(key, default):
        return "inside %s" % MERGE_TEXT[sid][1]
    return "its own tile" if svc.get("enabled") else "left out"


def merge_choices(sid):
    name, parent, why = MERGE_TEXT[sid]
    return [("Inside %s" % parent, why),
            ("Its own tile", "Keep a separate %s service on the home screen" % name),
            ("Leave it out", "%s titles go to Movies / TV Shows" % name)]


def set_merge(cfg, sid, choice):
    _parent, key, _default = backlot.MERGES[sid]
    svc = next((s for s in cfg["services"] if s["id"] == sid), None)
    cfg[key] = choice == 0
    if svc:
        svc["enabled"] = choice == 1


def choose_merge(sid):
    cfg = backlot.load()
    items = [xbmcgui.ListItem(a, b) for a, b in merge_choices(sid)]
    i = DIALOG.select("Where should %s go?" % MERGE_TEXT[sid][0], items, useDetails=True)
    if i < 0:
        return
    set_merge(cfg, sid, i)
    commit(cfg, "%s: %s" % (MERGE_TEXT[sid][0], merge_label(cfg, sid)))


def reload_set_art():
    DIALOG.notification(HEADING, "Looking for collection artwork...", backlot.ADDON.getAddonInfo("icon"), 2000)
    n = backlot.collection_art(overwrite=True)
    DIALOG.ok(HEADING, "Updated artwork for %d collection%s." % (n, "" if n == 1 else "s") if n else
              "No collection artwork files (movieset-poster.jpg and so on) were found next to your movies.")


def toggle_sets():
    cfg = backlot.load()
    cfg["group_sets"] = not cfg.get("group_sets", True)
    commit(cfg, "Collections %s" % ("grouped" if cfg["group_sets"] else "shown as single movies"))


BUSY = ("System.HasActiveModalDialog | Window.IsVisible(extendedprogressdialog) | "
        "Window.IsVisible(progressdialog) | Window.IsVisible(busydialog)")


def install_and_wait(addon_id, seconds):
    """Ask Kodi to install an add-on and wait until it's there. Gives up early
    when the user declines or Kodi stops showing any install activity."""
    monitor = xbmc.Monitor()
    has = "System.HasAddon(%s)" % addon_id
    if xbmc.getCondVisibility(has):
        return True
    xbmc.executebuiltin("InstallAddon(%s)" % addon_id, True)
    idle = 0.0
    waited = 0.0
    while waited < seconds and not monitor.abortRequested():
        if xbmc.getCondVisibility(has):
            return True
        idle = 0.0 if xbmc.getCondVisibility(BUSY) else idle + 0.5
        if idle >= 8:
            break
        monitor.waitForAbort(0.5)
        waited += 0.5
    return bool(xbmc.getCondVisibility(has))


def install_tmdbhelper(ask=True):
    """Install jurialmunkey's repository (shipped in the Backlot repository),
    then TMDb Helper from it, then switch on its library matching."""
    if backlot.tmdbhelper_installed():
        backlot.tune_tmdbhelper()
        if ask:
            DIALOG.ok(HEADING, "TMDb Helper is already installed. Cast details and similar titles are on.")
        return
    if ask and not DIALOG.yesno(HEADING, "TMDb Helper adds actor biographies, filmographies and similar titles to info screens.[CR][CR]Install it now? Kodi will ask you to confirm twice.",
                                yeslabel="Install", nolabel="Not now"):
        return
    monitor = xbmc.Monitor()

    if not xbmc.getCondVisibility("System.HasAddon(repository.jurialmunkey)"):
        if not install_and_wait("repository.jurialmunkey", 120):
            DIALOG.ok(HEADING, "The jurialmunkey repository wasn't installed, so TMDb Helper can't be added yet.")
            return
        xbmc.executebuiltin("UpdateAddonRepos", True)
        monitor.waitForAbort(8)
    if install_and_wait(backlot.TMDBH, 300):
        backlot.tune_tmdbhelper()
        DIALOG.ok(HEADING, "TMDb Helper is installed. Open any movie's info to see cast details and similar titles.")
    else:
        DIALOG.ok(HEADING, "TMDb Helper didn't finish installing. Try again from Backlot settings, or install it from the jurialmunkey repository.")


PSE = "script.preshowexperience"
PSE_REPO_URL = "https://preshowmedia.com/repo/"


def install_preshow(ask=True):
    """PreShow Experience isn't in Kodi's official repository. Fetch its
    repository add-on from preshowmedia.com, add it to Kodi, then install
    PreShow Experience from it (updates then arrive like any other add-on)."""
    import re
    import urllib.request
    import zipfile
    if xbmc.getCondVisibility("System.HasAddon(%s)" % PSE):
        if ask:
            DIALOG.ok(HEADING, "PreShow Experience is already installed.")
        return True
    if ask and not DIALOG.yesno(HEADING, "Install PreShow Experience? It plays trailers, intros and ratings before your movie, like a theater.[CR][CR]Its repository comes from preshowmedia.com.",
                                yeslabel="Install", nolabel="Not now"):
        return False
    progress = xbmcgui.DialogProgress()
    progress.create("PreShow Experience", "Getting the PreShow repository...")
    try:
        req = urllib.request.Request(PSE_REPO_URL, headers={"User-Agent": "Kodi Backlot"})
        listing = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        zips = sorted(set(re.findall(r'href="([^"]*repository\.preshow[^"/]*\.zip)"', listing)))
        if not zips:
            raise RuntimeError("no repository zip found at %s" % PSE_REPO_URL)
        name = zips[-1]
        url = name if name.startswith("http") else PSE_REPO_URL + name.lstrip("./")
        tmp = xbmcvfs.translatePath("special://temp/backlot-preshow-repo.zip")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Kodi Backlot"}), timeout=60) as r, \
                open(tmp, "wb") as f:
            f.write(r.read())
        progress.update(40, "Adding the repository to Kodi...")
        with zipfile.ZipFile(tmp) as z:
            repo_id = z.namelist()[0].split("/")[0]
            names = z.namelist()
            if not repo_id.startswith("repository.") or any(
                    n.startswith(("/", "\\")) or ".." in n.split("/") or not n.startswith(repo_id + "/") for n in names):
                raise RuntimeError("unexpected contents in %s" % name)
            z.extractall(xbmcvfs.translatePath("special://home/addons/"), names)
        xbmc.executebuiltin("UpdateLocalAddons", True)
        mon = xbmc.Monitor()
        for _ in range(20):
            if xbmc.getCondVisibility("System.HasAddon(%s)" % repo_id) or mon.waitForAbort(0.5):
                break
        backlot._rpc("Addons.SetAddonEnabled", {"addonid": repo_id, "enabled": True})
        xbmc.executebuiltin("UpdateAddonRepos", True)
        mon.waitForAbort(6)
    except Exception as e:  # noqa: BLE001
        progress.close()
        backlot.log("PreShow repository install failed: %s" % e, xbmc.LOGWARNING)
        DIALOG.ok(HEADING, "Couldn't reach the PreShow Experience repository. You can install it later from Backlot settings, or follow the guide at preshowexperience.com.")
        return False
    progress.update(70, "Installing PreShow Experience...")
    progress.close()
    if install_and_wait(PSE, 300):
        DIALOG.ok(HEADING, "PreShow Experience is installed. Movie info screens now have a PreShow button. Set up your sequences from its add-on settings.")
        return True
    DIALOG.ok(HEADING, "PreShow Experience didn't finish installing. Try again from Backlot settings.")
    return False


SOUND_CHOICES = [("resource.uisounds.backlot", "Backlot sounds", "Soft ticks as you move and a pop when you select, like Android TV."),
                 ("", "Keep what I have", "Leave Kodi's navigation sounds as they are now."),
                 ("OFF", "No sounds", "Navigate silently.")]


def choose_sounds(step=""):
    from setup_ui import choose
    cur_val = backlot._rpc("Settings.GetSettingValue", {"setting": "lookandfeel.soundskin"}).get("value", "")
    cur = 0 if cur_val == "resource.uisounds.backlot" else (2 if cur_val == "OFF" else 1)
    j = choose("Navigation sounds", [(a, b, "") for _v, a, b in SOUND_CHOICES], step=step, preselect=0, current=cur)
    if j >= 0 and SOUND_CHOICES[j][0]:
        backlot._rpc("Settings.SetSettingValue", {"setting": "lookandfeel.soundskin", "value": SOUND_CHOICES[j][0]})


WEATHER_PROVIDERS = [
    ("weather.multi", "Multi Weather", "Free, worldwide, no account needed (recommended)"),
    ("weather.gismeteo", "Gismeteo", "Free, worldwide"),
    ("weather.noaa", "NOAA", "Free, US locations only, from the National Weather Service"),
]


def current_weather_provider():
    res = backlot._rpc("Settings.GetSettingValue", {"setting": "weather.addon"})
    return res.get("value", "") if isinstance(res, dict) else ""


def setup_weather(ask=True):
    """Pick (and install) a weather provider, then open its settings to set a location."""
    provider = current_weather_provider()
    if provider and xbmc.getCondVisibility("System.HasAddon(%s)" % provider):
        if not ask or DIALOG.yesno(HEADING, "Weather comes from %s.[CR]Set or change your location now?" % provider,
                                   yeslabel="Set location", nolabel="Keep it"):
            xbmc.executebuiltin("Addon.OpenSettings(%s)" % provider, True)
        return True
    labels = []
    for aid, name, note in WEATHER_PROVIDERS:
        labels.append(xbmcgui.ListItem(name, note))
    i = DIALOG.select("Where should weather come from?", labels, useDetails=True)
    if i < 0:
        return False
    aid = WEATHER_PROVIDERS[i][0]
    if not xbmc.getCondVisibility("System.HasAddon(%s)" % aid):
        install_and_wait(aid, 180)
    if not xbmc.getCondVisibility("System.HasAddon(%s)" % aid):
        DIALOG.ok(HEADING, "%s wasn't installed. You can try again from Backlot settings." % WEATHER_PROVIDERS[i][1])
        return False
    backlot._rpc("Settings.SetSettingValue", {"setting": "weather.addon", "value": aid})
    DIALOG.ok(HEADING, "Next, set your location in %s's settings.[CR]Weather appears in the top-left corner once it has your location." % WEATHER_PROVIDERS[i][1])
    xbmc.executebuiltin("Addon.OpenSettings(%s)" % aid, True)
    return True


def _setting(sid):
    res = backlot._rpc("Settings.GetSettings", {"filter": {"section": "interface", "category": "skin"}})
    for st in res.get("settings", []) if isinstance(res, dict) else []:
        if st.get("id") == sid:
            return st
    return {}


def choose_theme():
    """Pick one of the skin's color themes (Kodi's 'Colors' skin setting)."""
    st = _setting("lookandfeel.skincolors")
    opts = st.get("options", [])
    if not opts:
        DIALOG.ok(HEADING, "No color themes found.")
        return False
    labels = [("Midnight (default)" if o["value"] in ("SKINDEFAULT", "defaults") else o["label"]) for o in opts]
    cur = st.get("value")
    pre = next((n for n, o in enumerate(opts) if o["value"] == cur), 0)
    i = DIALOG.select("Color theme", labels, preselect=pre)
    if i < 0:
        return False
    backlot._rpc("Settings.SetSettingValue", {"setting": "lookandfeel.skincolors", "value": opts[i]["value"]})
    return True


SETUP = "Backlot setup"
YES = getattr(xbmcgui, "DLG_YESNO_YES_BTN", 11)


def skin_bool(name, value):
    xbmc.executebuiltin("Skin.SetBool(%s)" % name if value else "Skin.Reset(%s)" % name)


def setup():
    """First-run walkthrough. Every answer can be changed later in Backlot settings."""
    home = xbmcgui.Window(10000)
    if home.getProperty("backlot.setup_running"):
        return
    home.setProperty("backlot.setup_running", "true")
    try:
        _setup()
    finally:
        home.clearProperty("backlot.setup_running")
        skin_bool("backlot.setup_done", True)


TOTAL_STEPS = 12


def _step(n):
    return "STEP %d OF %d" % (n, TOTAL_STEPS)


def _theme_options():
    st = _setting("lookandfeel.skincolors")
    opts = st.get("options", [])
    cur = st.get("value")
    return opts, cur


def theme_slug(value):
    return "theme_" + ("default" if value in ("SKINDEFAULT", "defaults") else
                       "".join(c for c in value.lower() if c.isalnum()))


LABELS = [("all", "Under every tile", "Every service is labeled."),
          ("", "Only under the one I'm on", "Clean look. The name appears under the tile you're on."),
          ("none", "Off", "No names. The logos speak for themselves.")]


def choose_labels(step="", circles=None):
    from setup_ui import choose
    cur_val = xbmc.getInfoLabel("Skin.String(backlot.labels)")
    cur = next((n for n, l in enumerate(LABELS) if l[0] == cur_val), 1)
    if circles is None:
        circles = xbmc.getCondVisibility("Skin.HasSetting(backlot.circles)")
    style = "circles" if circles else "banners"
    j = choose("Service names under the tiles",
               [(a, b, "labels_%s_%s" % (style, v or "focused")) for v, a, b in LABELS],
               step=step, preselect=cur, current=cur)
    if j >= 0:
        if LABELS[j][0]:
            xbmc.executebuiltin("Skin.SetString(backlot.labels,%s)" % LABELS[j][0])
        else:
            xbmc.executebuiltin("Skin.Reset(backlot.labels)")


def _setup():
    from setup_ui import choose
    if not DIALOG.yesno("Welcome to Backlot",
                        "A few quick questions to set up your home screen.[CR][CR]You can change any of this later in Settings > Backlot skin.",
                        yeslabel="Let's go", nolabel="Skip", defaultbutton=YES):
        backlot.publish()
        return
    circles_now = xbmc.getCondVisibility("Skin.HasSetting(backlot.circles)")

    # 1. tile style
    i = choose("How should your services look?", [
        ("Banners", "Wide full-color tiles with each service's logo, like classic Android TV.", "style_banners"),
        ("Circles", "Small round icons, like newer Google TV. Leaves more of the screen for artwork.", "style_circles")],
        step=_step(1), preselect=1 if circles_now else 0, current=1 if circles_now else 0)
    if i < 0:
        return
    skin_bool("backlot.circles", i == 1)
    choose_labels(step=_step(1), circles=i == 1)

    # 2. colors
    opts, cur = _theme_options()
    if opts:
        names = [("Midnight" if o["value"] in ("SKINDEFAULT", "defaults") else o["label"]) for o in opts]
        pre = next((n for n, o in enumerate(opts) if o["value"] == cur), 0)
        j = choose("Pick a color theme", [(nm, "Background, highlight and accent colors across the whole skin.",
                                           theme_slug(o["value"])) for nm, o in zip(names, opts)],
                   step=_step(2), preselect=pre, current=pre)
        if j >= 0:
            backlot._rpc("Settings.SetSettingValue", {"setting": "lookandfeel.skincolors", "value": opts[j]["value"]})

    # 3. services
    toggle_services(quiet=True)

    # 4. Hulu and Discovery+
    cfg = backlot.load()
    for sid, question in (("hulu", "In the US, Hulu is folding into the Disney+ app."),
                          ("discovery", "Max and Discovery+ are both Warner Bros. Discovery services.")):
        parent_id, key, default = backlot.MERGES[sid]
        svc = next((s for s in cfg["services"] if s["id"] == sid), {})
        cur = 0 if cfg.get(key, default) else (1 if svc.get("enabled") else 2)
        j = choose("Where should %s go?" % MERGE_TEXT[sid][0], [(a, b, "") for a, b in merge_choices(sid)],
                   question=question, step=_step(4), preselect=cur, current=cur)
        if j >= 0:
            set_merge(cfg, sid, j)

    # 5. episodes
    classic = xbmc.getCondVisibility("Skin.HasSetting(backlot.episodes_classic)")
    j = choose("How should episodes look?", [
        ("Seasons and episode list", "Seasons down the left, episodes on the right with a picture, runtime and description for each. Like Netflix today.", "episodes_modern"),
        ("One row of big thumbnails", "Large episode pictures in a single row, with a season switcher above.", "episodes_classic")],
        step=_step(5), preselect=1 if classic else 0, current=1 if classic else 0)
    if j >= 0:
        skin_bool("backlot.episodes_classic", j == 1)

    # 6. collections
    cur = 0 if cfg.get("group_sets", True) else 1
    j = choose("Movie collections", [
        ("One tile per collection", "All the movies in a collection (like every John Wick film) sit behind one tile you open.", "sets_grouped"),
        ("Every movie on its own", "Collections aren't grouped. Each movie gets its own tile.", "sets_single")],
        step=_step(6), preselect=cur, current=cur)
    if j >= 0:
        cfg["group_sets"] = j == 0

    # 7. leftovers
    cur = 0 if cfg.get("show_fallbacks", True) else 1
    j = choose("Movies and TV Shows tiles", [
        ("Add them", "Two extra tiles at the end of your services that open your whole movie and TV library.", "fallbacks_on"),
        ("Leave them off", "Only your services appear on the home screen.", "")],
        step=_step(7), preselect=cur, current=cur)
    if j >= 0:
        cfg["show_fallbacks"] = j == 0
    backlot.save(cfg)
    backlot.publish(cfg)

    # 8. info screens
    if not backlot.tmdbhelper_installed():
        j = choose("Cast details on info screens", [
            ("Install TMDb Helper", "Adds actor pages with photos, biographies and filmographies. Kodi will ask you to confirm twice.", ""),
            ("Not now", "Info screens show the cast from your library without biographies. You can install it later from Backlot settings.", "")],
            step=_step(8))
        if j == 0:
            install_tmdbhelper(ask=False)

    # 8b. PreShow Experience
    if not xbmc.getCondVisibility("System.HasAddon(%s)" % PSE):
        j = choose("PreShow Experience", [
            ("Install it", "Trailers, intros and ratings before your movie, like a night at the theater. Adds a PreShow button next to Play.", ""),
            ("Not now", "You can install it later from Backlot settings.", "")],
            step=_step(9))
        if j == 0:
            install_preshow(ask=False)

    # 9. similar titles
    allsim = xbmc.getCondVisibility("Skin.HasSetting(backlot.similar_all)")
    j = choose("'More like this' and filmographies", [
        ("Only what's in my library", "Suggestions come from your own movies and shows, so everything can be played.", ""),
        ("Everything", "Shows everything from TMDb and marks what you own. Needs TMDb Helper.", "")],
        step=_step(10), preselect=1 if allsim else 0, current=1 if allsim else 0)
    if j >= 0:
        skin_bool("backlot.similar_all", j == 1)

    # 10. weather
    hide = xbmc.getCondVisibility("Skin.HasSetting(backlot.hide_weather)")
    j = choose("Weather on the home screen", [
        ("Show it", "Temperature and conditions in the top-left corner. Next you'll pick a weather source and your location.", ""),
        ("Leave it off", "", "")],
        step=_step(11), preselect=1 if hide else 0, current=1 if hide else 0)
    if j == 0:
        skin_bool("backlot.hide_weather", False)
        setup_weather(ask=False)
    elif j == 1:
        skin_bool("backlot.hide_weather", True)
    choose_sounds(step=_step(12))
    DIALOG.ok("All set", "Backlot is ready. Change any of these answers in Settings > Backlot skin, or run setup again from there.")


def export_config():
    folder = DIALOG.browse(3, "Save setup to which folder?", "files")
    if not folder:
        return
    dest = folder.rstrip("/\\") + "/backlot-services.json"
    cfg = backlot.load()
    if xbmcvfs.File(dest, "w").write(json.dumps(cfg, indent=2, ensure_ascii=False)):
        notify("Saved backlot-services.json")
    else:
        DIALOG.ok(HEADING, "Couldn't write to that folder.")


def import_config():
    path = DIALOG.browse(1, "Choose backlot-services.json", "files", ".json")
    if not path:
        return
    f = xbmcvfs.File(path)
    try:
        cfg = json.loads(f.read())
        assert isinstance(cfg.get("services"), list)
    except (ValueError, AssertionError, AttributeError):
        DIALOG.ok(HEADING, "That file isn't a Backlot setup.")
        return
    finally:
        f.close()
    if DIALOG.yesno(HEADING, "Replace your current services with this setup?"):
        backlot.save(cfg)
        cfg = backlot.load()
        commit(cfg, "Setup imported")


def reset_all():
    if DIALOG.yesno(HEADING, "Remove custom services and put every preset back to default?"):
        if os.path.exists(backlot.CONFIG):
            shutil.move(backlot.CONFIG, backlot.CONFIG + ".bak")
        commit(backlot.load(), "Back to defaults")
