import math
import random
import heapq
from dataclasses import dataclass


@dataclass
class Result:
    ok: bool
    message: str

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return f"[{'OK ' if self.ok else 'FAIL'}] {self.message}"


GRID_W, GRID_H = 40, 24

ROOMS = {
    "kitchen":     (1, 1, 12, 8),
    "living_room": (15, 1, 26, 8),
    "bedroom":     (28, 1, 38, 8),
    "bathroom":    (1, 15, 12, 22),
    "study":       (28, 15, 38, 22),
}

CORRIDOR = (1, 10, 38, 13)

DOORS = [
    (6, 9), (6, 10),
    (20, 9), (20, 10),
    (33, 9), (33, 10),
    (6, 14), (6, 13),
    (33, 14), (33, 13),
]

LOCATIONS = {
    "kitchen":         (6, 4),
    "kitchen_counter": (10, 2),
    "living_room":     (20, 4),
    "dining_table":    (23, 3),
    "bedroom":         (33, 4),
    "bedside_table":   (36, 2),
    "bathroom":        (6, 18),
    "study":           (33, 18),
    "desk":            (36, 16),
    "hallway":         (20, 11),
}


@dataclass
class WorldObject:
    name: str
    location: str
    category: str
    safe: bool = True
    graspable: bool = True


WORLD_OBJECTS = [
    WorldObject("water_bottle",  "kitchen_counter", "drink"),
    WorldObject("juice_box",     "kitchen_counter", "drink"),
    WorldObject("empty_cup",     "kitchen_counter", "container"),
    WorldObject("kitchen_knife", "kitchen_counter", "sharp_utensil", safe=False),
    WorldObject("tv_remote",     "dining_table",    "electronics"),
    WorldObject("newspaper",     "dining_table",    "reading"),
    WorldObject("pill_bottle",   "bedside_table",   "medication", safe=False),
    WorldObject("eyeglasses",    "bedside_table",   "personal_item"),
    WorldObject("book",          "desk",            "reading"),
    WorldObject("towel",         "bathroom",        "linen"),
]


def _build_grid():
    grid = [[1] * GRID_W for _ in range(GRID_H)]

    def carve(x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if 0 <= x < GRID_W and 0 <= y < GRID_H:
                    grid[y][x] = 0

    for r in ROOMS.values():
        carve(*r)
    carve(*CORRIDOR)
    for x, y in DOORS:
        grid[y][x] = 0
    return grid


GRID = _build_grid()


def _astar(grid, start, goal):
    (sx, sy), (gx, gy) = start, goal
    if grid[sy][sx] or grid[gy][gx]:
        return None
    openh = [(0, start)]
    came = {start: None}
    g = {start: 0}
    while openh:
        _, cur = heapq.heappop(openh)
        if cur == goal:
            path = []
            while cur:
                path.append(cur)
                cur = came[cur]
            return path[::-1]
        cx, cy = cur
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H and grid[ny][nx] == 0:
                ng = g[cur] + 1
                nb = (nx, ny)
                if nb not in g or ng < g[nb]:
                    g[nb] = ng
                    heapq.heappush(openh, (ng + abs(nx - gx) + abs(ny - gy), nb))
                    came[nb] = cur
    return None


class Robot:
    def __init__(self, start="hallway", grasp_fail_prob=0.30, seed=0,
                 renderer=None, step_delay=0.0):
        self._rng = random.Random(seed)
        self._grasp_fail_prob = grasp_fail_prob
        self._renderer = renderer
        self._step_delay = step_delay

        self.known_locations = sorted(LOCATIONS.keys())
        self.known_objects = {}
        self.holding = None
        self.current_location = start
        self._pos = LOCATIONS[start]
        self._last_speech = ""
        self._log = []
        self._objects = {o.name: o for o in WORLD_OBJECTS}

        self._render()

    def _render(self, transient=None):
        if self._renderer:
            self._renderer(self, transient)

    def _sense_here(self):
        found = []
        for o in self._objects.values():
            if o.location == self.current_location:
                self.known_objects[o.name] = {
                    "name": o.name,
                    "location": o.location,
                    "category": o.category,
                }
                found.append(o.name)
        return found

    def navigate_to(self, location_name):
        if location_name not in LOCATIONS:
            return Result(False, f"Unknown location '{location_name}'. "
                                 f"Known locations: {self.known_locations}")
        path = _astar(GRID, self._pos, LOCATIONS[location_name])
        if path is None:
            return Result(False, f"No path to '{location_name}'.")
        for cell in path:
            self._pos = cell
            self._render(transient=f"-> {location_name}")
            if self._step_delay:
                import time
                time.sleep(self._step_delay)
        self.current_location = location_name
        found = self._sense_here()
        self._log.append(f"navigate_to({location_name})")
        msg = f"Arrived at {location_name}."
        if found:
            msg += f" Sensed objects here: {found}."
        return Result(True, msg)

    def pick(self, object_name):
        self._log.append(f"pick({object_name})")
        if self.holding is not None:
            return Result(False, f"Already holding '{self.holding}'. "
                                 f"Place it before picking something else.")
        if object_name not in self.known_objects:
            return Result(False, f"I have not sensed any '{object_name}'. "
                                 f"I only know about: {list(self.known_objects)}")
        obj = self._objects[object_name]
        if obj.location != self.current_location:
            return Result(False, f"'{object_name}' is at {obj.location}, "
                                 f"but I'm at {self.current_location}.")
        if not obj.graspable:
            return Result(False, f"'{object_name}' cannot be grasped.")
        if self._rng.random() < self._grasp_fail_prob:
            self._render(transient=f"pick {object_name} FAILED")
            return Result(False, f"Grasp of '{object_name}' slipped. "
                                 f"Object is still where it was.")
        self.holding = object_name
        self._render(transient=f"picked {object_name}")
        return Result(True, f"Picked up '{object_name}'.")

    def place(self, location_name=None):
        self._log.append(f"place({location_name})")
        if self.holding is None:
            return Result(False, "Not holding anything to place.")
        if location_name and location_name != self.current_location:
            return Result(False, f"I'm at {self.current_location}, not "
                                 f"{location_name}. Navigate there first.")
        placed = self.holding
        self.holding = None
        self._render(transient=f"placed {placed}")
        return Result(True, f"Placed '{placed}' at {self.current_location}.")

    def speak(self, text):
        self._last_speech = text
        self._log.append(f'speak("{text}")')
        self._render(transient="speaking")
        return Result(True, f'Robot said: "{text}"')


def ascii_renderer(robot, transient=None):
    chars = [[" " if GRID[y][x] == 0 else "#" for x in range(GRID_W)]
             for y in range(GRID_H)]
    for o in robot.known_objects.values():
        lx, ly = LOCATIONS[o["location"]]
        if chars[ly][lx] == " ":
            chars[ly][lx] = "*"
    rx, ry = robot._pos
    chars[ry][rx] = "R"
    print("\n" + "=" * GRID_W)
    for row in chars:
        print("".join(row))
    print(f"loc={robot.current_location}  holding={robot.holding}  "
          f"known_objects={list(robot.known_objects)}")
    if robot._last_speech:
        print(f'ROBOT SAYS: "{robot._last_speech}"')
    print("=" * GRID_W)


def make_pygame_renderer(cell=22):
    import pygame
    pygame.init()
    W, H = GRID_W * cell, GRID_H * cell + 80
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Home Robot")
    font = pygame.font.SysFont("monospace", 14)
    bigfont = pygame.font.SysFont("monospace", 18)

    def render(robot, transient=None):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
        screen.fill((25, 25, 30))
        for y in range(GRID_H):
            for x in range(GRID_W):
                rect = pygame.Rect(x * cell, y * cell, cell - 1, cell - 1)
                color = (60, 60, 70) if GRID[y][x] else (235, 235, 240)
                pygame.draw.rect(screen, color, rect)
        for lx, ly in LOCATIONS.values():
            pygame.draw.circle(screen, (170, 170, 200),
                               (lx * cell + cell // 2, ly * cell + cell // 2), 3)
        for o in robot.known_objects.values():
            lx, ly = LOCATIONS[o["location"]]
            pygame.draw.circle(screen, (40, 160, 90),
                               (lx * cell + cell // 2, ly * cell + cell // 2), cell // 3)
            screen.blit(font.render(o["name"], True, (20, 90, 40)),
                        (lx * cell - 6, ly * cell - 14))
        rx, ry = robot._pos
        pygame.draw.circle(screen, (40, 110, 230),
                           (rx * cell + cell // 2, ry * cell + cell // 2), cell // 2)
        y0 = GRID_H * cell + 6
        screen.blit(font.render(f"loc={robot.current_location}  holding={robot.holding}",
                                True, (230, 230, 230)), (8, y0))
        screen.blit(font.render(f"known={list(robot.known_objects)}",
                                True, (200, 200, 200)), (8, y0 + 18))
        if robot._last_speech:
            screen.blit(bigfont.render(f'SAYS: "{robot._last_speech}"',
                                       True, (250, 220, 120)), (8, y0 + 40))
        pygame.display.flip()

    return render
