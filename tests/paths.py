"""Траектории для тестов гонок: «идеальный пилот» летит равномерно через центры ворот."""

from __future__ import annotations

from app.catalog import Track
from app.game.track import build_layout

STEP_MS = 100
START_HEIGHT = 2.6


def perfect_path(track: Track, time_ms: int, reach: int | None = None, shift: float = 0.0) -> list[list[float]]:
    """Точки (t, x, y, z) до финиша (или до ворот номер reach при сходе), x смещён на shift метров."""
    layout = build_layout(track)
    gates = layout.gates if reach is None else layout.gates[:reach]
    end_z = track.length if reach is None else (gates[-1].z if gates else 0.0)
    anchors = [(0.0, 0.0, START_HEIGHT)] + [(g.z, g.x, g.y) for g in gates]
    last = anchors[-1]
    anchors.append((max(end_z, last[0]) + 1, last[1], last[2]))

    def at(z: float) -> tuple[float, float]:
        for (z0, x0, y0), (z1, x1, y1) in zip(anchors, anchors[1:]):
            if z0 <= z <= z1:
                k = 0.0 if z1 == z0 else (z - z0) / (z1 - z0)
                return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
        return last[1], last[2]

    points = []
    for t in list(range(0, time_ms, STEP_MS)) + [time_ms]:
        z = end_z * t / time_ms if time_ms else 0.0
        x, y = at(z)
        points.append([float(t), round(x + shift, 2), round(y, 2), round(z, 1)])
    return points
