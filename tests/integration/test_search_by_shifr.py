# Integration tests: routers/search_router.py — отчёт по шифру при пустом поиске
# Описание: POST /api/search на временной tlib.db. Если поиск по всей форме пуст, а шифру
#           соответствует ровно один отчёт, возвращается он: остальные поля могли остаться от
#           прошлого поиска. Шифр с двумя отчётами (4825 и 4825-TLIB) выдачу не подменяет.
#           Приложение собирается здесь, без общего conftest: тот заточен под auth и upload.

from __future__ import annotations

import logging
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.search_router as search_router_module
from config import DATABASE_TABLE_NAME
from services.database.tlib_table_spec import build_create_table_sql, build_insert_sql, build_values

REPORTS = [
    {"Шифр": 4825, "ДопШифр": "", "Маршрут": "Эльбрус", "Тип": "горный", "Год": 2010},
    {"Шифр": 4825, "ДопШифр": "TLIB", "Маршрут": "Хибины", "Тип": "пеший", "Год": 2015},
    {"Шифр": 7000, "ДопШифр": "", "Маршрут": "Катунь", "Тип": "водный", "Год": 2020},
]


@pytest.fixture()
def search_client(tmp_path, monkeypatch) -> TestClient:
    """Поиск по временной базе из REPORTS; лимитер не нужен — запросы лёгкие и маленькие."""
    db_path = tmp_path / "tlib.db"
    conn = sqlite3.connect(db_path)
    conn.execute(build_create_table_sql(DATABASE_TABLE_NAME))
    for report in REPORTS:
        conn.execute(build_insert_sql(DATABASE_TABLE_NAME), build_values(report))
    conn.commit()
    conn.close()
    monkeypatch.setattr(search_router_module, "DATABASE_PATH", str(db_path))

    application = FastAPI()
    application.include_router(search_router_module.router)
    application.state.heavy_query_limiter = None
    application.state.kategoria_unified_list = []
    with TestClient(application) as client:
        yield client


def _search(client: TestClient, form: dict) -> dict:
    response = client.post("/api/search", data={**form, "limit": "50", "offset": "0"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    return body


def _codes(body: dict) -> list[str]:
    return [f"{row['Шифр']}-{row['ДопШифр']}" for row in body["data"]]


def test_route_shifr_ignores_other_fields(search_client: TestClient, caplog):
    caplog.set_level(logging.INFO)

    body = _search(search_client, {"Маршрут": "4825", "Тип": "водный", "ГодС": "2019", "ГодПо": "2021"})

    assert _codes(body) == ["4825-"]
    assert body["total"] == 1
    assert body["has_more"] is False
    assert any(getattr(r, "extra_data", {}).get("by_shifr") for r in caplog.records)


def test_shifr_field_ignores_other_fields(search_client: TestClient):
    body = _search(search_client, {"Шифр": "7000", "Тип": "горный", "Автор": "Иванов"})
    assert _codes(body) == ["7000-"]


def test_shifr_with_dopshifr_ignores_other_fields(search_client: TestClient):
    body = _search(search_client, {"Шифр": "4825", "ДопШифр": "TLIB", "Тип": "горный"})
    assert _codes(body) == ["4825-TLIB"]


def test_shifr_with_two_reports_stays_empty(search_client: TestClient):
    """Шифр 4825 без ДопШифра — два отчёта: какой показать, неизвестно."""
    body = _search(search_client, {"Шифр": "4825", "Тип": "водный"})
    assert body["data"] == []
    assert body["total"] == 0


def test_dopshifr_alone_is_not_shifr(search_client: TestClient):
    body = _search(search_client, {"ДопШифр": "TLIB", "Тип": "горный"})
    assert body["data"] == []


def test_unknown_shifr_stays_empty(search_client: TestClient):
    body = _search(search_client, {"Шифр": "99999", "Тип": "горный"})
    assert body["data"] == []


def test_matching_search_unchanged(search_client: TestClient, caplog):
    caplog.set_level(logging.INFO)

    body = _search(search_client, {"Шифр": "4825", "Тип": "пеший"})

    assert _codes(body) == ["4825-TLIB"]
    assert not any(getattr(r, "extra_data", {}).get("by_shifr") for r in caplog.records)
