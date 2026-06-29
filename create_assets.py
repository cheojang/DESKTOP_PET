"""
에셋 자동 생성기: 몸통/팔/다리/꼬리 PNG를 4x 슈퍼샘플링으로 생성.
python create_assets.py 로 1회 실행.
"""

import os
from PIL import Image, ImageDraw

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
SCALE = 4       # 슈퍼샘플링 배율
BODY_W = 60     # 최종 몸통 너비 (px)
BODY_H = 80     # 최종 몸통 높이


def _canvas(w, h):
    return Image.new("RGBA", (w * SCALE, h * SCALE), (0, 0, 0, 0))


def _save(img, name):
    out = img.resize((img.width // SCALE, img.height // SCALE), Image.LANCZOS)
    path = os.path.join(ASSETS_DIR, name)
    out.save(path)
    print(f"  saved: {name}")


def make_body_idle():
    img = _canvas(BODY_W, BODY_H)
    d = ImageDraw.Draw(img)
    S = SCALE
    # 몸통 타원
    d.ellipse([10*S, 10*S, 50*S, 70*S], fill=(100, 180, 255, 230))
    # 배 하이라이트
    d.ellipse([18*S, 20*S, 42*S, 55*S], fill=(150, 210, 255, 120))
    _save(img, "body_idle.png")


def make_body_walk(frame):
    """frame: 0 또는 1 (다리 위상 차이)"""
    img = _canvas(BODY_W, BODY_H)
    d = ImageDraw.Draw(img)
    S = SCALE
    offset = 2 * S if frame == 0 else -2 * S
    d.ellipse([10*S, 10*S + offset, 50*S, 70*S + offset], fill=(100, 180, 255, 230))
    d.ellipse([18*S, 20*S + offset, 42*S, 55*S + offset], fill=(150, 210, 255, 120))
    _save(img, f"body_walk{frame}.png")


def make_body_sleep():
    img = _canvas(BODY_W, BODY_H)
    d = ImageDraw.Draw(img)
    S = SCALE
    # 앉은 자세 (납작한 타원)
    d.ellipse([8*S, 25*S, 52*S, 72*S], fill=(100, 180, 255, 230))
    d.ellipse([16*S, 33*S, 44*S, 62*S], fill=(150, 210, 255, 120))
    _save(img, "body_sleep.png")


def make_body_drag():
    img = _canvas(BODY_W, BODY_H)
    d = ImageDraw.Draw(img)
    S = SCALE
    # 발버둥 (찌그러진 모양)
    d.ellipse([5*S, 5*S, 55*S, 75*S], fill=(100, 180, 255, 230))
    d.ellipse([14*S, 15*S, 46*S, 58*S], fill=(150, 210, 255, 120))
    _save(img, "body_drag.png")


def make_arm(side, raised=False):
    """side: 'l' or 'r', raised: drag 상태"""
    img = _canvas(20, 30)
    d = ImageDraw.Draw(img)
    S = SCALE
    color = (80, 160, 240, 220)
    if raised:
        d.ellipse([2*S, 0, 18*S, 28*S], fill=color)
    else:
        d.ellipse([2*S, 4*S, 18*S, 28*S], fill=color)
    name = f"arm_{side}{'_up' if raised else ''}.png"
    _save(img, name)


def make_leg(phase):
    """phase: 0 or 1"""
    img = _canvas(16, 24)
    d = ImageDraw.Draw(img)
    S = SCALE
    offset = 3 * S if phase == 0 else -3 * S
    d.ellipse([2*S, 2*S + offset, 14*S, 22*S + offset], fill=(80, 150, 230, 220))
    _save(img, f"leg_{phase}.png")


def make_tail(phase):
    """phase: 0 or 1"""
    img = _canvas(24, 30)
    d = ImageDraw.Draw(img)
    S = SCALE
    pts_0 = [(12*S, 0), (22*S, 10*S), (20*S, 22*S), (10*S, 28*S), (4*S, 20*S)]
    pts_1 = [(12*S, 0), (20*S, 8*S), (22*S, 20*S), (14*S, 28*S), (4*S, 22*S)]
    pts = pts_0 if phase == 0 else pts_1
    d.polygon(pts, fill=(70, 140, 220, 210))
    _save(img, f"tail_{phase}.png")


def make_zzz():
    """수면 말풍선"""
    img = _canvas(36, 24)
    d = ImageDraw.Draw(img)
    S = SCALE
    d.text((4*S, 4*S), "Zzz", fill=(180, 200, 255, 200))
    _save(img, "zzz.png")


def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    print("에셋 생성 중...")
    make_body_idle()
    make_body_walk(0)
    make_body_walk(1)
    make_body_sleep()
    make_body_drag()
    make_arm("l")
    make_arm("r")
    make_arm("l", raised=True)
    make_arm("r", raised=True)
    make_leg(0)
    make_leg(1)
    make_tail(0)
    make_tail(1)
    make_zzz()
    print("완료.")


if __name__ == "__main__":
    main()
