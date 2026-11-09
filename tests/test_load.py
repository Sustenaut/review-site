"""load.py: what the pod's load container fetches, where the token may go, and what it bundles."""
from __future__ import annotations

import gzip
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import load  # noqa: E402

TOKEN = "pod-token"
SRC = "https://storage.sustenaut.eu/sources/f/"


def tarball(files: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue())


def storage(answers: dict[str, bytes], asked: list[str]):
    def fetch(url: str, token: str) -> bytes:
        assert token == TOKEN
        asked.append(url)
        return answers[url]
    return fetch


def test_it_loads_both_heads_into_one_directory_and_bundles_it(tmp_path):
    asked: list[str] = []
    answers = {
        load.PUBLICATION: tarball({"objects/a.cbor": b"A", "objects/b.cbor": b"B", "README": b"x"}),
        load.GATHERED: json.dumps({"objects": {"e.cbor": SRC + "1" * 64 + "/e.cbor"}}).encode(),
        SRC + "1" * 64 + "/e.cbor": b"E",
    }
    seen = {}

    def bundle(objects: Path, out: Path) -> None:
        seen.update({p.name: p.read_bytes() for p in objects.iterdir()})
        seen["out"] = out

    out = tmp_path / "bundles"
    assert load.load(out, TOKEN, storage(answers, asked), bundle) == (2, 1)
    assert seen == {"a.cbor": b"A", "b.cbor": b"B", "e.cbor": b"E", "out": out}
    assert asked[:2] == [load.PUBLICATION, load.GATHERED]


def test_a_tarball_entry_outside_objects_is_left_out(tmp_path):
    data = tarball({"objects/a.cbor": b"A", "../evil.cbor": b"X", "objects/sub/c.cbor": b"C"})
    assert load.objects(data, tmp_path) == 1
    assert [p.name for p in tmp_path.iterdir()] == ["a.cbor"]


def test_an_empty_publication_stops_the_pod(tmp_path):
    answers = {load.PUBLICATION: tarball({}), load.GATHERED: b"{}"}
    with pytest.raises(load.LoadError, match="no objects"):
        load.load(tmp_path / "b", TOKEN, storage(answers, []), lambda *_: None)


@pytest.mark.parametrize("name, url, why", [
    ("../e.cbor", SRC + "x/e.cbor", "not a file name"),
    ("e.cbor", None, "not uploaded"),
    ("e.cbor", "https://elsewhere.example/sources/f/x/e.cbor", "outside the sources tenant"),
    ("e.cbor", "https://storage.sustenaut.eu/publications/f/x/e.cbor", "outside the sources tenant"),
])
def test_the_index_may_name_only_files_in_the_sources_tenant(tmp_path, name, url, why):
    with pytest.raises(load.LoadError, match=why):
        load.extracts({"objects": {name: url}}, TOKEN, tmp_path, storage({}, []))


def test_the_token_goes_only_to_storage():
    with pytest.raises(load.LoadError, match="goes nowhere else"):
        load.get("https://elsewhere.example/x", TOKEN, opener=lambda *a, **k: pytest.fail("fetched"))


def test_without_a_token_it_says_where_it_looked(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(load, "TOKEN", tmp_path / "missing")
    assert load.main() == 1
    assert "no storage token at" in capsys.readouterr().err
