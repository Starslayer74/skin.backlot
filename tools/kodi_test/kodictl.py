#!/usr/bin/env python3
"""Drive the headless test Kodi over JSON-RPC (HTTP on localhost:8080).

    kodictl.py rpc <Method> '<json params>'
    kodictl.py builtin '<Kodi builtin>'
    kodictl.py key <action> [<action> ...]      (Input.ExecuteAction, e.g. down select back)
    kodictl.py wait-window <window name or id> [timeout]
    kodictl.py label '<InfoLabel>' ...
    kodictl.py bool '<condition>' ...
    kodictl.py shot <file.png> [settle_seconds]
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8080/jsonrpc"


def rpc(method, params=None, timeout=30):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        res = json.loads(r.read())
    if "error" in res:
        raise RuntimeError("%s: %s" % (method, res["error"]))
    return res.get("result")


def _builtin(cmd, wait):
    # Kodi 20 has no ExecuteBuiltin JSON-RPC method; the test add-on runs builtins for us
    return rpc("Addons.ExecuteAddon", {"addonid": "script.lineuptest", "params": {"cmd": cmd, "wait": "1" if wait else ""}, "wait": wait})


def labels(*names):
    return rpc("XBMC.GetInfoLabels", {"labels": list(names)})


def bools(*names):
    return rpc("XBMC.GetInfoBooleans", {"booleans": list(names)})


def action(*names, gap=0.35):
    for n in names:
        if n.startswith("text:"):
            rpc("Input.SendText", {"text": n[5:], "done": False})
        else:
            rpc("Input.ExecuteAction", {"action": n})
        time.sleep(gap)


def window():
    return labels("System.CurrentWindow", "System.CurrentControl", "Window.Property(xmlfile)")


def wait_for(cond, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if bools(cond).get(cond):
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.4)
    return False


def shot(path, settle=1.5):
    time.sleep(settle)
    disp = os.environ.get("DISPLAY", ":99")
    subprocess.run(["import", "-display", disp, "-window", "root", path], check=True)
    return path


def main(argv):
    cmd = argv[0]
    if cmd == "rpc":
        print(json.dumps(rpc(argv[1], json.loads(argv[2]) if len(argv) > 2 else {}), indent=1))
    elif cmd == "builtin":
        print(_builtin(argv[1], len(argv) > 2))
    elif cmd == "key":
        action(*argv[1:])
    elif cmd == "label":
        print(json.dumps(labels(*argv[1:]), indent=1))
    elif cmd == "bool":
        print(json.dumps(bools(*argv[1:]), indent=1))
    elif cmd == "wait":
        print(wait_for(argv[1], float(argv[2]) if len(argv) > 2 else 20))
    elif cmd == "shot":
        print(shot(argv[1], float(argv[2]) if len(argv) > 2 else 1.5))
    elif cmd == "win":
        print(window())


if __name__ == "__main__":
    main(sys.argv[1:])
