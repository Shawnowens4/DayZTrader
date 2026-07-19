"""
tests/verify_services_load.py — Import smoke test for all services.

Verifies that every existing and new Phase 1 stub service module
can be imported without error. Does not test any behavior.
Safe to run with bot stopped or running.

Usage:
    python tests/verify_services_load.py
    pytest tests/verify_services_load.py -v
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_existing_services_import():
    from bot.services import economy
    from bot.services import shop
    from bot.services import market
    from bot.services import delivery
    from bot.services import delivery_queue
    from bot.services import raffle
    from bot.services import security
    assert economy
    assert shop
    assert market
    assert delivery
    assert delivery_queue
    assert raffle
    assert security


def test_new_stub_services_import():
    from bot.services import idb
    from bot.services import xml_parser
    from bot.services import nitrado_monitor
    assert idb
    assert xml_parser
    assert nitrado_monitor


def test_idb_service_instantiates():
    from bot.services.idb import IDBService
    svc = IDBService()
    assert svc.DEFAULT_THUMB == "assets/default_item.webp"


def test_xml_parser_raises_not_implemented():
    from bot.services.xml_parser import XMLParserService
    import pytest
    svc = XMLParserService()
    with pytest.raises(NotImplementedError):
        svc.parse_types("dummy.xml")


def test_monitor_enums_accessible():
    from bot.services.nitrado_monitor import MonitorState, MonitorEvent, MonitorConfig
    assert MonitorState.IDLE == "IDLE"
    assert MonitorState.HEALTHY == "HEALTHY"
    assert MonitorEvent.CHECK_OK == "CHECK_OK"
    cfg = MonitorConfig()
    assert cfg.enabled is False
    assert cfg.restart_enabled is False


if __name__ == "__main__":
    test_existing_services_import()
    test_new_stub_services_import()
    test_idb_service_instantiates()
    test_xml_parser_raises_not_implemented()
    test_monitor_enums_accessible()
    print("All service import checks passed.")
