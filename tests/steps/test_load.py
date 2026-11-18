"""load.py: what the pod's load container fetches, where the token may go, and what it bundles."""
from __future__ import annotations

import gzip
import io
import json
import shutil
import sys
import tarfile
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import load  # noqa: E402

scenarios("load.feature")

TOKEN = "pod-token"
SRC = "https://storage.sustenaut.eu/sources/f/"
URLS = {"none": None, "in the sources tenant": SRC + "x/e.cbor",
        "on another host": "https://elsewhere.example/sources/f/x/e.cbor",
        "in the publications tenant": "https://storage.sustenaut.eu/publications/f/x/e.cbor"}


def tarball(files: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue())


@pytest.fixture
def storage():
    """What storage holds, by URL, and the URLs it was asked for, in turn."""
    return {"answers": {}, "asked": []}


def fetch_from(storage):
    def fetch(url: str, token: str) -> bytes:
        assert token == TOKEN
        storage["asked"].append(url)
        return storage["answers"][url]
    return fetch


@given("publication 0's tarball holding:")
def publication(storage, datatable):
    storage["answers"][load.PUBLICATION] = tarball({name: data.encode() for name, data in datatable[1:]})


@given(parsers.parse('the sources index naming "{name}" in the sources tenant, holding "{data}"'))
def sources_index(storage, name, data):
    url = SRC + "1" * 64 + "/" + name
    storage["answers"][load.GATHERED] = json.dumps({"objects": {name: url}}).encode()
    storage["answers"][url] = data.encode()


@given("an empty sources index")
def empty_sources_index(storage):
    storage["answers"][load.GATHERED] = b"{}"


def bundle(objects: Path, out: Path) -> None:
    """In pub bundle's place: the bundles are the objects it was given."""
    shutil.copytree(objects, out)


@when(parsers.parse('the load bundles into "{out}"'))
def bundles_into(ctx, storage, out):
    def run():
        published, cited = load.load(ctx.directory / out, TOKEN, fetch_from(storage), bundle)
        return {"published": published, "cited": cited}
    ctx.attempt(run)


@when(parsers.parse('the load takes the tarball\'s objects into "{into}"'))
def takes_objects(ctx, storage, into):
    (ctx.directory / into).mkdir()
    ctx.attempt(lambda: load.objects(storage["answers"][load.PUBLICATION], ctx.directory / into))


@when(parsers.parse('the load fetches "{url}"'))
def fetches(ctx, url):
    ctx.attempt(lambda: load.get(url, TOKEN, opener=lambda *a, **k: pytest.fail("fetched")))


@when(parsers.parse('the index names "{name}" at the URL {where}'))
def index_names(ctx, storage, name, where):
    ctx.attempt(lambda: load.extracts({"objects": {name: URLS[where]}}, TOKEN, ctx.directory, fetch_from(storage)))


@then(parsers.parse('storage was asked first for "{first}", then for "{second}"'))
def asked_in_turn(storage, first, second):
    assert storage["asked"][:2] == [f"{load.STORAGE}/{first}", f"{load.STORAGE}/{second}"], storage["asked"]


@then(parsers.parse('the refusal is a "{kind}"'))
def refusal_is(ctx, kind):
    """The refusal is of the class named, or of one made from it, by its name or
    its module's dotted name."""
    assert ctx.refused is not None, f"it was not refused: the result is {ctx.result!r}"
    kinds = type(ctx.refused.error).__mro__
    assert any(kind in (k.__name__, f"{k.__module__}.{k.__qualname__}") for k in kinds), repr(ctx.refused.error)
