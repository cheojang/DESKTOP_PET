"""
통짜 포즈 프레임 렌더러 (v2).

상태별로 미리 그려진 전신 포즈 프레임(80x120 PNG)을 순환 선택하고,
FACE_ANCHORS 에 맞춰 사용자 얼굴을 후드 개구부에 합성한다.
파츠(팔/다리/꼬리) paste 조립은 없다.
"""

import os
from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from pet_state_machine import FALL, IDLE, WALK, SLEEP, DRAG
from create_assets import FACE_ANCHORS
import face_warp

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

PET_W = 80    # 최종 렌더 너비
PET_H = 120   # 최종 렌더 높이

# 순환할 프레임 키 (상태별)
_FRAME_KEYS = [
    "pose_idle0", "pose_idle1",
    "pose_walk0", "pose_walk1", "pose_walk2", "pose_walk3",
    "pose_sleep0", "pose_sleep1",
    "pose_drag0", "pose_drag1",
    "pose_fall0", "pose_fall1",
    "pose_land",
]

# 상태별 얼굴 표정 (walk 은 방향에 따라 별도 처리)
_STATE_EXPR = {IDLE: "idle", SLEEP: "sleep", DRAG: "drag", FALL: "drag"}


def _load(name):
    path = os.path.join(ASSETS_DIR, name)
    if os.path.exists(path):
        return Image.open(path).convert("RGBA")
    return Image.new("RGBA", (PET_W, PET_H), (0, 0, 0, 0))


class PetRenderer:
    def __init__(self):
        self._assets = {}
        self._faces = {}
        self._frame = 0
        self._load_assets()

    def _load_assets(self):
        for n in _FRAME_KEYS + ["zzz"]:
            self._assets[n] = _load(f"{n}.png")
        self.reload_faces()

    def reload_faces(self):
        self._faces.clear()
        for expr in face_warp.EXPRESSIONS:
            img = face_warp.load_face(expr)
            if img:
                self._faces[expr] = img

    def tick(self):
        self._frame += 1

    def _face(self, expr):
        return self._faces.get(expr, self._faces.get("idle"))

    def _canvas(self):
        return Image.new("RGBA", (PET_W, PET_H), (0, 0, 0, 0))

    def render(self, state, direction, walk_speed=2.0):
        """상태에 맞는 PIL Image(RGBA) 반환. direction: 1=오른쪽, -1=왼쪽."""
        flip = (direction == -1)

        if state == WALK:
            step = max(1, int(8 / walk_speed))
            key = f"pose_walk{(self._frame // step) % 4}"
            expr = "walk_l" if flip else "walk_r"
        elif state == SLEEP:
            key = f"pose_sleep{(self._frame // 36) % 2}"
            expr = "sleep"
        elif state == DRAG:
            key = f"pose_drag{(self._frame // 8) % 2}"
            expr = "drag"
        elif state == FALL:
            key = f"pose_fall{(self._frame // 8) % 2}"
            expr = "drag"
        else:  # IDLE (및 기타)
            key = f"pose_idle{(self._frame // 24) % 2}"
            expr = "idle"

        c = self._canvas()
        self._blit_frame(c, key, flip, expr)

        if state == SLEEP and (self._frame // 30) % 2 == 0:
            self._paste(c, self._assets["zzz"], (48, 2))

        return c

    def _blit_frame(self, canvas, key, flip, expr):
        frame = self._assets[key]
        cx, cy, w, h = FACE_ANCHORS[key]
        if flip:
            frame = frame.transpose(Image.FLIP_LEFT_RIGHT)
            cx = PET_W - cx      # 앵커도 미러 (얼굴은 정방향 유지)
        self._paste(canvas, frame, (0, 0))

        face = self._face(expr)
        if face:
            f = face.resize((int(w), int(h)), Image.LANCZOS)
            self._paste(canvas, f, (int(cx - w / 2), int(cy - h / 2)))

    def _paste(self, canvas, img, xy):
        if img is None:
            return
        canvas.paste(img, xy, img)

    def to_pixmap(self, pil_img):
        """PIL RGBA Image → QPixmap."""
        data = pil_img.tobytes("raw", "RGBA")
        qimage = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimage)
