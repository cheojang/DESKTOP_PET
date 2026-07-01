"""
PetStateMachine 회귀 테스트.

GUI 바인딩(PySide6) 전환 시 상태머신 로직이 불변임을 고정한다.
GUI 바인딩과 무관한 순수 로직(물리/전이/CPU매핑/드래그/eSheep)만 검증.
random.seed 고정으로 결정론적으로 만든다.
"""

import random

import pytest

from pet_state_machine import (
    PetStateMachine,
    FALL, IDLE, WALK, SLEEP, DRAG,
    MIN_WALK_SPD, MAX_WALK_SPD,
)

SCREEN_W = 1920
SCREEN_H = 1080
FLOOR_Y = 960


@pytest.fixture
def sm():
    random.seed(0)
    return PetStateMachine(SCREEN_W, SCREEN_H, FLOOR_Y)


# --- 착지: FALL -> IDLE, y == floor ---

def test_lands_on_floor_enters_idle(sm):
    sm.state = FALL
    sm.y = FLOOR_Y - 5.0
    # 바닥에 도달할 때까지 낙하 (창 바닥 없음 -> floor_y 기준)
    for _ in range(120):
        sm.update(1 / 30.0)
        if sm.state != FALL:
            break
    assert sm.state == IDLE
    assert sm.y == float(FLOOR_Y)
    assert sm.vel_y == 0.0


def test_fall_does_not_pass_through_floor(sm):
    sm.state = FALL
    sm.y = FLOOR_Y - 100.0
    for _ in range(200):
        sm.update(1 / 30.0)
        assert sm.y <= float(FLOOR_Y)


# --- 전이: IDLE / WALK / SLEEP 등장 ---

def test_idle_transitions_to_walk_or_sleep(sm):
    sm._enter_idle()
    assert sm.state == IDLE
    # 타임아웃 강제 만료
    sm._state_timeout = 0.0
    sm._do_idle(1.0)
    assert sm.state in (WALK, SLEEP)


def test_walk_transitions_to_idle_or_sleep(sm):
    sm._enter_walk()
    assert sm.state == WALK
    sm._state_timeout = 0.0
    sm._do_walk(1.0)
    assert sm.state in (IDLE, SLEEP)


def test_sleep_transitions_to_walk(sm):
    sm._enter_sleep()
    assert sm.state == SLEEP
    sm._state_timeout = 0.0
    sm._do_sleep(1.0)
    assert sm.state == WALK


def test_all_three_states_appear_over_time(sm):
    """장시간 구동 시 IDLE/WALK/SLEEP 세 상태가 모두 등장하는지."""
    sm.state = FALL
    sm.y = FLOOR_Y - 5.0
    seen = set()
    for _ in range(5000):
        sm.update(1 / 30.0)
        seen.add(sm.state)
    assert {IDLE, WALK, SLEEP}.issubset(seen)


# --- 드래그: start_drag -> DRAG, end_drag -> FALL ---

def test_start_drag_enters_drag(sm):
    sm.state = IDLE
    sm.start_drag()
    assert sm.state == DRAG
    assert sm.vel_y == 0.0


def test_end_drag_enters_fall(sm):
    sm.start_drag()
    sm.end_drag(300, 200)
    assert sm.state == FALL
    assert sm.x == 300.0
    assert sm.y == 200.0
    assert sm.vel_y == 0.0


def test_move_drag_updates_position(sm):
    sm.start_drag()
    sm.move_drag(500, 400)
    assert sm.x == 500.0
    assert sm.y == 400.0


def test_drag_freezes_physics(sm):
    """DRAG 상태에서는 update()가 물리를 적용하지 않는다."""
    sm.start_drag()
    sm.move_drag(500, 400)
    sm.update(1 / 30.0)
    assert sm.state == DRAG
    assert sm.x == 500.0
    assert sm.y == 400.0


# --- eSheep _effective_floor: 창 위 유효 바닥 ---

def test_effective_floor_default_is_taskbar(sm):
    sm.set_window_floors([])
    sm.x = 500.0
    assert sm._effective_floor() == FLOOR_Y


def test_effective_floor_uses_window_top_when_over_window(sm):
    # 창: left=400, right=600, top=500 (작업표시줄 960보다 위)
    sm.set_window_floors([(400, 600, 500)])
    sm.x = 500.0   # 창 범위 안
    assert sm._effective_floor() == 500


def test_effective_floor_ignores_window_outside_x(sm):
    sm.set_window_floors([(400, 600, 500)])
    sm.x = 100.0   # 창 범위 밖
    assert sm._effective_floor() == FLOOR_Y


def test_effective_floor_picks_highest_window(sm):
    # 두 창이 겹치면 더 위(작은 top)를 선택
    sm.set_window_floors([(400, 600, 700), (400, 600, 500)])
    sm.x = 500.0
    assert sm._effective_floor() == 500


def test_walk_on_window_floor(sm):
    """창 위를 걸을 때 y가 창 상단으로 유지되는지."""
    sm.set_window_floors([(0, SCREEN_W, 500)])
    sm._enter_walk()
    sm.x = 500.0
    sm._state_timeout = 999.0   # 걷는 도중 전이 방지
    sm._do_walk(1 / 30.0)
    assert sm.y == 500.0


# --- CPU 연동 걷기 속도 범위 (1.0 ~ 6.0) ---

def test_walk_speed_min_at_zero_cpu(sm):
    sm._cpu_percent = 0.0
    sm._update_walk_speed()
    assert sm.walk_speed == MIN_WALK_SPD == 1.0


def test_walk_speed_max_at_full_cpu(sm):
    sm._cpu_percent = 100.0
    sm._update_walk_speed()
    assert sm.walk_speed == MAX_WALK_SPD == 6.0


def test_walk_speed_within_range(sm):
    for cpu in (0.0, 12.5, 37.0, 50.0, 88.0, 100.0):
        sm._cpu_percent = cpu
        sm._update_walk_speed()
        assert MIN_WALK_SPD <= sm.walk_speed <= MAX_WALK_SPD


def test_walk_speed_midpoint(sm):
    sm._cpu_percent = 50.0
    sm._update_walk_speed()
    # 1.0 + 0.5 * (6.0 - 1.0) = 3.5
    assert sm.walk_speed == pytest.approx(3.5)
