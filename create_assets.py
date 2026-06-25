# -*- coding: utf-8 -*-
import os
from PIL import Image, ImageDraw

def create_cat_assets():
    """
    데스크톱 펫의 동작별 핑크 젤리 고양이 몸통 자산들을 생성하여 assets/ 폴더에 저장합니다.
    """
    # 에셋 폴더 생성
    os.makedirs("assets", exist_ok=True)
    
    # 사랑스러운 아기 고양이 파스텔톤 색상 팔레트 정의
    pink_body = (255, 192, 203)      # 연한 베이비 핑크 (몸통 기본)
    pink_dark = (255, 130, 150)      # 진한 핑크 (발바닥 젤리 포인트)
    outline_color = (80, 50, 50)      # 부드러운 다크 브라운 (윤곽선)
    line_width = 3
    
    # -------------------------------------------------------------
    # 1. body_idle.png (단정히 앉아서 쉬는 대기 몸통)
    # - 목 조인트 타겟 좌표: (32, 25)
    # -------------------------------------------------------------
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 살랑살랑 올라간 꼬리
    draw.arc((36, 25, 52, 55), start=0, end=180, fill=pink_body, width=8)
    draw.arc((36, 25, 52, 55), start=0, end=180, fill=outline_color, width=line_width)
    
    # 포동포동한 둥근 몸통
    draw.ellipse((14, 25, 50, 55), fill=pink_body, outline=outline_color, width=line_width)
    
    # 얌전히 앉은 두 앞발
    draw.ellipse((16, 50, 28, 59), fill=pink_body, outline=outline_color, width=line_width)
    draw.ellipse((36, 50, 48, 59), fill=pink_body, outline=outline_color, width=line_width)
    
    # 발바닥 핑크 젤리 디테일
    draw.ellipse((19, 53, 25, 57), fill=pink_dark)
    draw.ellipse((39, 53, 45, 57), fill=pink_dark)
    
    img.save("assets/body_idle.png", "PNG")
    
    # -------------------------------------------------------------
    # 2. body_walk1.png (걷기 모션 프레임 1 - 앞발 뻗기)
    # - 목 조인트 타겟 좌표: (32, 25)
    # -------------------------------------------------------------
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 꼬리
    draw.arc((38, 20, 54, 50), start=30, end=210, fill=pink_body, width=8)
    draw.arc((38, 20, 54, 50), start=30, end=210, fill=outline_color, width=line_width)
    
    # 몸통
    draw.ellipse((14, 25, 50, 55), fill=pink_body, outline=outline_color, width=line_width)
    
    # 발 걷기 1 (왼발 뻗고 오른발 안착)
    draw.ellipse((12, 48, 24, 57), fill=pink_body, outline=outline_color, width=line_width)
    draw.ellipse((38, 52, 50, 59), fill=pink_body, outline=outline_color, width=line_width)
    
    img.save("assets/body_walk1.png", "PNG")
    
    # -------------------------------------------------------------
    # 3. body_walk2.png (걷기 모션 프레임 2 - 뒷발 뻗기)
    # - 목 조인트 타겟 좌표: (32, 25)
    # -------------------------------------------------------------
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 꼬리 반대 각도
    draw.arc((34, 20, 50, 50), start=0, end=180, fill=pink_body, width=8)
    draw.arc((34, 20, 50, 50), start=0, end=180, fill=outline_color, width=line_width)
    
    # 몸통
    draw.ellipse((14, 25, 50, 55), fill=pink_body, outline=outline_color, width=line_width)
    
    # 발 걷기 2 (왼발 안착하고 오른발 뻗기)
    draw.ellipse((18, 52, 30, 59), fill=pink_body, outline=outline_color, width=line_width)
    draw.ellipse((32, 48, 44, 57), fill=pink_body, outline=outline_color, width=line_width)
    
    img.save("assets/body_walk2.png", "PNG")
    
    # -------------------------------------------------------------
    # 4. body_sleep.png (바닥에 발 뻗고 옆으로 누운 눕기 몸통)
    # - 목 조인트 타겟 좌표: (18, 43) [누워있으므로 목 위치가 좌하단으로 낮아집니다]
    # -------------------------------------------------------------
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 편안하게 밑으로 만 꼬리
    draw.arc((42, 35, 58, 55), start=90, end=270, fill=pink_body, width=7)
    draw.arc((42, 35, 58, 55), start=90, end=270, fill=outline_color, width=line_width)
    
    # 납작하게 엎드려 늘어진 몸통
    draw.ellipse((10, 36, 52, 58), fill=pink_body, outline=outline_color, width=line_width)
    
    # 뻗은 귀여운 두 뒷발
    draw.ellipse((20, 53, 30, 60), fill=pink_body, outline=outline_color, width=line_width)
    draw.ellipse((34, 53, 44, 60), fill=pink_body, outline=outline_color, width=line_width)
    
    img.save("assets/body_sleep.png", "PNG")
    
    # -------------------------------------------------------------
    # 5. body_peek.png (벽을 움켜쥐고 매달려 있는 빼꼼 몸통)
    # - 목 조인트 타겟 좌표: (32, 22)
    # -------------------------------------------------------------
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 대롱대롱 매달려 길어진 타원 몸통
    draw.ellipse((20, 24, 44, 58), fill=pink_body, outline=outline_color, width=line_width)
    
    # 축 처진 귀여운 꼬리
    draw.arc((12, 45, 28, 61), start=270, end=90, fill=pink_body, width=6)
    draw.arc((12, 45, 28, 61), start=270, end=90, fill=outline_color, width=line_width)
    
    # 벽면을 꼬옥 짚고 있는 좌우 대칭 발
    draw.ellipse((10, 28, 20, 38), fill=pink_body, outline=outline_color, width=line_width)
    draw.ellipse((44, 28, 54, 38), fill=pink_body, outline=outline_color, width=line_width)
    
    # 대롱대롱 아래로 내린 뒷발
    draw.ellipse((22, 53, 30, 61), fill=pink_body, outline=outline_color, width=line_width)
    draw.ellipse((34, 53, 42, 61), fill=pink_body, outline=outline_color, width=line_width)
    
    img.save("assets/body_peek.png", "PNG")
    print("모든 몸통 스프라이트 자산이 assets/ 폴더 아래 정상적으로 생성되었습니다.")

if __name__ == "__main__":
    create_cat_assets()
