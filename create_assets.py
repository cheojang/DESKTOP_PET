"""
에셋 자동 생성기 (핑크 후드 아기 스타일) — v2 통짜 포즈 프레임.

v1 의 "몸통 PNG + 타원 팔다리 PNG 파츠 조립"을 폐기하고, 상태별 전신 포즈를
통짜 SVG 한 장으로 그린다. 팔다리는 몸통 실루엣에서 이어져 나오는 테이퍼 곡선
(limb_path)으로 그리고, 관절 굽힘은 곡률로 표현한다.

각 프레임은 80x120px (= PET_W x PET_H). 얼굴 개구부(크림 안감)의 위치·크기는
FACE_ANCHORS 로 내보내 렌더러가 사용자 얼굴을 합성할 수 있게 한다.

SVG 1.2 Tiny 서브셋 + PySide6.QtSvg 래스터라이즈. 신규 의존성 없음.
QApplication 은 만들지 않는다. 블러/마스크/클립/텍스트 미사용.

python create_assets.py 로 1회 실행. PNG 는 assets/ 에 저장된다.
"""

import io
import math
import os

from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
SCALE = 4       # 슈퍼샘플링 배율

PET_W = 80
PET_H = 120

# ---------------------------------------------------------------------------
# 팔레트 (reference_baby.jpg 기반, 요건서 §3.4)
# ---------------------------------------------------------------------------
HOOD_BASE = "#F0A6BD"
HOOD_SHADOW = "#E084A0"
HOOD_LIGHT = "#F8C4D4"
LINING = "#FDF4EC"
LINING_SHADOW = "#EAD9C8"
DOT = "#DCEEF2"
EAR_BASE = "#EFA1B8"
EAR_TIP = "#E58AA6"
SEED = "#C98A5E"
FRILL = "#FFFFFF"
FRILL_SHADOW = "#F0E6DC"
ONESIE_BASE = "#EF9DB4"
ONESIE_SHADOW = "#DD84A0"
ONESIE_LIGHT = "#F6BACB"
BUTTON = "#EAA24C"
BUTTON_RIM = "#D2822F"
BUTTON_LIGHT = "#F4C079"
CUFF = "#FCF6F0"
CUFF_BAND = "#F2B9C8"
FOOT = "#FCF6F0"
FOOT_SHADOW = "#E8D6C8"
SKIN = "#F7CBA8"
OUTLINE = "#8A5563"   # 연속 외곽선 (하드 블랙 금지)
ZZZ = "#B9A6DC"


# ---------------------------------------------------------------------------
# 공통 SVG 유틸
# ---------------------------------------------------------------------------
def _svg(w, h, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'{body}</svg>'
    )


def _stroke(width=1.2, opacity=0.85):
    return f'stroke="{OUTLINE}" stroke-opacity="{opacity}" stroke-width="{width}" ' \
           f'stroke-linejoin="round" stroke-linecap="round"'


_DEFS = f"""
<defs>
  <radialGradient id="hood" cx="0.42" cy="0.30" r="0.80">
    <stop offset="0" stop-color="{HOOD_LIGHT}"/>
    <stop offset="0.62" stop-color="{HOOD_BASE}"/>
    <stop offset="1" stop-color="{HOOD_SHADOW}"/>
  </radialGradient>
  <linearGradient id="onesie" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{ONESIE_LIGHT}"/>
    <stop offset="0.55" stop-color="{ONESIE_BASE}"/>
    <stop offset="1" stop-color="{ONESIE_SHADOW}"/>
  </linearGradient>
  <linearGradient id="sleeve" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{ONESIE_LIGHT}"/>
    <stop offset="1" stop-color="{ONESIE_SHADOW}"/>
  </linearGradient>
  <radialGradient id="button" cx="0.4" cy="0.35" r="0.75">
    <stop offset="0" stop-color="{BUTTON_LIGHT}"/>
    <stop offset="0.7" stop-color="{BUTTON}"/>
    <stop offset="1" stop-color="{BUTTON_RIM}"/>
  </radialGradient>
  <radialGradient id="cream" cx="0.5" cy="0.42" r="0.72">
    <stop offset="0" stop-color="{LINING}"/>
    <stop offset="1" stop-color="{LINING_SHADOW}"/>
  </radialGradient>
</defs>
"""


# ---------------------------------------------------------------------------
# 곡선 유틸: Catmull-Rom -> 3차 베지어 (연속 외곽선용)
# ---------------------------------------------------------------------------
def _catmull_rom(points, closed=True):
    pts = [(float(x), float(y)) for x, y in points]
    n = len(pts)
    if n < 3:
        d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f} "
        for p in pts[1:]:
            d += f"L {p[0]:.2f} {p[1]:.2f} "
        return d + ("Z" if closed else "")

    def get(i):
        if closed:
            return pts[i % n]
        return pts[max(0, min(n - 1, i))]

    d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f} "
    seg = n if closed else n - 1
    for i in range(seg):
        p0, p1, p2, p3 = get(i - 1), get(i), get(i + 1), get(i + 2)
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        d += f"C {c1x:.2f} {c1y:.2f} {c2x:.2f} {c2y:.2f} {p2[0]:.2f} {p2[1]:.2f} "
    if closed:
        d += "Z"
    return d


def _limb_path(nodes, widths):
    """
    센터라인(root->tip) + 노드별 반폭 -> 테이퍼 곡선 팔다리 외곽선 path.
    관절(무릎/팔꿈치)에서 곡률로 굽힘, 끝은 둥근 캡. 뿌리는 몸통 아래로 숨긴다.
    """
    n = len(nodes)

    def unit(dx, dy):
        L = math.hypot(dx, dy) or 1.0
        return dx / L, dy / L

    dirs = []
    for i in range(n):
        if i == 0:
            dx, dy = nodes[1][0] - nodes[0][0], nodes[1][1] - nodes[0][1]
        elif i == n - 1:
            dx, dy = nodes[i][0] - nodes[i - 1][0], nodes[i][1] - nodes[i - 1][1]
        else:
            dx, dy = nodes[i + 1][0] - nodes[i - 1][0], nodes[i + 1][1] - nodes[i - 1][1]
        dirs.append(unit(dx, dy))

    left, right = [], []
    for i in range(n):
        dx, dy = dirs[i]
        nx, ny = -dy, dx
        w = widths[i]
        left.append((nodes[i][0] + nx * w, nodes[i][1] + ny * w))
        right.append((nodes[i][0] - nx * w, nodes[i][1] - ny * w))

    tx = nodes[-1][0] + dirs[-1][0] * widths[-1]
    ty = nodes[-1][1] + dirs[-1][1] * widths[-1]
    ring = left + [(tx, ty)] + list(reversed(right))
    return _catmull_rom(ring, closed=True)


# ---------------------------------------------------------------------------
# 파츠 프래그먼트 (전부 절대좌표, 80x120 캔버스)
# ---------------------------------------------------------------------------
def _arm_svg(a):
    d = _limb_path(a["nodes"], a["widths"])
    s = f'<path d="{d}" fill="url(#sleeve)" {_stroke()}/>'
    hx, hy = a["nodes"][-1]
    # 흰 커프 + 살짝 보이는 손
    s += (f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{a.get("cuff", 3.0):.1f}" '
          f'fill="{CUFF}" {_stroke(0.9, 0.7)}/>')
    return s


def _leg_svg(l):
    d = _limb_path(l["nodes"], l["widths"])
    s = f'<path d="{d}" fill="url(#sleeve)" {_stroke()}/>'
    fx, fy = l["nodes"][-1]
    frx, fry = l.get("foot", (5.2, 3.8))
    s += (f'<ellipse cx="{fx:.1f}" cy="{fy:.1f}" rx="{frx}" ry="{fry}" '
          f'fill="{FOOT}" {_stroke(0.9, 0.7)}/>')
    s += (f'<ellipse cx="{fx:.1f}" cy="{fy + fry * 0.5:.1f}" rx="{frx * 0.8}" '
          f'ry="{fry * 0.4}" fill="{FOOT_SHADOW}" fill-opacity="0.55"/>')
    return s


def _torso_svg(t):
    cx, top, bot, thw, mhw, bhw = t
    mid = (top + bot) / 2.0
    pts = [
        (cx - thw, top), (cx - mhw, mid), (cx - bhw, bot),
        (cx, bot + 2.0), (cx + bhw, bot), (cx + mhw, mid),
        (cx + thw, top), (cx, top - 2.0),
    ]
    d = _catmull_rom(pts, closed=True)
    s = f'<path d="{d}" fill="url(#onesie)" {_stroke()}/>'
    # 좌상단 은은한 하이라이트
    s += (f'<ellipse cx="{cx - mhw * 0.45:.1f}" cy="{top + (bot - top) * 0.28:.1f}" '
          f'rx="{mhw * 0.5:.1f}" ry="{(bot - top) * 0.22:.1f}" '
          f'fill="{ONESIE_LIGHT}" fill-opacity="0.45"/>')
    return s


def _hood_svg(head, anchor):
    cx, cy, rx, ry = head
    acx, acy, aw, ah = anchor
    s = ""
    # 귀 (후드 뒤 -> 크라운 위로 돌출)
    edx = rx * 0.60
    ey = cy - ry * 0.82
    for sgn in (-1, 1):
        ex = cx + sgn * edx
        s += (f'<ellipse cx="{ex:.1f}" cy="{ey:.1f}" rx="6.4" ry="8.6" '
              f'fill="{EAR_BASE}" {_stroke()}/>')
        s += (f'<ellipse cx="{ex:.1f}" cy="{ey - 1.6:.1f}" rx="3.2" ry="4.6" '
              f'fill="{EAR_TIP}"/>')
    # 후드 외피
    s += f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" ' \
         f'fill="url(#hood)" {_stroke()}/>'
    # 물방울 도트 (핑크 링 위, 크림 개구부 밖)
    for fx, fy in [(-0.47, -0.76), (0.47, -0.76), (-0.73, -0.42),
                   (0.73, -0.42), (0.0, -0.90)]:
        s += (f'<circle cx="{cx + fx * rx:.1f}" cy="{cy + fy * ry:.1f}" '
              f'r="1.7" fill="{DOT}"/>')
    # 이마 딸기씨 패치
    s += (f'<ellipse cx="{cx + 0.34 * rx:.1f}" cy="{cy - 0.60 * ry:.1f}" '
          f'rx="2.3" ry="1.8" fill="{SEED}"/>')
    # 크림 안감 개구부 (얼굴 미등록 시 이 크림이 보인다. 얼굴 PNG 는 이 위에 합성)
    s += (f'<ellipse cx="{acx:.1f}" cy="{acy:.1f}" rx="{aw / 2 + 2:.1f}" '
          f'ry="{ah / 2 + 2:.1f}" fill="url(#cream)" {_stroke(0.9, 0.5)}/>')
    return s


def _frill_svg(f):
    cx, y, hw = f
    s = (f'<rect x="{cx - hw:.1f}" y="{y - 4:.1f}" width="{2 * hw:.1f}" '
         f'height="7" rx="3.2" fill="{FRILL}" {_stroke(0.9, 0.6)}/>')
    xs = [cx + off for off in (-hw * 0.72, -hw * 0.36, 0.0, hw * 0.36, hw * 0.72)]
    for x in xs:
        s += (f'<circle cx="{x:.1f}" cy="{y + 1.5:.1f}" r="4.6" '
              f'fill="{FRILL}" {_stroke(0.8, 0.5)}/>')
    return s


def _button_svg(b):
    x, y = b
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="url(#button)" '
            f'{_stroke(0.8, 0.6)}/>'
            f'<circle cx="{x - 1.1:.1f}" cy="{y - 1.1:.1f}" r="1.0" '
            f'fill="{BUTTON_LIGHT}" fill-opacity="0.85"/>')


# ---------------------------------------------------------------------------
# 포즈 조립
# ---------------------------------------------------------------------------
def _compose(p):
    parts = []
    # 다리 (몸통 뒤)
    for leg in p["legs"]:
        parts.append(_leg_svg(leg))
    # 뒤 팔
    for a in p["arms"]:
        if a["z"] == "back":
            parts.append(_arm_svg(a))
    # 몸통
    parts.append(_torso_svg(p["torso"]))
    # 앞 팔
    for a in p["arms"]:
        if a["z"] == "front":
            parts.append(_arm_svg(a))
    # 후드/머리
    parts.append(_hood_svg(p["head"], p["anchor"]))
    # 프릴 칼라 (목 연결부·팔 뿌리 덮음)
    parts.append(_frill_svg(p["frill"]))
    # 단추 (프릴 아래 몸통)
    for b in p["buttons"]:
        parts.append(_button_svg(b))
    # 머리 위로 들린 팔 (drag/fall)
    for a in p["arms"]:
        if a["z"] == "over":
            parts.append(_arm_svg(a))
    return _svg(PET_W, PET_H, _DEFS + "".join(parts))


def _mirror(p):
    """x 좌표를 40 기준으로 반전한 좌우 대칭 포즈(위상 반대)."""
    def mx(x):
        return 80.0 - x

    def mnodes(nodes):
        return [(mx(x), y) for x, y in nodes]

    cx, cy, rx, ry = p["head"]
    acx, acy, aw, ah = p["anchor"]
    fcx, fy, fhw = p["frill"]
    tcx, ttop, tbot, thw, tmhw, tbhw = p["torso"]
    return {
        "head": (mx(cx), cy, rx, ry),
        "anchor": (mx(acx), acy, aw, ah),
        "torso": (mx(tcx), ttop, tbot, thw, tmhw, tbhw),
        "frill": (mx(fcx), fy, fhw),
        "buttons": [(mx(x), y) for x, y in p["buttons"]],
        "legs": [dict(l, nodes=mnodes(l["nodes"])) for l in p["legs"]],
        "arms": [dict(a, nodes=mnodes(a["nodes"])) for a in p["arms"]],
    }


def _sink(p, dy):
    """상체(머리/몸통/프릴/팔/단추)만 dy 만큼 내린 숨쉬기 프레임 (다리·발 고정)."""
    cx, cy, rx, ry = p["head"]
    acx, acy, aw, ah = p["anchor"]
    fcx, fy, fhw = p["frill"]
    tcx, ttop, tbot, thw, tmhw, tbhw = p["torso"]

    def shift(nodes):
        return [(x, y + dy) for x, y in nodes]

    return {
        "head": (cx, cy + dy, rx, ry),
        "anchor": (acx, acy + dy, aw, ah),
        "torso": (tcx, ttop + dy, tbot + dy, thw, tmhw, tbhw),
        "frill": (fcx, fy + dy, fhw),
        "buttons": [(x, y + dy) for x, y in p["buttons"]],
        "legs": p["legs"],
        "arms": [dict(a, nodes=shift(a["nodes"])) for a in p["arms"]],
    }


LEG_W = [7.0, 6.0, 5.0]
ARM_W = [6.0, 5.0, 4.0]


def _pose_idle0():
    return {
        "head": (40, 38, 30, 29),
        "anchor": (40, 41, 44, 44),
        "torso": (40, 64, 98, 19, 20, 17),
        "frill": (40, 68, 25),
        "buttons": [(40, 78), (40, 86), (40, 94)],
        "legs": [
            {"nodes": [(34, 96), (33, 106), (33, 114)], "widths": LEG_W},
            {"nodes": [(46, 96), (47, 106), (47, 114)], "widths": LEG_W},
        ],
        "arms": [
            {"nodes": [(27, 68), (22, 80), (20, 90)], "widths": ARM_W, "z": "back"},
            {"nodes": [(53, 68), (58, 80), (60, 90)], "widths": ARM_W, "z": "back"},
        ],
    }


def _pose_walk0():
    # 접지A: 왼다리 들어올림(무릎 굽힘·발 뜸) + 오른다리 곧게 딛기(접지). 교차 없음.
    #        오른팔 굽혀 올림 + 왼팔 내려 뒤로 = 대각 스윙. 몸통 낮음(접지=바운스 저점).
    return {
        "head": (40, 40, 30, 29),
        "anchor": (40, 43, 44, 44),
        "torso": (40, 66, 98, 18, 20, 17),
        "frill": (40, 70, 24),
        "buttons": [(40, 80), (40, 88), (40, 96)],
        "legs": [
            # 왼다리: 무릎 바깥으로 굽히고 발 들어올림(y=108, 접지발보다 6px 위). 자기 쪽 유지.
            {"nodes": [(36, 97), (32, 105), (37, 109)], "widths": LEG_W},
            # 오른다리: 곧게 뻗어 바닥 딛기(y=115).
            {"nodes": [(46, 97), (47, 107), (47, 115)], "widths": LEG_W},
        ],
        "arms": [
            # 왼팔: 곧게 내려 손 낮게(y=96) + 몸통 좌측 실루엣 밖으로 살짝 노출.
            {"nodes": [(27, 68), (22, 83), (19, 96)], "widths": ARM_W, "z": "back"},
            # 오른팔: 팔꿈치 굽혀 손을 가슴 높이(y=76)로 펌핑 + 우측 실루엣 밖으로 노출.
            {"nodes": [(54, 68), (61, 72), (62, 77)], "widths": ARM_W, "z": "front"},
        ],
    }


def _pose_walk1():
    # 패싱: 두 다리 모아 곧게, 몸 최고점(바운스 상승 3px), 팔 중립.
    return {
        "head": (40, 37, 30, 29),
        "anchor": (40, 40, 44, 44),
        "torso": (40, 63, 97, 19, 20, 17),
        "frill": (40, 67, 25),
        "buttons": [(40, 77), (40, 85), (40, 93)],
        "legs": [
            {"nodes": [(38, 95), (38, 105), (38, 114)], "widths": LEG_W},
            {"nodes": [(43, 95), (43, 105), (43, 114)], "widths": LEG_W},
        ],
        "arms": [
            {"nodes": [(27, 67), (24, 79), (23, 90)], "widths": ARM_W, "z": "back"},
            {"nodes": [(54, 67), (57, 79), (58, 90)], "widths": ARM_W, "z": "back"},
        ],
    }


def _pose_sleep0():
    # 앉아 조는 자세: 엉덩이 바닥, 다리 앞으로, 몸 앞으로 웅크림 (idle 높이의 ~80%)
    return {
        "head": (40, 52, 28, 27),
        "anchor": (40, 55, 44, 44),
        "torso": (40, 76, 100, 18, 19, 18),
        "frill": (40, 79, 23),
        "buttons": [(40, 88), (40, 95)],
        "legs": [
            {"nodes": [(35, 98), (28, 105), (23, 109)], "widths": LEG_W,
             "foot": (5.5, 4.2)},
            {"nodes": [(45, 98), (52, 105), (57, 109)], "widths": LEG_W,
             "foot": (5.5, 4.2)},
        ],
        "arms": [
            {"nodes": [(30, 80), (26, 90), (29, 97)], "widths": ARM_W, "z": "front"},
            {"nodes": [(50, 80), (54, 90), (51, 97)], "widths": ARM_W, "z": "front"},
        ],
    }


def _pose_drag0():
    # 매달림A: 머리 위쪽이 잡힌 듯 몸이 아래로 늘어짐(길게), 팔 위·바깥, 다리 왼쪽 흔들
    return {
        "head": (40, 30, 29, 28),
        "anchor": (40, 33, 44, 44),
        "torso": (40, 57, 98, 16, 17, 14),      # idle 보다 길게 늘인 실루엣
        "frill": (40, 60, 22),
        "buttons": [(40, 70), (40, 80), (40, 90)],
        "legs": [
            {"nodes": [(37, 96), (33, 105), (29, 113)], "widths": [6, 5, 4]},
            {"nodes": [(44, 96), (40, 105), (36, 113)], "widths": [6, 5, 4]},
        ],
        "arms": [
            {"nodes": [(30, 60), (18, 47), (9, 35)], "widths": ARM_W, "z": "over"},
            {"nodes": [(52, 60), (62, 47), (70, 35)], "widths": ARM_W, "z": "over"},
        ],
    }


def _pose_drag1():
    # 매달림B: 다리 오른쪽으로 흔들 (팔·몸통·머리는 drag0 과 동일)
    p = _pose_drag0()
    p = dict(p)
    p["legs"] = [
        {"nodes": [(37, 96), (41, 105), (45, 113)], "widths": [6, 5, 4]},
        {"nodes": [(44, 96), (48, 105), (52, 113)], "widths": [6, 5, 4]},
    ]
    return p


def _pose_fall0():
    # 낙하 허우적A: 팔 위·바깥 벌림, 다리 아래·바깥 벌림 (동적 실루엣)
    return {
        "head": (40, 40, 29, 28),
        "anchor": (40, 42, 44, 44),
        "torso": (40, 64, 94, 18, 19, 16),
        "frill": (40, 67, 24),
        "buttons": [(40, 76), (40, 84), (40, 92)],
        "legs": [
            {"nodes": [(34, 92), (28, 103), (21, 113)], "widths": LEG_W},
            {"nodes": [(46, 92), (52, 103), (59, 113)], "widths": LEG_W},
        ],
        "arms": [
            {"nodes": [(29, 66), (18, 55), (9, 45)], "widths": ARM_W, "z": "over"},
            {"nodes": [(51, 66), (62, 55), (71, 45)], "widths": ARM_W, "z": "over"},
        ],
    }


def _pose_fall1():
    # 낙하 허우적B: 팔다리 위상 반대 (팔 아래·바깥, 다리 모아 굽힘)
    return {
        "head": (40, 41, 29, 28),
        "anchor": (40, 43, 44, 44),
        "torso": (40, 65, 95, 18, 19, 16),
        "frill": (40, 68, 24),
        "buttons": [(40, 77), (40, 85), (40, 93)],
        "legs": [
            {"nodes": [(35, 93), (31, 102), (28, 111)], "widths": LEG_W},
            {"nodes": [(45, 93), (49, 102), (52, 111)], "widths": LEG_W},
        ],
        "arms": [
            {"nodes": [(29, 70), (19, 80), (11, 89)], "widths": ARM_W, "z": "front"},
            {"nodes": [(51, 70), (61, 80), (69, 89)], "widths": ARM_W, "z": "front"},
        ],
    }


def _pose_land():
    # 착지 순간 쪼그림: 몸 낮고 넓게, 다리 넓게 굽힘, 팔 균형 벌림
    return {
        "head": (40, 44, 29, 28),
        "anchor": (40, 46, 44, 44),
        "torso": (40, 68, 92, 20, 21, 19),
        "frill": (40, 71, 25),
        "buttons": [(40, 80), (40, 88)],
        "legs": [
            {"nodes": [(33, 90), (25, 98), (23, 107)], "widths": [8, 7, 6],
             "foot": (5.8, 4.2)},
            {"nodes": [(47, 90), (55, 98), (57, 107)], "widths": [8, 7, 6],
             "foot": (5.8, 4.2)},
        ],
        "arms": [
            {"nodes": [(27, 72), (18, 78), (12, 84)], "widths": ARM_W, "z": "front"},
            {"nodes": [(53, 72), (62, 78), (68, 84)], "widths": ARM_W, "z": "front"},
        ],
    }


def _build_poses():
    idle0 = _pose_idle0()
    walk0 = _pose_walk0()
    walk1 = _pose_walk1()
    drag0 = _pose_drag0()
    sleep0 = _pose_sleep0()
    return {
        "pose_idle0": idle0,
        "pose_idle1": _sink(idle0, 1),
        "pose_walk0": walk0,
        "pose_walk1": walk1,
        "pose_walk2": _mirror(walk0),           # 접지B = 접지A 좌우 반전
        "pose_walk3": _mirror(walk1),           # 패싱, 팔 위상 반대
        "pose_sleep0": sleep0,
        "pose_sleep1": _sink(sleep0, 1),
        "pose_drag0": drag0,
        "pose_drag1": _pose_drag1(),
        "pose_fall0": _pose_fall0(),
        "pose_fall1": _pose_fall1(),
        "pose_land": _pose_land(),
    }


POSES = _build_poses()

# 얼굴 개구부 앵커 (렌더러가 얼굴 합성에 사용): 프레임별 (cx, cy, w, h)
FACE_ANCHORS = {key: tuple(p["anchor"]) for key, p in POSES.items()}


def build_zzz():
    """파스텔 'Zzz' 말풍선. 폰트 의존 회피 위해 path 로 Z 획. 36x24."""

    def z(x, y, s):
        return (
            f'<path d="M {x} {y} L {x + s} {y} L {x} {y + s} L {x + s} {y + s}" '
            f'fill="none" stroke="{ZZZ}" stroke-width="{max(1.4, s * 0.22):.1f}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )

    body = z(4, 14, 6) + z(14, 6, 10) + z(27, 2, 4)
    return _svg(36, 24, body)


# ---------------------------------------------------------------------------
# 계약: 13 포즈 + zzz
# ---------------------------------------------------------------------------
def build_asset_svgs():
    svgs = {key: _compose(p) for key, p in POSES.items()}
    svgs["zzz"] = build_zzz()
    return svgs


_NATIVE = {key: (PET_W, PET_H) for key in POSES}
_NATIVE["zzz"] = (36, 24)

# v1 파츠 키 (재생성 시 정리)
_LEGACY_KEYS = [
    "body_idle", "body_walk0", "body_walk1", "body_sleep", "body_drag",
    "arm_l", "arm_r", "arm_l_up", "arm_r_up",
    "leg_0", "leg_1", "tail_0", "tail_1",
]


# ---------------------------------------------------------------------------
# 래스터라이즈 (QApplication 없이 QtSvg → QImage → PIL)
# ---------------------------------------------------------------------------
def rasterize(svg, w, h):
    """SVG 문자열을 (w, h) RGBA PIL.Image 로 래스터라이즈. 4x 슈퍼샘플 후 축소."""
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))

    big = QImage(w * SCALE, h * SCALE, QImage.Format_RGBA8888)
    big.fill(Qt.transparent)
    painter = QPainter(big)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()

    small = big.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    small.save(buf, "PNG")
    buf.close()
    return Image.open(io.BytesIO(bytes(ba))).convert("RGBA")


def _cleanup_legacy():
    for key in _LEGACY_KEYS:
        path = os.path.join(ASSETS_DIR, f"{key}.png")
        if os.path.exists(path):
            os.remove(path)
            print(f"  removed legacy: {key}.png")


def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    print("에셋 생성 중...")
    _cleanup_legacy()
    svgs = build_asset_svgs()
    for key, svg in svgs.items():
        w, h = _NATIVE[key]
        img = rasterize(svg, w, h)
        img.save(os.path.join(ASSETS_DIR, f"{key}.png"))
        print(f"  saved: {key}.png")
    print("완료.")


if __name__ == "__main__":
    main()
