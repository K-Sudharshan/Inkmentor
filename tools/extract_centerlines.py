#!/usr/bin/env python3
"""
tools/extract_centerlines.py

Extracts centerline polylines from ReenieBeanie.ttf for handwriting pen animations.
License of font: SIL Open Font License 1.1 (confirmed in tools/OFL.txt).
"""

import os
import sys
import json
import math
import numpy as np
from PIL import ImageFont, Image, ImageDraw
from skimage.morphology import skeletonize
import networkx as nx

FONT_PATH = os.path.join(os.path.dirname(__file__), 'ReenieBeanie.ttf')
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), '..', 'reenie_centerlines.json')

# Characters that can appear in mathematical 'write' lines, questions, and solver output:
CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "+-*/=()[]{}<>,.:;'\"^_!?%|\\~` ²³·′−"
)

def rdp_simplify(points, epsilon):
    """Ramer-Douglas-Peucker polyline simplification."""
    if len(points) <= 2:
        return points
    p1 = np.array(points[0], dtype=float)
    p2 = np.array(points[-1], dtype=float)
    line_vec = p2 - p1
    line_len = np.linalg.norm(line_vec)
    if line_len == 0:
        dists = np.linalg.norm(points - p1, axis=1)
    else:
        line_unit = line_vec / line_len
        vecs = points - p1
        proj = np.outer(np.dot(vecs, line_unit), line_unit)
        dists = np.linalg.norm(vecs - proj, axis=1)

    max_idx = int(np.argmax(dists))
    max_dist = dists[max_idx]

    if max_dist > epsilon:
        left = rdp_simplify(points[:max_idx + 1], epsilon)
        right = rdp_simplify(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]

def merge_crossing_strokes(strokes):
    """Merge collinear stroke segments that meet at intersections (e.g. in 'x' and '+')."""
    if len(strokes) <= 1:
        return strokes

    changed = True
    while changed:
        changed = False
        n = len(strokes)
        pair_to_merge = None
        for i in range(n):
            for j in range(i + 1, n):
                s1, s2 = strokes[i], strokes[j]
                pairs = [
                    (s1[-1], s2[0], s1, s2, False, False),
                    (s1[-1], s2[-1], s1, s2, False, True),
                    (s1[0], s2[0], s1, s2, True, False),
                    (s2[-1], s1[0], s2, s1, False, False)
                ]
                for p_end, p_start, first, second, rev1, rev2 in pairs:
                    dist = math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1])
                    if dist <= 55:
                        f_pts = list(reversed(first)) if rev1 else list(first)
                        sec_pts = list(reversed(second)) if rev2 else list(second)
                        v1 = np.array(f_pts[-1]) - np.array(f_pts[-2])
                        v2 = np.array(sec_pts[1]) - np.array(sec_pts[0])
                        norm1, norm2 = np.linalg.norm(v1), np.linalg.norm(v2)
                        if norm1 > 0 and norm2 > 0:
                            cos_sim = float(np.dot(v1 / norm1, v2 / norm2))
                            if cos_sim > 0.2:
                                pair_to_merge = (i, j, f_pts + sec_pts)
                                break
                    if pair_to_merge: break
                if pair_to_merge: break
            if pair_to_merge: break

        if pair_to_merge:
            i, j, merged_pts = pair_to_merge
            strokes = [strokes[k] for k in range(n) if k != i and k != j] + [merged_pts]
            changed = True

    return strokes

def process_character(font, ch, em_size=1000):
    """
    Renders character at em_size, extracts skeleton, and produces ordered centerline strokes.
    """
    if ch == ' ':
        adv = font.getlength(' ')
        return {
            'char': ' ',
            'advance': round(float(adv), 1),
            'bbox': [0.0, 0.0, 0.0, 0.0],
            'strokes': []
        }

    bbox = font.getbbox(ch, anchor='ls')
    advance = font.getlength(ch)

    pad = 50
    min_x, min_y, max_x, max_y = bbox
    w = max_x - min_x + 2 * pad
    h = max_y - min_y + 2 * pad

    if w <= 0 or h <= 0:
        return None

    img = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(img)
    draw.text((pad - min_x, pad - min_y), ch, font=font, fill=255, anchor='ls')

    arr = np.array(img) > 128
    if not np.any(arr):
        return None

    skel = skeletonize(arr)

    # Build 8-connected graph
    G = nx.Graph()
    pts = np.argwhere(skel)
    for y, x in pts:
        G.add_node((int(y), int(x)))
    for y, x in pts:
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dy == 0 and dx == 0: continue
                ny, nx_ = int(y + dy), int(x + dx)
                if (ny, nx_) in G:
                    G.add_edge((int(y), int(x)), (ny, nx_))

    # Spur pruning (up to 28 px) and cycle breaking (micro-cycles <= 15)
    for _ in range(5):
        changed = False
        endpoints = [n for n in G.nodes() if G.degree(n) == 1]
        for ep in endpoints:
            path = [ep]
            curr = ep
            prev = None
            while True:
                neighbors = [nb for nb in G.neighbors(curr) if nb != prev]
                if len(neighbors) == 1:
                    prev = curr
                    curr = neighbors[0]
                    path.append(curr)
                    if G.degree(curr) >= 3:
                        break
                else:
                    break
            if curr != ep and G.degree(curr) >= 3 and len(path) <= 28:
                for node in path[:-1]:
                    G.remove_node(node)
                changed = True

        for c in list(nx.cycle_basis(G)):
            if len(c) <= 15:
                G.remove_edge(c[0], c[1])
                changed = True
        if not changed:
            break

    # Extract continuous strokes
    unvisited_edges = set(tuple(sorted((u, v))) for u, v in G.edges())
    raw_strokes = []

    while unvisited_edges:
        subG = nx.Graph()
        for u, v in unvisited_edges:
            subG.add_edge(u, v)

        endpoints = [n for n in subG.nodes() if subG.degree(n) == 1]
        if endpoints:
            endpoints.sort(key=lambda pt: (pt[0], pt[1]))
            start_node = endpoints[0]
        else:
            nodes = sorted(list(subG.nodes()), key=lambda pt: (pt[0], pt[1]))
            if not nodes:
                break
            start_node = nodes[0]

        path = [start_node]
        curr = start_node
        prev = None
        visited_nodes = {start_node}

        while True:
            cand = [nb for nb in subG.neighbors(curr) if nb != prev]
            if not cand:
                break

            if len(cand) == 1:
                next_node = cand[0]
            else:
                if len(path) >= 2:
                    dir_vec = np.array(curr, dtype=float) - np.array(path[-2], dtype=float)
                    norm = np.linalg.norm(dir_vec)
                    dir_unit = dir_vec / norm if norm > 0 else np.array([1.0, 0.0])
                    def score(nb):
                        v = np.array(nb, dtype=float) - np.array(curr, dtype=float)
                        v_norm = np.linalg.norm(v)
                        return float(np.dot(v / v_norm, dir_unit)) if v_norm > 0 else 0.0
                    cand.sort(key=score, reverse=True)
                next_node = cand[0]

            edge = tuple(sorted((curr, next_node)))
            if edge in unvisited_edges:
                unvisited_edges.remove(edge)

            if next_node in visited_nodes:
                path.append(next_node)
                break

            prev = curr
            curr = next_node
            path.append(curr)
            visited_nodes.add(curr)

        if len(path) >= 3:
            raw_strokes.append(path)

    # Convert coordinates to font units (SVG top-down from baseline)
    out_strokes = []
    for stroke in raw_strokes:
        pts = [(pt[1] - pad + min_x, pt[0] - pad + min_y) for pt in stroke]
        st_len = sum(math.hypot(pts[i][0] - pts[i-1][0], pts[i][1] - pts[i-1][1]) for i in range(1, len(pts)))
        if st_len < 40 and ch not in '.,:;·\'"':
            continue

        simplified = rdp_simplify(pts, 2.5)
        rounded = [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in simplified]
        if len(rounded) >= 2:
            out_strokes.append(rounded)

    # Merge crossing strokes that intersect (e.g. in 'x' and '+')
    out_strokes = merge_crossing_strokes(out_strokes)

    # If letter 'd' has a dominant stroke (>600 font units) and a tiny remnant spur (<50 font units), remove spur
    if ch in 'd23' and len(out_strokes) > 1:
        lengths = [sum(math.hypot(s[i][0]-s[i-1][0], s[i][1]-s[i-1][1]) for i in range(1, len(s))) for s in out_strokes]
        max_l = max(lengths)
        out_strokes = [s for idx, s in enumerate(out_strokes) if lengths[idx] > 50 or lengths[idx] == max_l]

    # Ensure natural handwriting direction (top to bottom)
    for i, st in enumerate(out_strokes):
        if st[0][1] > st[-1][1] + 30 and ch not in '/\\':
            out_strokes[i] = list(reversed(st))

    # Stroke ordering
    if ch in 'ij':
        # Stem first, then dot
        out_strokes.sort(key=lambda st: len(st), reverse=True)
    elif ch == 'x':
        # Main stroke (top-left to bottom-right) then crossing stroke
        out_strokes.sort(key=lambda st: st[0][0])
    elif ch == '+':
        # Vertical stroke first, then horizontal crossbar
        out_strokes.sort(key=lambda st: abs(st[0][0] - st[-1][0]))
    else:
        out_strokes.sort(key=lambda st: (st[0][1], st[0][0]))

    return {
        'char': ch,
        'advance': round(float(advance), 1),
        'bbox': [round(float(min_x), 1), round(float(min_y), 1), round(float(max_x), 1), round(float(max_y), 1)],
        'strokes': out_strokes
    }

def main():
    print(f"Loading font: {FONT_PATH}")
    font = ImageFont.truetype(FONT_PATH, size=1000)

    results = {}
    success_count = 0
    fail_list = []

    for ch in CHARS:
        try:
            res = process_character(font, ch)
            if res and (len(res['strokes']) > 0 or ch == ' '):
                results[ch] = res
                success_count += 1
            else:
                fail_list.append((ch, "No strokes extracted"))
        except Exception as e:
            fail_list.append((ch, str(e)))

    print(f"\nProcessing complete: {success_count}/{len(CHARS)} glyphs succeeded.")
    if fail_list:
        print("Failed glyphs:")
        for ch, reason in fail_list:
            print(f"  {ascii(ch)} (ord {ord(ch)}): {reason}")

    output_path = os.path.abspath(OUTPUT_JSON)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, separators=(',', ':'))
    print(f"\nWrote centerline data to {output_path} (size: {os.path.getsize(output_path)} bytes)")

if __name__ == '__main__':
    main()
