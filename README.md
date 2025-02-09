# Platformer Game Client

This project is a simple platformer game built with [Pygame](https://www.pygame.org/) in Python. The game offers both singleplayer and multiplayer modes. In multiplayer mode, the client uses [Socket.IO](https://socket.io/) to connect to a remote server (typically implemented in Node.js) to synchronize player positions in real time.

The server is responsible for:
- **Assigning Unique IDs**: When a client connects, the server sends a unique player ID.
- **Broadcasting Player Updates**: It collects and disseminates players’ positions so that each client can render other players.
- **Handling Disconnections**: When a player disconnects, the server updates the list of active players and informs the remaining clients.

For more details on the server implementation, refer to the [Socket.IO Multiplayer Server documentation](#server-integration).

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Code Breakdown](#code-breakdown)
  - [Socket.IO Client Setup](#socketio-client-setup)
  - [Game Menu & Mode Selection](#game-menu--mode-selection)
  - [Game Mechanics](#game-mechanics)
- [Server Integration](#server-integration)
- [Customization](#customization)
- [License](#license)
- [Author](#author)

## Overview

The game client is written in Python using Pygame for graphics and user input. It provides a start menu to choose between Singleplayer and Multiplayer modes. In multiplayer mode, the client establishes a Socket.IO connection to a remote server with extended ping settings to maintain a stable connection over WebSocket.

### Key Points:
- **Multiplayer Mode**: Uses Socket.IO to send and receive real-time player updates.
- **Smooth Interpolation**: Remote player positions are smoothly interpolated to create seamless movement.
- **Extended Ping Settings**: The client uses custom ping intervals and timeouts to maintain connection reliability.
- **Server Coordination**: The server assigns a unique ID to each client and manages player data.

## Features

- **Dual Game Modes**: Singleplayer and Multiplayer.
- **Real-Time Communication**: Socket.IO client is configured with extended ping settings and forces WebSocket transport.
- **Smooth Remote Updates**: Linear interpolation is used to update remote players’ positions smoothly.
- **Basic Platformer Mechanics**: Simple physics, collision detection, and jumping.

## Requirements

- Python 3.x
- [Pygame](https://www.pygame.org/wiki/GettingStarted)
- [python-socketio](https://python-socketio.readthedocs.io/)

## Installation

1. **Clone the Repository:**

   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install Dependencies:**

   Use `pip` to install the required libraries:

   ```bash
   pip install pygame python-socketio
   ```

## Usage

Run the game client with:

```bash
python game_client.py
```

On launch, a menu will appear allowing you to choose between:
- **Singleplayer**: Play the game locally.
- **Multiplayer**: Connect to the remote Socket.IO server (at `https://game-server-production-f1e6.up.railway.app`) to exchange player updates.

## Code Breakdown

Below is an overview of the key components of the code.

### Socket.IO Client Setup

- **Logging & Helper Function:**

  A linear interpolation function (`lerp`) is defined to smoothly update remote players’ positions:

  ```python
  def lerp(a, b, t):
      return a + (b - a) * t
  ```

  Logging is configured to help monitor Socket.IO events.

- **Client Initialization with Extended Ping Settings:**

  The Socket.IO client is initialized to use WebSocket transport with a 30-second ping interval and a 90-second timeout. This setup is designed for a robust connection:

  ```python
  try:
      sio = socketio.Client(
          reconnection=True,
          reconnection_attempts=0,  # Unlimited reconnection attempts
          reconnection_delay=1,
          engineio_options={
              'transports': ['websocket'],
              'ping_interval': 30,  # Send a ping every 30 seconds
              'ping_timeout': 90    # Wait 90 seconds for a pong before disconnecting
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
  ```

- **Event Handlers:**

  The client listens for key events:
  
  - `connect`: Notifies successful connection.
  - `disconnect`: Notifies when disconnected.
  - `your_id`: Receives and stores the unique player ID from the server.
  - `player_update`: Updates remote player data based on the server’s broadcast.

### Game Menu & Mode Selection

- **Menu Screen:**

  A simple Pygame-based menu lets you choose between Singleplayer and Multiplayer. Depending on the selection, the Socket.IO client either starts in a separate thread (multiplayer) or is replaced with a dummy object (singleplayer).

  ```python
  def menu_screen(screen):
      # Displays the start menu and returns True for Multiplayer, False for Singleplayer.
      ...
  ```

### Game Mechanics

- **Player Class & Physics:**

  The `Player` class handles movement, physics (gravity, collision detection), and rendering of the player character.

- **Platforms:**

  A list of platforms is defined as rectangles that the player can interact with.

- **Main Game Loop:**

  The game loop:
  
  - Processes events.
  - Updates player movement.
  - In multiplayer mode, periodically emits the player's current position to the server (every 50 ms).
  - Interpolates remote players’ positions using the `lerp` function.
  - Renders the game scene (platforms, local and remote players).

  ```python
  while True:
      clock.tick(60)
      # Event processing, input handling, and game state updates.
      ...
      
      # Throttle outgoing updates:
      if multiplayer_mode and current_time - last_update_time > update_interval:
          if hasattr(sio, 'connected') and sio.connected:
              sio.emit('player_update', {'x': player.rect.x, 'y': player.rect.y})
          last_update_time = current_time
      
      # Smoothly update remote players:
      for pid, pdata in remote_players.items():
          pdata['current_x'] = lerp(pdata['current_x'], pdata['target_x'], 0.1)
          pdata['current_y'] = lerp(pdata['current_y'], pdata['target_y'], 0.1)
      
      # Render the game objects:
      ...
      
      pygame.display.flip()
  ```

## Server Integration

The multiplayer features rely on a separate Socket.IO server, typically built using Node.js. This server:

- **Assigns Unique IDs**: On connection, the server sends a unique ID via the `your_id` event.
- **Broadcasts Updates**: It listens for `player_update` events from all connected clients, updates a global state, and broadcasts this state back to each client.
- **Manages Disconnections**: When a client disconnects, the server removes that player’s data and broadcasts the updated player list.

For more information on the server, see the [Socket.IO Multiplayer Server documentation](./README_server.md) or refer to your server's setup instructions.

## Customization

- **Gameplay Enhancements**: Modify the `Player` class or add new game mechanics.
- **UI Improvements**: Enhance the menu or game graphics using Pygame.
- **Networking**: Extend the Socket.IO event system to include new features (e.g., in-game chat, power-ups).
