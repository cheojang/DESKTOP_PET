"""
에셋 생성기(create_assets) 순수 로직 테스트 (v2 — 통짜 포즈 프레임).

TDD 대상:
  - build_asset_svgs() 키 집합(13 포즈 + zzz) 정확 일치
  - FACE_ANCHORS: 13 포즈 전부, 개구부가 캔버스 내부 + 중심 픽셀 불투명(안감 채움)
  - rasterize(svg, w, h) 반환 크기/모드(RGBA)
  - main() 산출: 포즈 80x120 / zzz 36x24, 모서리 투명, 포즈 중앙 내용 존재
  - walk0 vs walk2 좌우 위상 반대(다리 x위상) 정량 체크
  - 구 파츠 키 PNG 정리 로직
"""

import os
import sys

import pytest

# 오프스크린 강제 (QApplication 없이 QtSvg 래스터라이즈)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import create_assets  # noqa: E402
from PIL import Image  # noqa: E402


# 계약: 13 포즈 프레임 (전부 80x120) + zzz (36x24)
POSE_KEYS = [
    "pose_idle0", "pose_idle1",
    "pose_walk0", "pose_walk1", "pose_walk2", "pose_walk3",
    "pose_sleep0", "pose_sleep1",
    "pose_drag0", "pose_drag1",
    "pose_fall0", "pose_fall1",
    "pose_land",
]
ALL_KEYS = POSE_KEYS + ["zzz"]

NATIVE_SIZES = {k: (80, 120) for k in POSE_KEYS}
NATIVE_SIZES["zzz"] = (36, 24)


def test_build_asset_svgs_key_set_matches_contract():
    svgs = create_assets.build_asset_svgs()
    assert set(svgs.keys()) == set(ALL_KEYS)
    assert len(svgs) == 14


def test_build_asset_svgs_values_are_svg_strings():
    svgs = create_assets.build_asset_svgs()
    for key, svg in svgs.items():
        assert isinstance(svg, str), key
        assert "<svg" in svg, key


def test_native_sizes_table_matches_contract():
    assert set(create_assets._NATIVE.keys()) == set(ALL_KEYS)
    for k in POSE_KEYS:
        assert create_assets._NATIVE[k] == (80, 120), k
    assert create_assets._NATIVE["zzz"] == (36, 24)


def test_face_anchors_cover_all_pose_frames():
    anchors = create_assets.FACE_ANCHORS
    assert set(anchors.keys()) == set(POSE_KEYS)
    for key, (cx, cy, w, h) in anchors.items():
        # 개구부가 캔버스(80x120) 내부에 완전히 들어와야 한다
        assert 0 <= cx - w / 2 and cx + w / 2 <= 80, key
        assert 0 <= cy - h / 2 and cy + h / 2 <= 120, key
        assert w > 0 and h > 0, key


def test_rasterize_returns_requested_size_and_rgba():
    svg = create_assets.build_asset_svgs()["pose_idle0"]
    img = create_assets.rasterize(svg, 80, 120)
    assert img.size == (80, 120)
    assert img.mode == "RGBA"


def test_main_writes_all_assets_with_native_sizes(tmp_path, monkeypatch):
    monkeypatch.setattr(create_assets, "ASSETS_DIR", str(tmp_path))
    create_assets.main()

    for key, (w, h) in NATIVE_SIZES.items():
        path = os.path.join(str(tmp_path), f"{key}.png")
        assert os.path.exists(path), f"missing {key}.png"
        img = Image.open(path).convert("RGBA")
        assert img.size == (w, h), f"{key} size {img.size} != {(w, h)}"


def test_pose_frames_transparent_corners_and_solid_center(tmp_path, monkeypatch):
    monkeypatch.setattr(create_assets, "ASSETS_DIR", str(tmp_path))
    create_assets.main()

    for key in POSE_KEYS:
        img = Image.open(os.path.join(str(tmp_path), f"{key}.png")).convert("RGBA")
        px = img.load()
        w, h = img.size
        for cx, cy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            assert px[cx, cy][3] == 0, f"{key} corner ({cx},{cy}) not transparent"
        # 몸통 중앙(캐릭터 존재)은 불투명
        assert px[w // 2, h // 2][3] > 0, f"{key} center transparent"


def test_face_opening_center_is_filled(tmp_path, monkeypatch):
    """얼굴 미등록 시에도 개구부가 '빈 구멍'이 아니라 안감으로 채워져야 한다."""
    monkeypatch.setattr(create_assets, "ASSETS_DIR", str(tmp_path))
    create_assets.main()

    for key in POSE_KEYS:
        img = Image.open(os.path.join(str(tmp_path), f"{key}.png")).convert("RGBA")
        px = img.load()
        cx, cy, _, _ = create_assets.FACE_ANCHORS[key]
        assert px[int(cx), int(cy)][3] > 0, f"{key} face opening not filled at ({cx},{cy})"


def _lower_mask(img):
    """다리 영역(y>=95) 불투명 마스크를 0/1 2차원 리스트로."""
    w, h = img.size
    px = img.load()
    rows = []
    for y in range(95, h):
        rows.append([1 if px[x, y][3] > 40 else 0 for x in range(w)])
    return rows


def _iou(a, b):
    inter = union = 0
    for ra, rb in zip(a, b):
        for va, vb in zip(ra, rb):
            if va or vb:
                union += 1
                if va and vb:
                    inter += 1
    return inter / union if union else 1.0


def test_walk0_and_walk2_are_leg_phase_opposite(tmp_path, monkeypatch):
    """walk2 는 walk0 의 좌우 반전(위상 반대)이고, walk0 자체는 비대칭(성큼걸음)이어야 한다."""
    monkeypatch.setattr(create_assets, "ASSETS_DIR", str(tmp_path))
    create_assets.main()

    w0 = Image.open(os.path.join(str(tmp_path), "pose_walk0.png")).convert("RGBA")
    w2 = Image.open(os.path.join(str(tmp_path), "pose_walk2.png")).convert("RGBA")

    m0 = _lower_mask(w0)
    m2 = _lower_mask(w2)
    m0_mirror = [list(reversed(r)) for r in m0]

    # walk2 는 walk0 을 좌우 반전한 것과 매우 유사 (위상 반대)
    assert _iou(m2, m0_mirror) > 0.7, "walk2 is not the mirror of walk0"
    # walk0 다리는 스스로 좌우 비대칭 (성큼 내딛는 자세) — 정지 대칭이면 안 됨
    assert _iou(m0, m0_mirror) < 0.9, "walk0 legs are symmetric (no stride)"


def test_main_cleans_up_legacy_part_assets(tmp_path, monkeypatch):
    """v1 파츠 키 PNG(body_*/arm_*/leg_*/tail_*)를 재생성 시 제거한다."""
    monkeypatch.setattr(create_assets, "ASSETS_DIR", str(tmp_path))
    legacy = [
        "body_idle", "body_walk0", "body_walk1", "body_sleep", "body_drag",
        "arm_l", "arm_r", "arm_l_up", "arm_r_up",
        "leg_0", "leg_1", "tail_0", "tail_1",
    ]
    for name in legacy:
        Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(
            os.path.join(str(tmp_path), f"{name}.png")
        )

    create_assets.main()

    for name in legacy:
        assert not os.path.exists(os.path.join(str(tmp_path), f"{name}.png")), \
            f"legacy asset {name}.png was not removed"
    # zzz 는 유지되는 키
    assert os.path.exists(os.path.join(str(tmp_path), "zzz.png"))
