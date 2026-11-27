from __future__ import annotations

import weakref
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QUrl, Qt
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeyEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QMessageBox, QWidget

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.Anchor import CenterWindow, ForceForeground
from automaton_gui.I18n import T
from automaton_gui.theme.Palettes import STRUCTURE
from automaton_gui.theme.Theme import theme
from automaton_gui.Version import VersionedTitle

# Base window class ported from guis/framework/GuiApp.ahk2 (merged with the
# project ZzzGui base: themed by default, theme menu, theme persistence hook).
#
# A subclass sets a few class attributes and implements build() to add its
# central widget; the base does the rest: title/size, theme + dark title bar,
# the menu bar, anchored centering, and Enter-as-primary-action.
#
#   class MyWindow(GuiApp):
#       title = "Hello"
#       width = 600
#       height = 400
#       def build(self):
#           self.setCentralWidget(QLabel("hi"))
#       def OnEnter(self):
#           ...  # primary action (confirm / save)
#
# Qt does most of what the AHK framework hand-rolled: native QMenuBar, live QSS
# theme swaps (no Destroy+rebuild Reopen needed), native layouts (so the AHK
# LayoutEngine/Components tree is NOT ported - screens use Qt layouts in build()).


class GuiApp(QMainWindow):
    title: str = ""
    # NOT `width`/`height`: those shadow QWidget.width()/height() methods, so any
    # `self.width()` call (incl. centering) would blow up on the int attribute.
    winWidth: int = gc.WINDOW_DEFAULT_WIDTH
    winHeight: int = gc.WINDOW_DEFAULT_HEIGHT
    themed: bool = True
    autoShow: bool = False

    def __init__(
        self, parent: QWidget | None = None, strings: dict | None = None, embedded: bool = False
    ) -> None:
        super().__init__(parent)
        self._strings = strings or {}
        # a page inside another window (the setup wizard): no menu bar, Enter or Escape of its own
        self.embedded = embedded
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
        self._themeActions: dict[str, QAction] = {}
        # Optional sink for theme picks (config_menu wires this to persist
        # [General] theme= to the conf). None on plain/preview windows.
        self._onThemeChange: Callable[[str], None] | None = None
        # QMenuBar.addMenu does not give the QMenu a Python owner, so without a
        # retained reference the C++ menu is GC-collected (the Theme menu only
        # survived because _themeActions kept its actions alive). Keep every
        # created menu here so action menus persist for their window's lifetime.
        self._menus: list = []
        self.Configure()
        self._BuildWindow()
        if not embedded:
            self.Menu()
        self.Build()
        self.OnBuilt()
        if not embedded:
            EnterRouter.Instance().Register(self)
        if self.autoShow:
            self.ShowCentered()

    # ---- hooks a subclass may override ----
    def Build(self) -> None:
        """Build the central widget + layout (the AHK Layout() analogue)."""

    def Configure(self) -> None:
        """Pre-build tweaks (set title/size dynamically)."""

    def Menu(self) -> None:
        """Build the menu bar. Base adds the Theme menu when themed; override and
        call the Add*Menu helpers top-to-bottom in the order you want them."""
        if self.themed:
            self.AddThemeMenu()

    def OnBuilt(self) -> None:
        """Post-build tweaks (after every control exists)."""

    def OnClose(self) -> bool:
        """Teardown on close/escape. Return True to VETO the close (e.g. an
        unsaved-changes prompt declined)."""
        return False

    def OnEnter(self) -> None:
        """The window's primary action (confirm / save). Wired through the
        process-wide Enter router; base is a no-op so windows that don't override
        leave Enter inert."""

    def T(self, key: str, default: str, **kwargs) -> str:
        return T(self._strings, key, default, **kwargs)

    # ---- core build ----
    def _BuildWindow(self) -> None:
        self.setWindowTitle(VersionedTitle(self.title))
        self.resize(self.winWidth, self.winHeight)
        if self.themed and not self.embedded:
            app = QApplication.instance()
            if app is not None and not app.styleSheet():
                theme.Apply(app)
            theme.ApplyTitlebar(self)

    # ---- show / close ----
    def ShowCentered(self, offsetX: int = 0, offsetY: int = 0) -> None:
        """Center over the anchor (game window, else primary work area) and show.
        The GuiWindow.Show analogue."""
        CenterWindow(self, offsetX, offsetY)
        self.show()
        self.raise_()
        self.activateWindow()
        ForceForeground(int(self.winId()))

    def closeEvent(self, event) -> None:
        if self.OnClose():
            event.ignore()
            return
        EnterRouter.Instance().Unregister(self)
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (event.key() == Qt.Key.Key_Escape) and not self.embedded:
            self.close()
            return
        super().keyPressEvent(event)

    # ---- theme switching ----
    def SetTheme(self, mode: str) -> None:
        """Switch the active palette live. Qt re-styles every window from the one
        app-wide stylesheet, so no window rebuild (AHK Reopen) is needed - only
        this window's menu checkmark is refreshed."""
        if theme.mode == mode:
            return
        theme.SetMode(mode)
        self._RefreshThemeMenu()
        if self._onThemeChange is not None:
            self._onThemeChange(theme.mode)

    def _RefreshThemeMenu(self) -> None:
        for pid, action in self._themeActions.items():
            action.setChecked(pid == theme.mode)

    # ---- menu bar ----
    def AddThemeMenu(self) -> None:
        """Add the Theme menu, grouped into submenus per palettes.STRUCTURE (add
        a theme there and it appears here), with a check on the active palette."""
        menu = self.menuBar().addMenu(self.T("menu.theme", "&Theme"))
        self._menus.append(menu)
        group = QActionGroup(self)
        group.setExclusive(True)
        for groupLabel, items in STRUCTURE:
            target = menu if groupLabel == "" else menu.addMenu(groupLabel)
            for pid, label in items:
                action = target.addAction(label)
                action.setCheckable(True)
                action.setChecked(pid == theme.mode)
                action.triggered.connect(self._ThemeSetter(pid))
                group.addAction(action)
                self._themeActions[pid] = action

    def AddConfigMenu(self, label: str, items: list[dict]) -> None:
        """Open config files in the OS default editor. items: {name, path}."""
        menu = self.menuBar().addMenu(label)
        self._menus.append(menu)
        for item in items:
            action = menu.addAction(item["name"])
            action.triggered.connect(self._OpenExternally(item["path"]))

    def AddActionMenu(self, label: str, items: list[dict]) -> None:
        """Generic action menu. items: {name, action} where action is callable."""
        menu = self.menuBar().addMenu(label)
        self._menus.append(menu)
        for item in items:
            action = menu.addAction(item["name"])
            action.triggered.connect(self._ActionRunner(item["action"]))

    def AddDynamicMenu(self, label: str, populate: Callable[[QMenu], None]) -> None:
        """Menu rebuilt by `populate(menu)` every time it opens, so its items can
        follow state that changes while the window stays up."""
        menu = self.menuBar().addMenu(label)
        self._menus.append(menu)

        def Rebuild() -> None:
            for child in menu.findChildren(QMenu):
                child.deleteLater()
            menu.clear()
            populate(menu)

        menu.aboutToShow.connect(Rebuild)
        populate(menu)

    def _ThemeSetter(self, pid: str) -> Callable[..., None]:
        return lambda checked=False: self.SetTheme(pid)

    def _ActionRunner(self, action: Callable[[], None]) -> Callable[..., None]:
        return lambda checked=False: action()

    def _OpenExternally(self, path: str) -> Callable[..., None]:
        def Handler(checked: bool = False) -> None:
            import os

            if os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.warning(
                    self,
                    self.T("window.file_not_found_title", "File not found"),
                    self.T("window.file_not_found_body", "File not found:\n{path}", path=path),
                )

        return Handler


class EnterRouter(QObject):
    """One process-wide Enter route, ported from GuiApp._WireEnter / the ~Enter
    hotkey. In AHK a single non-suppressing ~Enter hotkey, scoped to "one of our
    windows is foreground", fired only the active window's OnEnter (a hidden
    default button misfires with multiple windows open). Here: ONE application
    event filter fires OnEnter when a Return/Enter keypress reaches a registered
    top-level window. A key event propagates up the focus widget's parent chain
    until accepted or the top-level; keying on the window (the propagation
    endpoint) fires OnEnter exactly ONCE, regardless of which child held focus,
    while a child that legitimately consumes Enter (a multi-line edit) stops
    propagation and keeps its own behavior. Never consumes (returns False) so the
    keystroke still reaches the focused control."""

    _instance: EnterRouter | None = None

    @classmethod
    def Instance(cls) -> EnterRouter:
        if cls._instance is None:
            cls._instance = EnterRouter()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._windows: set[GuiApp] = set()
        self._installed = False

    def Register(self, window: GuiApp) -> None:
        self._windows.add(window)
        # A window deleted without a close (a retired tray host) never unregisters.
        # Weak, so the connection does not keep the window alive.
        windowRef = weakref.ref(window)
        window.destroyed.connect(lambda: self._windows.discard(windowRef()))
        self._EnsureInstalled()

    def Unregister(self, window: GuiApp) -> None:
        self._windows.discard(window)

    def _EnsureInstalled(self) -> None:
        if self._installed:
            return
        app = QApplication.instance()
        if app is None:
            return
        app.installEventFilter(self)
        self._installed = True

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        isEnter = (event.type() == QEvent.Type.KeyPress) and (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        )
        # A held Enter must not repeat the action, nor land on the window that
        # takes focus after this one closes.
        if isEnter and (not event.isAutoRepeat()) and (obj in self._windows):
            obj.OnEnter()
        return False
