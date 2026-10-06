# PyInstaller spec for the heure bleue desktop app.
#
#   pyinstaller heurebleue.spec
#
# Output: dist/HeureBleue.app (macOS), dist/HeureBleue/ (Windows, Linux).
# The bundle carries web/, the shipped painting index and the icon; everything
# the wall writes goes to the user's application folder (see heurebleue/config.py).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(SPECPATH)))
from heurebleue import __version__  # noqa: E402

NAME = "HeureBleue"
(Path(SPECPATH) / "assets" / "VERSION").write_text(__version__ + "\n", encoding="utf-8")  # read back by the updater
ICON = {"darwin": "assets/icon.icns", "win32": "assets/icon.ico"}.get(sys.platform, "assets/icon.png")

hidden = ["heurebleue.nowplaying.macos", "heurebleue.nowplaying.windows", "heurebleue.nowplaying.linux", "certifi", "cryptography"]
if sys.platform == "win32":
    hidden += ["winsdk", "winsdk.windows.media.control", "winsdk.windows.storage.streams"]

datas = [("web", "web"), ("data/paintings.json", "data"), ("assets/icon.png", "assets"), ("assets/VERSION", ".")]
if sys.platform == "darwin" and (Path(SPECPATH) / "vendor" / "media-control" / "bin").exists():
    datas.append(("vendor/media-control", "vendor/media-control"))  # tools/vendor_media_control.py puts it there

a = Analysis(
    ["tools/app_entry.py"],
    pathex=[SPECPATH],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "unittest", "pydoc", "doctest", "test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NAME,
    console=False,     # no terminal window; `HeureBleue doctor` still prints when run from a shell
    icon=ICON,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=ICON,
        bundle_identifier="dev.heurebleue.wall",
        version=__version__,
        info_plist={
            "CFBundleDisplayName": "heure bleue",
            "CFBundleShortVersionString": __version__,
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.music",
            # Without this key macOS refuses the AppleScript calls that read Spotify and Music.
            "NSAppleEventsUsageDescription": "heure bleue reads the song playing in Spotify or Music to pick a painting.",
            "NSLocationWhenInUseUsageDescription": "Only if you choose \u201cuse my position\u201d for the weather.",
        },
    )
