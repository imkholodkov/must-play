import io
import zipfile

import pytest

from app.etl import download_data


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, content_type: str):
        super().__init__(body)
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def zip_bytes(name: str, content: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, content)
    return buf.getvalue()


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(download_data, "DATA_DIR", tmp_path)
    return tmp_path


def test_fetch_extracts_zip(data_dir, monkeypatch):
    body = zip_bytes("steam_games_reviews.csv", "app_id,name,reviews\n1,Game,ok\n")
    monkeypatch.setattr(download_data.urllib.request, "urlopen", lambda url: FakeResponse(body, "application/zip"))

    path = download_data.fetch("reviews")

    assert path == data_dir / "steam_games_reviews.csv"
    assert path.read_text().startswith("app_id,name,reviews")
    assert not (data_dir / "steam_games_reviews.csv.zip").exists()


def test_fetch_skips_existing_file(data_dir, monkeypatch):
    existing = data_dir / "steam_games.csv"
    existing.write_text("old")
    monkeypatch.setattr(download_data.urllib.request, "urlopen", lambda url: pytest.fail("не должно качать"))

    assert download_data.fetch("games") == existing
    assert existing.read_text() == "old"


def test_download_rejects_html_page(data_dir, monkeypatch):
    monkeypatch.setattr(
        download_data.urllib.request, "urlopen", lambda url: FakeResponse(b"<html>", "text/html; charset=utf-8")
    )

    with pytest.raises(RuntimeError, match="HTML"):
        download_data.download("some-id", data_dir / "file.csv")
