"""load.py: what the pod's load container fetches, where the token may go, and what it bundles."""
from __future__ import annotations

import gzip
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest
from pytest_bdd import parsers, scenarios, then, when

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import load  # noqa: E402

scenarios("load.feature")

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


@then("it loads both heads into one directory and bundles it")
def it_loads_both_heads_into_one_directory_and_bundles_it(tmp_path):
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


@then("a tarball entry outside objects is left out")
def a_tarball_entry_outside_objects_is_left_out(tmp_path):
    data = tarball({"objects/a.cbor": b"A", "../evil.cbor": b"X", "objects/sub/c.cbor": b"C"})
    assert load.objects(data, tmp_path) == 1
    assert [p.name for p in tmp_path.iterdir()] == ["a.cbor"]


@then("an empty publication stops the pod")
def an_empty_publication_stops_the_pod(tmp_path):
    answers = {load.PUBLICATION: tarball({}), load.GATHERED: b"{}"}
    with pytest.raises(load.LoadError, match="no objects"):
        load.load(tmp_path / "b", TOKEN, storage(answers, []), lambda *_: None)


URLS = {"none": None, "in the sources tenant": SRC + "x/e.cbor",
        "on another host": "https://elsewhere.example/sources/f/x/e.cbor",
        "in the publications tenant": "https://storage.sustenaut.eu/publications/f/x/e.cbor"}


@when(parsers.parse('the index names "{name}" at the URL {where}'), target_fixture="refused")
def index_names(tmp_path, name, where):
    with pytest.raises(load.LoadError) as refused:
        load.extracts({"objects": {name: URLS[where]}}, TOKEN, tmp_path, storage({}, []))
    return refused.value


@then(parsers.parse('the load refuses it as "{why}"'))
def load_refuses(refused, why):
    assert why in str(refused)


@then("the token goes only to storage")
def the_token_goes_only_to_storage():
    with pytest.raises(load.LoadError, match="goes nowhere else"):
        load.get("https://elsewhere.example/x", TOKEN, opener=lambda *a, **k: pytest.fail("fetched"))


@then("without a token it says where it looked")
def without_a_token_it_says_where_it_looked(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(load, "TOKEN", tmp_path / "missing")
    assert load.main() == 1
    assert "no storage token at" in capsys.readouterr().err
