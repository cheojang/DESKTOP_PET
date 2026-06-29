"""
스프라이트 합성 렌더러.
PIL로 파츠를 합성하고 QPixmap으로 변환.
"""

import os
from PIL import Image
from PyQt5.QtGui import QImage, QPixmap

from pet_state_machine import FALL, IDLE, WALK, SLEEP, DRAG
import face_warp

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

PET_W = 80    # 최종 렌더 너비
PET_H = 120   # 최종 렌더 높이


def _load(name):
    path = os.path.join(ASSETS_DIR, name)
    if os.path.exists(path):
        return Image.open(path).convert("RGBA")
    # 에셋 없으면 투명 이미지 반환
    return Image.new("RGBA", (PET_W, PET_H), (0, 0, 0, 0))


class PetRenderer:
    def __init__(self):
        self._assets = {}
        self._faces  = {}
        self._frame  = 0
        self._load_assets()

    def _load_assets(self):
        names = [
            "body_idle", "body_walk0", "body_walk1",
            "body_sleep", "body_drag",
            "arm_l", "arm_r", "arm_l_up", "arm_r_up",
            "leg_0", "leg_1", "tail_0", "tail_1", "zzz",
        ]
        for n in names:
            self._assets[n] = _load(f"{n}.png")

        for expr in face_warp.EXPRESSIONS:
            img = face_warp.load_face(expr)
            if img:
                self._faces[expr] = img

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

    def _paste(self, canvas, img, xy, flip=False):
        if img is None:
            return
        src = img.transpose(Image.FLIP_LEFT_RIGHT) if flip else img
        canvas.paste(src, xy, src)

    def render(self, state, direction, walk_speed=2.0):
        """
        상태에 맞는 PIL Image(RGBA) 반환.
        direction: 1=오른쪽, -1=왼쪽
        """
        flip = (direction == -1)
        anim = (self._frame // max(1, int(8 / walk_speed))) % 2

        if state in (FALL, IDLE):
            return self._render_idle(flip)
        elif state == WALK:
            return self._render_walk(anim, flip)
        elif state == SLEEP:
            return self._render_sleep(flip)
        elif state == DRAG:
            return self._render_drag(flip)
        return self._render_idle(flip)

    def _render_idle(self, flip):
        c = self._canvas()
        body = self._assets["body_idle"].resize((60, 80), Image.LANCZOS)
        # 꼬리
        tail = self._assets[f"tail_{self._frame // 20 % 2}"].resize((20, 26), Image.LANCZOS)
        self._paste(c, tail, (flip and 55 or 5, 40), flip=False)
        # 팔
        arm = self._assets["arm_l"].resize((18, 26), Image.LANCZOS)
        self._paste(c, arm, (2, 30), flip=flip)
        arm_r = self._assets["arm_r"].resize((18, 26), Image.LANCZOS)
        self._paste(c, arm_r, (60, 30), flip=flip)
        # 몸통
        self._paste(c, body, (10, 20), flip=flip)
        # 얼굴
        face = self._face("idle")
        if face:
            fsize = (44, 44)
            f = face.resize(fsize, Image.LANCZOS)
            self._paste(c, f, (18, 8), flip=flip)
        # 다리
        leg = self._assets["leg_0"].resize((14, 20), Image.LANCZOS)
        self._paste(c, leg, (20, 90), flip=flip)
        self._paste(c, leg, (44, 90), flip=flip)
        return c

    def _render_walk(self, anim, flip):
        c  = self._canvas()
        body = self._assets[f"body_walk{anim}"].resize((60, 80), Image.LANCZOS)
        # 꼬리
        tail = self._assets[f"tail_{anim}"].resize((20, 26), Image.LANCZOS)
        self._paste(c, tail, (5, 40), flip=False)
        # 팔 (교차)
        arm_a = self._assets["arm_l"].resize((18, 26), Image.LANCZOS)
        arm_b = self._assets["arm_r"].resize((18, 26), Image.LANCZOS)
        if anim == 0:
            self._paste(c, arm_a, (2, 30), flip=flip)
            self._paste(c, arm_b, (60, 28), flip=flip)
        else:
            self._paste(c, arm_a, (2, 28), flip=flip)
            self._paste(c, arm_b, (60, 30), flip=flip)
        # 몸통
        self._paste(c, body, (10, 20), flip=flip)
        # 얼굴
        expr = "walk_r" if not flip else "walk_l"
        face = self._face(expr)
        if face:
            f = face.resize((44, 44), Image.LANCZOS)
            self._paste(c, f, (18, 8), flip=False)
        # 다리 (교차)
        leg0 = self._assets["leg_0"].resize((14, 20), Image.LANCZOS)
        leg1 = self._assets["leg_1"].resize((14, 20), Image.LANCZOS)
        if anim == 0:
            self._paste(c, leg0, (20, 90), flip=flip)
            self._paste(c, leg1, (44, 90), flip=flip)
        else:
            self._paste(c, leg1, (20, 90), flip=flip)
            self._paste(c, leg0, (44, 90), flip=flip)
        return c

    def _render_sleep(self, flip):
        c    = self._canvas()
        body = self._assets["body_sleep"].resize((60, 80), Image.LANCZOS)
        tail = self._assets["tail_0"].resize((20, 26), Image.LANCZOS)
        self._paste(c, tail, (5, 50), flip=False)
        self._paste(c, body, (10, 28), flip=flip)
        face = self._face("sleep")
        if face:
            f = face.resize((44, 44), Image.LANCZOS)
            self._paste(c, f, (18, 16), flip=flip)
        # Zzz 말풍선
        zzz = self._assets["zzz"]
        if (self._frame // 30) % 2 == 0:
            self._paste(c, zzz, (50, 0), flip=False)
        return c

    def _render_drag(self, flip):
        c    = self._canvas()
        body = self._assets["body_drag"].resize((60, 80), Image.LANCZOS)
        # 팔 들어올린 상태
        arm_lu = self._assets["arm_l_up"].resize((18, 26), Image.LANCZOS)
        arm_ru = self._assets["arm_r_up"].resize((18, 26), Image.LANCZOS)
        self._paste(c, arm_lu, (0, 18), flip=flip)
        self._paste(c, arm_ru, (62, 18), flip=flip)
        # 몸통
        self._paste(c, body, (10, 18), flip=flip)
        # 얼굴
        face = self._face("drag")
        if face:
            f = face.resize((44, 44), Image.LANCZOS)
            self._paste(c, f, (18, 6), flip=flip)
        # 다리 발버둥
        leg0 = self._assets["leg_0"].resize((14, 20), Image.LANCZOS)
        leg1 = self._assets["leg_1"].resize((14, 20), Image.LANCZOS)
        ph = (self._frame // 4) % 2
        self._paste(c, leg0 if ph == 0 else leg1, (18, 92), flip=flip)
        self._paste(c, leg1 if ph == 0 else leg0, (46, 92), flip=flip)
        return c

    def to_pixmap(self, pil_img):
        """PIL RGBA Image → QPixmap."""
        data   = pil_img.tobytes("raw", "RGBA")
        qimage = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimage)
