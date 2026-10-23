#!/usr/bin/env python3
"""Build a Kodi repository folder for Backlot.

Usage:
    python3 tools/build_repo.py <out_dir> <base_url> <addon_dir> [<addon_dir> ...]

Writes <out_dir>/repo/ containing addons.xml, addons.xml.md5 and
zips/<id>/<id>-<version>.zip plus each add-on's icon/fanart, the layout
Kodi's <datadir zip="true"> expects. repository.backlot is always built and
listed first; its <info>/<checksum>/<datadir> URLs are rewritten to base_url.
"""
import hashlib
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode"}
SKIP_EXT = {".pyc", ".pyo"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


def read_addon(addon_dir):
    path = os.path.join(addon_dir, "addon.xml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    root = ET.fromstring(text.encode("utf-8"))
    return root.get("id"), root.get("version"), text, root


def set_repo_urls(addon_dir, base_url):
    path = os.path.join(addon_dir, "addon.xml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    base = base_url.rstrip("/") + "/"
    text = re.sub(r"(<info[^>]*>)[^<]*(</info>)", r"\g<1>%saddons.xml\2" % base, text)
    text = re.sub(r"(<checksum[^>]*>)[^<]*(</checksum>)", r"\g<1>%saddons.xml.md5\2" % base, text)
    text = re.sub(r"(<datadir[^>]*>)[^<]*(</datadir>)", r"\g<1>%szips/\2" % base, text)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def zip_addon(addon_dir, addon_id, dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for cur, dirs, files in os.walk(addon_dir):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                if name in SKIP_NAMES or os.path.splitext(name)[1] in SKIP_EXT:
                    continue
                full = os.path.join(cur, name)
                rel = os.path.relpath(full, addon_dir).replace(os.sep, "/")
                z.write(full, addon_id + "/" + rel)


def addon_entry(text):
    body = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", text).strip()
    return body


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    out_dir, base_url, dirs = argv[0], argv[1], argv[2:]
    os.chdir(ROOT)
    repo_id = "repository.backlot"
    dirs = [d.rstrip("/\\") for d in dirs if os.path.basename(d.rstrip("/\\")) != repo_id]
    set_repo_urls(repo_id, base_url)
    dirs.insert(0, repo_id)

    repo = os.path.join(out_dir, "repo")
    if os.path.isdir(repo):
        shutil.rmtree(repo)
    os.makedirs(os.path.join(repo, "zips"))

    entries = []
    for d in dirs:
        addon_id, version, text, root = read_addon(d)
        zdir = os.path.join(repo, "zips", addon_id)
        os.makedirs(zdir, exist_ok=True)
        zpath = os.path.join(zdir, "%s-%s.zip" % (addon_id, version))
        zip_addon(d, addon_id, zpath)
        for el in root.iter():
            if el.tag in ("icon", "fanart", "banner", "clearlogo") and el.text:
                src = os.path.join(d, el.text.strip())
                if os.path.isfile(src):
                    dst = os.path.join(zdir, el.text.strip())
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
        entries.append(addon_entry(text))
        print("built %s %s" % (addon_id, version))

    xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
    xml += "\n".join(entries) + "\n</addons>\n"
    data = xml.encode("utf-8")
    with open(os.path.join(repo, "addons.xml"), "wb") as f:
        f.write(data)
    with open(os.path.join(repo, "addons.xml.md5"), "w") as f:
        f.write(hashlib.md5(data).hexdigest())
    print("wrote %s" % repo)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
