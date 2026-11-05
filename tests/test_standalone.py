"""Tests that need no Home Assistant: URL building and constants."""

import importlib.util
import pathlib
import sys

PKG = pathlib.Path(__file__).parent.parent / "custom_components" / "reolink_doorbell_talk"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"rt_{name}", PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_stream_source_quotes_credentials():
    const = _load("const")
    url = const.stream_source("10.0.0.5", "adm in", "p&ss=w#rd.", const.QUALITY_LIGHT)
    assert "channel0_sub.bcs" in url
    assert "p%26ss%3Dw%23rd." in url
    assert "adm%20in" in url
    assert "&password=p&ss" not in url


def test_stream_source_quality_main():
    const = _load("const")
    assert "channel0_main.bcs" in const.stream_source("h", "u", "p", const.QUALITY_HIGH)


def test_webrtc_source_uses_main_with_opus():
    const = _load("const")
    url = const.webrtc_source("h", "u", "p")
    assert url.startswith("ffmpeg:http://h/flv") and "audio=opus" in url


def test_frame_constants():
    talk = _load("talk")
    assert talk.FRAME_BYTES == 160 and talk.MAX_BUFFER_FRAMES == 10


def test_card_files_have_no_url_escapes():
    www = PKG / "www"
    for f in ("reolink-talk-card.js", "reolink-talk-lan-card.js", "talk-ws.js"):
        assert "%C" not in (www / f).read_text(encoding="utf-8"), f


def test_translations_have_same_keys():
    import json

    def keys(d, prefix=""):
        for k, v in d.items():
            if isinstance(v, dict):
                yield from keys(v, prefix + k + ".")
            else:
                yield prefix + k

    tr = PKG / "translations"
    base = set(keys(json.loads((tr / "en.json").read_text(encoding="utf-8"))))
    for name in ("es.json", "es-419.json"):
        got = set(keys(json.loads((tr / name).read_text(encoding="utf-8"))))
        assert got == base, (name, base ^ got)


if __name__ == "__main__":
    for _name in sorted(dir()):
        if _name.startswith("test_"):
            globals()[_name]()
            print("ok", _name)

