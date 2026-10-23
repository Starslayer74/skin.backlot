import sys
import xbmc
args = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
cmd = args.get("cmd", "")
if cmd:
    xbmc.executebuiltin(cmd, args.get("wait") == "1")
