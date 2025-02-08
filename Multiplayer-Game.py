import sys
import pygame
import threading
import socketio
import logging
import time


# --- Helper: Linear Interpolation Function ---
def lerp(a, b, t):
    return a + (b - a) * t


# --- Set Up Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("socketio")

# --- SOCKET.IO CLIENT INITIALIZATION WITH EXTENDED PING SETTINGS ---
# (Using engineio_options if supported)
try:
    sio = socketio.Client(
        reconnection=True,
        reconnection_attempts=0,  # Unlimited reconnection attempts
        reconnection_delay=1,
        engineio_options={
            'transports': ['websocket'],
            'ping_interval': 30,  # Send a ping every 30 seconds
            'ping_timeout': 90  # Wait 90 seconds for a pong before disconnecting
        }
    )
    logger.info("Initialized Socket.IO client with custom settings (WebSocket, extended ping).")
except TypeError:
    sio = socketio.Client(
        reconnection=True,
        reconnection_attempts=0,
        reconnection_delay=1
    )
    logger.info("Initialized Socket.IO client without custom engineio_options.")
sio.logger = logger

# --- Global Variables ---
remote_players = {}
local_player_id = None  # Will be assigned by the server


# --- SOCKET.IO EVENT HANDLERS ---
@sio.event
def connect():
    print("Connected to game server.")


@sio.event
def disconnect():
    print("Disconnected from game server.")


@sio.on('your_id')
def on_your_id(data):
    global local_player_id
    local_player_id = data
    print("Received local player id:", local_player_id)


@sio.on('player_update')
def on_player_update(data):
    global remote_players
    # data is a dictionary mapping player ids to {'x': ..., 'y': ...}
    for pid, pdata in data.items():
        if pid == local_player_id:
            continue  # Skip our own data
        if pid not in remote_players:
            remote_players[pid] = {
                'current_x': pdata['x'],
                'current_y': pdata['y'],
                'target_x': pdata['x'],
                'target_y': pdata['y']
            }
        else:
            remote_players[pid]['target_x'] = pdata['x']
            remote_players[pid]['target_y'] = pdata['y']
    # Remove players that are no longer in the update.
    for pid in list(remote_players.keys()):
        if pid not in data:
            del remote_players[pid]


def socket_thread():
    try:
        # Connect to your public server URL (forcing WebSocket transport)
        sio.connect('https://game-server-production-f1e6.up.railway.app', transports=['websocket'])
        sio.wait()  # Keeps the socket thread alive
    except Exception as e:
        print("Socket connection error:", e)


# --- START MENU FUNCTION ---
def menu_screen(screen):
    """Display a start-menu to select Singleplayer or Multiplayer."""
    font = pygame.font.SysFont(None, 48)
    title_text = font.render("Select Game Mode", True, (0, 0, 0))
    sp_button = pygame.Rect(150, 250, 200, 100)  # Singleplayer button
    mp_button = pygame.Rect(450, 250, 200, 100)  # Multiplayer button
    sp_text = font.render("Singleplayer", True, (255, 255, 255))
    mp_text = font.render("Multiplayer", True, (255, 255, 255))

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                if sp_button.collidepoint(mx, my):
                    return False
                elif mp_button.collidepoint(mx, my):
                    return True
        screen.fill((200, 200, 200))
        screen.blit(title_text, (screen.get_width() // 2 - title_text.get_width() // 2, 150))
        pygame.draw.rect(screen, (0, 100, 200), sp_button)
        pygame.draw.rect(screen, (200, 100, 0), mp_button)
        screen.blit(sp_text, (sp_button.centerx - sp_text.get_width() // 2,
                              sp_button.centery - sp_text.get_height() // 2))
        screen.blit(mp_text, (mp_button.centerx - mp_text.get_width() // 2,
                              mp_button.centery - mp_text.get_height() // 2))
        pygame.display.flip()
        pygame.time.delay(30)


# --- INITIALIZE PYGAME AND DISPLAY THE MENU ---
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Platformer Game Menu")
multiplayer_mode = menu_screen(screen)
mode_text = "Multiplayer" if multiplayer_mode else "Singleplayer"
pygame.display.set_caption("Platformer Game (" + mode_text + ")")

if multiplayer_mode:
    # Start the socket connection in a separate thread
    threading.Thread(target=socket_thread, daemon=True).start()
else:
    # For singleplayer mode, override sio with a dummy object.
    class DummySocket:
        def emit(self, event, data):
            pass

        def disconnect(self):
            pass


    sio = DummySocket()
    remote_players = {}

# --- GAME SETUP: COLORS, CLOCK, AND GAME CLASSES ---
clock = pygame.time.Clock()
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)


class Player:
    def __init__(self, x, y, width=50, height=50, color=BLUE):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.velocity_x = 0
        self.velocity_y = 0
        self.on_ground = False

    def handle_input(self):
        keys = pygame.key.get_pressed()
        self.velocity_x = 0
        if keys[pygame.K_LEFT]:
            self.velocity_x = -5
        if keys[pygame.K_RIGHT]:
            self.velocity_x = 5
        if keys[pygame.K_SPACE] and self.on_ground:
            self.velocity_y = -15
            self.on_ground = False

    def update(self, platforms):
        self.velocity_y += 1
        if self.velocity_y > 10:
            self.velocity_y = 10
        self.rect.x += self.velocity_x
        for plat in platforms:
            if self.rect.colliderect(plat):
                if self.velocity_x > 0:
                    self.rect.right = plat.left
                elif self.velocity_x < 0:
                    self.rect.left = plat.right
                self.velocity_x = 0
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


platforms = [
    pygame.Rect(0, HEIGHT - 50, WIDTH, 50),  # Ground
    pygame.Rect(100, 400, 200, 20),
    pygame.Rect(400, 300, 200, 20),
    pygame.Rect(250, 200, 150, 20)
]
player = Player(50, HEIGHT - 100)

# --- Throttle outgoing updates: send only every 50 ms ---
last_update_time = 0
update_interval = 0.05  # 50 milliseconds

# --- MAIN GAME LOOP ---
while True:
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    player.handle_input()
    player.update(platforms)

    current_time = time.time()
    if multiplayer_mode and current_time - last_update_time > update_interval:
        if hasattr(sio, 'connected') and sio.connected:
            sio.emit('player_update', {'x': player.rect.x, 'y': player.rect.y})
        last_update_time = current_time

    # Interpolate remote players for smooth movement.
    for pid, pdata in remote_players.items():
        pdata['current_x'] = lerp(pdata['current_x'], pdata['target_x'], 0.1)
        pdata['current_y'] = lerp(pdata['current_y'], pdata['target_y'], 0.1)

    screen.fill(WHITE)
    for plat in platforms:
        pygame.draw.rect(screen, BLACK, plat)
    player.draw(screen)
    if multiplayer_mode:
        for pid, pdata in remote_players.items():
            remote_rect = pygame.Rect(pdata['current_x'], pdata['current_y'], 50, 50)
            pygame.draw.rect(screen, RED, remote_rect)
    pygame.display.flip()

if multiplayer_mode:
    sio.disconnect()
