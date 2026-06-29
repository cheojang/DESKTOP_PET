"""
데스크톱 펫 메인 컨트롤러.
PyQt5 투명 오버레이 윈도우 + 60FPS 게임 루프.
"""

import sys
import os
import platform
import subprocess

from PyQt5.QtCore    import Qt, QTimer, QPoint
from PyQt5.QtGui     import QIcon
from PyQt5.QtWidgets import (
    QApplication, QLabel, QWidget,
    QSystemTrayIcon, QMenu, QAction, QFileDialog, QMessageBox
)

# assets 자동 생성
from create_assets import main as create_assets
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
if not os.path.isdir(ASSETS_DIR) or not os.listdir(ASSETS_DIR):
    print("에셋 생성 중...")
    create_assets()

from pet_state_machine import PetStateMachine, FALL, IDLE, WALK, SLEEP, DRAG
from pet_renderer       import PetRenderer, PET_W, PET_H
import face_warp

IS_WINDOWS = platform.system() == "Windows"

FRAME_MS = 16   # ~60 FPS


def get_window_floors(own_hwnd=None):
    """
    Windows: 열린 창들의 (left, right, top) 목록 반환.
    비Windows: 빈 리스트.
    """
    if not IS_WINDOWS:
        return []
    try:
        import ctypes
        user32 = ctypes.windll.user32
        floors = []

        def enum_cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            if own_hwnd and hwnd == own_hwnd:
                return True
            # 타이틀 없는 창 제외
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
            if bottom - top < 40:
                return True
            floors.append((left, right, top))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return floors
    except Exception:
        return []


class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()

        # 투명 오버레이 윈도우 설정
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedSize(PET_W, PET_H)

        # 레이블 (스프라이트 표시용)
        self._label = QLabel(self)
        self._label.setGeometry(0, 0, PET_W, PET_H)

        # 스크린 정보
        screen  = QApplication.primaryScreen()
        geom    = screen.availableGeometry()
        self._screen_w = geom.width()
        self._screen_h = geom.height()
        self._floor_y  = geom.bottom() - PET_H

        # 상태 머신 + 렌더러
        self._sm  = PetStateMachine(self._screen_w, self._floor_y, self._floor_y)
        self._ren = PetRenderer()

        # 드래그 관련
        self._drag_offset = QPoint(0, 0)

        # 시스템 트레이
        self._setup_tray()

        # 게임 루프 타이머
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(FRAME_MS)

        # 창 위 바닥 업데이트 타이머 (500ms)
        self._floor_timer = QTimer(self)
        self._floor_timer.timeout.connect(self._update_window_floors)
        self._floor_timer.start(500)

        self._last_ms = 0
        self._own_hwnd = None

        self.show()

        # 자기 HWND 저장 (Windows)
        if IS_WINDOWS:
            try:
                self._own_hwnd = int(self.winId())
            except Exception:
                pass

    def _setup_tray(self):
        # 기본 아이콘 (에셋 없으면 빈 픽스맵)
        icon_path = os.path.join(ASSETS_DIR, "body_idle.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self._tray = QSystemTrayIcon(icon, self)
        menu = QMenu()

        act_photo  = QAction("사진 교체", self)
        act_quit   = QAction("종료",     self)
        act_photo.triggered.connect(self._change_photo)
        act_quit.triggered.connect(QApplication.quit)

        menu.addAction(act_photo)
        menu.addSeparator()
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)
        self._tray.setToolTip("Desktop Pet")
        self._tray.show()

    def _change_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            None, "얼굴 사진 선택", "",
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        try:
            saved = face_warp.generate_expressions(path)
            self._ren.reload_faces()
            self._tray.showMessage("Desktop Pet", f"표정 {len(saved)}장 생성 완료!", QSystemTrayIcon.Information, 2000)
        except Exception as e:
            QMessageBox.warning(None, "오류", str(e))

    def _update_window_floors(self):
        floors = get_window_floors(self._own_hwnd)
        self._sm.set_window_floors(floors)

    def _on_tick(self):
        dt = FRAME_MS / 1000.0
        self._sm.update(dt)
        self._ren.tick()

        # 위치 업데이트
        x = int(self._sm.x - PET_W // 2)
        y = int(self._sm.y - PET_H)
        x = max(0, min(x, self._screen_w - PET_W))
        y = max(0, min(y, self._screen_h - PET_H))
        self.move(x, y)

        # 렌더링
        pil_img = self._ren.render(self._sm.state, self._sm.dir, self._sm.walk_speed)
        pixmap  = self._ren.to_pixmap(pil_img)
        self._label.setPixmap(pixmap)

    # --- 마우스 드래그 ---

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.pos()
            self._sm.start_drag()

    def mouseMoveEvent(self, event):
        if self._sm.state == DRAG:
            global_pos = event.globalPos()
            cx = global_pos.x() + PET_W  // 2
            cy = global_pos.y() + PET_H
            self._sm.move_drag(cx, cy)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._sm.state == DRAG:
            global_pos = event.globalPos()
            cx = global_pos.x() + PET_W // 2
            cy = global_pos.y() + PET_H
            self._sm.end_drag(cx, cy)


def make_bat():
    """Windows용 원클릭 실행 .bat 생성."""
    if not IS_WINDOWS:
        return
    bat = os.path.join(os.path.dirname(__file__), "run_pet.bat")
    if os.path.exists(bat):
        return
    script = os.path.abspath(__file__)
    content = (
        "@echo off\n"
        "chcp 65001 > nul\n"
        f'cd /d "{os.path.dirname(script)}"\n'
        f'start pythonw.exe "{script}"\n'
    )
    with open(bat, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    make_bat()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet = DesktopPet()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
