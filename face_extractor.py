# -*- coding: utf-8 -*-
import sys
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw

def extract_face(input_path, output_path, target_size=50):
    """
    입력 이미지에서 얼굴을 검출하고, 동그란 투명 원 마스크로 오려내어 PNG로 저장합니다.
    
    :param input_path: 원본 인물 이미지 경로
    :param output_path: 가공된 얼굴 PNG를 저장할 경로
    :param target_size: 오려낸 얼굴의 가로/세로 규격 (기본값: 50 픽셀)
    :return: 성공 여부 (True / False)
    """
    try:
        if not os.path.exists(input_path):
            print(f"오류: 입력 이미지가 존재하지 않습니다: {input_path}")
            return False

        # Windows 환경의 한글 파일 경로 호환성을 위해 바이너리 형태로 안전하게 로드
        img_array = np.fromfile(input_path, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            print("오류: 이미지를 디코딩할 수 없습니다.")
            return False

        # 얼굴 검출 속도 및 정확도를 위해 그레이스케일(흑백) 변환
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # OpenCV에 기본 내장된 Haar Cascade 얼굴 감지 모델 파일 경로 획득
        face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(face_cascade_path)

        # 얼굴 검출 (스케일 및 최소 이웃 픽셀 조건 지정)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        # 이미지 색상 공간을 BGR에서 RGB로 변환하여 PIL 이미지로 래핑
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        # 감지된 얼굴이 1개 이상 있는 경우
        if len(faces) > 0:
            print(f"사진 속에서 얼굴을 {len(faces)}개 감지했습니다. 가장 큰 얼굴을 추출합니다.")
            # 화면에서 가장 큰 영역을 차지하는 얼굴을 메인 펫으로 선택
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            x, y, w, h = faces[0]
            
            # 얼굴 전반(머리카락 및 턱선)이 넉넉히 들어가도록 좌우 15%, 상하 20% 마진을 추가하여 자릅니다.
            margin_x = int(w * 0.15)
            margin_y = int(h * 0.20)
            
            crop_x1 = max(0, x - margin_x)
            crop_y1 = max(0, y - margin_y)
            crop_x2 = min(pil_img.width, x + w + margin_x)
            crop_y2 = min(pil_img.height, y + h + margin_y)
        else:
            # 예외 처리(Fallback): 사진 속에서 얼굴 감지가 실패했을 경우
            # 사진 상단 중앙 영역(통상 머리가 위치한 곳)을 기하학적 비율로 자동 둥글게 크롭
            print("경고: 사진 속에서 사람 얼굴을 감지하지 못했습니다. 상단 중앙 영역을 얼굴로 대체하여 크롭합니다.")
            w = int(pil_img.width * 0.5)
            h = w
            x = (pil_img.width - w) // 2
            y = int(pil_img.height * 0.1) # 상단 10% 지점
            
            crop_x1 = max(0, x)
            crop_y1 = max(0, y)
            crop_x2 = min(pil_img.width, x + w)
            crop_y2 = min(pil_img.height, y + h)

        # 1) 사각형으로 얼굴 부분 오려내기
        cropped = pil_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        
        # 2) 둥근 형태 마스크 이미지(L 모드, 검은색 바탕) 생성
        mask = Image.new("L", cropped.size, 0)
        draw = ImageDraw.Draw(mask)
        # 마스크 위에 흰색 타원을 그려서 타원 안만 보이게 만듦 (안티앨리어싱 효과 적용)
        draw.ellipse((0, 0, cropped.size[0], cropped.size[1]), fill=255)
        
        # 3) 오려낸 얼굴에 투명 알파 채널 적용
        face_rgba = cropped.convert("RGBA")
        face_rgba.putalpha(mask)
        
        # 4) 펫 몸통 목 규격에 최적화된 50x50 사이즈로 고품질 축소
        resized_face = face_rgba.resize((target_size, target_size), Image.Resampling.LANCZOS)
        
        # 5) PNG 포맷으로 투명도 보존하여 최종 저장
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
            
        resized_face.save(output_path, "PNG")
        print(f"얼굴 원형 오려내기 성공! 저장 경로: {output_path}")
        return True

    except Exception as e:
        print(f"얼굴 크롭 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python face_extractor.py <입력_이미지> <출력_이미지> [규격_크기]")
    else:
        in_p = sys.argv[1]
        out_p = sys.argv[2]
        size = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        extract_face(in_p, out_p, size)
