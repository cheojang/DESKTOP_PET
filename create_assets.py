"""
에셋 자동 생성기 (핑크 후드 아기 스타일).

각 파츠를 손으로 쓴 SVG(1.2 Tiny 서브셋)로 그리고 PySide6.QtSvg 로 래스터라이즈한다.
신규 의존성 없음 (QtSvg 는 PySide6 에 포함). QApplication 은 만들지 않는다.
블러 필터는 QtSvg 미지원 → 소프트 셰이딩은 그라데이션 + 반투명 레이어로만 표현.

python create_assets.py 로 1회 실행. PNG 는 assets/ 에 저장된다.
"""

import io
import os

from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
SCALE = 4       # 슈퍼샘플링 배율

# ---------------------------------------------------------------------------
# 팔레트 (reference_baby.jpg 기반, 아키텍트 브리프 §1)
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
OUTLINE = "#8A5563"   # 아주 옅은 플럼 저알파 외곽선 (하드 블랙 금지)
ZZZ = "#B9A6DC"


# ---------------------------------------------------------------------------
# 공통 SVG 유틸
# ---------------------------------------------------------------------------
def _svg(w, h, body):
    """viewBox w x h 인 SVG 문서 문자열."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'{body}</svg>'
    )


def _stroke(width=0.6, opacity=0.28):
    return f'stroke="{OUTLINE}" stroke-opacity="{opacity}" stroke-width="{width}"'


_BODY_DEFS = f"""
<defs>
  <radialGradient id="hood" cx="0.42" cy="0.30" r="0.75">
    <stop offset="0" stop-color="{HOOD_LIGHT}"/>
    <stop offset="0.65" stop-color="{HOOD_BASE}"/>
    <stop offset="1" stop-color="{HOOD_SHADOW}"/>
  </radialGradient>
  <linearGradient id="onesie" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{ONESIE_LIGHT}"/>
    <stop offset="0.55" stop-color="{ONESIE_BASE}"/>
    <stop offset="1" stop-color="{ONESIE_SHADOW}"/>
  </linearGradient>
  <radialGradient id="button" cx="0.4" cy="0.35" r="0.75">
    <stop offset="0" stop-color="{BUTTON_LIGHT}"/>
    <stop offset="0.7" stop-color="{BUTTON}"/>
    <stop offset="1" stop-color="{BUTTON_RIM}"/>
  </radialGradient>
  <linearGradient id="cream" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{LINING}"/>
    <stop offset="1" stop-color="{LINING_SHADOW}"/>
  </linearGradient>
  <linearGradient id="sleeve" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{ONESIE_LIGHT}"/>
    <stop offset="1" stop-color="{ONESIE_SHADOW}"/>
  </linearGradient>
</defs>
"""


# ---------------------------------------------------------------------------
# 파츠 프래그먼트
# ---------------------------------------------------------------------------
def _hood():
    """핑크 후드(귀 2개 + 도트무늬) + 크림 안감 링. 얼굴 개구부는 렌더러가 face 로 덮는다."""
    dots = ""
    for cx, cy in [(6, 13), (8, 26), (52, 15), (54, 28), (12, 5), (48, 6), (30, 1)]:
        dots += f'<circle cx="{cx}" cy="{cy}" r="1.7" fill="{DOT}"/>'
    return f"""
  <!-- 후드 외피 -->
  <ellipse cx="30" cy="15" rx="29" ry="23" fill="url(#hood)" {_stroke()}/>
  <!-- 크림 안감 링 -->
  <ellipse cx="30" cy="18" rx="24" ry="21" fill="url(#cream)"/>
  {dots}
  <!-- 이마 딸기씨 패치 -->
  <ellipse cx="43" cy="6" rx="2.4" ry="1.9" fill="{SEED}"/>
  <!-- 귀 (정수리 좌우 둥근 돌기, 크라운 위로 노출) -->
  <ellipse cx="19" cy="2" rx="6" ry="9" fill="{EAR_BASE}" {_stroke()}/>
  <ellipse cx="41" cy="2" rx="6" ry="9" fill="{EAR_BASE}" {_stroke()}/>
  <ellipse cx="19" cy="0.5" rx="3.2" ry="4.6" fill="{EAR_TIP}"/>
  <ellipse cx="41" cy="0.5" rx="3.2" ry="4.6" fill="{EAR_TIP}"/>
"""


def _frill(cy=40):
    """목 둘레 흰 스캘럽 프릴 칼라."""
    scallops = ""
    for cx in [10, 19, 28, 37, 46]:
        scallops += (
            f'<circle cx="{cx}" cy="{cy + 1}" r="5" '
            f'fill="{FRILL}" {_stroke(0.5, 0.2)}/>'
        )
    return (
        f'<rect x="7" y="{cy - 5}" width="46" height="7" rx="3" '
        f'fill="{FRILL}"/>{scallops}'
    )


def _onesie(top=40, bottom=80):
    """핑크 온지 몸통 + 하이라이트 + 앰버 단추 3개."""
    h = bottom - top
    buttons = ""
    step = h * 0.24
    y0 = top + h * 0.36
    for i in range(3):
        cy = y0 + i * step
        buttons += (
            f'<circle cx="30" cy="{cy:.1f}" r="3.4" fill="url(#button)" '
            f'{_stroke(0.4, 0.25)}/>'
            f'<circle cx="28.7" cy="{cy - 1.1:.1f}" r="1.0" '
            f'fill="{BUTTON_LIGHT}" fill-opacity="0.8"/>'
        )
    return f"""
  <rect x="6" y="{top}" width="48" height="{h}" rx="16"
        fill="url(#onesie)" {_stroke()}/>
  <ellipse cx="21" cy="{top + 12}" rx="12" ry="9"
           fill="{ONESIE_LIGHT}" fill-opacity="0.45"/>
  {buttons}
"""


def _body(transform=""):
    inner = _hood() + _onesie() + _frill()
    if transform:
        inner = f'<g transform="{transform}">{inner}</g>'
    return _svg(60, 80, _BODY_DEFS + inner)


def _center_transform(sx, sy, dx=0.0, dy=0.0, cx=30.0, cy=45.0):
    """중심(cx,cy) 기준 스케일 + 평행이동."""
    return (
        f'translate({cx + dx},{cy + dy}) scale({sx},{sy}) translate({-cx},{-cy})'
    )


def build_body_idle():
    return _body()


def build_body_walk(frame):
    # 수직 바운스 오프셋만
    dy = -1.5 if frame == 0 else 1.5
    return _body(_center_transform(1.0, 1.0, dy=dy))


def build_body_sleep():
    # 앉은 납작 실루엣 (아래로 내려 눌린 느낌)
    return _body(_center_transform(1.06, 0.9, dy=5.0))


def build_body_drag():
    # 살짝 늘어난 실루엣
    return _body(_center_transform(0.95, 1.07, dy=-3.0))


def build_arm(side, raised=False):
    """짧은 핑크 팔 + 흰 커프 + 작은 손. side 는 색만 참조(대칭). 20x30."""
    if raised:
        # 손을 위로: 소매 하단→상단, 커프/손 위쪽
        sleeve = '<rect x="4" y="8" width="12" height="20" rx="6" fill="url(#sleeve)" %s/>' % _stroke()
        band = '<rect x="3" y="7" width="14" height="4" rx="2" fill="%s"/>' % CUFF_BAND
        cuff = '<rect x="3" y="4" width="14" height="6" rx="3" fill="%s" %s/>' % (CUFF, _stroke(0.5, 0.2))
        hand = '<circle cx="10" cy="4" r="3.4" fill="%s" %s/>' % (SKIN, _stroke(0.4, 0.2))
    else:
        sleeve = '<rect x="4" y="2" width="12" height="20" rx="6" fill="url(#sleeve)" %s/>' % _stroke()
        band = '<rect x="3" y="19" width="14" height="4" rx="2" fill="%s"/>' % CUFF_BAND
        cuff = '<rect x="3" y="20" width="14" height="6" rx="3" fill="%s" %s/>' % (CUFF, _stroke(0.5, 0.2))
        hand = '<circle cx="10" cy="26" r="3.4" fill="%s" %s/>' % (SKIN, _stroke(0.4, 0.2))
    return _svg(20, 30, _BODY_DEFS + sleeve + band + cuff + hand)


def build_leg(phase):
    """핑크 다리 + 흰 발싸개. phase 로 발끝 위상차. 16x24."""
    toe_dx = -1 if phase == 0 else 2
    leg = '<rect x="4" y="0" width="9" height="15" rx="4.5" fill="url(#sleeve)" %s/>' % _stroke()
    sole = (
        '<ellipse cx="%d" cy="18" rx="7" ry="5" fill="%s" %s/>'
        % (8 + toe_dx, FOOT, _stroke(0.5, 0.2))
    )
    shade = (
        '<ellipse cx="%d" cy="20.5" rx="6.5" ry="2.2" fill="%s" fill-opacity="0.6"/>'
        % (8 + toe_dx, FOOT_SHADOW)
    )
    return _svg(16, 24, _BODY_DEFS + leg + shade + sole)


def build_tail(phase):
    """은은한 온지 뒷자락(저알파). 레퍼런스엔 꼬리가 없으므로 옷 뒷단처럼 살짝만. 24x30."""
    sway = 0 if phase == 0 else 2
    return _svg(24, 30, _BODY_DEFS + (
        '<ellipse cx="%d" cy="16" rx="9" ry="12" fill="url(#sleeve)" '
        'fill-opacity="0.55"/>' % (12 + sway)
    ))


def build_zzz():
    """파스텔 'Zzz' 말풍선. 폰트 의존 회피 위해 path 로 Z 획을 그린다. 36x24."""

    def z(x, y, s):
        # 상단 가로 - 대각선 - 하단 가로
        return (
            f'<path d="M {x} {y} L {x + s} {y} L {x} {y + s} L {x + s} {y + s}" '
            f'fill="none" stroke="{ZZZ}" stroke-width="{max(1.4, s * 0.22):.1f}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )

    # 가운데 Z 의 대각선이 스프라이트 중심(18,12)을 지나도록 배치
    body = z(4, 14, 6) + z(14, 6, 10) + z(27, 2, 4)
    return _svg(36, 24, body)


# ---------------------------------------------------------------------------
# 계약: 14개 키 → SVG 문자열
# ---------------------------------------------------------------------------
def build_asset_svgs():
    return {
        "body_idle": build_body_idle(),
        "body_walk0": build_body_walk(0),
        "body_walk1": build_body_walk(1),
        "body_sleep": build_body_sleep(),
        "body_drag": build_body_drag(),
        "arm_l": build_arm("l"),
        "arm_r": build_arm("r"),
        "arm_l_up": build_arm("l", raised=True),
        "arm_r_up": build_arm("r", raised=True),
        "leg_0": build_leg(0),
        "leg_1": build_leg(1),
        "tail_0": build_tail(0),
        "tail_1": build_tail(1),
        "zzz": build_zzz(),
    }


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

    small = big.scaled(
        w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
    )

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    small.save(buf, "PNG")
    buf.close()
    return Image.open(io.BytesIO(bytes(ba))).convert("RGBA")


# 파일명 = 키 + ".png", 네이티브 크기
_NATIVE = {
    "body_idle": (60, 80), "body_walk0": (60, 80), "body_walk1": (60, 80),
    "body_sleep": (60, 80), "body_drag": (60, 80),
    "arm_l": (20, 30), "arm_r": (20, 30), "arm_l_up": (20, 30), "arm_r_up": (20, 30),
    "leg_0": (16, 24), "leg_1": (16, 24),
    "tail_0": (24, 30), "tail_1": (24, 30),
    "zzz": (36, 24),
}


def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    print("에셋 생성 중...")
    svgs = build_asset_svgs()
    for key, svg in svgs.items():
        w, h = _NATIVE[key]
        img = rasterize(svg, w, h)
        img.save(os.path.join(ASSETS_DIR, f"{key}.png"))
        print(f"  saved: {key}.png")
    print("완료.")


if __name__ == "__main__":
    main()
