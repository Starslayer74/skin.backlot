"""Helpers for scripted screenshot runs."""
import subprocess, sys, time
import kodictl as k
OUT = "/home/claude/shots/"
def b(cmd, wait=0.8):
    k._builtin(cmd, False); time.sleep(wait)
def key(*a): k.action(*a)
def shot(name, settle=2.0):
    k.shot(OUT + name + ".png", settle); print("shot", name, k.window()["System.CurrentControl"])
def svc(n, circles=False, settle=6):
    b("SetFocus(%d,%d,absolute)" % (301 if circles else 300, n), 0.5)
def reload():
    b("ReloadSkin()", 5)
def setbool(name, on):
    b(("Skin.SetBool(%s)" if on else "Skin.Reset(%s)") % name, 0.3)
def setstr(name, val):
    b("Skin.SetString(%s,%s)" % (name, val) if val else "Skin.Reset(%s)" % name, 0.3)
def theme(value):
    k.rpc("Settings.SetSettingValue", {"setting": "lookandfeel.skincolors", "value": value}); time.sleep(4)
def home():
    b("ActivateWindow(Home)", 1.5)
if __name__ == "__main__":
    exec(sys.argv[1])
