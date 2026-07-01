---
name: desktop-pet-dev
description: Desktop Pet(윈도우 데스크톱 펫 가젯) 개발 오케스트레이터. 펫 기능 추가·수정·개선(PySide6 전환, CharacterPack 상업화, 등록 UX, 알림 읽어주기, exe 패키징 등)을 ARCHITECT→BUILDER→REVIEWER 팀 루프로 조율한다. "펫 만들자/고치자/개선하자", "캐릭터팩", "펫에 ~기능 추가", "다시 실행/재실행/이어서" 등 이 프로젝트 개발 요청 시 반드시 사용. 단순 질문은 직접 응답 가능.
---

# Desktop Pet 개발 오케스트레이터

Desktop Pet 프로젝트의 기능 개발을 3-에이전트 팀(pet-architect / pet-builder / pet-reviewer)의
**계획→구현→검증 루프**로 조율한다. 실행 모드는 **에이전트 팀**.

승인된 로드맵: `C:\Users\cheoj\.claude\plans\sunny-jumping-iverson.md` (M0~M3).

## Phase 0: 컨텍스트 확인 (항상 먼저)
1. `_workspace/` 존재 여부 확인:
   - 없음 → **초기 실행**.
   - 있음 + 사용자가 부분 수정 요청 → **부분 재실행**(해당 모듈 에이전트만 재호출).
   - 있음 + 새 작업 → 기존 `_workspace/`를 `_workspace_{YYYYMMDD_HHMMSS}/`로 이동 후 새 실행.
2. `git status`로 작업트리 상태 확인. 현재 브랜치·HEAD 확인.
3. 착수할 마일스톤/모듈을 로드맵에서 확정하고 사용자에게 1줄 브리핑.

## Phase 1: 팀 가동 (에이전트 팀 패턴)
1. `Agent` 도구로 팀원을 spawn한다: `pet-architect`, `pet-builder`, `pet-reviewer`
   (각 `.claude/agents/*.md` 정의 사용). 고추론이라 모델 opus.
2. `TaskCreate`로 모듈 작업과 의존성을 만든다(브리프→구현→검수 순서).
3. 팀원은 `SendMessage`로 직접 조율, `_workspace/` 파일로 산출물을 주고받는다.

## Phase 2: 모듈 개발 루프 (모듈마다 반복)
```
ARCHITECT: _workspace/{NN}_architect_{module}_brief.md 작성 (계약·성공기준·리스크등급·회귀체크)
  → BUILDER: 로직=TDD(Red→Green→Refactor) / GUI=오프스크린 스모크. 코드+tests 작성
             → _workspace/{NN}_builder_{module}_review-request.md
  → REVIEWER: 계약·규칙·회귀 검수 → _workspace/{NN}_reviewer_{module}_feedback.md (Approve/Reject)
  → ARCHITECT: 승인/반려 판정. 반려면 BUILDER 재작업(1회 재시도).
```
- 로직 모듈은 `pytest` 통과가 Green 신호 → 루프 자동 진행 가능.
- GUI 모듈은 루프 끝에 **오프스크린 스모크 통과 + 사용자 수동 실행 안내**.

## Phase 3: 검증 게이트 + 커밋
1. **검증:** `.venv\Scripts\python.exe -m pytest`(로직) + 오프스크린 스모크(GUI) 통과 확인.
2. **회귀 확인:** M0 baseline 기능(낙하·걷기·드래그·잠자기·웹캠·CPU연동·창위걷기) 유지.
3. **커밋(오케스트레이터만):** 승인 관문(사용자 승인 대기) 후 단일 커밋. 브랜치가 main이면 먼저 분기 검토.
   - push는 사용자가 명시적으로 요청할 때만.

## 데이터 전달
- 중간 산출물: `_workspace/{phase}_{agent}_{artifact}.md` (보존 — 감사 추적용).
- 각 결과서 상단에 `## 다음 단계 참조` 블록(미해결 이슈·핵심 결정·다음 단계) 의무.
- 실시간 조율: `SendMessage`. 작업/의존성: `TaskCreate`/`TaskUpdate`.

## 에러 핸들링
- 팀원 1회 재시도 후 재실패 → 해당 결과 없이 진행하되 보고서에 누락 명시.
- 상충 데이터는 삭제 말고 출처 병기. 테스트 실패 시 완료로 보고 금지.

## 품질 게이트 (리스크 등급별)
- 경량(1파일·가역): 내부 검수(리뷰어)만.
- 표준(다파일·기능추가): 리뷰어 검수 + pytest/스모크 통과.
- 중대(계약변경·비가역): 단계마다 리뷰어 재검수 + 사용자 승인 관문.
- 외부 독립 AI 리뷰(러너 제외)는 현재 미구성 — 필요 시 추후 `external-review-loop` 스킬 추가.

## 테스트 시나리오
- **정상 흐름:** "CharacterPack 기능 추가" → Phase0 초기실행 → architect 브리프(character.py 계약)
  → builder TDD로 팩 로딩 구현+tests → reviewer 경계면(팩↔renderer 자산키) 검수 Approve
  → pytest 통과 → 승인 후 커밋.
- **에러 흐름:** builder pytest 실패 → 완료 보고 안 함 → architect가 실패 원인 확인,
  브리프 대비 수정지시 → builder 재작업 1회 → 여전히 실패면 누락 명시하고 사용자에게 보고.
