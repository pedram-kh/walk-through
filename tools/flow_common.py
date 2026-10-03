"""Particle-current helpers shared by Blender build scripts (Blender 4.5 LTS, mathutils).

Used by a stop's build.py for the current that wraps its objects, and by
tools/build_route.py for the journey currents that carry it from stop to stop.
A current is one or more paths (control points in any 3D frame); particles sit on
fibres at a fixed offset from a path and move along it in the browser
(runtime/flow.js). Callers pass the module-level `random` state they seeded, so
results stay deterministic.
"""
import math, random
from mathutils import Vector


def catmull_rom(points, steps=24):
    """Smooth curve through the points (uniform Catmull-Rom)."""
    pts = [points[0] * 2 - points[1], *points, points[-1] * 2 - points[-2]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1:i + 3]
        for k in range(steps):
            t = k / steps
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(points[-1].copy())
    return out


def resample(line, n):
    """n points evenly spaced along a polyline, and its length."""
    lengths = [0.0]
    for a, b in zip(line, line[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    out, j = [], 0
    for i in range(n):
        s = lengths[-1] * i / (n - 1)
        while j < len(line) - 2 and lengths[j + 1] < s:
            j += 1
        seg = lengths[j + 1] - lengths[j]
        out.append(line[j].lerp(line[j + 1], (s - lengths[j]) / seg if seg else 0))
    return out, lengths[-1]


def path_frames(samples, facing):
    """Normal and binormal along the path; the normal starts square to `facing`
    (usually the camera's view direction) and is carried along without twisting
    (parallel transport)."""
    n = len(samples)
    tangents = [(samples[min(i + 1, n - 1)] - samples[max(i - 1, 0)]).normalized() for i in range(n)]
    normal = tangents[0].cross(facing.normalized()).normalized()
    normals = []
    for t in tangents:
        normal = (normal - t * normal.dot(t)).normalized()
        normals.append(normal)
    return normals, [t.cross(nm) for t, nm in zip(tangents, normals)]


def smoothstep(a, b, x):
    x = min(max((x - a) / (b - a), 0.0), 1.0)
    return x * x * (3 - 2 * x)


def make_current(flows, *, facing, samples, amount, twist, base, bright, radius):
    """Particles for a set of paths.

    flows: list of (control points as Vectors, particles, width, fibres, speed).
    Returns (paths, rows, still): paths hold the resampled points, normals and
    binormals (Vectors) with length and speed; rows match the 11 floats per
    particle in flow.bin; still is (point, rgba, size) per particle at time 0,
    placed exactly as runtime/flow.js places it, for preview renders.
    """
    paths, rows, still = [], [], []
    for curve, (control, count, width, fibres, speed) in enumerate(flows):
        points, length = resample(catmull_rom(control), samples)
        normals, binormals = path_frames(points, facing)
        paths.append({'points': points, 'normals': normals, 'binormals': binormals, 'length': length, 'speed': speed})
        strands = [(abs(random.gauss(0, 0.5)) * width, random.uniform(0, math.tau)) for _ in range(fibres)]
        for _ in range(int(count * amount)):
            if random.random() < 0.8:      # on a fibre
                (r, theta), jitter = random.choice(strands), 0.012
            else:                          # loose haze around the current
                r, theta, jitter = abs(random.gauss(0, 0.6)) * width, random.uniform(0, math.tau), 0.05
            t0, ja, jb = random.random(), random.gauss(0, jitter), random.gauss(0, jitter)
            mix, gain = random.random() ** 2, random.uniform(0.6, 2.0)
            color = [gain * (b * (1 - mix) + br * mix) for b, br in zip(base, bright)]
            size = radius * random.uniform(0.4, 1.25)
            rows.append((curve, t0, r, theta, ja, jb, size, *color, random.random()))
            f = t0 * (samples - 1)
            i = min(int(f), samples - 2)
            u = f - i
            nm = normals[i].lerp(normals[i + 1], u).normalized()
            bn = binormals[i].lerp(binormals[i + 1], u).normalized()
            angle, taper = theta + twist * t0, 0.35 + 0.65 * math.sin(math.pi * t0)
            point = points[i].lerp(points[i + 1], u) + (nm * math.cos(angle) + bn * math.sin(angle)) * r * taper + nm * ja + bn * jb
            fade = smoothstep(0, 0.06, t0) * (1 - smoothstep(0.9, 1, t0))
            still.append((point, (*(c * fade for c in color), 1), size))
    return paths, rows, still
