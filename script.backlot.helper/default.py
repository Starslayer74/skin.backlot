# -*- coding: utf-8 -*-
"""RunScript(script.backlot.helper[,action])
actions: manage (default), publish, report, add
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

import backlot  # noqa: E402
import manage  # noqa: E402

action = sys.argv[1] if len(sys.argv) > 1 else "manage"
if action == "publish":
    backlot.publish()
elif action == "startup":
    # The skin asks for this when it finds no tiles. The helper's service
    # publishes at startup too, so only step in if the service isn't running.
    import xbmc  # noqa: E402
    mon = xbmc.Monitor()
    for _ in range(10):
        if backlot.HOME.getProperty("backlot.service") or backlot.HOME.getProperty("backlot.ready"):
            break
        if mon.waitForAbort(0.5):
            break
    if not backlot.HOME.getProperty("backlot.service") and not backlot.HOME.getProperty("backlot.ready"):
        backlot.publish()
elif action == "report":
    manage.unmatched_report()
elif action == "open" and len(sys.argv) > 3:
    # from an info screen TMDb Helper opened: play a library movie, or open a library show
    import xbmc  # noqa: E402
    dbtype, dbid = sys.argv[2], sys.argv[3]
    if dbtype == "movie" and dbid.isdigit():
        backlot._rpc("Player.Open", {"item": {"movieid": int(dbid)}})
    elif dbtype == "tvshow" and dbid.isdigit():
        xbmc.executebuiltin("ActivateWindow(Videos,videodb://tvshows/titles/%s/,return)" % dbid)
elif action == "info" and len(sys.argv) > 3:
    # open the info screen for another library title (from "More like this")
    from resources.lib import info  # noqa: E402
    info.show(sys.argv[2], sys.argv[3])
elif action == "setup":
    manage.setup()
elif action == "launch" and len(sys.argv) > 2:
    backlot.launch(sys.argv[2])
elif action == "preshow":
    manage.install_preshow()
elif action == "sounds":
    manage.choose_sounds()
elif action == "reorder":
    manage.reorder()
elif action == "labels":
    manage.choose_labels()
elif action == "theme":
    manage.choose_theme()
elif action == "weather":
    manage.setup_weather()
elif action == "tmdbhelper":
    manage.install_tmdbhelper()
elif action == "add":
    manage.add_custom()
else:
    manage.main()
