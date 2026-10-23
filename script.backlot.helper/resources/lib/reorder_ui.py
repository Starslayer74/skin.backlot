# -*- coding: utf-8 -*-
"""Arrange the home-screen service tiles: OK picks a tile up, left/right moves
it, OK drops it, Back saves."""
import xbmcgui

import backlot

LEFT, RIGHT = 1, 2
SELECT = (7, 100)
BACK = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)
HINT_IDLE = "Pick the tile you want to move."
HINT_MOVING = "Move %s left or right, then press OK to drop it."


class ReorderDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.svcs = kwargs.get("services", [])
        self.moving = -1
        self.saved = False

    def _fill(self, idx):
        s = self.svcs[idx]
        li = self.lst.getListItem(idx)
        li.setLabel(s["name"])
        li.setArt({"logo": backlot.logo_for(s) or ""})
        li.setProperty("tint", backlot.tint(s.get("color") or backlot.FALLBACK_COLOR))
        li.setProperty("position", "%d" % (idx + 1))
        li.setProperty("moving", "true" if idx == self.moving else "")

    def onInit(self):
        self.lst = self.getControl(200)
        self.lst.reset()
        self.lst.addItems([xbmcgui.ListItem(s["name"]) for s in self.svcs])
        for n in range(len(self.svcs)):
            self._fill(n)
        self.setProperty("hint", HINT_IDLE)
        self.setFocusId(200)

    def _move(self, step):
        new = self.moving + step
        if not 0 <= new < len(self.svcs):
            self.lst.selectItem(self.moving)
            return
        old = self.moving
        self.svcs[old], self.svcs[new] = self.svcs[new], self.svcs[old]
        self.moving = new
        self._fill(old)
        self._fill(new)
        self.lst.selectItem(new)

    def onAction(self, action):
        a = action.getId()
        if a in BACK:
            if self.moving >= 0:
                self._drop()
                return
            self.saved = True
            self.close()
        elif self.moving >= 0 and a == LEFT:
            self._move(-1)
        elif self.moving >= 0 and a == RIGHT:
            self._move(1)

    def _drop(self):
        idx = self.moving
        self.moving = -1
        self._fill(idx)
        self.setProperty("hint", HINT_IDLE)

    def onClick(self, control_id):
        if control_id != 200:
            return
        pos = self.lst.getSelectedPosition()
        if self.moving >= 0:
            self._drop()
        else:
            self.moving = pos
            self._fill(pos)
            self.setProperty("hint", HINT_MOVING % self.svcs[pos]["name"])


def arrange(cfg):
    """Returns True if the new order was saved."""
    active_ids = [s["id"] for s in backlot.active_services(cfg)]
    shown = [s for s in cfg["services"] if s["id"] in active_ids]
    if len(shown) < 2:
        return False
    dlg = ReorderDialog("script-backlot-reorder.xml", backlot.ADDON_PATH, "Default", "1080i", services=list(shown))
    dlg.doModal()
    if not dlg.saved:
        del dlg
        return False
    new = dlg.svcs
    del dlg
    rest = [s for s in cfg["services"] if s["id"] not in active_ids]
    cfg["services"] = new + rest
    return True
