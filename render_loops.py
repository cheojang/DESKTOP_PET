"""
루핑 모션 검증용 GIF 생성기.

레퍼런스(Seedance 2.0 image->video 프롬프트)의 루프 원칙 검증:
  - 끝=시작: 각 상태 GIF가 이음새 없이 반복되는가
  - 카메라 고정: 캔버스/스케일 불변, 발 접지 안정
  - 주체만 움직임: 배경 투명, 드리프트 없음

출력:
  _workspace/walk_loop.gif       (걷기 4프레임 루프, 히어로)
  _workspace/all_states.gif      (5상태 동시 루프 4프레임)
더미 얼굴은 임시로 faces/ 에 넣었다가 삭제한다.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = os.path.dirname(os.path.abspath(__file__))   # 리포 루트 (이 파일이 루트에 위치)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from PIL import Image, ImageDraw  # noqa: E402
import face_warp  # noqa: E402
import create_assets  # noqa: E402
from pet_state_machine import IDLE, WALK, SLEEP, DRAG, FALL  # noqa: E402

WS = os.path.join(_ROOT, "_workspace")
os.makedirs(WS, exist_ok=True)
SCALE = 3
CW, CH = 80 * SCALE, 120 * SCALE


def _dummy_faces():
    os.makedirs(face_warp.FACES_DIR, exist_ok=True)
    created = []
    base = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.ellipse([6, 6, 54, 54], fill=(247, 203, 168, 255))
    d.ellipse([18, 24, 27, 34], fill=(70, 50, 40, 255))
    d.ellipse([33, 24, 42, 34], fill=(70, 50, 40, 255))
    d.ellipse([13, 34, 23, 42], fill=(255, 170, 170, 160))
    d.ellipse([37, 34, 47, 42], fill=(255, 170, 170, 160))
    d.arc([21, 34, 39, 50], start=10, end=170, fill=(150, 70, 70, 255), width=3)
    for expr in face_warp.EXPRESSIONS:
        p = os.path.join(face_warp.FACES_DIR, f"face_{expr}.png")
        base.save(p)
        created.append(p)
    return created


def _bg(img):
    """투명 프레임을 흰 배경 위에 얹어 GIF(무투명) 프레임으로."""
    canvas = Image.new("RGBA", img.size, (250, 250, 252, 255))
    canvas.alpha_composite(img)
    return canvas.convert("RGB")


def _up(img):
    return img.resize((CW, CH), Image.NEAREST)


def main():
    from pet_renderer import PetRenderer
    created = _dummy_faces()
    try:
        ren = PetRenderer()

        def frame_at(state, tick):
            ren._frame = tick
            return ren.render(state, 1, 2.0)

        # 각 상태의 distinct pose 이미지 (더미 얼굴, 오른쪽)
        # walk step=8/2=4 틱, idle //24, sleep //36(+zzz //30), drag/fall //8
        idle = [frame_at(IDLE, 0), frame_at(IDLE, 24)]
        walk = [frame_at(WALK, t) for t in (0, 4, 8, 12)]
        sleep = [frame_at(SLEEP, 0), frame_at(SLEEP, 60)]   # 둘 다 zzz on
        drag = [frame_at(DRAG, 0), frame_at(DRAG, 8)]
        fall = [frame_at(FALL, 0), frame_at(FALL, 8)]

        # 1) 걷기 히어로 루프 (4프레임)
        gif_frames = [_bg(_up(f)) for f in walk]
        gif_frames[0].save(
            os.path.join(WS, "walk_loop.gif"), save_all=True,
            append_images=gif_frames[1:], duration=140, loop=0, disposal=2)
        print("saved: walk_loop.gif")

        # 2) 5상태 동시 루프 (LCM=4 프레임). 2포즈 상태는 2프레임마다, walk는 매프레임.
        idx = {
            "idle":  [0, 0, 1, 1],
            "walk":  [0, 1, 2, 3],
            "sleep": [0, 0, 1, 1],
            "drag":  [0, 1, 0, 1],
            "fall":  [0, 1, 0, 1],
        }
        pools = {"idle": idle, "walk": walk, "sleep": sleep, "drag": drag, "fall": fall}
        order = ["idle", "walk", "sleep", "drag", "fall"]
        labels = {"idle": "IDLE", "walk": "WALK", "sleep": "SLEEP",
                  "drag": "DRAG", "fall": "FALL"}

        pad = 10
        lab_h = 20
        cell_w = CW + pad
        board_w = cell_w * len(order) + pad
        board_h = CH + lab_h + pad * 2

        combo = []
        for k in range(4):
            board = Image.new("RGBA", (board_w, board_h), (250, 250, 252, 255))
            d = ImageDraw.Draw(board)
            for i, name in enumerate(order):
                img = _up(pools[name][idx[name][k]])
                x = pad + i * cell_w
                board.alpha_composite(img, (x, pad))
                d.text((x + 4, CH + pad + 2), labels[name], fill=(40, 40, 40, 255))
            combo.append(board.convert("RGB"))
        combo[0].save(
            os.path.join(WS, "all_states.gif"), save_all=True,
            append_images=combo[1:], duration=160, loop=0, disposal=2)
        print("saved: all_states.gif")

    finally:
        for p in created:
            if os.path.exists(p):
                os.remove(p)
        if os.path.isdir(face_warp.FACES_DIR) and not os.listdir(face_warp.FACES_DIR):
            os.rmdir(face_warp.FACES_DIR)


if __name__ == "__main__":
    main()
