# -*- coding: utf-8 -*-
"""Backlot setup dialog: a question, choices on the left and a large preview
of the focused choice on the right."""
import os

import xbmcgui

import backlot

PREVIEWS = os.path.join(backlot.ADDON_PATH, "resources", "media", "setup")
ACTION_BACK = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)


def preview(name):
    """Path of a bundled preview image, or '' if there isn't one."""
    if not name:
        return ""
    path = os.path.join(PREVIEWS, name + ".jpg")
    return path if os.path.exists(path) else ""


class ChoiceDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.heading = kwargs.get("heading", "")
        self.question = kwargs.get("question", "")
        self.step = kwargs.get("step", "")
        self.choices = kwargs.get("choices", [])
        self.preselect = kwargs.get("preselect", 0)
        self.current = kwargs.get("current", -1)
        self.result = -1

    def onInit(self):
        self.setProperty("heading", self.heading)
        self.setProperty("question", self.question)
        self.setProperty("step", self.step)
        lst = self.getControl(100)
        lst.reset()
        items = []
        for n, (label, desc, img) in enumerate(self.choices):
            li = xbmcgui.ListItem(label, desc)
            pic = preview(img) if img and not os.path.isabs(img) else img
            if pic:
                li.setArt({"thumb": pic})
            if n == self.current:
                li.setProperty("current", "true")
            items.append(li)
        lst.addItems(items)
        lst.selectItem(max(0, min(self.preselect, len(items) - 1)))
        self.setFocusId(100)

    def onClick(self, control_id):
        if control_id == 100:
            self.result = self.getControl(100).getSelectedPosition()
            self.close()

    def onAction(self, action):
        if action.getId() in ACTION_BACK:
            self.result = -1
            self.close()


def choose(heading, choices, question="", step="", preselect=0, current=-1):
    """choices: [(label, description, preview name or path)]. Returns the
    chosen index, or -1 if the user backed out."""
    dlg = ChoiceDialog("script-backlot-choice.xml", backlot.ADDON_PATH, "Default", "1080i",
                       heading=heading, question=question, step=step, choices=choices,
                       preselect=preselect, current=current)
    dlg.doModal()
    result = dlg.result
    del dlg
    return result
