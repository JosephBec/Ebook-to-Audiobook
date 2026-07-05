from pathlib import Path

from src.plex_delivery import sanitize_title, plex_output_name, deliver


def test_sanitize_title():
    assert sanitize_title('A/B: "C"?') == "A B C"


def test_output_name_without_range():
    assert plex_output_name("My Book") == "My Book.m4b"


def test_output_name_with_range():
    assert plex_output_name("My Book", (3, 7)) == "My Book - Chapters 3 - 7.m4b"


def test_deliver_moves_and_renames(tmp_path):
    src = tmp_path / "a.m4b"
    src.write_bytes(b"data")
    dest_dir = tmp_path / "lib"
    result = deliver(src, str(dest_dir), "The Count of Monte Cristo", None)
    assert result == dest_dir / "The Count of Monte Cristo.m4b"
    assert result.exists() and not src.exists()
