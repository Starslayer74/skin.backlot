#!/bin/bash
# Fresh or refreshed headless Kodi 20 for Backlot testing.
#   sync.sh start   - (re)copy add-ons into the test profile and start Kodi on Xvfb :99
#   sync.sh stop
# Test profile: $KHOME (default /root/.kodi). Media library: /srv/media (see make_library.py)
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KHOME="${KHOME:-/root/.kodi}"
export DISPLAY=:99
stop() { pkill -f kodi.bin 2>/dev/null || true; for i in $(seq 30); do pgrep -f kodi.bin >/dev/null || break; sleep 0.5; done; pkill -9 -f kodi.bin 2>/dev/null || true; }
if [ "$1" = stop ]; then stop; exit 0; fi
stop
pgrep -f "Xvfb :99" >/dev/null || (Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &) ; sleep 1
mkdir -p "$KHOME/addons" "$KHOME/userdata"
for a in skin.backlot script.backlot.helper resource.uisounds.backlot; do rm -rf "$KHOME/addons/$a"; cp -r "$ROOT/$a" "$KHOME/addons/"; done
# the distro Kodi here is 20 (xbmc.gui 5.16.0); the skin targets 21. Relax the requirement in the test copy only.
sed -i 's/addon="xbmc.gui" version="5.17.0"/addon="xbmc.gui" version="5.16.0"/' "$KHOME/addons/skin.backlot/addon.xml"
rm -rf "$KHOME/addons/script.lineuptest"; cp -r "$ROOT/tools/kodi_test/script.lineuptest" "$KHOME/addons/"
cp "$ROOT/tools/kodi_test/advancedsettings.xml" "$KHOME/userdata/"
[ -f "$KHOME/userdata/guisettings.xml" ] || cp "$ROOT/tools/kodi_test/guisettings.xml" "$KHOME/userdata/"
[ -f "$KHOME/userdata/sources.xml" ] || cp "$ROOT/tools/kodi_test/sources.xml" "$KHOME/userdata/"
(LIBGL_ALWAYS_SOFTWARE=1 nohup kodi --standalone --windowing=x11 >/tmp/kodi.out 2>&1 &)
for i in $(seq 120); do curl -s -m 2 -o /dev/null -d '{"jsonrpc":"2.0","id":1,"method":"JSONRPC.Ping"}' -H 'Content-Type: application/json' http://127.0.0.1:8080/jsonrpc && { echo "kodi up"; exit 0; }; sleep 1; done
echo "kodi did not answer"; tail -20 "$KHOME/temp/kodi.log"; exit 1
