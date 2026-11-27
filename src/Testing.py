"""Pytest fixtures and hooks shared by the commons and game test suites."""

import gc

import pytest


@pytest.fixture
def qapp():
    from automaton_gui.App import BuildApp

    return BuildApp()


@pytest.fixture(autouse=True)
def destroyLeftoverWindows():
    """Every window a test leaves behind is destroyed, not just hidden: hundreds of live leftovers
    make each later restyle (a theme switch) crawl through all of them."""
    yield
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        widget.hide()
        widget.deleteLater()
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def pytest_sessionfinish(session):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        widget.deleteLater()
    app.processEvents()
    gc.collect()
