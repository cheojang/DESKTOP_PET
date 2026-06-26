# -*- coding: utf-8 -*-
import sys
import os
import cv2
from PIL import Image, ImageDraw
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PyQt5.QtGui import QImage, QPixmap, QFont

class CameraBooth(QDialog):
    def __init__(self, output_dir="faces", parent=None):
        super().__init__(parent)
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 1. 촬영 단계별 가이드 시나리오 설정
        # (안내 메시지, 저장될 파일 이름)
        self.steps = [
            ("1단계: 정면을 편안하게 바라봐 주세요.", "face_idle.png"),
            ("2단계: 눈을 꼬옥 감아보세요.", "face_sleep.png"),
            ("3단계: 얼굴을 오른쪽으로 돌려보세요.", "face_walk_r.png"),
            ("4단계: 크게 놀란 표정을 지어보세요!", "face_drag.png")
        ]
        self.current_step = 0
        
        # 2. 윈도우 기본 창 설정
        self.setWindowTitle("나만의 캐릭터 촬영실 (Camera Booth)")
        self.setFixedSize(660, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint) # 물음표 버튼 제거
        
        # 3. 비디오 캡처 객체 초기화 (기본 웹캠 0번 로드)
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "오류", "노트북 카메라(웹캠)를 열 수 없습니다.\n카메라가 정상 연결되어 있는지 확인해 주세요.")
            sys.exit(1)
            
        self.init_ui()
        
        # 4. 카메라 비디오 프레임 주기적 갱신 타이머 시작 (30ms 마다 프레임 갱신)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)
        
        # 현재 화면 프레임 보관용
        self.current_frame = None

    def init_ui(self):
        """카메라 부스용 화면 레이아웃과 폰트 스타일을 구성합니다."""
        layout = QVBoxLayout()
        
        # 1) 상단 촬영 가이드 자막 라벨
        self.guide_label = QLabel(self.steps[self.current_step][0], self)
        self.guide_label.setAlignment(Qt.AlignCenter)
        guide_font = QFont("맑은 고딕", 14, QFont.Bold)
        self.guide_label.setFont(guide_font)
        self.guide_label.setStyleSheet("color: #E67E22; background-color: #FDEDEC; padding: 8px; border-radius: 6px;")
        layout.addWidget(self.guide_label)
        
        # 2) 중앙 카메라 실시간 화면 표시 라벨
        self.video_label = QLabel(self)
        self.video_label.setFixedSize(640, 400)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("border: 3px solid #BDC3C7; background-color: #2C3E50;")
        layout.addWidget(self.video_label)
        
        # 3) 하단 조작 버튼 영역
        button_layout = QHBoxLayout()
        
        self.capture_btn = QPushButton("사진 촬영 (Spacebar)", self)
        self.capture_btn.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        self.capture_btn.setStyleSheet("background-color: #2ECC71; color: white; padding: 10px; border-radius: 5px;")
        self.capture_btn.clicked.connect(self.capture_photo)
        button_layout.addWidget(self.capture_btn)
        
        cancel_btn = QPushButton("취소 및 종료 (ESC)", self)
        cancel_btn.setFont(QFont("맑은 고딕", 11))
        cancel_btn.setStyleSheet("background-color: #E74C3C; color: white; padding: 10px; border-radius: 5px;")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def update_frame(self):
        """실시간 카메라 프레임을 읽어와서 화면 중앙에 가이드 선과 함께 그립니다."""
        ret, frame = self.cap.read()
        if not ret:
            return
            
        # 좌우 거울 효과를 위해 비디오 가로 대칭 반전
        self.current_frame = cv2.flip(frame, 1)
        
        # 비디오 프레임 규격 조절 (640x480)
        self.current_frame = cv2.resize(self.current_frame, (640, 480))
        
        # 디스플레이용 프레임 복사본 생성 (가이드 점선 타원을 덧그림)
        display_frame = self.current_frame.copy()
        
        # 화면 중앙에 얼굴 크기 조절용 점선 가이드 타원 그리기 (중심 320, 240, 가로반지름 95, 세로반지름 120)
        cv2.ellipse(
            display_frame,
            (320, 240),
            (95, 120),
            0, 0, 360,
            (52, 152, 219), # 파란색 가이드 라인
            2,
            lineType=cv2.LINE_AA
        )
        
        # 화면 출력을 위한 BGR -> RGB 포맷 변환 및 QImage 매핑
        rgb_image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # 640x400 영역에 맞게 잘라서 QLabel에 출력
        self.video_label.setPixmap(QPixmap.fromImage(q_img).copy(0, 40, 640, 400))

    def crop_and_save_face(self, frame, save_path, target_size=50):
        """캡처된 프레임에서 얼굴을 탐지하여 둥글게 원형 마스크 크롭하여 저장합니다."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame)
        
        if len(faces) > 0:
            # 가장 크게 찍힌 얼굴 바운딩 박스 선택
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            x, y, w, h = faces[0]
            
            # 머리와 볼 살선 마진 확보
            margin_x = int(w * 0.15)
            margin_y = int(h * 0.20)
            
            c_x1 = max(0, x - margin_x)
            c_y1 = max(0, y - margin_y)
            c_x2 = min(pil_img.width, x + w + margin_x)
            c_y2 = min(pil_img.height, y + h + margin_y)
            cropped = pil_img.crop((c_x1, c_y1, c_x2, c_y2))
        else:
            # 얼굴 감지 실패 시 화면 가운데(가이드 타원 가상 바운딩박스) 강제 크롭
            print("웹캠 촬영 중 얼굴 미감지: 가이드 영역으로 강제 크롭합니다.")
            c_x1, c_y1 = 320 - 95, 240 - 120
            c_x2, c_y2 = 320 + 95, 240 + 120
            cropped = pil_img.crop((c_x1, c_y1, c_x2, c_y2))
            
        # 투명 원 마스크 적용
        mask = Image.new("L", cropped.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, cropped.size[0], cropped.size[1]), fill=255)
        
        face_rgba = cropped.convert("RGBA")
        face_rgba.putalpha(mask)
        
        # 정규화된 크기(50x50)로 변환 후 저장
        resized = face_rgba.resize((target_size, target_size), Image.Resampling.LANCZOS)
        resized.save(save_path, "PNG")
        return True

    def capture_photo(self):
        """현재 비디오 프레임을 캡처하여 펫 얼굴 조립용 PNG 파일로 저장합니다."""
        if self.current_frame is None:
            return
            
        guide_msg, filename = self.steps[self.current_step]
        save_path = os.path.join(self.output_dir, filename)
        
        # 얼굴 크롭 및 저장 수행
        success = self.crop_and_save_face(self.current_frame, save_path, target_size=50)
        
        if success:
            # 3단계(옆면 사진)인 경우, 좌측으로 걷기 얼굴 파일도 가로 대칭 반전시켜 즉시 빌드
            if filename == "face_walk_r.png":
                walk_r_img = cv2.imread(save_path, cv2.IMREAD_UNCHANGED)
                if walk_r_img is not None:
                    walk_l_img = cv2.flip(walk_r_img, 1)
                    cv2.imwrite(os.path.join(self.output_dir, "face_walk_l.png"), walk_l_img)
            
            # 다음 촬영 단계로 전환
            self.current_step += 1
            if self.current_step < len(self.steps):
                # 가이드 텍스트 업데이트
                self.guide_label.setText(self.steps[self.current_step][0])
            else:
                # 모든 단계 촬영 완료 시 카메라 리소스를 끄고 모달 창 닫음
                self.timer.stop()
                self.cap.release()
                QMessageBox.information(self, "완료", "모든 각도의 캐릭터 얼굴 촬영이 끝났습니다!\n새로운 다중 표정 펫이 적용됩니다. 🎉")
                self.accept()
        else:
            QMessageBox.warning(self, "실패", "사진 촬영 처리에 오류가 발생했습니다. 다시 시도해 주세요.")

    # --- 키보드 조작 이벤트 매핑 ---
    def keyPressEvent(self, event):
        if event.key() in [Qt.Key_Space, Qt.Key_Return]:
            # 스페이스바나 엔터키 입력 시 캡처 실행
            self.capture_photo()
        elif event.key() == Qt.Key_Escape:
            # ESC 키 입력 시 카메라 끄고 다이얼로그 닫기
            self.timer.stop()
            self.cap.release()
            self.reject()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """창이 우상단 X 버튼 등으로 강제 닫힐 때 카메라 메모리를 정상 해제합니다."""
        self.timer.stop()
        self.cap.release()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    booth = CameraBooth("faces")
    booth.exec_()
