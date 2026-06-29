"""
사진 → 얼굴 추출 → AR 표정 8장 생성.

rembg 주의: 모듈 레벨 import 금지 (onnxruntime 없으면 sys.exit 호출).
함수 내부에서 subprocess로 사용 가능 여부 테스트 후 지연 import.
"""

import os
import sys
import subprocess
import cv2
import numpy as np
from PIL import Image

FACES_DIR = os.path.join(os.path.dirname(__file__), "faces")
FACE_SIZE = (60, 60)    # 최종 얼굴 패치 크기

CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

EXPRESSIONS = ["idle", "sleep", "walk_r", "walk_l", "cry", "laugh", "angry", "drag"]


def _rembg_available():
    try:
        result = subprocess.run(
            [sys.executable, "-c", "from rembg import remove"],
            capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def _remove_bg(pil_img):
    """rembg로 배경 제거. 불가능하면 원본 반환."""
    if _rembg_available():
        from rembg import remove  # 지연 import
        return remove(pil_img)
    return pil_img


def detect_face(img_path):
    """OpenCV Haar Cascade로 얼굴 감지 → (x, y, w, h) or None."""
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        return None
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(CASCADE_PATH)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) == 0:
        return None
    # 가장 큰 얼굴
    return max(faces, key=lambda f: f[2] * f[3])


def _crop_face(img_bgr, rect, margin=0.35):
    """얼굴 영역 + 마진 크롭 → PIL RGBA."""
    x, y, w, h = rect
    mx = int(w * margin)
    my = int(h * margin)
    ih, iw = img_bgr.shape[:2]
    x1 = max(0, x - mx)
    y1 = max(0, y - my)
    x2 = min(iw, x + w + mx)
    y2 = min(ih, y + h + my)
    crop = img_bgr[y1:y2, x1:x2]
    rgb  = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb).convert("RGBA")


def _get_landmarks(img_bgr, rect):
    """MediaPipe Face Mesh로 468 랜드마크 반환. 실패 시 None."""
    try:
        import mediapipe as mp
        mp_fm = mp.solutions.face_mesh
        with mp_fm.FaceMesh(static_image_mode=True, max_num_faces=1,
                            refine_landmarks=True) as fm:
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            result = fm.process(rgb)
            if not result.multi_face_landmarks:
                return None
            h, w = img_bgr.shape[:2]
            lm = result.multi_face_landmarks[0].landmark
            return [(int(p.x * w), int(p.y * h)) for p in lm]
    except Exception:
        return None


def _warp_face(face_pil, direction, landmarks, img_shape):
    """좌우 워프 이펙트 (walk_r / walk_l)."""
    arr  = np.array(face_pil)
    h, w = arr.shape[:2]
    amount = 8 if direction == "r" else -8
    M = np.float32([[1, 0, amount], [0, 1, 0]])
    warped = cv2.warpAffine(arr, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(warped)


def _draw_eyes_closed(face_pil, landmarks, img_shape):
    """눈 감은 효과 (sleep)."""
    from PIL import ImageDraw
    out = face_pil.copy()
    d   = ImageDraw.Draw(out)
    if landmarks:
        # 랜드마크 기준 눈 좌표 변환
        ih, iw = img_shape[:2]
        fw, fh = out.size
        # 왼쪽 눈 중심 (랜드마크 #159 ~ #145 근처)
        scale_x = fw / iw
        scale_y = fh / ih
        for idx in [159, 145, 386, 374]:
            lx, ly = landmarks[idx]
            sx, sy = int(lx * scale_x), int(ly * scale_y)
            d.line([(sx - 8, sy), (sx + 8, sy)], fill=(60, 40, 20, 240), width=3)
    return out


def _draw_tears(face_pil):
    from PIL import ImageDraw
    out = face_pil.copy()
    d   = ImageDraw.Draw(out)
    fw, fh = out.size
    for tx in [fw // 3, fw * 2 // 3]:
        for ty_off in range(fh // 2, fh, 5):
            d.ellipse([tx - 2, ty_off, tx + 2, ty_off + 4], fill=(100, 160, 255, 180))
    return out


def _draw_blush(face_pil):
    from PIL import ImageDraw
    out = face_pil.copy()
    d   = ImageDraw.Draw(out)
    fw, fh = out.size
    r = fw // 6
    d.ellipse([fw // 8, fh // 2, fw // 8 + r * 2, fh // 2 + r], fill=(255, 150, 150, 100))
    d.ellipse([fw - fw // 8 - r * 2, fh // 2, fw - fw // 8, fh // 2 + r], fill=(255, 150, 150, 100))
    return out


def _draw_angry(face_pil):
    from PIL import ImageDraw
    out = face_pil.copy()
    d   = ImageDraw.Draw(out)
    fw, fh = out.size
    # 찡그린 눈썹
    d.line([(fw // 5, fh // 4), (fw * 2 // 5, fh // 3)], fill=(60, 30, 10, 240), width=3)
    d.line([(fw * 3 // 5, fh // 3), (fw * 4 // 5, fh // 4)], fill=(60, 30, 10, 240), width=3)
    # 분노마크
    d.text((fw * 3 // 4, fh // 6), "怒", fill=(220, 50, 50, 200))
    return out


def _draw_surprised(face_pil):
    from PIL import ImageDraw
    out = face_pil.copy()
    d   = ImageDraw.Draw(out)
    fw, fh = out.size
    # 동그란 눈
    for ex in [fw // 3, fw * 2 // 3]:
        ey = fh // 3
        d.ellipse([ex - 8, ey - 8, ex + 8, ey + 8], outline=(40, 30, 20, 240), width=2)
    return out


def generate_expressions(img_path):
    """
    img_path 사진에서 8가지 표정 PNG를 faces/ 에 저장.
    반환: 성공한 표정 이름 목록.
    """
    os.makedirs(FACES_DIR, exist_ok=True)

    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        raise ValueError(f"이미지를 열 수 없습니다: {img_path}")

    rect = detect_face(img_path)
    if rect is None:
        # 얼굴 미감지 시 전체 이미지를 얼굴로 사용
        h, w = img_bgr.shape[:2]
        rect = (0, 0, w, h)

    face_pil = _crop_face(img_bgr, rect)
    face_pil = _remove_bg(face_pil)
    face_pil = face_pil.resize(FACE_SIZE, Image.LANCZOS)

    landmarks = _get_landmarks(img_bgr, rect)
    ih, iw   = img_bgr.shape[:2]
    img_shape = img_bgr.shape

    saved = []
    expressions = {
        "idle":   face_pil,
        "sleep":  _draw_eyes_closed(face_pil, landmarks, img_shape),
        "walk_r": _warp_face(face_pil, "r", landmarks, img_shape),
        "walk_l": _warp_face(face_pil, "l", landmarks, img_shape),
        "cry":    _draw_tears(face_pil),
        "laugh":  _draw_blush(face_pil),
        "angry":  _draw_angry(face_pil),
        "drag":   _draw_surprised(face_pil),
    }

    for name, img in expressions.items():
        path = os.path.join(FACES_DIR, f"face_{name}.png")
        img.save(path)
        saved.append(name)

    return saved


def load_face(expression="idle"):
    """faces/face_{expression}.png → PIL Image. 없으면 None."""
    path = os.path.join(FACES_DIR, f"face_{expression}.png")
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python face_warp.py <이미지경로>")
        sys.exit(1)
    result = generate_expressions(sys.argv[1])
    print("생성된 표정:", result)
