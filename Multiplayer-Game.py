import sys
import pygame
import threading
import socketio
import logging
import time
import math


# --- Helper Function: Linear Interpolation ---
def lerp(a, b, t):
    return a + (b - a) * t


# --- Set Up Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("socketio")


# --- SOCKET.IO MANAGER (with leaderboard event) ---
class SocketManager:
    """
    Encapsulates the Socket.IO client, events, and networking thread.
    Multiplayer functionality remains largely unchanged.
    """

    def __init__(self, multiplayer_mode=True):
        self.multiplayer_mode = multiplayer_mode
        self.remote_players = {}  # Data for other players
        self.local_player_id = None
        self.leaderboard = []  # Latest leaderboard data from the server
        # This callback will be set by the game to handle level advancement
        self.advance_level_callback = None
        if self.multiplayer_mode:
            self._init_socket()
        else:
            self._create_dummy_socket()

    def _init_socket(self):
        # Initialize the Socket.IO client with extended ping settings.
        try:
            self.sio = socketio.Client(
                reconnection=True,
                reconnection_attempts=0,  # Unlimited attempts
                reconnection_delay=1,
                engineio_options={
                    'transports': ['websocket'],
                    'ping_interval': 30,  # Send a ping every 30 seconds
                    'ping_timeout': 90  # Wait 90 seconds for a pong
                }
            )
            logger.info("Initialized Socket.IO client with custom engineio_options.")
        except TypeError:
            self.sio = socketio.Client(
                reconnection=True,
                reconnection_attempts=0,
                reconnection_delay=1
            )
            logger.info("Initialized Socket.IO client without custom engineio_options.")
        self.sio.logger = logger
        self._register_events()
        self.thread = threading.Thread(target=self._socket_thread, daemon=True)
        self.thread.start()

    def _create_dummy_socket(self):
        # For singleplayer mode, we don’t need a real socket.
        class DummySocket:
            def emit(self, event, data):
                pass

            def disconnect(self):
                pass

        self.sio = DummySocket()
        self.remote_players = {}

    def _register_events(self):
        @self.sio.event
        def connect():
            print("Connected to game server.")

        @self.sio.event
        def disconnect():
            print("Disconnected from game server.")

        @self.sio.on('your_id')
        def on_your_id(data):
            self.local_player_id = data
            print("Received local player id:", self.local_player_id)

        @self.sio.on('player_update')
        def on_player_update(data):
            # Data is a dict mapping player IDs to {'x': ..., 'y': ..., 'username': ..., 'score': ...}
            for pid, pdata in data.items():
                if pid == self.local_player_id:
                    continue  # Skip our own data
                if pid not in self.remote_players:
                    self.remote_players[pid] = {
                        'current_x': pdata['x'],
                        'current_y': pdata['y'],
                        'target_x': pdata['x'],
                        'target_y': pdata['y']
                    }
                else:
                    self.remote_players[pid]['target_x'] = pdata['x']
                    self.remote_players[pid]['target_y'] = pdata['y']
            # Remove players not in the current update.
            for pid in list(self.remote_players.keys()):
                if pid not in data:
                    del self.remote_players[pid]

        @self.sio.on('advance_level')
        def on_advance_level(data):
            print("Received advance_level event from server.")
            if self.advance_level_callback:
                self.advance_level_callback()

        @self.sio.on('leaderboard_update')
        def on_leaderboard_update(data):
            self.leaderboard = data
            print("Received leaderboard update:", data)

    def _socket_thread(self):
        try:
            # Connect to the server (forcing the WebSocket transport)
            self.sio.connect(
                'https://game-server-production-f1e6.up.railway.app',
                transports=['websocket']
            )
            self.sio.wait()  # Keep the socket thread alive
        except Exception as e:
            print("Socket connection error:", e)

    def emit_update(self, data):
        # Throttle or check connection before emitting updates.
        if hasattr(self.sio, 'connected') and self.sio.connected:
            self.sio.emit('player_update', data)

    def disconnect(self):
        self.sio.disconnect()


# --- PLAYER CLASS ---
class Player:
    def __init__(self, x, y, width=50, height=50, color=(0, 0, 255)):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.velocity_x = 0
        self.velocity_y = 0
        self.on_ground = False
        self.speed = 5
        self.jump_strength = -15
        self.gravity = 1
        self.terminal_velocity = 10

    def handle_input(self):
        keys = pygame.key.get_pressed()
        self.velocity_x = 0
        if keys[pygame.K_LEFT]:
            self.velocity_x = -self.speed
        if keys[pygame.K_RIGHT]:
            self.velocity_x = self.speed
        if keys[pygame.K_SPACE] and self.on_ground:
            self.velocity_y = self.jump_strength
            self.on_ground = False

    def update(self, platforms):
        # Apply gravity
        self.velocity_y += self.gravity
        if self.velocity_y > self.terminal_velocity:
            self.velocity_y = self.terminal_velocity

        # Horizontal movement and collision
        self.rect.x += self.velocity_x
        for plat in platforms:
            if self.rect.colliderect(plat):
                if self.velocity_x > 0:
                    self.rect.right = plat.left
                elif self.velocity_x < 0:
                    self.rect.left = plat.right
                self.velocity_x = 0

        # Vertical movement and collision
        self.rect.y += self.velocity_y
        self.on_ground = False
        for plat in platforms:
            if self.rect.colliderect(plat):
                if self.velocity_y > 0:
                    self.rect.bottom = plat.top
                    self.velocity_y = 0
                    self.on_ground = True
                elif self.velocity_y < 0:
                    self.rect.top = plat.bottom
                    self.velocity_y = 0

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)


# --- PORTAL CLASS ---
class Portal:
    def __init__(self, x, y, radius=30):
        self.x = x
        self.y = y
        self.radius = radius
        self.angle = 0  # For animation

    def update(self):
        self.angle = (self.angle + 5) % 360

    def draw(self, surface):
        pulse = int(self.radius + 5 * math.sin(pygame.time.get_ticks() * 0.005))
        glow_color = (50, 50, 50)
        pygame.draw.circle(surface, glow_color, (self.x, self.y), pulse + 5)
        pygame.draw.circle(surface, (0, 0, 0), (self.x, self.y), pulse)
        end_x = self.x + pulse * math.cos(math.radians(self.angle))
        end_y = self.y + pulse * math.sin(math.radians(self.angle))
        pygame.draw.line(surface, (255, 255, 255), (self.x, self.y), (end_x, end_y), 3)

    def get_rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)


# --- GAME CLASS (with UI overlays) ---
class Game:
    def __init__(self, multiplayer_mode):
        pygame.init()
        self.WIDTH, self.HEIGHT = 800, 600
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        mode_text = "Multiplayer" if multiplayer_mode else "Singleplayer"
        pygame.display.set_caption(f"Platformer Game ({mode_text})")
        self.clock = pygame.time.Clock()
        self.multiplayer_mode = multiplayer_mode

        self.socket_manager = SocketManager(multiplayer_mode)
        if self.multiplayer_mode:
            self.socket_manager.advance_level_callback = self.advance_level_sync

        self.last_update_time = time.time()
        self.update_interval = 0.05  # 50 ms update interval
        self.player = Player(50, self.HEIGHT - 100)
        # Define levels with start positions, platforms, and portals.
        self.levels = {
            1: {
                "start": (50, self.HEIGHT - 100),
                "platforms": [
                    pygame.Rect(0, self.HEIGHT - 50, self.WIDTH, 50),  # Ground
                    pygame.Rect(150, 450, 150, 20),
                    pygame.Rect(350, 350, 150, 20),
                    pygame.Rect(550, 250, 150, 20)
                ],
                "portal": Portal(700, self.HEIGHT - 100, 30)
            },
            2: {
                "start": (50, self.HEIGHT - 100),
                "platforms": [
                    pygame.Rect(0, self.HEIGHT - 50, self.WIDTH, 50),  # Ground
                    pygame.Rect(100, 400, 150, 20),
                    pygame.Rect(300, 300, 150, 20),
                    pygame.Rect(500, 200, 150, 20)
                ],
                "portal": None  # End level (or add another portal if desired)
            }
        }
        self.current_level = 1
        self.platforms = self.levels[self.current_level]["platforms"]
        self.portal = self.levels[self.current_level].get("portal")
        self.running = True
        self.font = pygame.font.SysFont("Arial", 24)
        self.score = 0  # Score can be updated as desired (here, we use the level number)

        # UI Flags and data for settings and leaderboard
        self.show_leaderboard = False
        self.show_settings = False
        self.username = "Player"
        self.username_input = self.username
        # Define button rectangles for UI (settings in top-left, leaderboard in top-right)
        self.settings_button_rect = pygame.Rect(10, 10, 100, 40)
        self.leaderboard_button_rect = pygame.Rect(self.WIDTH - 110, 10, 100, 40)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # If the settings overlay is NOT active, check for button clicks.
                if not self.show_settings:
                    if self.settings_button_rect.collidepoint(event.pos):
                        self.show_settings = True
                        self.username_input = self.username  # prefill with current username
                    elif self.leaderboard_button_rect.collidepoint(event.pos):
                        self.show_leaderboard = not self.show_leaderboard
                # (Optional: clicks outside an open overlay could close it.)

            elif event.type == pygame.KEYDOWN:
                if self.show_settings:
                    if event.key == pygame.K_RETURN:
                        # Confirm the username and close the settings overlay.
                        self.username = self.username_input
                        self.show_settings = False
                    elif event.key == pygame.K_BACKSPACE:
                        self.username_input = self.username_input[:-1]
                    else:
                        self.username_input += event.unicode

    def reset_player(self):
        # Reset player's position and velocities to the current level's start.
        start_pos = self.levels[self.current_level]["start"]
        self.player.rect.x, self.player.rect.y = start_pos
        self.player.velocity_x = 0
        self.player.velocity_y = 0

    def _advance_level_local(self):
        if self.current_level < max(self.levels.keys()):
            self.current_level += 1
            start_pos = self.levels[self.current_level]["start"]
            self.player.rect.x, self.player.rect.y = start_pos
            self.platforms = self.levels[self.current_level]["platforms"]
            self.portal = self.levels[self.current_level].get("portal")
            self.score = self.current_level  # update score; customize as needed
            print(f"Advanced to level {self.current_level}!")
        else:
            print("You completed all levels!")
            self.running = False

    def advance_level_sync(self):
        # Callback for networked level advancement.
        self._advance_level_local()

    def update(self):
        # Pump the event queue to keep key states updated.
        pygame.event.pump()
        # Only process game controls if settings overlay is not active.
        if not self.show_settings:
            self.player.handle_input()
            self.player.update(self.platforms)

            # Out-of-bounds reset.
            if (self.player.rect.top > self.HEIGHT or
                    self.player.rect.left > self.WIDTH or
                    self.player.rect.right < 0):
                print("Out of bounds! Resetting player position.")
                self.reset_player()

            # Check for portal collision.
            if self.portal and self.player.rect.colliderect(self.portal.get_rect()):
                print("Portal reached!")
                if self.multiplayer_mode:
                    self.socket_manager.sio.emit('advance_level', {})
                self._advance_level_local()

            if self.portal:
                self.portal.update()

        # Send local player update (with username and score) at a throttled interval.
        current_time = time.time()
        if self.multiplayer_mode and current_time - self.last_update_time > self.update_interval:
            self.socket_manager.emit_update({
                'x': self.player.rect.x,
                'y': self.player.rect.y,
                'username': self.username,
                'score': self.score
            })
            self.last_update_time = current_time

        # Interpolate remote players for smooth movement.
        if self.multiplayer_mode:
            for pdata in self.socket_manager.remote_players.values():
                pdata['current_x'] = lerp(pdata['current_x'], pdata['target_x'], 0.1)
                pdata['current_y'] = lerp(pdata['current_y'], pdata['target_y'], 0.1)

    def draw(self):
        # Draw game elements.
        self.screen.fill((0, 0, 0))
        for plat in self.platforms:
            pygame.draw.rect(self.screen, (255, 255, 255), plat)
        self.player.draw(self.screen)
        if self.portal:
            self.portal.draw(self.screen)
        if self.multiplayer_mode:
            for pdata in self.socket_manager.remote_players.values():
                remote_rect = pygame.Rect(pdata['current_x'], pdata['current_y'], 50, 50)
                pygame.draw.rect(self.screen, (255, 0, 0), remote_rect)
            # (Optional) Display connection status.
            status_text = "Connected" if hasattr(self.socket_manager.sio,
                                                 'connected') and self.socket_manager.sio.connected else "Disconnected"
            status_surface = self.font.render(f"Status: {status_text}", True,
                                              (0, 255, 0) if status_text == "Connected" else (255, 0, 0))
            self.screen.blit(status_surface, (10, 60))
        level_surface = self.font.render(f"Level: {self.current_level}", True, (255, 255, 255))
        self.screen.blit(level_surface, (self.WIDTH - 120, 60))

        # --- Draw UI Buttons ---
        # Settings button (top-left)
        pygame.draw.rect(self.screen, (100, 100, 100), self.settings_button_rect)
        settings_text = self.font.render("Settings", True, (255, 255, 255))
        self.screen.blit(settings_text, (self.settings_button_rect.x + 5, self.settings_button_rect.y + 5))
        # Display current username next to settings button.
        username_text = self.font.render(self.username, True, (255, 255, 255))
        self.screen.blit(username_text, (self.settings_button_rect.right + 10, self.settings_button_rect.y + 5))

        # Leaderboard button (top-right)
        pygame.draw.rect(self.screen, (100, 100, 100), self.leaderboard_button_rect)
        leaderboard_text = self.font.render("Leaderboard", True, (255, 255, 255))
        text_rect = leaderboard_text.get_rect(center=self.leaderboard_button_rect.center)
        self.screen.blit(leaderboard_text, text_rect)

        # --- Draw Leaderboard Overlay if toggled ---
        if self.show_leaderboard:
            overlay = pygame.Surface((self.WIDTH * 0.8, self.HEIGHT * 0.8))
            overlay.set_alpha(230)
            overlay.fill((50, 50, 50))
            overlay_rect = overlay.get_rect(center=(self.WIDTH / 2, self.HEIGHT / 2))
            self.screen.blit(overlay, overlay_rect)
            title = self.font.render("Leaderboard", True, (255, 255, 255))
            self.screen.blit(title, (overlay_rect.x + 20, overlay_rect.y + 20))
            # Display leaderboard entries (show username if available, else socket id).
            if hasattr(self.socket_manager, 'leaderboard'):
                for i, entry in enumerate(self.socket_manager.leaderboard):
                    name = entry.get('username', entry.get('id', 'Unknown'))
                    score = entry.get('score', 0)
                    entry_text = self.font.render(f"{i + 1}. {name}: {score}", True, (255, 255, 255))
                    self.screen.blit(entry_text, (overlay_rect.x + 20, overlay_rect.y + 60 + i * 30))

        # --- Draw Settings Overlay if active ---
        if self.show_settings:
            overlay = pygame.Surface((self.WIDTH * 0.5, self.HEIGHT * 0.3))
            overlay.set_alpha(230)
            overlay.fill((50, 50, 50))
            overlay_rect = overlay.get_rect(center=(self.WIDTH / 2, self.HEIGHT / 2))
            self.screen.blit(overlay, overlay_rect)
            prompt = self.font.render("Enter username:", True, (255, 255, 255))
            self.screen.blit(prompt, (overlay_rect.x + 20, overlay_rect.y + 20))
            input_box = pygame.Rect(overlay_rect.x + 20, overlay_rect.y + 60, overlay_rect.width - 40, 40)
            pygame.draw.rect(self.screen, (100, 100, 100), input_box)
            username_input_text = self.font.render(self.username_input, True, (255, 255, 255))
            self.screen.blit(username_input_text, (input_box.x + 5, input_box.y + 5))
            instruction = self.font.render("Press Enter to confirm", True, (200, 200, 200))
            self.screen.blit(instruction, (overlay_rect.x + 20, overlay_rect.y + overlay_rect.height - 40))

        pygame.display.flip()

    def run(self):
        while self.running:
            self.clock.tick(60)
            self.handle_events()
            self.update()
            self.draw()
        if self.multiplayer_mode:
            self.socket_manager.disconnect()
        pygame.quit()
        sys.exit()


# --- IMPROVED MENU SCREEN FUNCTION ---
def menu_screen(screen):
    clock = pygame.time.Clock()
    font_title = pygame.font.SysFont("Arial", 64)
    font_option = pygame.font.SysFont("Arial", 32)

    title_text = font_title.render(" Platformer", True, (255, 255, 255))
    sp_text = font_option.render("Singleplayer", True, (0, 0, 0))
    mp_text = font_option.render("Multiplayer", True, (0, 0, 0))

    sp_button = pygame.Rect(screen.get_width() // 2 - 220, 300, 200, 80)
    mp_button = pygame.Rect(screen.get_width() // 2 + 20, 300, 200, 80)

    selecting = True
    mode = None
    while selecting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                if sp_button.collidepoint(mx, my):
                    mode = False
                    selecting = False
                elif mp_button.collidepoint(mx, my):
                    mode = True
                    selecting = False

        screen.fill((20, 20, 20))
        for i in range(50):
            x = (i * 17) % screen.get_width()
            y = (i * 23) % screen.get_height()
            pygame.draw.circle(screen, (100, 100, 100), (x, y), 2)

        shadow = font_title.render(" Platformer", True, (0, 0, 0))
        screen.blit(shadow, (screen.get_width() // 2 - shadow.get_width() // 2 + 4, 100 + 4))
        screen.blit(title_text, (screen.get_width() // 2 - title_text.get_width() // 2, 100))

        pygame.draw.rect(screen, (0, 150, 200), sp_button, border_radius=10)
        pygame.draw.rect(screen, (200, 150, 0), mp_button, border_radius=10)
        screen.blit(sp_text,
                    (sp_button.centerx - sp_text.get_width() // 2, sp_button.centery - sp_text.get_height() // 2))
        screen.blit(mp_text,
                    (mp_button.centerx - mp_text.get_width() // 2, mp_button.centery - mp_text.get_height() // 2))

        pygame.display.flip()
        clock.tick(60)
    return mode


# --- MAIN FUNCTION ---
def main():
    pygame.init()
    WIDTH, HEIGHT = 800, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Platformer Menu")
    multiplayer_mode = menu_screen(screen)
    game = Game(multiplayer_mode)
    game.run()


if __name__ == '__main__':
    main()
