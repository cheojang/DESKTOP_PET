"""
에셋 생성기(create_assets) 순수 로직 테스트.

TDD 대상:
  - build_asset_svgs() 키 집합(14종) 정확 일치
  - rasterize(svg, w, h) 반환 크기/모드(RGBA)
  - main() 산출 파일: 14개 존재 + 네이티브 크기표 일치 + 모서리 투명 + 중앙 내용 존재
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


# 계약: 14개 키 + 네이티브 크기 (파일명 = 키 + ".png")
NATIVE_SIZES = {
    "body_idle": (60, 80),
    "body_walk0": (60, 80),
    "body_walk1": (60, 80),
    "body_sleep": (60, 80),
    "body_drag": (60, 80),
    "arm_l": (20, 30),
    "arm_r": (20, 30),
    "arm_l_up": (20, 30),
    "arm_r_up": (20, 30),
    "leg_0": (16, 24),
    "leg_1": (16, 24),
    "tail_0": (24, 30),
    "tail_1": (24, 30),
    "zzz": (36, 24),
}


def test_build_asset_svgs_has_exactly_14_keys():
    svgs = create_assets.build_asset_svgs()
    assert set(svgs.keys()) == set(NATIVE_SIZES.keys())
    assert len(svgs) == 14


def test_build_asset_svgs_values_are_svg_strings():
    svgs = create_assets.build_asset_svgs()
    for key, svg in svgs.items():
        assert isinstance(svg, str), key
        assert "<svg" in svg, key


def test_rasterize_returns_requested_size_and_rgba():
    svg = create_assets.build_asset_svgs()["body_idle"]
    img = create_assets.rasterize(svg, 60, 80)
    assert img.size == (60, 80)
    assert img.mode == "RGBA"


@pytest.mark.parametrize("w,h", [(20, 30), (16, 24)])
def test_rasterize_respects_arbitrary_size(w, h):
    svg = create_assets.build_asset_svgs()["arm_l"]
    img = create_assets.rasterize(svg, w, h)
    assert img.size == (w, h)
    assert img.mode == "RGBA"


def test_main_writes_all_14_assets_with_native_sizes(tmp_path, monkeypatch):
    # assets 디렉토리를 임시 경로로 우회 (실제 assets/ 오염 방지)
    monkeypatch.setattr(create_assets, "ASSETS_DIR", str(tmp_path))
    create_assets.main()

    from PIL import Image

    for key, (w, h) in NATIVE_SIZES.items():
        path = os.path.join(str(tmp_path), f"{key}.png")
        assert os.path.exists(path), f"missing {key}.png"
        img = Image.open(path).convert("RGBA")
        assert img.size == (w, h), f"{key} size {img.size} != {(w, h)}"


def test_generated_assets_are_transparent_at_corners_and_solid_at_center(tmp_path, monkeypatch):
    monkeypatch.setattr(create_assets, "ASSETS_DIR", str(tmp_path))
    create_assets.main()

    from PIL import Image

    for key, (w, h) in NATIVE_SIZES.items():
        img = Image.open(os.path.join(str(tmp_path), f"{key}.png")).convert("RGBA")
        px = img.load()
        # 네 모서리 alpha == 0
        for cx, cy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            assert px[cx, cy][3] == 0, f"{key} corner ({cx},{cy}) not transparent"
        # 중앙부 내용 존재 (non-zero alpha)
        assert px[w // 2, h // 2][3] > 0, f"{key} center transparent"
