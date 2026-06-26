# -*- coding: utf-8 -*-
import sys
import os
import cv2
import numpy as np
import mediapipe as mp
from PIL import Image, ImageDraw

def get_skin_color(img, pts):
    """지정된 다각형 영역 주변의 평균 피부색을 구합니다."""
    mask = np.zeros(img.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    mean_color = cv2.mean(img, mask=mask)[:3]
    return tuple(map(int, mean_color))

def warp_face_angle(face_crop, landmarks, w, h, direction="right"):
    """
    코를 중심으로 좌우 영역을 비대칭 스케일링하여
    고개를 살짝 한쪽으로 돌린 입체감(3D 회전 효과)을 생성합니다.
    """
    # 코 중앙 랜드마크 인덱스 1번
    nose_x = int(landmarks[1].x * w)
    
    # 얼굴 좌우 변환용 3점 정의 (아핀 변환 사용)
    # 원본 점
    src_pts = np.float32([
        [0, 0],
        [nose_x, 0],
        [w, 0],
        [0, h],
        [nose_x, h],
        [w, h]
    ])
    
    # 변형될 목표 점 (방향에 따라 가로 비율 비대칭 조절)
    if direction == "right":
        # 오른쪽으로 고개 돌림 (왼쪽 뺨 압축, 오른쪽 뺨 확장)
        new_nose_x = int(nose_x * 0.8)
    else:
        # 왼쪽으로 고개 돌림 (왼쪽 뺨 확장, 오른쪽 뺨 압축)
        new_nose_x = int(nose_x * 1.2)
        
    dst_pts = np.float32([
        [0, 0],
        [new_nose_x, 0],
        [w, 0],
        [0, h],
        [new_nose_x, h],
        [w, h]
    ])
    
    # 뺨 좌우 영역별 아핀 매핑
    result = np.zeros_like(face_crop)
    
    # 1) 왼쪽 영역 변환
    src_l = np.float32([[0, 0], [nose_x, 0], [0, h], [nose_x, h]])
    dst_l = np.float32([[0, 0], [new_nose_x, 0], [0, h], [new_nose_x, h]])
    M_l = cv2.getPerspectiveTransform(src_l, dst_l)
    warp_l = cv2.warpPerspective(face_crop, M_l, (w, h))
    
    # 왼쪽 영역 마스크
    mask_l = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask_l, [np.array([[0, 0], [new_nose_x, 0], [new_nose_x, h], [0, h]], dtype=np.int32)], 255)
    
    # 2) 오른쪽 영역 변환
    src_r = np.float32([[nose_x, 0], [w, 0], [nose_x, h], [w, h]])
    dst_r = np.float32([[new_nose_x, 0], [w, 0], [new_nose_x, h], [w, h]])
    M_r = cv2.getPerspectiveTransform(src_r, dst_r)
    warp_r = cv2.warpPerspective(face_crop, M_r, (w, h))
    
    # 오른쪽 영역 마스크
    mask_r = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask_r, [np.array([[new_nose_x, 0], [w, 0], [w, h], [new_nose_x, h]], dtype=np.int32)], 255)
    
    # 결합
    result = cv2.bitwise_and(warp_l, warp_l, mask=mask_l) + cv2.bitwise_and(warp_r, warp_r, mask=mask_r)
    return result

def draw_spiral(img, center, max_r=7):
    """눈동자 자리에 만화풍의 뱅글뱅글 골뱅이 눈(당황 표정)을 그립니다."""
    cx, cy = center
    # 나선 그리기 (선 조각들을 이어서 달팽이 모양 만듦)
    for theta in np.arange(0, 4 * np.pi, 0.1):
        r = int((theta / (4 * np.pi)) * max_r)
        x = int(cx + r * math.cos(theta))
        y = int(cy + r * math.sin(theta))
        if theta == 0:
            last_x, last_y = x, y
        cv2.line(img, (last_x, last_y), (x, y), (70, 50, 50), 2)
        last_x, last_y = x, y

def generate_faces(input_path, output_dir="faces", target_size=50):
    """
    입력 이미지에서 얼굴을 검출하고, 랜드마크 분석을 통해
    표정별(대기, 걷기-좌, 걷기-우, 잠자기, 당황) 얼굴 PNG를 자동 생성합니다.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 윈도우 한글 경로 완벽 지원 디코딩
    img_array = np.fromfile(input_path, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_UNCHANGED)
    
    if img is None:
        print(f"오류: 이미지를 읽을 수 없습니다. ({input_path})")
        return False
        
    # 만약 투명 채널이 없는 3채널 이미지라면 4채널로 통일
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        
    h_orig, w_orig = img.shape[:2]
    
    # 1. 1단계와 동일한 방식으로 Haar Cascade 얼굴 검출기 가동
    face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(face_cascade_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    
    # 얼굴 사각형 획득
    if len(faces) > 0:
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h = faces[0]
        
        # 랜드마크 인식을 돕기 위해 사방 마진을 크게 둔 고해상도 사각형 크롭 (200x200 픽셀 근처 타겟)
        margin_x = int(w * 0.15)
        margin_y = int(h * 0.25)
        
        crop_x1 = max(0, x - margin_x)
        crop_y1 = max(0, y - margin_y)
        crop_x2 = min(w_orig, x + w + margin_x)
        crop_y2 = min(h_orig, y + h + margin_y)
        
        # 고해상도 얼굴 크롭본 생성
        face_crop = img[crop_y1:crop_y2, crop_x1:crop_x2].copy()
    else:
        # 얼굴 검출 실패 시 Fallback: 사진 상단 가운데 크롭
        print("얼굴 감지 실패: 상단 영역으로 강제 크롭을 수행합니다.")
        crop_w = int(w_orig * 0.6)
        crop_h = crop_w
        crop_x = (w_orig - crop_w) // 2
        crop_y = int(h_orig * 0.1)
        
        crop_x1, crop_y1 = max(0, crop_x), max(0, crop_y)
        crop_x2, crop_y2 = min(w_orig, crop_x + crop_w), min(h_orig, crop_y + crop_h)
        face_crop = img[crop_y1:crop_y2, crop_x1:crop_x2].copy()

    # 크롭된 얼굴 해상도
    ch, cw = face_crop.shape[:2]
    
    # 2. 미디어파이프 얼굴 랜드마크 분석 실행
    mp_face_mesh = mp.solutions.face_mesh
    
    # 미디어파이프 가동 (RGB 채널 사용)
    face_crop_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGRA2RGB)
    
    landmarks = None
    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5
    ) as face_mesh:
        results = face_mesh.process(face_crop_rgb)
        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            print("MediaPipe 인공지능 얼굴 랜드마크를 성공적으로 검출했습니다.")

    # 3. 마스킹 처리를 위한 둥근 원형 마스크 생성 도구 정의 (PIL 이용)
    def apply_circle_mask_and_save(cv2_image, save_name):
        # cv2 BGR -> PIL RGBA 변환
        img_rgb = cv2.cvtColor(cv2_image, cv2.COLOR_BGRA2RGBA)
        pil_img = Image.fromarray(img_rgb)
        
        # 원형 마스크 그리기
        mask = Image.new("L", pil_img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, pil_img.size[0], pil_img.size[1]), fill=255)
        
        pil_img.putalpha(mask)
        
        # 50x50 정규화 리사이징 및 저장
        resized = pil_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(output_dir, save_name), "PNG")
        print(f"표정 생성 완료: {save_name}")

    # --- 만약 랜드마크 검출이 완전히 실패한 경우 Fallback 처리 ---
    if landmarks is None:
        print("경고: MediaPipe 랜드마크 감지 실패. 기본 이미지 복사형 모션으로 대체합니다.")
        apply_circle_mask_and_save(face_crop, "face_idle.png")
        apply_circle_mask_and_save(face_crop, "face_sleep.png") # 잠자는 척 복사
        apply_circle_mask_and_save(face_crop, "face_walk_r.png")
        apply_circle_mask_and_save(face_crop, "face_walk_l.png")
        apply_circle_mask_and_save(face_crop, "face_drag.png")
        return True

    # -------------------------------------------------------------
    # 3-1. face_idle.png (대기 상태 - 정면 원본 크롭)
    # -------------------------------------------------------------
    apply_circle_mask_and_save(face_crop, "face_idle.png")

    # -------------------------------------------------------------
    # 3-2. face_sleep.png (잠자기 상태 - 감은 눈 아치형 덧그리기)
    # - 왼쪽 눈 랜드마크 바운딩: 159(위), 145(아래), 33(안쪽), 133(바깥쪽)
    # - 오른쪽 눈 랜드마크 바운딩: 386(위), 374(아래), 362(안쪽), 263(바깥쪽)
    # -------------------------------------------------------------
    sleep_img = face_crop.copy()
    
    # 왼쪽 눈 랜드마크 좌표값 픽셀 변환
    l_in_x, l_in_y = int(landmarks[33].x * cw), int(landmarks[33].y * ch)
    l_out_x, l_out_y = int(landmarks[133].x * cw), int(landmarks[133].y * ch)
    l_top_x, l_top_y = int(landmarks[159].x * cw), int(landmarks[159].y * ch)
    l_bot_x, l_bot_y = int(landmarks[145].x * cw), int(landmarks[145].y * ch)
    
    # 오른쪽 눈 랜드마크 좌표값 픽셀 변환
    r_in_x, r_in_y = int(landmarks[362].x * cw), int(landmarks[362].y * ch)
    r_out_x, r_out_y = int(landmarks[263].x * cw), int(landmarks[263].y * ch)
    r_top_x, r_top_y = int(landmarks[386].x * cw), int(landmarks[386].y * ch)
    r_bot_x, r_bot_y = int(landmarks[374].x * cw), int(landmarks[374].y * ch)

    # 1) 눈 영역 다각형 구성해서 주변 피부색으로 메꾸기
    l_eye_poly = np.array([
        [l_in_x, l_in_y], [l_top_x, l_top_y], [l_out_x, l_out_y], [l_bot_x, l_bot_y]
    ], dtype=np.int32)
    r_eye_poly = np.array([
        [r_in_x, r_in_y], [r_top_x, r_top_y], [r_out_x, r_out_y], [r_bot_x, r_bot_y]
    ], dtype=np.int32)

    # 주변 피부색 계산 및 채우기
    l_skin = get_skin_color(sleep_img, l_eye_poly)
    r_skin = get_skin_color(sleep_img, r_eye_poly)
    
    cv2.fillPoly(sleep_img, [l_eye_poly], l_skin)
    cv2.fillPoly(sleep_img, [r_eye_poly], r_skin)

    # 2) 감은 눈 아치선(⌒ ⌒ 모양) 그리기
    # 다크브라운 꼬마 펫 윤곽선에 맞춰 눈 감은 선 드로잉
    line_col = (80, 50, 50)
    
    # 왼쪽 눈 아치선 (눈꺼풀 중심선을 둥글게 이음)
    l_center_x = (l_in_x + l_out_x) // 2
    l_center_y = (l_in_y + l_out_y) // 2 + 1
    cv2.ellipse(sleep_img, (l_center_x, l_center_y), (abs(l_out_x - l_in_x) // 2, 4), 180, 0, 180, line_col, 2)

    # 오른쪽 눈 아치선
    r_center_x = (r_in_x + r_out_x) // 2
    r_center_y = (r_in_y + r_out_y) // 2 + 1
    cv2.ellipse(sleep_img, (r_center_x, r_center_y), (abs(r_out_x - r_in_x) // 2, 4), 180, 0, 180, line_col, 2)

    apply_circle_mask_and_save(sleep_img, "face_sleep.png")

    # -------------------------------------------------------------
    # 3-3. face_walk_r.png (걷기 우측 - 코 기준 좌우 아핀 와핑)
    # -------------------------------------------------------------
    walk_r_img = warp_face_angle(face_crop, landmarks, cw, ch, direction="right")
    apply_circle_mask_and_save(walk_r_img, "face_walk_r.png")

    # -------------------------------------------------------------
    # 3-4. face_walk_l.png (걷기 좌측 - 우측 각도를 좌우반전시켜 자동 생성)
    # -------------------------------------------------------------
    walk_l_img = cv2.flip(walk_r_img, 1) # 1: 가로 대칭 반전
    apply_circle_mask_and_save(walk_l_img, "face_walk_l.png")

    # -------------------------------------------------------------
    # 3-5. face_drag.png (대롱대롱 당황 상태 - 뱅글뱅글 눈동자 묘사)
    # -------------------------------------------------------------
    drag_img = face_crop.copy()
    l_eye_center = ((l_in_x + l_out_x) // 2, (l_in_y + l_out_y) // 2)
    r_eye_center = ((r_in_x + r_out_x) // 2, (r_in_y + r_out_y) // 2)
    
    # 기존 눈동자 자리에 골뱅이 나선선 그리기
    draw_spiral(drag_img, l_eye_center, max_r=int(abs(l_out_x - l_in_x) * 0.35))
    draw_spiral(drag_img, r_eye_center, max_r=int(abs(r_out_x - r_in_x) * 0.35))
    
    apply_circle_mask_and_save(drag_img, "face_drag.png")
    
    print("AI 랜드마크 기반 다중 표정 세트 합성 성공!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python face_warp.py <입력_인물_사진>")
    else:
        generate_faces(sys.argv[1])
