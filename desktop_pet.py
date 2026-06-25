# -*- coding: utf-8 -*-
# Windows 환경에서 PyQt5와 onnxruntime 간의 DLL 로드 순서 꼬임 방지를 위해 rembg/OpenCV를 가장 먼저 임포트합니다.
import rembg
import cv2

import sys
import os
import math
import random
from PIL import Image, ImageDraw
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QSystemTrayIcon, QMenu, QAction, QFileDialog, QMessageBox
from PyQt5.QtGui import QPixmap, QTransform, QIcon, QImage

# 2단계에서 개발한 얼굴 자동 추출 모듈 함수 불러오기
from face_extractor import extract_face

# 캐릭터의 행동 상태 정의
STATE_FALL = 0   # 낙하 중 (중력 적용)
STATE_IDLE = 1   # 제자리에 멈춰 서서 쉼 (앉기 몸통)
STATE_WALK = 2   # 좌우로 걸어다님 (걷기 발버둥 몸통 1/2 교차)
STATE_DRAG = 3   # 마우스로 끌려다님 (매달리기 대롱대롱 몸통)
STATE_PEEK = 4   # 화면 경계(벽, 바닥)에 숨어 빼꼼하기 (매달리기 몸통)
STATE_SLEEP = 5  # 바닥에 누워 잠자기 (눕기 납작한 몸통 + 쌔근쌔근 호흡 모션)

# 빼꼼 위치의 세부 종류 정의
PEEK_LEFT = 0
PEEK_RIGHT = 1
PEEK_BOTTOM = 2

class DesktopPet(QMainWindow):
    def __init__(self, face_path="face.png"):
        super().__init__()
        self.face_path = face_path
        
        # 1. 윈도우 스타일 (테두리 없음, 항상 위, 작업 표시줄 생략, 투명 배경)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 2. 이미지 규격 표준화 (최종 조립 캐릭터는 항상 100x100 크기)
        self.char_size = 100
        self.window_width = 120   # 회전 시 잘림 방지용 윈도우 창 버퍼 크기
        self.window_height = 120
        self.resize(self.window_width, self.window_height)
        
        # 3. 캐릭터를 그릴 QLabel 레이블 배치 (창 정중앙 정렬)
        self.label = QLabel(self)
        self.label.setGeometry(
            (self.window_width - self.char_size) // 2,
            self.window_height - self.char_size, # 창 바닥에 발끝 정렬
            self.char_size,
            self.char_size
        )
        self.label.setScaledContents(True)
        
        # 4. 각 동작별 몸통 템플릿 파일 경로 및 얼굴 부착 조인트(목) 좌표 정의 (가로 64, 세로 64 기준)
        self.joints = {
            'idle': ('assets/body_idle.png', (32, 25)),
            'walk1': ('assets/body_walk1.png', (32, 25)),
            'walk2': ('assets/body_walk2.png', (32, 25)),
            'sleep': ('assets/body_sleep.png', (18, 43)),
            'peek': ('assets/body_peek.png', (32, 22))
        }
        
        # 5. 물리 및 상태 제어 변수들
        self.state = STATE_FALL
        self.velocity_x = 0
        self.velocity_y = 0
        self.gravity = 0.8
        
        self.walk_speed = 1.3   # 업무에 방해되지 않는 적당한 아장아장 속도
        self.walk_direction = 1 # 1: 오른쪽, -1: 왼쪽
        
        # 애니메이션 및 상태 지속 시간용
        self.anim_time = 0.0
        self.state_timer_counter = 0
        self.state_duration = random.randint(100, 200)
        
        # 빼꼼(Peek) 동작 전용 변수들
        self.peek_type = None
        self.peek_phase = 0    # 0: 숨어 들어가는 중, 1: 훔쳐보는 중, 2: 복귀하는 중
        self.peek_target_x = 0
        self.peek_target_y = 0
        self.peek_return_x = 0
        self.peek_return_y = 0
        self.peek_speed = 1.2
        
        # 최초 합성 프레임 생성 및 적용
        self.update_character_visual()
        
        # 6. 마우스 드래그 변수
        self.drag_position = QPoint()
        self.is_dragging = False
        
        # 7. 시스템 트레이 아이콘 구축
        self.init_tray()
        
        # 8. 주기적으로 동작(30ms 마다, 약 33fps)을 제어할 타이머 시작
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_behavior)
        self.timer.start(30)

    def pil_to_qpixmap(self, pil_img):
        """PIL Image 객체를 고속으로 QPixmap 데이터로 바꾸어 줍니다."""
        im_data = pil_img.tobytes("raw", "RGBA")
        qimg = QImage(im_data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimg)

    def assemble_pet(self, body_key, flip=False, sleep_y_offset=0, head_wobble=0):
        """
        주어진 몸통 템플릿과 사용자 얼굴(face.png)을 결합하여
        하나의 완성된 100x100 RGBA 이미지를 생성합니다.
        """
        body_path, joint = self.joints[body_key]
        neck_x, neck_y = joint
        
        # 1) 몸통 및 얼굴 오픈
        body_img = Image.open(body_path).convert("RGBA")
        face_img = Image.open(self.face_path).convert("RGBA")
        
        # 2) 100x100 크기의 완전 투명 캔버스 생성
        canvas = Image.new("RGBA", (self.char_size, self.char_size), (0, 0, 0, 0))
        
        # 3) 몸통 합성 (캔버스 아래쪽 중앙 배치 - 몸통 크기는 64x64)
        body_x = (self.char_size - 64) // 2  # 18
        body_y = self.char_size - 64         # 36
        canvas.paste(body_img, (body_x, body_y), body_img)
        
        # 4) 얼굴 합성 (목 조인트 중심에 얼굴 50x50의 센터가 오도록 계산)
        joint_abs_x = body_x + neck_x
        joint_abs_y = body_y + neck_y
        
        face_x = joint_abs_x - 25
        face_y = joint_abs_y - 25 + sleep_y_offset
        
        canvas.paste(face_img, (face_x, face_y), face_img)
        
        # 5) 걷는 방향에 맞추어 좌우 반전 처리
        if flip:
            canvas = canvas.transpose(Image.FLIP_LEFT_RIGHT)
            
        return canvas

    def update_character_visual(self):
        """현재 캐릭터의 상태에 최적화된 스프라이트 결합 프레임을 QLabel에 반영합니다."""
        if not os.path.exists(self.face_path):
            # face.png가 없을 경우 sample_cat.png에서 임시 생성 시도
            if os.path.exists("sample_cat.png"):
                extract_face("sample_cat.png", self.face_path, target_size=50)
            else:
                return

        # 상태별로 템플릿 몸통을 정하여 합성
        if self.state == STATE_FALL:
            # 낙하 중에는 대기(앉은) 몸통 적용
            composed = self.assemble_pet('idle', flip=(self.walk_direction < 0))
            
        elif self.state == STATE_IDLE:
            # 쉴 때는 앉은 몸통 적용
            composed = self.assemble_pet('idle', flip=(self.walk_direction < 0))
            
        elif self.state == STATE_WALK:
            # 걸어갈 때는 걷기 1, 2 발 모양 프레임을 교차 재생
            frame_num = int(self.anim_time) % 2
            walk_key = 'walk1' if frame_num == 0 else 'walk2'
            composed = self.assemble_pet(walk_key, flip=(self.walk_direction < 0))
            
        elif self.state == STATE_DRAG:
            # 마우스에 들려 끌려갈 때는 매달려 다리 버둥대는 대롱이 몸통 적용
            composed = self.assemble_pet('peek', flip=(self.walk_direction < 0))
            
        elif self.state == STATE_PEEK:
            # 화면 가장자리에 붙어 숨을 때 매달리기 몸통 적용
            composed = self.assemble_pet('peek', flip=(self.walk_direction < 0))
            
        elif self.state == STATE_SLEEP:
            # 자는 동안은 눕기 몸통을 쓰며, 숨 쉬는 리듬에 맞춰 머리 위치를 오르내림 (쌔근쌔근 연출)
            breath_offset = int(math.sin(self.anim_time) * 1.5) # 1~2픽셀 오차
            composed = self.assemble_pet('sleep', flip=(self.walk_direction < 0), sleep_y_offset=breath_offset)
            
        else:
            composed = self.assemble_pet('idle')

        # QLabel에 완성본 대입
        pixmap = self.pil_to_qpixmap(composed)
        self.label.setPixmap(pixmap)

    def init_tray(self):
        """윈도우 우측 하단 시스템 트레이 아이콘을 설정합니다."""
        self.tray_icon = QSystemTrayIcon(self)
        self.update_tray_icon()
        
        tray_menu = QMenu()
        
        change_photo_action = QAction("사진 변경 (새 펫 등록)", self)
        change_photo_action.triggered.connect(self.change_pet_photo)
        tray_menu.addAction(change_photo_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("종료", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def update_tray_icon(self):
        """트레이 영역에 펫 얼굴 아이콘이 뜨도록 갱신합니다."""
        if os.path.exists(self.face_path):
            self.tray_icon.setIcon(QIcon(self.face_path))
            self.tray_icon.setToolTip("나만의 데스크톱 펫 v2.0")

    def change_pet_photo(self):
        """사용자가 선택한 사진에서 OpenCV로 얼굴만 오려내어 실시간 조립합니다."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "새로운 펫 사진 선택",
            "",
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp);;모든 파일 (*)",
            options=options
        )
        
        if file_path:
            self.state = STATE_FALL
            self.velocity_y = 0
            
            output_face_path = os.path.abspath(self.face_path)
            
            # 사용자 진행 알림
            reply = QMessageBox.information(
                self,
                "얼굴 교체 중",
                "선택하신 사진에서 얼굴을 자동 감지해 잘라내는 중입니다.\n약 1~3초가 소요됩니다.",
                QMessageBox.Ok
            )
            
            # 2단계의 얼굴 감지 크롭기 작동
            success = extract_face(file_path, output_face_path, target_size=50)
            
            if success:
                self.update_tray_icon()
                self.update_character_visual()
                
                # 공중에서 떨어지며 교체 확인 시켜주기
                min_x, max_x, floor_y = self.get_screen_bounds()
                self.move(self.x(), floor_y - 250)
                
                QMessageBox.information(self, "성공", "얼굴 교체에 성공했습니다! 귀여운 새 모션으로 작동합니다. 👶✨")
            else:
                QMessageBox.critical(self, "실패", "얼굴을 감지하지 못했습니다. 얼굴이 뚜렷한 정면 사진을 다시 업로드해 주세요.")

    def get_screen_bounds(self):
        """사용 가능한 화면의 좌우/하단 경계 범위를 구합니다."""
        desktop = QApplication.desktop()
        screen_rect = desktop.availableGeometry(self)
        return screen_rect.left(), screen_rect.right() - self.window_width, screen_rect.bottom() - self.window_height

    def start_peek(self, peek_type, current_x, current_y):
        """지정된 타입으로 빼꼼(Peek) 상태를 시작합니다."""
        self.state = STATE_PEEK
        self.peek_type = peek_type
        self.peek_phase = 0
        self.state_timer_counter = 0
        self.anim_time = 0.0
        
        min_x, max_x, floor_y = self.get_screen_bounds()
        self.peek_return_x = current_x
        self.peek_return_y = current_y
        
        # 몸통이 100x100 캔버스 내부에서 약 64x64 크기이므로 30px 버퍼
        visible_buffer = 30
        
        if peek_type == PEEK_LEFT:
            self.peek_target_x = min_x - (self.window_width - visible_buffer)
            self.peek_target_y = current_y
            self.walk_direction = 1
            
        elif peek_type == PEEK_RIGHT:
            self.peek_target_x = max_x + (self.window_width - visible_buffer)
            self.peek_target_y = current_y
            self.walk_direction = -1
            
        elif peek_type == PEEK_BOTTOM:
            visible_h_buffer = 35
            self.peek_target_x = current_x
            self.peek_target_y = floor_y + (self.window_height - visible_h_buffer)

    def update_behavior(self):
        """매 프레임 호출되어 펫의 상태(물리, 애니메이션, 인공지능)를 갱신합니다."""
        min_x, max_x, floor_y = self.get_screen_bounds()
        
        # 디버그용으로 초기 10프레임 동안의 위치와 상태 정보를 콘솔에 출력합니다.
        if not hasattr(self, 'debug_count'):
            self.debug_count = 0
        if self.debug_count < 10:
            print(f"[DEBUG] State: {self.state}, Pos: ({self.x()}, {self.y()}), FloorY: {floor_y}, Bounds X: ({min_x} ~ {max_x})")
            self.debug_count += 1
            if self.debug_count == 10:
                print("[DEBUG] 디버그 출력 완료. 계속 동작 중...")
        
        # --- 1. 드래그나 빼꼼 상태가 아니고 공중에 떠 있으면 무조건 FALL(낙하) 상태로 전환 ---
        if self.state not in [STATE_DRAG, STATE_PEEK] and self.y() < floor_y:
            if self.state != STATE_FALL:
                self.state = STATE_FALL
                self.velocity_y = 0
        
        # --- 2. 상태별 물리 연산 및 좌표 이동 ---
        if self.state == STATE_DRAG:
            pass
            
        elif self.state == STATE_FALL:
            self.velocity_y += self.gravity
            next_y = self.y() + int(self.velocity_y)
            
            # 바닥 충돌 판정
            if next_y >= floor_y:
                self.move(self.x(), floor_y)
                self.velocity_y = 0
                self.state = STATE_IDLE
                self.state_timer_counter = 0
                self.state_duration = random.randint(50, 150)
            else:
                self.move(self.x(), next_y)
                
        elif self.state == STATE_WALK:
            next_x = self.x() + int(self.velocity_x)
            
            # 모니터 좌우 경계 도달 확인
            if next_x <= min_x:
                next_x = min_x
                if random.random() < 0.30:
                    self.start_peek(PEEK_LEFT, next_x, self.y())
                    return
                else:
                    self.walk_direction = 1
                    self.velocity_x = self.walk_speed * self.walk_direction
            elif next_x >= max_x:
                next_x = max_x
                if random.random() < 0.30:
                    self.start_peek(PEEK_RIGHT, next_x, self.y())
                    return
                else:
                    self.walk_direction = -1
                    self.velocity_x = self.walk_speed * self.walk_direction
                
            self.move(next_x, self.y())
            
            # 걷기 프레임 재생 시간 갱신
            self.anim_time += 0.20
            
            # 일정 시간 걸으면 지쳐서 쉬거나 눕도록 제어
            self.state_timer_counter += 1
            if self.state_timer_counter >= self.state_duration:
                # 쉴 행동 결정
                self.state = random.choice([STATE_IDLE, STATE_SLEEP])
                self.state_timer_counter = 0
                self.state_duration = random.randint(100, 250)
                self.anim_time = 0.0
                
        elif self.state == STATE_IDLE:
            self.state_timer_counter += 1
            if self.state_timer_counter >= self.state_duration:
                rand_val = random.random()
                if rand_val < 0.15:
                    self.start_peek(PEEK_BOTTOM, self.x(), self.y())
                elif rand_val < 0.35:
                    # 앉아 쉬다가 누워 자기로 전환
                    self.state = STATE_SLEEP
                    self.state_timer_counter = 0
                    self.state_duration = random.randint(150, 350)
                    self.anim_time = 0.0
                else:
                    # 다시 걷기
                    self.state = STATE_WALK
                    self.state_timer_counter = 0
                    self.state_duration = random.randint(150, 300)
                    self.walk_direction = random.choice([1, -1])
                    self.velocity_x = self.walk_speed * self.walk_direction
                    self.anim_time = 0.0
                    
        elif self.state == STATE_SLEEP:
            # 자는 동안에도 호흡 사인파를 갱신
            self.anim_time += 0.10
            
            self.state_timer_counter += 1
            if self.state_timer_counter >= self.state_duration:
                # 꿀잠을 자고 나면 다시 걷기 시작
                self.state = STATE_WALK
                self.state_timer_counter = 0
                self.state_duration = random.randint(150, 300)
                self.walk_direction = random.choice([1, -1])
                self.velocity_x = self.walk_speed * self.walk_direction
                self.anim_time = 0.0
                    
        elif self.state == STATE_PEEK:
            # --- 3. 빼꼼(Peek) 행동 시뮬레이션 ---
            curr_x = self.x()
            curr_y = self.y()
            
            if self.peek_phase == 0:
                # [Phase 0] 숨기 진입
                dx = self.peek_target_x - curr_x
                dy = self.peek_target_y - curr_y
                dist = math.hypot(dx, dy)
                
                if dist < 2.0:
                    self.move(self.peek_target_x, self.peek_target_y)
                    self.peek_phase = 1
                    self.state_timer_counter = 0
                    self.state_duration = random.randint(120, 220)
                else:
                    step_x = (dx / dist) * self.peek_speed
                    step_y = (dy / dist) * self.peek_speed
                    self.move(curr_x + int(step_x), curr_y + int(step_y))
                
            elif self.peek_phase == 1:
                # [Phase 1] 훔쳐보기 대기
                self.anim_time += 0.15
                
                self.state_timer_counter += 1
                if self.state_timer_counter >= self.state_duration:
                    self.peek_phase = 2
                    
            elif self.peek_phase == 2:
                # [Phase 2] 복귀
                dx = self.peek_return_x - curr_x
                dy = self.peek_return_y - curr_y
                dist = math.hypot(dx, dy)
                
                if dist < 2.0:
                    self.move(self.peek_return_x, self.peek_return_y)
                    self.state = STATE_WALK
                    self.state_timer_counter = 0
                    self.state_duration = random.randint(150, 300)
                    
                    if self.peek_type == PEEK_LEFT:
                        self.walk_direction = 1
                    elif self.peek_type == PEEK_RIGHT:
                        self.walk_direction = -1
                    else:
                        self.walk_direction = random.choice([1, -1])
                        
                    self.velocity_x = self.walk_speed * self.walk_direction
                    self.anim_time = 0.0
                else:
                    step_x = (dx / dist) * self.peek_speed
                    step_y = (dy / dist) * self.peek_speed
                    self.move(curr_x + int(step_x), curr_y + int(step_y))

        # 프레임의 합성 비주얼을 매 프레임 업데이트
        self.update_character_visual()

    # --- 마우스 클릭 및 드래그 이벤트 연동 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.state = STATE_DRAG
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            self.update_character_visual()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.is_dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.state = STATE_FALL
            self.velocity_y = 0
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    QApplication.setQuitOnLastWindowClosed(False)
    
    face_image = "face.png"
    # face.png가 없을 경우 sample_cat.png에서 가공 시도
    if not os.path.exists(face_image) and os.path.exists("sample_cat.png"):
        extract_face("sample_cat.png", face_image, target_size=50)
        
    pet = DesktopPet(face_image)
    pet.move(500, 100)
    pet.show()
    
    sys.exit(app.exec_())
