"""
웹캠 촬영 부스.
사용자 얼굴을 정면 1장 촬영 → face_warp.generate_expressions()로
AI 표정 8장(idle/sleep/walk_r/walk_l/cry/laugh/angry/drag) 자동 생성.
"""

import os
import sys
import tempfile
import cv2

from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtGui     import QImage, QPixmap, QFont
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMessageBox
)

import face_warp

PREVIEW_W = 640
PREVIEW_H = 480


class CameraBooth(QDialog):
    """
    웹캠 미리보기 + 촬영 → AI 표정 생성 다이얼로그.

    종료 코드:
      accept() : 촬영 + 표정 생성 성공
      reject() : 취소 / 카메라 오류
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("웹캠 촬영 — AI 표정 생성")
        self.setFixedSize(PREVIEW_W + 20, PREVIEW_H + 130)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._frame    = None     # 최신 BGR 프레임 (거울 반전됨)
        self._saved    = []       # 생성된 표정 이름
        self._busy     = False    # 표정 생성 중 중복 클릭 방지

        # 웹캠 열기
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            QMessageBox.critical(
                self, "카메라 오류",
                "웹캠을 열 수 없습니다.\n카메라 연결 상태와 다른 앱의 점유 여부를 확인하세요."
            )
            self._cap = None
            # __init__ 후 호출자가 exec_() 하기 전에 닫히도록 예약
            QTimer.singleShot(0, self.reject)
            return

        self._init_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)
        self._timer.start(33)   # 미리보기 ~30FPS

    # --- UI ---

    def _init_ui(self):
        layout = QVBoxLayout()

        self._guide = QLabel("얼굴을 화면 중앙 타원 안에 맞추고 정면을 보세요.", self)
        self._guide.setAlignment(Qt.AlignCenter)
        self._guide.setFont(QFont("", 12, QFont.Bold))
        self._guide.setStyleSheet(
            "color:#E67E22; background:#FDEDEC; padding:8px; border-radius:6px;"
        )
        layout.addWidget(self._guide)

        self._video = QLabel(self)
        self._video.setFixedSize(PREVIEW_W, PREVIEW_H)
        self._video.setAlignment(Qt.AlignCenter)
        self._video.setStyleSheet("border:3px solid #BDC3C7; background:#2C3E50;")
        layout.addWidget(self._video)

        btn_row = QHBoxLayout()

        self._capture_btn = QPushButton("촬영 + AI 표정 생성 (Space)", self)
        self._capture_btn.setFont(QFont("", 11, QFont.Bold))
        self._capture_btn.setStyleSheet(
            "background:#2ECC71; color:white; padding:10px; border-radius:5px;"
        )
        self._capture_btn.clicked.connect(self._capture)
        btn_row.addWidget(self._capture_btn)

        cancel_btn = QPushButton("취소 (Esc)", self)
        cancel_btn.setFont(QFont("", 11))
        cancel_btn.setStyleSheet(
            "background:#E74C3C; color:white; padding:10px; border-radius:5px;"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)
        self.setLayout(layout)

    # --- 미리보기 루프 ---

    def _update_frame(self):
        if self._cap is None:
            return
        ret, frame = self._cap.read()
        if not ret:
            return

        frame = cv2.flip(frame, 1)                      # 거울 반전
        frame = cv2.resize(frame, (PREVIEW_W, PREVIEW_H))
        self._frame = frame

        disp = frame.copy()
        # 중앙 얼굴 가이드 타원
        cv2.ellipse(disp, (PREVIEW_W // 2, PREVIEW_H // 2),
                    (110, 140), 0, 0, 360, (52, 152, 219), 2, cv2.LINE_AA)

        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self._video.setPixmap(QPixmap.fromImage(qimg))

    # --- 촬영 + AI 표정 생성 ---

    def _capture(self):
        if self._busy or self._frame is None:
            return
        self._busy = True
        self._capture_btn.setEnabled(False)
        self._guide.setText("AI가 표정을 생성 중입니다... 잠시만요.")
        QApplication.processEvents()

        # 미리보기 정지 + 카메라 해제 (생성 동안 리소스 점유 해제)
        if hasattr(self, "_timer"):
            self._timer.stop()
        snapshot = self._frame.copy()
        self._release_camera()

        tmp_path = os.path.join(tempfile.gettempdir(), "pet_webcam_capture.png")
        cv2.imwrite(tmp_path, snapshot)

        try:
            self._saved = face_warp.generate_expressions(tmp_path)
        except Exception as e:
            QMessageBox.warning(self, "표정 생성 실패", str(e))
            self.reject()
            return
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        QMessageBox.information(
            self, "완료",
            f"AI 표정 {len(self._saved)}장 생성 완료!\n펫에 새 얼굴이 적용됩니다."
        )
        self.accept()

    @property
    def saved_expressions(self):
        return self._saved

    # --- 리소스 정리 ---

    def _release_camera(self):
        if getattr(self, "_timer", None) is not None:
            self._timer.stop()
        if getattr(self, "_cap", None) is not None:
            self._cap.release()
            self._cap = None

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return):
            self._capture()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._release_camera()
        event.accept()

    def reject(self):
        self._release_camera()
        super().reject()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    booth = CameraBooth()
    if booth.exec_() == QDialog.Accepted:
        print("생성된 표정:", booth.saved_expressions)
    else:
        print("취소됨")
