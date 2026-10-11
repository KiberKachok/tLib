# Unit tests: шапки файлов — только описание модуля, без версий, дат и журнала изменений
# Описание: История изменений хранится в git. Тест проходит по файлам из git ls-files и падает,
#           если в ведущем блоке комментариев есть строка «Version N.N» или запись журнала
#           («N.N: …», «vN.N: …», «N.N - …», «Изменения vN.N: …»). Выполняется в pre-flight
#           push_test.ps1 и push_prod.ps1, поэтому старый формат не уходит ни на стенд, ни на прод.

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Расширения файлов, у которых есть шапка-комментарий
HEADER_EXTENSIONS = {".py", ".js", ".css", ".html", ".sh", ".ini", ".txt"}

VERSION_RE = re.compile(r"\bVersion\s+\d+\.\d+")
CHANGELOG_ENTRY_RE = re.compile(r"^\s*(?:Изменения\s+)?v?\d+\.\d+(?:\.\d+)?\s*(?::|-\s)")


def _tracked_files() -> list[Path]:
    """Отслеживаемые git файлы с шапкой; без git тест пропускается."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git недоступен — список файлов получить нельзя")
    return [
        ROOT / name
        for name in out.splitlines()
        if Path(name).suffix in HEADER_EXTENSIONS and "node_modules" not in name
    ]


def _header_lines(lines: list[str], suffix: str) -> list[tuple[int, str]]:
    """Строки ведущего блока комментариев: (номер строки, текст без маркера комментария)."""
    if suffix in (".css", ".html"):
        opener, closer = ("/*", "*/") if suffix == ".css" else ("<!--", "-->")
        if not lines or not lines[0].lstrip().startswith(opener):
            return []
        result = []
        for index, line in enumerate(lines):
            result.append((index + 1, line.replace(opener, "", 1) if index == 0 else line))
            if closer in line:
                break
        return result

    marker = "//" if suffix == ".js" else "#"
    result = []
    for index, line in enumerate(lines):
        if index == 0 and line.startswith("#!"):
            continue
        if not line.startswith(marker):
            break
        result.append((index + 1, line[len(marker):]))
    return result


def test_headers_have_no_versions_or_changelog():
    problems = []
    for path in _tracked_files():
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        for number, text in _header_lines(lines, path.suffix):
            if VERSION_RE.search(text) or CHANGELOG_ENTRY_RE.match(text):
                problems.append(f"{path.relative_to(ROOT).as_posix()}:{number}: {text.strip()[:80]}")
    assert not problems, (
        "В шапке файла версия или журнал изменений. Шапка — только описание модуля, "
        "история — в git (сообщение коммита):\n" + "\n".join(problems)
    )
