"""
물리 엔진 + 상태 전이 + CPU 연동 모델.
"""

import random
import time
import sys
import psutil

# 상태 상수
FALL  = "FALL"
IDLE  = "IDLE"
WALK  = "WALK"
SLEEP = "SLEEP"
DRAG  = "DRAG"

GRAVITY      = 0.6
MAX_FALL_VEL = 20.0
BASE_WALK_SPD = 2.0    # px/frame
MIN_WALK_SPD  = 1.0
MAX_WALK_SPD  = 6.0

IDLE_TIMEOUT_MIN  = 2.0   # 초
IDLE_TIMEOUT_MAX  = 5.0
WALK_TIMEOUT_MIN  = 3.0
WALK_TIMEOUT_MAX  = 8.0
SLEEP_TIMEOUT_MIN = 5.0
SLEEP_TIMEOUT_MAX = 15.0


class PetStateMachine:
    def __init__(self, screen_w, screen_h, floor_y):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.floor_y  = floor_y   # 바닥 Y좌표 (작업표시줄 상단)

        self.x = float(screen_w // 2)
        self.y = 0.0
        self.vel_y   = 0.0
        self.dir     = 1          # 1=오른쪽, -1=왼쪽
        self.state   = FALL
        self.walk_speed = BASE_WALK_SPD

        self._state_timer   = 0.0
        self._state_timeout = 0.0
        self._last_cpu_poll = 0.0
        self._cpu_percent   = 0.0

        # 열린 창 바닥 목록 (eSheep) — [(left, right, top), ...]
        self._window_floors = []

    # --- public ---

    def set_floor(self, floor_y):
        self.floor_y = floor_y

    def set_window_floors(self, floors):
        self._window_floors = floors

    def start_drag(self):
        if self.state != DRAG:
            self.state  = DRAG
            self.vel_y  = 0.0

    def end_drag(self, x, y):
        self.x     = float(x)
        self.y     = float(y)
        self.state = FALL
        self.vel_y = 0.0

    def move_drag(self, x, y):
        self.x = float(x)
        self.y = float(y)

    def update(self, dt):
        """dt: 경과 시간(초). 상태 전이 + 물리 적용."""
        self._poll_cpu()
        self._update_walk_speed()

        if self.state == DRAG:
            return

        if self.state == FALL:
            self._do_fall(dt)
        elif self.state == IDLE:
            self._do_idle(dt)
        elif self.state == WALK:
            self._do_walk(dt)
        elif self.state == SLEEP:
            self._do_sleep(dt)

    # --- private ---

    def _poll_cpu(self):
        now = time.monotonic()
        if now - self._last_cpu_poll >= 1.0:
            self._cpu_percent   = psutil.cpu_percent(interval=None)
            self._last_cpu_poll = now

    def _update_walk_speed(self):
        ratio = self._cpu_percent / 100.0
        self.walk_speed = MIN_WALK_SPD + ratio * (MAX_WALK_SPD - MIN_WALK_SPD)

    def _effective_floor(self):
        """현재 X 위치에서 유효한 바닥 Y를 반환 (창 위 or 작업표시줄)."""
        best = self.floor_y
        pet_cx = self.x
        for (left, right, top) in self._window_floors:
            if left <= pet_cx <= right and top < best:
                best = top
        return best

    def _do_fall(self, dt):
        self.vel_y = min(self.vel_y + GRAVITY, MAX_FALL_VEL)
        self.y    += self.vel_y

        floor = self._effective_floor()
        if self.y >= floor:
            self.y     = float(floor)
            self.vel_y = 0.0
            self._enter_idle()

    def _do_idle(self, dt):
        self._state_timer += dt
        if self._state_timer >= self._state_timeout:
            if random.random() < 0.65:
                self._enter_walk()
            else:
                self._enter_sleep()

    def _do_walk(self, dt):
        self._state_timer += dt

        # 발 아래 유효 바닥 추적
        floor = self._effective_floor()
        self.y = float(floor)

        self.x += self.dir * self.walk_speed

        # 화면 경계 반전
        if self.x <= 0:
            self.x  = 0.0
            self.dir = 1
        elif self.x >= self.screen_w:
            self.x  = float(self.screen_w)
            self.dir = -1

        # 창 밖으로 발이 벗어나면 낙하
        if self._should_fall():
            self.state = FALL
            return

        if self._state_timer >= self._state_timeout:
            if random.random() < 0.6:
                self._enter_idle()
            else:
                self._enter_sleep()

    def _do_sleep(self, dt):
        self._state_timer += dt
        if self._state_timer >= self._state_timeout:
            self._enter_walk()

    def _should_fall(self):
        """창 바닥 위에 있었는데 창 경계를 벗어났으면 True."""
        if not self._window_floors:
            return False
        pet_cx = self.x
        on_window = any(left <= pet_cx <= right for left, right, _ in self._window_floors)
        # 창 위에 있다가 벗어난 경우 + 메인 바닥보다 위에 있는 경우
        if not on_window and self.y < self.floor_y - 2:
            return True
        return False

    def _enter_idle(self):
        self.state          = IDLE
        self._state_timer   = 0.0
        self._state_timeout = random.uniform(IDLE_TIMEOUT_MIN, IDLE_TIMEOUT_MAX)

    def _enter_walk(self):
        self.state          = WALK
        self._state_timer   = 0.0
        self._state_timeout = random.uniform(WALK_TIMEOUT_MIN, WALK_TIMEOUT_MAX)
        if random.random() < 0.5:
            self.dir = -self.dir

    def _enter_sleep(self):
        self.state          = SLEEP
        self._state_timer   = 0.0
        self._state_timeout = random.uniform(SLEEP_TIMEOUT_MIN, SLEEP_TIMEOUT_MAX)

    @property
    def cpu_percent(self):
        return self._cpu_percent
