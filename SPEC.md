# Desktop Pet — Core Specification v3.0

사용자 사진에서 얼굴을 자동 추출하여 캐릭터 몸통과 합성한 뒤,
**윈도우 바탕화면 위를 자유롭게 돌아다니는** 데스크톱 가젯 프로그램.

---

## 참고 프로그램 (벤치마크)

| 프로그램 | 핵심 기믹 | 참고 링크 |
|---|---|---|
| **Shimeji-ee** | 바탕화면을 돌아다니고, 열린 창을 타고 올라가고, 마우스 포인터를 던지는 인터랙션 | https://github.com/kilkakon/Shimeji-ee |
| **eSheep** | 열린 윈도우 창 위를 양이 걸어 다니고, 창 밖으로 나가면 낙하 | https://github.com/Adrianotiger/desktopPet |
| **RunCat** | 작업표시줄에서 고양이가 뛰는 속도로 실시간 CPU 사용량을 보여줌 | https://github.com/Kyome22/RunCat_for_windows |

---

## 기술 스택

| 영역 | 기술 | 설명 |
|---|---|---|
| 언어 | Python 3.x | |
| GUI | PyQt5 | 투명 오버레이 윈도우 (`FramelessWindowHint` + `TranslucentBackground`) |
| 얼굴 감지 | OpenCV Haar Cascade | `haarcascade_frontalface_default.xml` |
| 얼굴 랜드마크 | MediaPipe Face Mesh | AR 이펙트용 468개 랜드마크 |
| 배경 제거 | rembg (optional) | 로컬 AI 누끼. onnxruntime 없으면 sys.exit() 호출하므로 **반드시 지연(lazy) import** 필수 |
| 시스템 모니터링 | psutil | CPU 사용률 → 걷기 속도 연동 (RunCat) |
| 윈도우 API | ctypes user32.dll | 열린 창 좌표 감지 (eSheep) |
| 이미지 처리 | Pillow (PIL) | 스프라이트 합성, 4x 슈퍼샘플링 |

---

## 아키텍처

```
desktop_pet.py (Controller)
├── pet_state_machine.py (Model) — 물리, 상태 전이, CPU 연동
├── pet_renderer.py (View) — 스프라이트 합성, PIL→QPixmap
├── face_warp.py — 사진→얼굴 추출→AR 표정 8장 생성
└── create_assets.py — 몸통/팔/다리/꼬리 에셋 자동 생성 (1회 실행)
```

---

## 코어 기능

### 1. 투명 오버레이 윈도우
- `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`
- 배경 100% 투명, 작업표시줄에 미표시
- 시스템 트레이 아이콘으로 메뉴 제공 (사진 변경 / 종료)

### 2. 중력 + 바닥 착지
- 프로그램 시작 시 화면 상단에서 자유낙하 (가속도 적용)
- 작업표시줄 상단을 바닥으로 인식하여 착지
- **주의**: 작업표시줄 높이를 하드코딩(40px)하지 말 것. `QScreen.availableGeometry()` 사용

### 3. 걷기 모션
- 바닥 착지 후 좌우 자동 이동
- 2프레임 이상 걷기 애니메이션 (바운스 + 팔다리 교차)
- 화면 끝 도달 시 방향 전환
- **CPU 사용률 연동 (RunCat)**: `psutil.cpu_percent()`로 1초 간격 폴링, 사용률에 비례하여 걷기 속도/애니메이션 속도 가변

### 4. 마우스 드래그
- 좌클릭으로 집어서 이동
- 드래그 중 발버둥 모션
- 놓으면 현재 위치에서 자유낙하

### 5. 상태 전이 시스템
```
FALL → (바닥 닿음) → IDLE
IDLE → (랜덤 타이머) → WALK(65%) 또는 SLEEP(35%)
WALK → (랜덤 타이머) → IDLE 또는 SLEEP
WALK → (화면 끝) → 방향 전환
WALK → (창 밖 이탈) → FALL
SLEEP → (랜덤 타이머) → WALK
DRAG → (마우스 놓음) → FALL
```

### 6. 열린 창 위 걷기 (eSheep)
- `ctypes.windll.user32.GetForegroundWindow()` + `GetWindowRect()`로 활성 창 좌표 실시간 감지
- 펫이 창의 상단 테두리를 바닥으로 인식하여 걸어 다님
- 창 끝에서 벗어나면 자유낙하
- **자기 자신의 윈도우는 반드시 제외** (`winId()` 비교)
- 바탕화면, 작업표시줄, 타이틀 없는 시스템 창도 제외

### 7. 사진으로 얼굴 교체
- 트레이 메뉴 → 파일 선택 다이얼로그 (PNG/JPG)
- OpenCV Haar Cascade로 얼굴 영역 감지 → 넉넉한 마진으로 크롭
- (optional) rembg로 배경 완전 제거 (AI 로컬 처리, 무료, 오프라인)
- MediaPipe Face Mesh로 랜드마크 추출 → AR 이펙트로 표정 8장 자동 생성:
  - `idle` (기본), `sleep` (눈 감음), `walk_r`/`walk_l` (측면 워프)
  - `cry` (눈물), `laugh` (홍조+웃는 눈), `angry` (찡그린 눈썹+분노마크), `drag` (놀란 눈)
- **rembg 주의사항**: `from rembg import remove`를 모듈 레벨에서 하면 onnxruntime 미설치 시 `sys.exit()` 호출로 프로세스 사망. 반드시 함수 내부에서 subprocess 테스트 후 지연 import 할 것.

### 8. 스프라이트 에셋 시스템
- `create_assets.py`로 몸통(상태별 5종) + 발 + 손 + 꼬리 PNG 자동 생성
- 4x 슈퍼샘플링 후 LANCZOS 축소 → 안티앨리어싱된 고품질
- 에셋 없을 시 자동 생성하는 메커니즘 필요 (현재 수동 1회 실행)

### 9. 60FPS 렌더링 루프
- QTimer 16ms 간격으로 메인 루프 구동
- 상태별(idle/walk/sleep/drag) 전용 합성 메서드
- PIL로 파츠 합성 → `QImage.Format_RGBA8888` → `QPixmap` → `QLabel.setPixmap()`

### 10. 원클릭 실행
- 바탕화면에 `.bat` 파일 생성
- `pythonw.exe` 사용 (콘솔 창 숨김)
- `cd /d` + `chcp 65001`로 경로/인코딩 문제 방지

---

## 파일 구조 (목표)

```
DESKTOP_PET/
├── desktop_pet.py      # 메인 컨트롤러 (PyQt5 윈도우 + 게임 루프)
├── pet_state_machine.py # 물리 엔진 + 상태 전이 + CPU 연동
├── pet_renderer.py      # 스프라이트 합성 렌더러
├── face_warp.py         # 사진→얼굴 추출→AR 표정 생성
├── create_assets.py     # 몸통/사지 에셋 자동 생성기
├── requirements.txt     # pip 의존성 목록
├── .gitignore
├── assets/              # 생성된 몸통/사지 PNG 에셋
└── faces/               # 생성된 표정별 얼굴 PNG
```

---

## 의존성 (requirements.txt)

```
PyQt5
pillow
opencv-python
mediapipe
psutil
numpy
rembg[cpu]
```

---

## 알려진 함정 (Known Pitfalls)

1. **rembg sys.exit()**: rembg 패키지는 onnxruntime 백엔드가 없으면 import 단계에서 `sys.exit()`을 호출하여 try/except로 잡을 수 없음. 반드시 `subprocess.run([sys.executable, "-c", "from rembg import remove"])` 테스트 후 지연 import.
2. **cp949 인코딩**: Windows 터미널에서 한글/이모지 print 시 `UnicodeEncodeError` 발생. print문에 이모지 사용 금지.
3. **eSheep 자기참조**: `GetForegroundWindow()`가 펫 자신의 윈도우를 반환할 수 있음. `winId()`와 비교하여 자기를 밟지 않도록 처리 필수.
4. **작업표시줄 높이**: 40px 하드코딩 대신 `QScreen.availableGeometry().bottom()` 사용. DPI 스케일링 환경에서 깨짐.
5. **에셋 미생성**: `create_assets.py` 미실행 시 빈 화면. 메인 시작 시 assets/ 폴더 존재 여부 체크 후 자동 생성 권장.
