# CLAUDE.md — Desktop Pet

윈도우 바탕화면 위를 돌아다니는 데스크톱 펫(가젯). 사용자 사진→얼굴 합성→투명 오버레이
캐릭터. 기능 명세는 `SPEC.md`, 개발 로드맵은
`C:\Users\cheoj\.claude\plans\sunny-jumping-iverson.md`(M0~M3) 참조.

## 하네스: Desktop Pet 개발

**목표:** 검증된 작동 기반 위에 상업화·품질 개선(PySide6·CharacterPack·등록UX·알림·패키징)을
회귀 없이 계층적으로 얹는다.

**트리거:** 펫 기능 개발·수정·개선 요청 시 `desktop-pet-dev` 스킬(오케스트레이터)을 사용하라.
팀 구성: `pet-architect` → `pet-builder` → `pet-reviewer` (계획→구현→검증 루프). 단순 질문은 직접 응답 가능.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-07-01 | 초기 구성 (3에이전트 + 오케스트레이터 + 교리) | 전체 | 하네스 기반 개발 착수 |
| 2026-07-14 | 모션 교리 추가 (루핑 5원칙) | `references/motion-doctrine.md` | 루핑 애니메이션 레퍼런스 학습 |
| 2026-07-14 | 외부 플랫폼 워크플로우 기록 (구현 없음, 참고 지식만) | `references/external-platform-workflow.md` | 모션 제작을 시댄스 등 별도 플랫폼에 위임 예정 — 프롬프트 로직만 학습·보관 |
