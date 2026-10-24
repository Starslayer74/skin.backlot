# -*- coding: utf-8 -*-
"""Publishes the service tiles when Kodi starts and after library scans."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

import xbmc  # noqa: E402

import backlot  # noqa: E402


class Monitor(xbmc.Monitor):
    def onNotification(self, sender, method, data):
        if method in ("VideoLibrary.OnScanFinished", "VideoLibrary.OnCleanFinished"):
            backlot.publish()
            if method == "VideoLibrary.OnScanFinished":
                backlot.collection_art()


if __name__ == "__main__":
    monitor = Monitor()
    backlot.HOME.setProperty("backlot.service", "running")
    try:
        backlot.first_run()
        backlot.publish()
        backlot.tune_tmdbhelper()
        # let Kodi finish starting up before touching the disks
        if not monitor.waitForAbort(30):
            backlot.collection_art()
    except Exception as e:  # never take Kodi's service loop down
        backlot.log("publish failed: %s" % e, xbmc.LOGERROR)
    monitor.waitForAbort()
    backlot.HOME.clearProperty("backlot.service")
