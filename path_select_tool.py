# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pesi (PESI3D, pesi3d.de)
"""Path Select — pick a path of edges by clicking a few points along it.

Works like the «Smart Path Selection» of Profile Builder for SketchUp:

1. Click an edge: the path starts there.
2. Move the mouse to another edge: the shortest way along the edges, from
   the end you clicked last to that edge, is shown (blue).
3. Click: that part is added (orange). Repeat as often as needed — the path
   grows on from the last click and closes when it reaches its own start.
4. The path IS the selection from the first click on (Ctrl+C, Move, Delete
   work right away). Ctrl / Shift / Shift+Ctrl on the FIRST click: add to /
   toggle in / remove from the selection there was, as with Select.
5. Enter or double-click ends the path (the selection stays); the next click
   starts a new one.

Backspace takes back the last part, Esc drops the path and gives back the
selection there was before. The tool stays on; Space returns to Select.

Extensions ▸ Path Select (Alt+C). Right-click ▸ Select Contour grows the
selected edges along their chains (through points where exactly two edges
meet).

Not affiliated with or endorsed by mind.sight.studios or Trimble Inc.;
«Profile Builder» and «SketchUp» are named only to describe the workflow.
"""
from __future__ import annotations

import heapq
import itertools

VERSION = "1.1"

_PREVIEW_RGB = (77, 140, 242)        # the app's hover blue
_PATH_RGB = (242, 115, 41)           # the app's selection orange


# ---- Graph helpers ----------------------------------------------------------

def _usable(e) -> bool:
    return not getattr(e, "hidden", False)


def _elen(e) -> float:
    return (e.b - e.a).length()


def shortest_route(sources, targets, blocked_edges=(), blocked_verts=()):
    """Shortest way along the edges (A*, straight-line distance as the
    guide) from any vertex in ``sources`` to the first vertex of ``targets``
    reached. Returns ``(source, target, [edges])`` or ``None``. Blocked
    edges / vertices are never walked."""
    targets = set(targets)
    blocked_edges = set(blocked_edges)
    blocked_verts = set(blocked_verts)
    tpos = [t.position for t in targets]

    def h(v):
        p = v.position
        return min((p - q).length() for q in tpos)

    tie = itertools.count()
    dist, prev, origin = {}, {}, {}
    heap = []
    for s in sources:
        dist[s] = 0.0
        origin[s] = s
        heap.append((h(s), next(tie), s))
    heapq.heapify(heap)
    done = set()
    while heap:
        _f, _t, v = heapq.heappop(heap)
        if v in done:
            continue
        done.add(v)
        if v in targets:
            route = []
            w = v
            while w in prev:
                e, w = prev[w]
                route.append(e)
            route.reverse()
            return origin[v], v, route
        d = dist[v]
        for e in v.edges:
            if e in blocked_edges or not _usable(e):
                continue
            w = e.other(v)
            if w in done or (w in blocked_verts and w not in targets):
                continue
            nd = d + _elen(e)
            if nd < dist.get(w, float("inf")):
                dist[w] = nd
                prev[w] = (e, v)
                origin[w] = origin[v]
                heapq.heappush(heap, (nd + h(w), next(tie), w))
    return None


def contour_of(edge) -> list:
    """The chain through ``edge``: walk both ways while exactly two usable
    edges meet at a point (stops at junctions and loose ends)."""
    seen = {edge}
    parts = []
    for start in (edge.v1, edge.v0):
        part, cur, v = [], edge, start
        while True:
            nb = [e for e in v.edges if _usable(e)]
            if len(nb) != 2:
                break
            nxt = nb[0] if nb[1] is cur else nb[1]
            if nxt in seen:
                break
            seen.add(nxt)
            part.append(nxt)
            cur, v = nxt, nxt.other(v)
        parts.append(part)
    return list(reversed(parts[1])) + [edge] + parts[0]


# ---- The path being built ---------------------------------------------------

class PathState:
    """Edges in order of picking, the two open ends, and an undo stack."""

    def __init__(self) -> None:
        self.edges: list = []
        self.ends: list = []          # [start vertex, end vertex]
        self.closed = False
        self.waypoints: list = []     # vertices clicked (for the dots)
        self.active = None            # end the path grows from (None = either)
        self._undo: list = []

    def __bool__(self) -> bool:
        return bool(self.edges)

    def start(self, edge) -> None:
        self.__init__()
        self.edges = [edge]
        self.ends = [edge.v0, edge.v1]
        self.waypoints = [edge.v0, edge.v1]

    def interior_vertices(self) -> set:
        vs = set()
        for e in self.edges:
            vs.add(e.v0)
            vs.add(e.v1)
        return vs - set(self.ends)

    def route_to(self, edge):
        """Preview: ``(end index, edges to add, new end vertex, closes)`` for
        the shortest way to ``edge``, or None."""
        if not self.edges or self.closed or edge in self.edges:
            return None
        sources = (self.ends if self.active is None
                   else [self.ends[self.active]])
        found = shortest_route(sources, (edge.v0, edge.v1),
                               blocked_edges=self.edges,
                               blocked_verts=self.interior_vertices())
        if found is None:
            return None
        src, hit, route = found
        far = edge.other(hit)
        # The target edge was walked as the last step? Then «hit» is already
        # its far end; otherwise step along it.
        if route and route[-1] is edge:
            far = hit
        else:
            route = route + [edge]
        idx = 0 if src is self.ends[0] else 1
        other_end = self.ends[1 - idx]
        closes = far is other_end and self.ends[0] is not self.ends[1]
        if far in self.interior_vertices():
            return None                # would run into the path itself
        return idx, route, far, closes

    def commit(self, preview) -> None:
        idx, route, far, closes = preview
        self._undo.append((list(self.edges), list(self.ends), self.closed,
                           list(self.waypoints), self.active))
        if idx == 0:
            self.edges = list(reversed(route)) + self.edges
        else:
            self.edges = self.edges + route
        self.ends[idx] = far
        self.closed = closes
        self.active = idx
        self.waypoints.append(far)

    def undo(self) -> bool:
        if self._undo:
            (self.edges, self.ends, self.closed, self.waypoints,
             self.active) = self._undo.pop()
            return True
        if self.edges:
            self.__init__()
            return True
        return False


# ---- The tool ---------------------------------------------------------------

def _make_tool_class():
    """Built inside a function on purpose: a ``Tool`` subclass at module level
    would become a one-shot entry in the Extensions menu; this one is an
    active tool, switched on by our own menu entry."""
    from PySide6.QtCore import Qt
    from core.mesh import Edge
    from tools.base import Tool
    from tools.select import selection_mode

    class PathSelectTool(Tool):
        name = "Path Select"
        shortcut = None
        description = ("Click edges along a path; the shortest way between "
                       "the clicks is added and selected. Enter or "
                       "double-click ends it, Backspace takes back a step, "
                       "Esc drops it.")
        uses_snap = False
        box_select = False

        def __init__(self) -> None:
            self.path = PathState()
            self.preview = None
            self._hover_key = None
            self._base = set()          # selection before the path began
            self._mode = "replace"

        # Esc asks ``viewport._tool_busy`` — a non-empty ``nodes`` says a
        # path is in progress, so Esc cancels it instead of the selection.
        @property
        def nodes(self):
            return self.path.edges

        # -- lifecycle --
        def on_activate(self, viewport) -> None:
            self._reset()
            viewport.flash_status(
                "Path Select: click an edge to start, then click along the "
                "path — it is selected as it grows. Enter = done, "
                "Backspace = back, Esc = cancel.", 6000)

        def on_deactivate(self, viewport) -> None:
            self._reset()
            viewport.set_hover(None)
            viewport.update()

        def on_cancel(self, viewport) -> None:
            # Give back the selection there was before the path.
            sel = viewport.scene.selection
            sel.clear()
            sel.update(self._base)
            viewport.scene.bump_view()
            self._reset()
            viewport.flash_status("Path cancelled.", 2000)
            viewport.update()

        def _reset(self) -> None:
            self.path = PathState()
            self.preview = None
            self._hover_key = None

        # -- picking --
        @staticmethod
        def _pick_edge(viewport, x, y):
            pick = getattr(viewport, "pick_visible_edge", None) \
                or viewport.pick_edge
            e = pick(x, y)
            return e if isinstance(e, Edge) and _usable(e) else None

        def on_hover(self, ctx) -> None:
            vp = ctx.viewport
            edge = self._pick_edge(vp, ctx.screen.x(), ctx.screen.y())
            vp.set_hover(edge)
            key = (edge, len(self.path.edges), self.path.closed,
                   getattr(vp.scene, "version", None))
            if key == self._hover_key:
                return
            self._hover_key = key
            self.preview = (self.path.route_to(edge)
                            if (edge is not None and self.path) else None)
            self._status(vp)
            vp.update()

        def on_click(self, ctx) -> None:
            vp = ctx.viewport
            edge = self._pick_edge(vp, ctx.screen.x(), ctx.screen.y())
            if edge is None:
                return
            if not self.path:
                self._mode = selection_mode(ctx.modifiers)
                self._base = set(vp.scene.selection)
                self.path.start(edge)
            elif self.preview is not None and self.preview[1] \
                    and self.preview[1][-1] is edge:
                self.path.commit(self.preview)
            else:
                pv = self.path.route_to(edge)
                if pv is not None:
                    self.path.commit(pv)
            self.preview = None
            self._sync(vp)
            self._hover_key = None
            self._status(vp)
            vp.update()

        def _sync(self, vp) -> None:
            """The scene selection = the selection before the path, with
            the path applied the way the first click's modifiers said."""
            sel = vp.scene.selection
            sel.clear()
            if self._mode != "replace":
                sel.update(self._base)
            vp.scene.select(list(self.path.edges), mode=self._mode)

        def on_double_click(self, ctx) -> None:
            self._finish(ctx.viewport, ctx.modifiers)

        def on_key(self, viewport, key, modifiers) -> bool:
            if key in (Qt.Key_Return, Qt.Key_Enter):
                if self.path:
                    self._finish(viewport, modifiers)
                    return True
                return False
            if key == Qt.Key_Backspace:
                if self.path.undo():
                    self.preview = None
                    self._sync(viewport)
                    self._hover_key = None
                    self._status(viewport)
                    viewport.update()
                    return True
                return False
            return False

        def _finish(self, viewport, modifiers) -> None:
            if not self.path:
                return
            edges = list(self.path.edges)
            self._sync(viewport)
            closed = self.path.closed
            self._reset()
            viewport.flash_status(
                f"Path done, selected: {len(edges)} edges · "
                f"{self._fmt(viewport, sum(map(_elen, edges)))}"
                f"{' · closed' if closed else ''}", 4000)
            viewport.update()

        # -- status bar --
        @staticmethod
        def _fmt(viewport, metres) -> str:
            try:
                return viewport._format_dim_value(
                    metres, viewport.scene.dimension_style)
            except Exception:  # noqa: BLE001 — the length is a nicety
                return f"{metres:.2f} m"

        def _status(self, vp) -> None:
            if not self.path:
                return
            n = len(self.path.edges)
            length = sum(map(_elen, self.path.edges))
            text = f"Path: {n} edges · {self._fmt(vp, length)}"
            if self.path.closed:
                text += " · closed"
            elif self.preview is not None:
                add = self.preview[1]
                text += (f"  (+{len(add)} → "
                         f"{self._fmt(vp, length + sum(map(_elen, add)))})")
            text += "  ·  selected · Enter = done, Backspace = back, Esc = cancel"
            vp.flash_status(text, 8000)

    return PathSelectTool


# ---- Wiring -----------------------------------------------------------------

# ---------------------------------------------------------------------------
# Toolbar (PESI3D): icons drawn in IngeTrazo's own icon style
# ---------------------------------------------------------------------------

def _pesi3d_icons():
    """Icon key → draw(painter, ink, accent) on a 48 px canvas."""
    import math  # noqa: F401
    from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: F401
    from PySide6.QtGui import (QBrush, QColor, QPainterPath, QPen,  # noqa: F401
                               QPolygonF)

    def _a(c, alpha):
        return QColor(c.red(), c.green(), c.blue(), alpha)

    def _poly(pts):
        return QPolygonF([QPointF(x, y) for x, y in pts])

    def _thin(p, ink, alpha=120, width=1.8, dashed=False):
        pen = QPen(_a(ink, alpha), width, Qt.DashLine if dashed else Qt.SolidLine)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)

    def _grid(p, ink, x0=8, y0=8, n=3, step=10.67):
        p.save()
        _thin(p, ink, 90, 1.5)
        for i in range(n + 1):
            p.drawLine(QPointF(x0 + i * step, y0), QPointF(x0 + i * step, y0 + n * step))
            p.drawLine(QPointF(x0, y0 + i * step), QPointF(x0 + n * step, y0 + i * step))
        p.restore()

    def path_select_icon(p, ink, acc):
        _grid(p, ink)
        s = 32 / 3
        pts = [(8, 40), (8 + s, 40), (8 + s, 40 - s), (8 + 2 * s, 40 - s),
               (8 + 2 * s, 8 + s), (40, 8 + s), (40, 8)]
        pen = QPen(acc, 4.0)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        p.save()
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(_poly(pts))
        p.restore()
        for x, y in (pts[0], pts[-1]):          # the two clicks
            p.save()
            p.setPen(QPen(ink, 2.4))
            p.setBrush(QColor(255, 255, 255))
            p.drawEllipse(QPointF(x, y), 4.0, 4.0)
            p.restore()

    def select_contour_icon(p, ink, acc):
        # One picked edge (ink) grown along its whole contour (accent).
        path = QPainterPath()
        path.moveTo(24, 9)
        path.cubicTo(36, 9, 41, 16, 40, 24)
        path.cubicTo(39, 33, 32, 39, 23, 39)
        path.cubicTo(13, 39, 7, 33, 8, 24)
        path.cubicTo(9, 15, 13, 9, 24, 9)
        pen = QPen(acc, 4.0)
        pen.setCapStyle(Qt.RoundCap)
        p.save()
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.restore()
        thick = QPen(ink, 5.0)
        thick.setCapStyle(Qt.RoundCap)
        p.save()
        p.setPen(thick)
        p.drawLine(QPointF(9.2, 30), QPointF(16, 37))
        p.restore()
        # arrows running out along the contour from the picked edge
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(ink))
        p.drawPolygon(_poly([(30, 13.5), (23, 9), (30, 4.5)]))
        p.drawPolygon(_poly([(37.5, 31), (41, 23.5), (44.5, 31)]))
        p.restore()

    return {"path": path_select_icon, "contour": select_contour_icon}


def _pesi3d_toolbar(app, title, entries):
    """A toolbar of this plugin's own — one icon per command (PESI3D).

    ``entries`` = (icon key, text, tip, callable). The icons are drawn
    like IngeTrazo's own (views/icons.py: 48 px, ink = the palette's text
    colour, 3 px pen, the orange accent) and redrawn when the theme flips.
    The toolbar moves, floats and hides like the built-in ones (right-click
    on any toolbar); its place is kept by its objectName."""
    try:
        from PySide6.QtCore import QEvent, QObject, QSize, Qt
        from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
        from PySide6.QtWidgets import QApplication, QToolBar
    except Exception:  # noqa: BLE001 — no Qt, no toolbar
        return None
    win = getattr(app, "window", None)
    if win is None:
        return None
    draws = _pesi3d_icons()

    def make_icon(key):
        draw = draws.get(key)
        if draw is None:
            return QIcon()
        qa = QApplication.instance()
        ink = (QColor(qa.palette().windowText().color()) if qa is not None
               else QColor(40, 44, 52))
        pm = QPixmap(48, 48)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(ink, 3.0)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        try:
            draw(p, ink, QColor(243, 115, 41))
        finally:
            p.end()
        return QIcon(pm)

    name = f"pesi3d_{getattr(app, 'key', title)}"
    tb = None
    make = getattr(win, "_new_toolbar", None)     # the host's own builder
    if callable(make):
        try:
            tb = make(title, name)
        except Exception:  # noqa: BLE001
            tb = None
    if tb is None:
        tb = QToolBar(title, win)
        tb.setObjectName(name)
        tb.setMovable(True)
        tb.setFloatable(True)
        try:
            from views.icons import toolbar_icon_px
            px = int(toolbar_icon_px())
        except Exception:  # noqa: BLE001
            px = 24
        tb.setIconSize(QSize(px, px))
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        win.addToolBar(Qt.TopToolBarArea, tb)

    actions = []
    for key, text, tip, fn in entries:
        act = QAction(make_icon(key), text, tb)
        act.setToolTip(f"{text}\n{tip}" if tip else text)
        if tip:
            act.setStatusTip(tip)
        act.triggered.connect(lambda _c=False, f=fn: f())
        tb.addAction(act)
        actions.append((act, key))

    class _ThemeWatch(QObject):
        def eventFilter(self, obj, event):  # noqa: N802 — Qt override
            if event.type() in (QEvent.PaletteChange,
                                QEvent.ApplicationPaletteChange,
                                QEvent.StyleChange):
                for a, k in actions:
                    a.setIcon(make_icon(k))
            return False

    watch = _ThemeWatch(tb)
    tb.installEventFilter(watch)
    tb._pesi3d_watch = watch
    _pesi3d_place_later(win)
    return tb


def _pesi3d_place_later(win):
    """A toolbar the saved window layout does not know yet lands at the end
    of the top row, squeezed behind the built-in ones. Once the window is
    laid out, put new PESI3D toolbars on a row of their own under the
    built-in ones — only the first time each one appears; after that the
    user's own arrangement (saved with the window) wins. Every PESI3D
    plugin carries this code; the first one to get here does it for all."""
    if getattr(win, "_pesi3d_place_pending", False):
        return
    win._pesi3d_place_pending = True
    from PySide6.QtCore import QSettings, Qt, QTimer
    from PySide6.QtWidgets import QToolBar

    def place():
        win._pesi3d_place_pending = False
        try:
            st = QSettings()
            key = "plugins/pesi3d/placed_toolbars"
            placed = st.value(key) or []
            if isinstance(placed, str):
                placed = [placed]
            placed = list(placed)
            bars = [t for t in win.findChildren(QToolBar)
                    if t.objectName().startswith("pesi3d_")]
            new = [t for t in bars if t.objectName() not in placed]
            if not new:
                return
            fresh = not placed            # no PESI3D row yet → open one
            for i, t in enumerate(sorted(new, key=lambda t: t.objectName())):
                shown = not t.isHidden()
                win.removeToolBar(t)
                if fresh and i == 0:
                    win.addToolBarBreak(Qt.TopToolBarArea)
                win.addToolBar(Qt.TopToolBarArea, t)
                t.setVisible(shown)
            st.setValue(key, placed + [t.objectName() for t in new])
        except Exception:  # noqa: BLE001 — layout only, never break the app
            pass

    QTimer.singleShot(0, place)


def setup(app):
    from PySide6.QtCore import QLineF, QPointF, Qt
    from PySide6.QtGui import QColor, QPen

    tool = _make_tool_class()()

    def activate():
        win, vp = app.window, app.viewport
        vp.set_active_tool(tool)
        # As Paste does: no toolbar button is ours, so none stays checked,
        # and the status bar names the tool.
        for action in getattr(win, "_tool_actions", {}).values():
            action.setChecked(False)
        label = getattr(win, "_tool_label", None)
        if label is not None:
            label.setText(f"Tool: {tool.name}")
        for name in ("_refresh_vcb", "_update_status_hint"):
            fn = getattr(win, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    pass

    app.add_menu_action(
        "Path Select", activate, "Alt+C",
        tip="Select a path of edges by clicking along it — the shortest way "
            "between the clicks is filled in.")

    def _lines(edges):
        import numpy as np
        if not edges:
            return []
        pts = np.empty((len(edges) * 2, 3))
        for i, e in enumerate(edges):
            a, b = e.a, e.b
            pts[2 * i] = (a.x(), a.y(), a.z())
            pts[2 * i + 1] = (b.x(), b.y(), b.z())
        px, py, front = app.world_to_pixels(pts)
        return [QLineF(px[i], py[i], px[i + 1], py[i + 1])
                for i in range(0, len(px), 2) if front[i] and front[i + 1]]

    def _pen(rgb, width):
        pen = QPen(QColor(*rgb))
        pen.setWidthF(width)
        pen.setCapStyle(Qt.RoundCap)
        return pen

    def overlay(viewport, painter):
        if viewport.active_tool is not tool or not tool.path:
            return
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        if tool.preview is not None:
            lines = _lines(tool.preview[1])
            if lines:
                painter.setPen(_pen(_PREVIEW_RGB, 3.0))
                painter.drawLines(lines)
        lines = _lines(tool.path.edges)
        if lines:
            painter.setPen(_pen(_PATH_RGB, 3.5))
            painter.drawLines(lines)
        # Clicked points as dots.
        import numpy as np
        wp = tool.path.waypoints
        if wp:
            pts = np.array([(v.position.x(), v.position.y(), v.position.z())
                            for v in wp])
            px, py, front = app.world_to_pixels(pts)
            painter.setPen(_pen((255, 255, 255), 1.5))
            painter.setBrush(QColor(*_PATH_RGB))
            for x, y, f in zip(px, py, front):
                if f:
                    painter.drawEllipse(QPointF(x, y), 4.0, 4.0)

    app.add_overlay(overlay)

    # Right-click ▸ Select Contour: grow the selected edges along their chains.
    def grow(edges=None):
        from core.mesh import Edge
        if edges is None:
            edges = [e for e in (app.viewport.scene.selection or ())
                     if isinstance(e, Edge)]
        if not edges:
            return
        out, seen = [], set()
        for e in edges:
            for c in contour_of(e):
                if c not in seen:
                    seen.add(c)
                    out.append(c)
        app.viewport.scene.select(out, mode="add")
        app.viewport.update()

    def context_menu(menu, selection):
        from core.mesh import Edge
        edges = [e for e in (selection or ()) if isinstance(e, Edge)]
        if not edges:
            return

        menu.addAction("Select Contour", lambda: grow(edges))

    app.add_context_menu(context_menu)

    _pesi3d_toolbar(app, "Path Select", [
        ("path", "Path Select  (Alt+C)",
         "Select a path of edges by clicking along it — the shortest way "
         "between the clicks is filled in.", activate),
        ("contour", "Select Contour",
         "Grow the selected edges along their whole contour.",
         lambda: grow(None)),
    ])
