"""
=============================================================
 MINI RACING GAME  -  made with Python + Pygame
=============================================================
Features (what to show in the demo):
  * Player car controlled with WASD or Arrow keys
  * 3 AI (NPC) cars, with 3 selectable difficulty levels
  * 3 different tracks to choose from
  * Lap timing (current lap, best lap, list of all laps)
  * Live race position (1st / 2nd / 3rd / 4th)
  * Random bonus pickups on the track (points + nitro)
  * Going off the track slows the car down
  * Nitro charges while you drive, press X to boost

Run it with:   python racing_game.py
(needs pygame:  pip install pygame)
=============================================================
"""

import math
import random
import sys

import pygame

# ------------------------------------------------------------------
# 1. BASIC SETTINGS (all the "magic numbers" live here so they are
#    easy to find and easy to explain)
# ------------------------------------------------------------------
WIDTH, HEIGHT = 1000, 700          # window size
FPS = 60                           # frames per second
TOTAL_LAPS = 3                     # laps needed to finish the race
WAYPOINTS = 180                    # how many points describe a track

# Player car physics (tuned to be slow/easy to control)
ACCELERATION = 230.0               # pixels per second^2
BRAKE_POWER = 420.0
NATURAL_DRAG = 95.0                # car slows down on its own
TOP_SPEED = 330.0                  # top speed on the road
OFFROAD_SPEED = 145.0              # top speed on the grass (slower!)
TURN_SPEED = 165.0                 # degrees per second
NITRO_MAX = 100.0
NITRO_GAIN = 13.0                  # nitro charged per second while driving
NITRO_USE = 38.0                   # nitro spent per second while boosting
NITRO_BOOST = 1.55                 # speed multiplier while boosting

# Colours
GRASS = (36, 92, 52)
ROAD = (74, 74, 80)
KERB = (210, 210, 215)
WHITE = (240, 240, 240)
BLACK = (18, 18, 20)
YELLOW = (250, 205, 60)
CYAN = (90, 220, 230)
RED = (225, 70, 70)

PLAYER_COLOR = (235, 230, 60)
NPC_COLORS = [(70, 140, 235), (225, 80, 95), (130, 215, 120)]

# NPC difficulty presets: speed factor, how far ahead it looks, how sloppy it is
DIFFICULTIES = {
    "Easy":   {"speed": 0.85, "look": 10, "noise": 0.30},
    "Normal": {"speed": 0.98, "look": 14, "noise": 0.14},
    "Hard":   {"speed": 1.12, "look": 18, "noise": 0.05},
}
DIFF_NAMES = ["Easy", "Normal", "Hard"]


# ------------------------------------------------------------------
# 2. SMALL MATH HELPERS
# ------------------------------------------------------------------
def clamp(value, low, high):
    """Keep a value inside the range [low, high]."""
    return max(low, min(high, value))


def wrap_angle(deg):
    """Bring an angle into the range -180..180 degrees."""
    while deg > 180:
        deg -= 360
    while deg < -180:
        deg += 360
    return deg


def point_segment_distance(px, py, ax, ay, bx, by):
    """Shortest distance from point P to the line segment A-B.
    Also returns t = how far along the segment the closest point is."""
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else clamp(((px - ax) * dx + (py - ay) * dy) / length_sq, 0.0, 1.0)
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy), t


def format_time(seconds):
    """Turn 83.472 seconds into the string 1:23.47 (nice for lap times)."""
    if seconds is None:
        return "--:--.--"
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    return "%d:%05.2f" % (minutes, rest)


# ------------------------------------------------------------------
# 3. THE TRACK
#    A track is just a closed loop of points (the centre line) plus a
#    width. Everything else (is the car on the road? what position is
#    each car in?) is calculated from that loop.
# ------------------------------------------------------------------
class Track:
    def __init__(self, name, shape_fn, width, description):
        self.name = name
        self.width = width
        self.description = description
        self.points = []

        cx, cy = WIDTH // 2, 360          # centre of the track on screen
        for i in range(WAYPOINTS):
            angle = 2 * math.pi * i / WAYPOINTS
            rx, ry = shape_fn(angle)      # radius in x and y for this angle
            self.points.append((cx + rx * math.cos(angle),
                                cy + ry * math.sin(angle)))

    # --- geometry -------------------------------------------------
    def project(self, pos, hint):
        """Find which waypoint the car is closest to, and how far it is
        from the centre line. 'hint' is the last known waypoint, so we
        only search nearby (fast). If the car seems lost we search all."""
        idx, dist = self._search(pos, range(hint - 20, hint + 21))
        if dist > self.width:                       # car is far away -> full search
            idx, dist = self._search(pos, range(WAYPOINTS))
        return idx, dist

    def _search(self, pos, index_range):
        best_dist, best_idx = 1e9, 0
        for k in index_range:
            i = k % WAYPOINTS
            j = (i + 1) % WAYPOINTS
            ax, ay = self.points[i]
            bx, by = self.points[j]
            d, t = point_segment_distance(pos[0], pos[1], ax, ay, bx, by)
            if d < best_dist:
                best_dist = d
                best_idx = j if t > 0.5 else i
        return best_idx, best_dist

    def direction_at(self, idx):
        """Heading (in degrees) of the track at a waypoint."""
        ax, ay = self.points[idx % WAYPOINTS]
        bx, by = self.points[(idx + 3) % WAYPOINTS]
        return math.degrees(math.atan2(by - ay, bx - ax))

    def point_with_offset(self, idx, side_offset):
        """A point on the track, pushed sideways by 'side_offset' pixels.
        Used to place cars on a starting grid and to give NPCs lanes."""
        x, y = self.points[idx % WAYPOINTS]
        heading = math.radians(self.direction_at(idx))
        # normal (perpendicular) direction
        nx, ny = -math.sin(heading), math.cos(heading)
        return x + nx * side_offset, y + ny * side_offset

    # --- drawing --------------------------------------------------
    def draw(self, screen):
        screen.fill(GRASS)
        # kerb / outline first, then the darker road on top of it
        pygame.draw.lines(screen, KERB, True, self.points, int(self.width) + 10)
        pygame.draw.lines(screen, ROAD, True, self.points, int(self.width))
        # dashed centre line
        for i in range(0, WAYPOINTS, 4):
            pygame.draw.line(screen, (120, 120, 125),
                             self.points[i], self.points[(i + 2) % WAYPOINTS], 2)
        # start / finish line (small checkered squares across the road)
        half = self.width / 2
        for s in range(-int(half), int(half), 12):
            x, y = self.point_with_offset(0, s)
            color = WHITE if (s // 12) % 2 == 0 else BLACK
            pygame.draw.rect(screen, color, (x - 5, y - 5, 11, 11))


def build_tracks():
    """The 3 selectable tracks. Each shape function returns the x and y
    radius for a given angle - that is what makes the curves."""
    return [
        Track("1. Oval Speedway", lambda a: (400, 215), 110,
              "Wide and fast - good for learning the controls."),
        Track("2. Snake Circuit", lambda a: (370 + 50 * math.sin(3 * a),
                                             205 + 40 * math.sin(3 * a)), 95,
              "Long sweeping curves, medium difficulty."),
        Track("3. Hairpin Loop", lambda a: (355 + 55 * math.sin(5 * a),
                                            200 + 45 * math.sin(5 * a)), 82,
              "Narrow and twisty - brake before the corners!"),
    ]


# ------------------------------------------------------------------
# 4. THE CAR
#    One class is used for both the player and the NPCs. The only
#    difference is where the steering/throttle commands come from.
# ------------------------------------------------------------------
class Car:
    def __init__(self, track, name, color, is_player, grid_slot):
        self.track = track
        self.name = name
        self.color = color
        self.is_player = is_player

        # --- starting grid: cars line up behind the start line ----
        start_idx = (-6 * (grid_slot // 2)) % WAYPOINTS
        side = (track.width / 4) * (1 if grid_slot % 2 == 0 else -1)
        self.x, self.y = track.point_with_offset(start_idx, side)
        self.angle = track.direction_at(start_idx)   # degrees, 0 = facing right
        self.lane = side                             # preferred lane for NPCs

        # --- state ------------------------------------------------
        self.speed = 0.0
        self.on_road = True
        self.last_idx = start_idx
        self.progress = 0.0          # how many waypoints travelled in total
        self.lap = 0
        self.lap_times = []
        self.lap_start = 0.0
        self.race_time = 0.0
        self.finish_time = None
        self.stuck_timer = 0.0       # used to rescue a car stuck on the grass

        # player extras
        self.nitro = 30.0
        self.boosting = False
        self.score = 0

        self.image = self._make_image()

    def _make_image(self):
        """Draw the little car once into a surface, then just rotate it."""
        surf = pygame.Surface((24, 13), pygame.SRCALPHA)
        pygame.draw.rect(surf, self.color, (0, 0, 24, 13), border_radius=4)
        pygame.draw.rect(surf, (35, 35, 45), (15, 2, 6, 9), border_radius=2)  # windscreen
        pygame.draw.rect(surf, BLACK, (3, -1, 5, 3))                          # wheels
        pygame.draw.rect(surf, BLACK, (3, 11, 5, 3))
        return surf

    # -------------------------------------------------------------
    def update(self, dt, keys, race_running):
        if self.finish_time is not None:
            self.speed *= 0.95            # already finished: gently roll out
            self._move(dt)
            return
        if race_running:
            self.race_time += dt

        # 1) decide steering + throttle
        if self.is_player:
            steer, throttle, brake, want_nitro = self._player_input(keys)
        else:
            steer, throttle, brake, want_nitro = self._npc_input()
        if not race_running:                       # during the countdown
            steer = throttle = brake = 0.0
            want_nitro = False

        # 2) nitro (only the player has it)
        self.boosting = False
        if self.is_player:
            if want_nitro and self.nitro > 0 and self.speed > 20:
                self.boosting = True
                self.nitro = max(0.0, self.nitro - NITRO_USE * dt)
            elif self.on_road and self.speed > 120:
                # nitro charges up the longer you keep driving fast
                self.nitro = min(NITRO_MAX, self.nitro + NITRO_GAIN * dt)

        # 3) speed
        top = TOP_SPEED if self.on_road else OFFROAD_SPEED
        if not self.is_player:
            top *= self.speed_factor
        if self.boosting:
            top *= NITRO_BOOST

        if throttle > 0:
            self.speed += ACCELERATION * (1.6 if self.boosting else 1.0) * throttle * dt
        if brake > 0:
            self.speed -= BRAKE_POWER * brake * dt
        # drag: much stronger on grass, so the car clearly slows down off track
        drag = NATURAL_DRAG * (1.0 if self.on_road else 3.2)
        self.speed -= drag * dt * (1 if self.speed > 0 else -1)
        self.speed = clamp(self.speed, -90.0, top)
        # stop completely when coasting, so the car does not creep forever
        if abs(self.speed) < 2 and throttle == 0:
            self.speed = 0.0

        # 4) steering - you can only turn while actually moving
        grip = clamp(abs(self.speed) / 70.0, 0.0, 1.0)
        self.angle += steer * TURN_SPEED * grip * dt * (1 if self.speed >= 0 else -1)

        self._move(dt)
        self._update_track_position()
        self._rescue_if_stuck(dt, race_running)

    def _rescue_if_stuck(self, dt, race_running):
        """If a car ends up crawling around on the grass it would be stuck
        forever, so after a few seconds we put it back on the road."""
        crawling = abs(self.speed) < 25
        # the player is allowed to sit still on the road on purpose
        if race_running and crawling and not (self.is_player and self.on_road):
            self.stuck_timer += dt
        else:
            self.stuck_timer = 0.0
        if self.stuck_timer > (2.0 if not self.on_road else 4.0):
            self.x, self.y = self.track.point_with_offset(self.last_idx, self.lane)
            self.angle = self.track.direction_at(self.last_idx)
            self.speed = 0.0
            self.stuck_timer = 0.0
            self.on_road = True

    def _move(self, dt):
        rad = math.radians(self.angle)
        self.x += math.cos(rad) * self.speed * dt
        self.y += math.sin(rad) * self.speed * dt
        # never let a car leave the window
        self.x = clamp(self.x, 8, WIDTH - 8)
        self.y = clamp(self.y, 8, HEIGHT - 8)

    def _update_track_position(self):
        idx, dist = self.track.project((self.x, self.y), self.last_idx)
        self.on_road = dist <= self.track.width / 2

        # how many waypoints did we advance since the last frame?
        step = (idx - self.last_idx) % WAYPOINTS
        if step > WAYPOINTS // 2:
            step -= WAYPOINTS
        # a car can realistically only move 1-2 waypoints per frame, so
        # clamping also stops anyone from "cutting" across the infield
        self.progress += clamp(step, -3, 3)
        self.last_idx = idx

        # finished a lap?
        new_lap = int(self.progress // WAYPOINTS)
        if new_lap > self.lap:
            self.lap = new_lap
            self.lap_times.append(self.race_time - self.lap_start)
            self.lap_start = self.race_time
            if self.lap >= TOTAL_LAPS:
                self.finish_time = self.race_time

    # -------------------------------------------------------------
    def _player_input(self, keys):
        steer = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            steer -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            steer += 1.0
        throttle = 1.0 if (keys[pygame.K_w] or keys[pygame.K_UP]) else 0.0
        brake = 1.0 if (keys[pygame.K_s] or keys[pygame.K_DOWN]) else 0.0
        return steer, throttle, brake, keys[pygame.K_x]

    def _npc_input(self):
        """Simple AI driver:
             1. aim at a point a few waypoints ahead on the track
             2. steer towards it
             3. slow down when the corner ahead is sharp
        The 'noise' value makes easier opponents drive less accurately."""
        # look further ahead the faster we are going (like a real driver)
        look = int(clamp(5 + self.speed / 28.0, 5, self.look_ahead))
        target = self.track.point_with_offset(self.last_idx + look, self.lane * 0.6)
        wanted = math.degrees(math.atan2(target[1] - self.y, target[0] - self.x))
        error = wrap_angle(wanted - self.angle)
        error += random.uniform(-20, 20) * self.noise   # easy NPCs are sloppy
        steer = clamp(error / 25.0, -1.0, 1.0)

        # how much does the track bend over the next few waypoints?
        bend = abs(wrap_angle(self.track.direction_at(self.last_idx + 12) -
                              self.track.direction_at(self.last_idx)))
        corner_limit = TOP_SPEED * self.speed_factor * clamp(1.0 - bend / 110.0, 0.45, 1.0)

        throttle, brake = 1.0, 0.0
        if self.speed > corner_limit:               # too fast for the corner
            throttle, brake = 0.0, 0.55
        if abs(error) > 45:                         # pointing the wrong way
            throttle = min(throttle, 0.4)
        if self.speed < 60:                         # always pull away properly
            throttle, brake = 1.0, 0.0
        if random.random() < 0.04 * self.noise:     # occasional AI mistake
            throttle *= 0.4
        return steer, throttle, brake, False

    def set_difficulty(self, difficulty):
        preset = DIFFICULTIES[difficulty]
        self.speed_factor = preset["speed"] * random.uniform(0.97, 1.03)
        self.look_ahead = preset["look"]
        self.noise = preset["noise"]

    # -------------------------------------------------------------
    def draw(self, screen):
        rotated = pygame.transform.rotate(self.image, -self.angle)
        rect = rotated.get_rect(center=(self.x, self.y))
        screen.blit(rotated, rect)
        if self.boosting:                           # little flame behind the car
            rad = math.radians(self.angle)
            fx = self.x - math.cos(rad) * 16
            fy = self.y - math.sin(rad) * 16
            pygame.draw.circle(screen, (255, 160, 40), (int(fx), int(fy)), 5)
        if self.is_player:                          # marker so you find yourself
            pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y - 18)), 3)


# ------------------------------------------------------------------
# 5. BONUS PICKUPS
#    They pop up at random spots on the track and give points or nitro.
# ------------------------------------------------------------------
class Bonus:
    def __init__(self, track):
        self.kind = random.choice(["coin", "coin", "nitro"])
        idx = random.randrange(WAYPOINTS)
        side = random.uniform(-track.width / 2 + 16, track.width / 2 - 16)
        self.x, self.y = track.point_with_offset(idx, side)
        self.timer = 0.0

    def draw(self, screen):
        # a tiny pulsing circle so it is easy to spot
        pulse = 2 * math.sin(self.timer * 6)
        radius = int(9 + pulse)
        if self.kind == "coin":
            pygame.draw.circle(screen, YELLOW, (int(self.x), int(self.y)), radius)
            pygame.draw.circle(screen, (160, 120, 20), (int(self.x), int(self.y)), radius, 2)
        else:
            pygame.draw.circle(screen, CYAN, (int(self.x), int(self.y)), radius)
            pygame.draw.circle(screen, (20, 90, 110), (int(self.x), int(self.y)), radius, 2)


# ------------------------------------------------------------------
# 6. THE GAME (menu -> race -> results)
# ------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Mini Racing Game")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.f_small = pygame.font.SysFont("consolas", 16)
        self.f_mid = pygame.font.SysFont("consolas", 22, bold=True)
        self.f_big = pygame.font.SysFont("consolas", 40, bold=True)

        self.tracks = build_tracks()
        self.track_choice = 0
        self.diff_choice = 1
        self.state = "menu"          # "menu", "race", "results"

    # -------------------------------------------------------------
    def start_race(self):
        self.track = self.tracks[self.track_choice]
        difficulty = DIFF_NAMES[self.diff_choice]

        self.player = Car(self.track, "YOU", PLAYER_COLOR, True, 0)
        self.cars = [self.player]
        for i in range(3):                       # 3 NPC opponents
            npc = Car(self.track, "CPU %d" % (i + 1), NPC_COLORS[i], False, i + 1)
            npc.set_difficulty(difficulty)
            self.cars.append(npc)

        self.bonuses = [Bonus(self.track) for _ in range(4)]
        self.countdown = 3.0                     # 3..2..1..GO!
        self.message = ""
        self.message_timer = 0.0
        self.state = "race"

    # -------------------------------------------------------------
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)                   # safety if the window lags
            self.handle_events()
            keys = pygame.key.get_pressed()

            if self.state == "menu":
                self.draw_menu()
            elif self.state == "race":
                self.update_race(dt, keys)
                self.draw_race()
            else:
                self.draw_results()
            pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type != pygame.KEYDOWN:
                continue
            key = event.key

            if self.state == "menu":
                if key in (pygame.K_LEFT, pygame.K_a):
                    self.track_choice = (self.track_choice - 1) % len(self.tracks)
                elif key in (pygame.K_RIGHT, pygame.K_d):
                    self.track_choice = (self.track_choice + 1) % len(self.tracks)
                elif key in (pygame.K_UP, pygame.K_w):
                    self.diff_choice = (self.diff_choice - 1) % 3
                elif key in (pygame.K_DOWN, pygame.K_s):
                    self.diff_choice = (self.diff_choice + 1) % 3
                elif key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.start_race()
                elif key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
            else:
                if key == pygame.K_ESCAPE:
                    self.state = "menu"
                elif key == pygame.K_r:
                    self.start_race()

    # -------------------------------------------------------------
    def update_race(self, dt, keys):
        if self.countdown > 0:
            self.countdown -= dt
        running = self.countdown <= 0

        for car in self.cars:
            car.update(dt, keys, running)

        self.handle_car_bumps()
        self.handle_bonuses(dt)

        if self.message_timer > 0:
            self.message_timer -= dt

        # race is over once the player crosses the line
        if self.player.finish_time is not None:
            self.final_order = self.ranking()
            self.state = "results"

    def handle_car_bumps(self):
        """Very simple collision: if two cars touch, push them apart."""
        for i in range(len(self.cars)):
            for j in range(i + 1, len(self.cars)):
                a, b = self.cars[i], self.cars[j]
                dx, dy = b.x - a.x, b.y - a.y
                dist = math.hypot(dx, dy)
                if 0 < dist < 20:
                    push = (20 - dist) / 2
                    nx, ny = dx / dist, dy / dist
                    a.x -= nx * push
                    a.y -= ny * push
                    b.x += nx * push
                    b.y += ny * push
                    a.speed *= 0.92
                    b.speed *= 0.92

    def handle_bonuses(self, dt):
        for i, bonus in enumerate(self.bonuses):
            bonus.timer += dt
            if math.hypot(self.player.x - bonus.x, self.player.y - bonus.y) < 18:
                if bonus.kind == "coin":
                    self.player.score += 50
                    self.show_message("+50 points!")
                else:
                    self.player.nitro = min(NITRO_MAX, self.player.nitro + 40)
                    self.show_message("+Nitro!")
                # replace the collected bonus with a new one somewhere else
                self.bonuses[i] = Bonus(self.track)

    def show_message(self, text):
        self.message = text
        self.message_timer = 1.2

    def ranking(self):
        """Sort the cars: finished cars first (by time), then by how far
        around the track they are. Index 0 = 1st place."""
        def key(car):
            if car.finish_time is not None:
                return (0, car.finish_time)
            return (1, -car.progress)
        return sorted(self.cars, key=key)

    # -------------------------------------------------------------
    # DRAWING
    # -------------------------------------------------------------
    def text(self, txt, font, color, x, y):
        self.screen.blit(font.render(txt, True, color), (x, y))

    def panel(self, x, y, w, h):
        box = pygame.Surface((w, h), pygame.SRCALPHA)
        box.fill((0, 0, 0, 150))
        self.screen.blit(box, (x, y))

    def draw_menu(self):
        self.screen.fill((24, 28, 38))
        self.text("MINI RACING GAME", self.f_big, YELLOW, 300, 60)
        self.text("A simple Python + Pygame racing game", self.f_small, WHITE, 330, 110)

        # ---- track selection ----
        self.text("CHOOSE TRACK   (Left / Right)", self.f_mid, CYAN, 120, 175)
        for i, track in enumerate(self.tracks):
            selected = (i == self.track_choice)
            color = YELLOW if selected else (170, 170, 175)
            prefix = ">" if selected else " "
            self.text("%s %s" % (prefix, track.name), self.f_mid, color, 140, 215 + i * 34)
            if selected:
                self.text(track.description, self.f_small, WHITE, 420, 221 + i * 34)

        # ---- difficulty selection ----
        self.text("NPC DIFFICULTY   (Up / Down)", self.f_mid, CYAN, 120, 345)
        for i, name in enumerate(DIFF_NAMES):
            selected = (i == self.diff_choice)
            color = YELLOW if selected else (170, 170, 175)
            prefix = ">" if selected else " "
            self.text("%s %s" % (prefix, name), self.f_mid, color, 140, 385 + i * 34)

        # ---- controls ----
        self.panel(120, 500, 760, 150)
        lines = [
            "CONTROLS",
            "  W / Up ....... accelerate        S / Down ..... brake / reverse",
            "  A / Left ..... steer left        D / Right .... steer right",
            "  X ............ use nitro         R ............ restart race",
            "  ESC .......... back to menu",
            "Collect yellow coins for points and blue pickups for nitro.  %d laps to win." % TOTAL_LAPS,
        ]
        for i, line in enumerate(lines):
            color = YELLOW if i == 0 else WHITE
            self.text(line, self.f_small, color, 140, 515 + i * 22)

        self.text("Press ENTER to start", self.f_mid, (120, 240, 140), 400, 665)

    def draw_race(self):
        self.track.draw(self.screen)
        for bonus in self.bonuses:
            bonus.draw(self.screen)
        for car in self.cars:
            car.draw(self.screen)
        self.draw_hud()

    def draw_hud(self):
        player = self.player
        order = self.ranking()
        position = order.index(player) + 1
        best = min(player.lap_times) if player.lap_times else None
        current_lap_time = player.race_time - player.lap_start

        # ---- left panel: the important race info ----
        self.panel(10, 10, 230, 185)
        rows = [
            ("LAP", "%d / %d" % (min(player.lap + 1, TOTAL_LAPS), TOTAL_LAPS)),
            ("POSITION", "%d / %d" % (position, len(self.cars))),
            ("THIS LAP", format_time(current_lap_time)),
            ("BEST LAP", format_time(best)),
            ("SCORE", str(player.score)),
            ("SPEED", "%d km/h" % int(abs(player.speed) / 2)),
        ]
        for i, (label, value) in enumerate(rows):
            self.text(label, self.f_small, CYAN, 22, 20 + i * 24)
            self.text(value, self.f_small, WHITE, 130, 20 + i * 24)

        # ---- nitro bar ----
        self.text("NITRO  (X)", self.f_small, CYAN, 22, 168)
        pygame.draw.rect(self.screen, (60, 60, 65), (120, 168, 100, 14), border_radius=3)
        fill = int(player.nitro)
        bar_color = (255, 160, 40) if player.boosting else CYAN
        pygame.draw.rect(self.screen, bar_color, (120, 168, fill, 14), border_radius=3)

        # ---- right panel: standings + lap times ----
        self.panel(WIDTH - 240, 10, 230, 215)
        self.text("STANDINGS", self.f_small, YELLOW, WIDTH - 228, 20)
        for i, car in enumerate(order):
            color = PLAYER_COLOR if car.is_player else car.color
            self.text("%d. %-6s lap %d" % (i + 1, car.name, min(car.lap + 1, TOTAL_LAPS)),
                      self.f_small, color, WIDTH - 228, 44 + i * 22)
        self.text("LAP TIMES", self.f_small, YELLOW, WIDTH - 228, 140)
        if player.lap_times:
            for i, t in enumerate(player.lap_times):
                self.text("Lap %d  %s" % (i + 1, format_time(t)),
                          self.f_small, WHITE, WIDTH - 228, 162 + i * 20)
        else:
            self.text("-", self.f_small, WHITE, WIDTH - 228, 162)

        # ---- warnings / messages in the middle ----
        if not player.on_road:
            self.text("OFF TRACK - SLOWING DOWN!", self.f_mid, RED, 330, HEIGHT - 50)
        if self.message_timer > 0:
            self.text(self.message, self.f_mid, YELLOW, 440, HEIGHT - 85)

        # ---- countdown ----
        if self.countdown > 0:
            label = str(int(self.countdown) + 1)
            self.text(label, self.f_big, WHITE, WIDTH // 2 - 12, HEIGHT // 2 - 30)
        elif self.countdown > -1.0:
            self.text("GO!", self.f_big, (120, 240, 140), WIDTH // 2 - 45, HEIGHT // 2 - 30)

    def draw_results(self):
        self.screen.fill((24, 28, 38))
        player = self.player
        place = self.final_order.index(player) + 1

        self.text("RACE FINISHED", self.f_big, YELLOW, 330, 60)
        self.text("You finished in position %d of %d" % (place, len(self.cars)),
                  self.f_mid, CYAN, 320, 125)

        # final standings
        self.panel(150, 180, 700, 160)
        self.text("FINAL ORDER", self.f_small, YELLOW, 175, 192)
        for i, car in enumerate(self.final_order):
            color = PLAYER_COLOR if car.is_player else car.color
            # cars still driving when the player crossed the line are ranked
            # by how far around the track they got
            if car.finish_time is not None:
                total = format_time(car.finish_time)
            else:
                total = "still on lap %d" % min(car.lap + 1, TOTAL_LAPS)
            self.text("%d. %-7s  %s" % (i + 1, car.name, total),
                      self.f_mid, color, 175, 220 + i * 28)

        # player summary
        self.panel(150, 360, 700, 200)
        best = min(player.lap_times) if player.lap_times else None
        position_bonus = max(0, (len(self.cars) - place + 1) * 100)
        summary = [
            "YOUR RACE",
            "Track .............. %s" % self.track.name,
            "Difficulty ......... %s" % DIFF_NAMES[self.diff_choice],
            "Total time ......... %s" % format_time(player.finish_time),
            "Best lap ........... %s" % format_time(best),
            "All laps ........... %s" % ", ".join(format_time(t) for t in player.lap_times),
            "Bonus points ....... %d" % player.score,
            "Position bonus ..... %d" % position_bonus,
            "FINAL SCORE ........ %d" % (player.score + position_bonus),
        ]
        for i, line in enumerate(summary):
            color = YELLOW if i in (0, len(summary) - 1) else WHITE
            self.text(line, self.f_small, color, 175, 372 + i * 21)

        self.text("Press R to race again    ESC for the menu",
                  self.f_mid, (120, 240, 140), 280, 600)


# ------------------------------------------------------------------
# 7. START THE GAME
# ------------------------------------------------------------------
if __name__ == "__main__":
    Game().run()
