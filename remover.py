# -*- coding: utf-8 -*-
import sys
import os
from PIL import Image
from rembg import remove

def remove_background(input_path, output_path, target_height=128):
    """
    입력 이미지의 배경을 제거하고, 지정된 높이에 맞춰 비율을 유지한 뒤 PNG 파일로 저장합니다.
    
    :param input_path: 원본 이미지 파일 경로
    :param output_path: 배경이 제거된 저장할 PNG 파일 경로
    :param target_height: 캐릭터의 세로 크기 (기본값: 128 픽셀)
    :return: 성공 여부 (True / False)
    """
    try:
        if not os.path.exists(input_path):
            print(f"오류: 입력 파일을 찾을 수 없습니다. ({input_path})")
            return False
            
        print(f"AI 배경 제거 작업을 시작합니다... (대상: {os.path.basename(input_path)})")
        
        # 1. 이미지 열기
        input_image = Image.open(input_path)
        
        # 2. rembg를 이용해 AI 배경 제거 수행
        output_image = remove(input_image)
        
        # 3. 투명도(Alpha 채널) 기준 불필요한 외곽 빈 여백 자동 잘라내기 (Auto-crop)
        bbox = output_image.getbbox()
        if bbox:
            output_image = output_image.crop(bbox)
            print("캐릭터 주변의 불필요한 여백을 잘라냈습니다.")
        
        # 4. 캐릭터 크기 리사이징 (세로 길이를 기준으로 가로 비율 유지)
        width, height = output_image.size
        aspect_ratio = width / height
        target_width = int(target_height * aspect_ratio)
        
        # 고품질 리사이징 필터 적용
        resized_image = output_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # 5. PNG 파일로 저장 (투명도 유지)
        # 만약 대상 디렉토리가 없으면 생성
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
            
        resized_image.save(output_path, "PNG")
        print(f"배경 제거 완료! 저장된 경로: {output_path} (크기: {target_width}x{target_height})")
        return True
        
    except Exception as e:
        print(f"배경 제거 중 오류가 발생했습니다: {e}")
        return False

if __name__ == "__main__":
    # 터미널에서 단독으로도 실행할 수 있도록 인자 처리 설정
    if len(sys.argv) < 3:
        print("사용법: python remover.py <입력_이미지_경로> <출력_이미지_경로> [세로_크기]")
    else:
        in_path = sys.argv[1]
        out_path = sys.argv[2]
        h = int(sys.argv[3]) if len(sys.argv) > 3 else 128
        remove_background(in_path, out_path, h)
