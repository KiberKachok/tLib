# Тесты прогресса подготовки кеша для читателя (config/cache.py CACHE_DETAIL_*,
# services/cache/cache_pipeline.extract_files)
# Описание: detail из _prepare.json читатель видит под этапом — во вьюере PDF, в превью картинок
#           и треков, у ссылок «Прочее». Шаблоны форматируются в колбэках распаковки и рендера:
#           лишнее или пропущенное имя подстановки бросило бы KeyError посреди подготовки и
#           оборвало бы её, поэтому набор имён у каждого шаблона закреплён здесь — тот же, что
#           в местах вызова.

import asyncio
import string
import zipfile

import pytest

from config import (
    CACHE_DETAIL_EXTRACTING,
    CACHE_DETAIL_PDF,
    CACHE_DETAIL_PDF_PAGES,
    CACHE_DETAIL_PAGES,
    CACHE_DETAIL_IMAGES,
)
from services.cache.cache_pipeline import extract_files


# Имена подстановок, с которыми шаблон форматируется в местах вызова
_CALL_SITE_FIELDS = [
    (CACHE_DETAIL_EXTRACTING, {"done", "total"}),               # cache_pipeline.extract_files
    (CACHE_DETAIL_PDF, {"idx", "total"}),                       # cache_pipeline.convert_pdfs
    (CACHE_DETAIL_PDF_PAGES, {"idx", "total", "done", "pages"}),  # convert_pdfs._page_progress
    (CACHE_DETAIL_PAGES, {"done", "total"}),                    # convert_standalone_pdf, resume_pdf_conversion
    (CACHE_DETAIL_IMAGES, {"idx", "total"}),                    # cache_pipeline.convert_images
]


@pytest.mark.parametrize("template, fields", _CALL_SITE_FIELDS)
def test_detail_template_fields_match_call_sites(template, fields):
    names = {name for _, name, _, _ in string.Formatter().parse(template) if name}
    assert names == fields
    assert template.format(**{field: 1 for field in fields})


def test_extract_files_reports_progress_in_russian(tmp_path):
    zip_path = tmp_path / "00001-TST.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("route.gpx", "<gpx/>")
        zf.writestr("notes.txt", "text")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    statuses: list[dict] = []

    def record_status(archive_name, **status):
        statuses.append(status)

    # Собственный loop: asyncio.run() обнулил бы текущий loop, на который полагаются другие тесты
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(extract_files("00001-TST", zip_path, cache_dir, record_status))
    finally:
        loop.close()

    assert statuses[-1]["detail"] == CACHE_DETAIL_EXTRACTING.format(done=2, total=2)
    assert (cache_dir / "route.gpx").is_file()
