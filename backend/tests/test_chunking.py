from pathlib import Path

from app.services.chunking import chunk_file, doc_type_for


def test_doc_type_for_supported_and_unsupported_extensions(tmp_path):
    assert doc_type_for(Path("a.py")) == "python"
    assert doc_type_for(Path("a.md")) == "markdown"
    assert doc_type_for(Path("a.txt")) == "text"
    assert doc_type_for(Path("a.json")) == "json"
    assert doc_type_for(Path("a.yaml")) == "yaml"
    assert doc_type_for(Path("a.exe")) is None


def test_markdown_chunks_split_on_headers(tmp_path):
    content = "# Title\nintro line\n\n## Section A\nline a1\nline a2\n\n## Section B\nline b1\n"
    path = tmp_path / "doc.md"
    path.write_text(content)

    chunks = chunk_file(path)

    assert len(chunks) == 3
    assert chunks[0].content.startswith("# Title")
    assert chunks[1].content.startswith("## Section A")
    assert chunks[2].content.startswith("## Section B")
    for c in chunks:
        assert c.doc_type == "markdown"
        assert c.start_line >= 1
        assert c.end_line >= c.start_line


def test_python_chunks_split_on_top_level_def_and_class(tmp_path):
    content = (
        "import os\n\n"
        "def foo():\n    return 1\n\n"
        "class Bar:\n    def method(self):\n        pass\n"
    )
    path = tmp_path / "mod.py"
    path.write_text(content)

    chunks = chunk_file(path)

    assert len(chunks) == 3  # leading imports, foo, Bar
    assert "import os" in chunks[0].content
    assert chunks[1].content.startswith("def foo")
    assert chunks[2].content.startswith("class Bar")


def test_python_falls_back_to_window_on_syntax_error(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def foo(:\n    pass\n")

    chunks = chunk_file(path)

    assert len(chunks) == 1
    assert chunks[0].doc_type == "python"


def test_chunk_metadata_covers_every_line_exactly_once_for_windowed_files(tmp_path):
    lines = [f"line {i}" for i in range(1, 101)]
    path = tmp_path / "notes.txt"
    path.write_text("\n".join(lines))

    chunks = chunk_file(path)

    covered = []
    for c in chunks:
        covered.extend(range(c.start_line, c.end_line + 1))
    assert covered == list(range(1, 101))


def test_large_markdown_section_is_capped(tmp_path):
    body = "\n".join(f"detail line {i}" for i in range(100))
    content = f"# Title\n{body}\n"
    path = tmp_path / "big.md"
    path.write_text(content)

    chunks = chunk_file(path)

    assert len(chunks) > 1
    for c in chunks:
        assert c.end_line - c.start_line + 1 <= 60
