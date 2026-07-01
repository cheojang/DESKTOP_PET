"""
오프스크린 GUI 스모크 (PySide6 전환 검증).

QT_QPA_PLATFORM=offscreen 으로 실행할 것. 실제 창을 띄우지 않는다.
검증 항목:
  1. 3개 GUI 모듈 import (desktop_pet, pet_renderer, camera_booth)
  2. DesktopPet 구성 (트레이/타이머/상태머신/렌더러 생성)
  3. 60틱 게임 루프(_on_tick) 무예외
  4. 5개 상태(FALL/IDLE/WALK/SLEEP/DRAG) 렌더 무예외 + QPixmap 변환

print에 이모지 금지 (Windows cp949).
"""

import os
import sys

# 이 스크립트는 프로젝트 루트에서 실행되지만, tests/ 안에서도 동작하도록 경로 보정
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main():
    from PySide6.QtWidgets import QApplication

    # 1. import 검증
    import pet_renderer
    import camera_booth  # noqa: F401  (import 자체가 검증)
    import desktop_pet
    from pet_state_machine import FALL, IDLE, WALK, SLEEP, DRAG
    print("[OK] 3개 GUI 모듈 import 성공")

    app = QApplication.instance() or QApplication(sys.argv)

    # 2. DesktopPet 구성
    pet = desktop_pet.DesktopPet()
    assert pet._sm is not None
    assert pet._ren is not None
    print("[OK] DesktopPet 구성 성공 (상태머신/렌더러/트레이/타이머)")

    # 3. 60틱 게임 루프 무예외
    for _ in range(60):
        pet._on_tick()
    print("[OK] 60틱 렌더 루프 무예외")

    # 4. 5개 상태 렌더 + QPixmap 변환 무예외
    ren = pet_renderer.PetRenderer()
    for state in (FALL, IDLE, WALK, SLEEP, DRAG):
        for direction in (1, -1):
            img = ren.render(state, direction, 2.0)
            pm = ren.to_pixmap(img)
            assert not pm.isNull(), f"QPixmap null for state={state} dir={direction}"
    print("[OK] 5개 상태 x 2방향 렌더 + QPixmap 변환 무예외")

    print("SMOKE PASS")


if __name__ == "__main__":
    main()
