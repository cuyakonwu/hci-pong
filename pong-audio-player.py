"""
    # PONG PLAYER EXAMPLE

    HOW TO CONNECT TO HOST AS PLAYER 1
    > python pong-audio-player.py p1 --host_ip HOST_IP --host_port 5005 --player_ip YOUR_IP --player_port 5007

    HOW TO CONNECT TO HOST AS PLAYER 2
    > python pong-audio-player.py p2 --host_ip HOST_IP --host_port 5006 --player_ip YOUR_IP --player_port 5008

    about IP and ports: 127.0.0.1 means your own computer, change it to play across computer under the same network. port numbers are picked to avoid conflits.

    DEBUGGING:

    You can use keyboards to send command, such as "g 1" to start the game, see the end of this file

"""
#native imports
import time
from playsound import playsound
import argparse

from pythonosc import osc_server
from pythonosc import dispatcher
from pythonosc import udp_client

# threading so that listenting to speech would not block the whole program
import threading
# speech recognition (default using google, requiring internet)
import speech_recognition as sr
# pitch & volume detection
import aubio
import numpy as num
import pyaudio
import wave
import subprocess

mode = ''
debug = False
quit = False

host_ip = "127.0.0.1"
host_port_1 = 5005 # you are player 1 if you talk to this port
host_port_2 = 5006
player_1_ip = "127.0.0.1"
player_2_ip = "127.0.0.1"
player_1_port = 5007
player_2_port = 5008

player_ip = "127.0.0.1"
player_port = 0
host_port = 0

if __name__ == '__main__' :

    parser = argparse.ArgumentParser(description='Program description')
    parser.add_argument('mode', help='host, player (ip & port required)')
    parser.add_argument('--host_ip', type=str, required=False)
    parser.add_argument('--host_port', type=int, required=False)
    parser.add_argument('--player_ip', type=str, required=False)
    parser.add_argument('--player_port', type=int, required=False)
    parser.add_argument('--debug', action='store_true', help='show debug info')
    args = parser.parse_args()
    print("> run as " + args.mode)
    mode = args.mode
    if (args.host_ip):
        host_ip = args.host_ip
    if (args.host_port):
        host_port = args.host_port
    if (args.player_ip):
        player_ip = args.player_ip
    if (args.player_port):
        player_port = args.player_port
    if (args.debug):
        debug = True


if mode == 'p1':
    player_side = 'left'
elif mode == 'p2':
    player_side = 'right'


# GAME INFO

# functions receiving messages from host

# Global Variables
difficulty_announced = False
player_said_hi = False
opponent_said_hi = False
game_running = False
level_confirmed = False
player_frozen = False
game_paused = False
paused_by_player = None
difficulty_selection = True
big_paddle_available = False
big_paddle_active = False
current_level = "easy"

prev_score_p1 = 0
prev_score_p2 = 0
score_lock = threading.Lock()

player_paddle_position = 225
ball_y_position = 225

# Locks for thread safety
paddle_position_lock = threading.Lock()
ball_position_lock = threading.Lock()


if mode == 'p1':
    player_side = 'left'
elif mode == 'p2':
    player_side = 'right'

def on_receive_game(address, *args):
    global game_running, difficulty_announced, difficulty_selection, player_said_hi
    global opponent_said_hi, current_volume, level_confirmed, game_paused, paused_by_player
    game_state = args[0]
    print(f"> Game state: {game_state}")

    if game_state == 1:
        if not game_running:
            print("> Game started")
            game_running = True
            difficulty_announced = False
            difficulty_selection = False
            player_said_hi = False
            opponent_said_hi = False
            game_paused = False
            paused_by_player = None
            current_volume = 0.5
            subprocess.run(['say', 'The game has started'])
        elif game_paused:
            # Game was paused, now it's resumed
            game_paused = False
            paused_by_player = None
            print("> Game resumed")
            subprocess.run(['say', 'Game resumed'])
    elif game_state == 0:
        if game_running:
            # Game was running, now it's paused
            game_paused = True
            print("> Game paused")
            subprocess.run(['say', 'Game paused'])
        else:
            # Game is in menu state
            if not level_confirmed:
                if not difficulty_announced:
                    print("> In menu (Player 1)")
                    subprocess.run(['say', 'Select difficulty. Easy, Hard, or Insane'])
                    difficulty_announced = True
                    difficulty_selection = True
                    player_said_hi = False
                    opponent_said_hi = False
                    current_volume = 0.0
            else:
                print("> In menu, difficulty already confirmed.")
    else:
        print(f"> Unknown game state: {game_state}")
        subprocess.run(['say', 'Received unknown game state'])


# Ball Sound Variables
current_freq = 440.0  # Starting frequency
current_volume = 0.0          # Volume (0.0 - 1.0)
fs = 44100     # Hz
freq_lock = threading.Lock()
volume_lock = threading.Lock()

def audio_callback(in_data, frame_count, time_info, status):
    global current_freq, current_volume, game_running
    if game_running and current_volume > 0:
        with freq_lock:
            freq = current_freq
        with volume_lock:
            vol = current_volume
        t = (num.arange(frame_count) + audio_callback.frame_index) / fs
        data = (num.sin(2 * num.pi * freq * t)).astype(num.float32)
        audio_callback.frame_index += frame_count
        data *= vol
    else:
        data = num.zeros(frame_count, dtype=num.float32)
    return (data.tobytes(), pyaudio.paContinue)


audio_callback.frame_index = 0

paddle_position = 225
ball_position_lock = threading.Lock()

def on_receive_ball(address, *args):
    global current_freq, current_volume, ball_y_position
    y = args[1]
    x = args[0]

    min_freq = 200.0
    max_freq = 1000.0
    min_y = 0.0
    max_y = 450.0

    min_volume = 0.01
    max_volume = 0.75
    min_x = 0.0
    max_x = 800.0

    new_freq = min_freq + (max_y - y) * (max_freq - min_freq) / (max_y - min_y)

    if player_side == 'left':
        new_volume = min_volume + (max_x - x) * (max_volume - min_volume) / (max_x - min_x)
    else:
        new_volume = min_volume + (x - min_x) * (max_volume - min_volume) / (max_x - min_x)

    new_volume = max(min(new_volume, max_volume), min_volume)

    with freq_lock:
        current_freq = new_freq
    with volume_lock:
        current_volume = new_volume

    with ball_position_lock:
        ball_y_position = y


def on_receive_paddle(address, *args):
    global ball_y_position
    if len(args) < 2:
        print("Error: /paddle message missing arguments.")
        return
    x = args[0]  # Ball's X-position (if needed)
    y = args[1]  # Ball's Y-position
    with ball_position_lock:
        ball_y_position = y
    if debug:
        print(f"Received ball position: x={x}, y={y}")


def on_receive_hitpaddle(address, *args):
    paddle_number = args[0]
    if (paddle_number == 1 and mode == 'p1') or (paddle_number == 2 and mode == 'p2'):
        print(f"> Ball hit your paddle ({paddle_number})")
        hit()
    else:
        # The ball hit the opponent's paddle
        print(f"> Ball hit opponent's paddle ({paddle_number})")
        pass


def on_receive_ballout(address, *args):
    side = args[0]  # 1 for left side, 2 for right side
    print(f"> Ball went out on {'left' if side == 1 else 'right'} side")


def on_receive_ballbounce(address, *args):
    # example sound
    hit()
    print("> ball bounced on up/down side: " + str(args[0]) )


def on_receive_scores(address, *args):
    global prev_score_p1, prev_score_p2
    score_p1 = args[0]
    score_p2 = args[1]
    print(f"> Scores now: {score_p1} vs. {score_p2}")

    with score_lock:
        # Determine if the scores have changed
        if score_p1 != prev_score_p1 or score_p2 != prev_score_p2:
            subprocess.run(f'say "The score is {score_p1} to {score_p2}"', shell=True)

        prev_score_p1 = score_p1
        prev_score_p2 = score_p2


def on_receive_level(address, *args):
    global difficulty_selection, level_confirmed, difficulty_announced, mode, current_level
    diff = ["easy", "hard", "insane"]
    difficulty_levels = {
        "easy": 1,
        "hard": 2,
        "insane": 3
    }

    if len(args) > 0:
        # Received level from host
        level = args[0]
        print(f"> Level now: {level}")
        difficulty_selection = False
        level_confirmed = True
        difficulty_announced = True
        # Announce to the player
        level_name = next((k for k, v in difficulty_levels.items() if v == level), "Unknown")
        print(f"Difficulty is {level_name}")
        current_level = level_name
    else:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            print("[speech recognition] Please say a difficulty level (easy, hard, insane):")
            subprocess.run(['say', 'Please say a difficulty level: easy, hard, or insane'])
            audio = r.listen(source)
        try:
            recog_text = r.recognize_google(audio).lower().strip()
            print(f"Recognized text: '{recog_text}'")
            if recog_text in difficulty_levels:
                level = difficulty_levels[recog_text]
                print(f"Setting difficulty to {recog_text.capitalize()} (Level {level})")
                subprocess.run(['say', f'Setting difficulty to {recog_text}'])
                client.send_message('/setlevel', level)
                difficulty_selection = False  # Stop prompting for difficulty
                print("Waiting for host to confirm the difficulty level...")
            else:
                print(f"Unrecognized difficulty level: '{recog_text}'")
                subprocess.run(['say', 'Please say easy, hard, or insane'])
        except sr.UnknownValueError:
            print("[speech recognition] Could not understand audio")
            subprocess.run(['say', 'Please say easy, hard, or insane'])
            recog_text = r.recognize_google(audio).lower().strip()
            print(f"Recognized text: '{recog_text}'")
        except sr.RequestError as e:
            print(f"[speech recognition] Could not request results; {e}")
            subprocess.run(['say', 'Speech recognition error'])
            recog_text = r.recognize_google(audio).lower().strip()
            print(f"Recognized text: '{recog_text}'")


def on_receive_powerup(address, *args):
    global player_frozen, big_paddle_available, big_paddle_active
    if not args:
        print("> Power-up message received without arguments.")
        return
    powerup_type = args[0]
    print(f"> Power-up now: {powerup_type}")

    if powerup_type == 0:
        print("> No active power-up or power-up expired.")
        return

    if powerup_type in [1, 2]:
        player_to_freeze = 'p1' if powerup_type == 1 else 'p2'
        if mode == player_to_freeze:
            if not player_frozen:
                print("You are frozen!")
                subprocess.run(['say', 'You are frozen for the next 10 seconds'])
                playsound('self_freeze.mp3', block=False)
                player_frozen = True
                threading.Timer(10.0, unfreeze_player).start()
        else:
            print("Opponent is frozen.")
            subprocess.run(['say', 'Your opponent is frozen'])
            threading.Timer(10.0, opponent_unfrozen_message).start()
    elif powerup_type in [3, 4]:
        player_with_powerup = 'p1' if powerup_type == 3 else 'p2'
        if mode == player_with_powerup:
            big_paddle_available = True
            print("You have received a Big Paddle power-up.")
            playsound('big_paddle_self.wav', block=False)
            subprocess.run(['say', 'You have received a Big Paddle power-up. You can activate it by saying big.'])
            threading.Timer(10.0, expire_big_paddle).start()
        else:
            print("Opponent has received a Big Paddle power-up.")
            playsound('big_paddle_opp.wav', block=False)
            subprocess.run(['say', 'Your opponent has a Big Paddle power-up available for the next 10 seconds.'])
            threading.Timer(10.0, opponent_big_paddle_expired_message).start()


def unfreeze_player():
    global player_frozen
    player_frozen = False
    subprocess.run(['say', 'You can move again'])

def opponent_unfrozen_message():
    subprocess.run(['say', 'Your opponent can move again'])

def expire_big_paddle():
    global big_paddle_available
    big_paddle_available = False
    subprocess.run(['say', 'Your Big Paddle power-up has expired.'])

def opponent_big_paddle_expired_message():
    subprocess.run(['say', 'Your opponent\'s Big Paddle power-up has expired.'])


def on_receive_p1_bigpaddle(address, *args):
    global big_paddle_available, big_paddle_active
    arg = args[0] if args else 0
    print(f"> /p1bigpaddle received with argument: {arg}")

    if arg == 0:
        big_paddle_active = True
        print("Big Paddle activated for Player 1.")
        if mode == 'p1':
            playsound('big_paddle_self.wav', block=False)
            subprocess.run(['say', 'Big Paddle activated.'])
            # Optionally, start a timer to deactivate after a duration
            threading.Timer(8.0, deactivate_big_paddle).start()
    elif arg == 1:
        big_paddle_active = False
        print("Big Paddle deactivated for Player 1.")
        if mode == 'p1':
            subprocess.run(['say', 'Big Paddle deactivated.'])
    else:
        print(f"Unknown argument for /p1bigpaddle: {arg}")

def on_receive_p2_bigpaddle(address, *args):
    global big_paddle_available, big_paddle_active
    arg = args[0] if args else 0
    print(f"> /p2bigpaddle received with argument: {arg}")

    if arg == 0:
        big_paddle_active = True
        print("Big Paddle activated for Player 2.")
        if mode == 'p2':
            playsound('big_paddle_self.wav', block=False)
            subprocess.run(['say', 'Big Paddle activated.'])
            # Optionally, start a timer to deactivate after a duration
            threading.Timer(8.0, deactivate_big_paddle).start()
    elif arg == 1:
        big_paddle_active = False
        print("Big Paddle deactivated for Player 2.")
        if mode == 'p2':
            subprocess.run(['say', 'Big Paddle deactivated.'])
    else:
        print(f"Unknown argument for /p2bigpaddle: {arg}")

def deactivate_big_paddle():
    global big_paddle_active
    big_paddle_active = False
    subprocess.run(['say', 'Big Paddle has expired.'])
    print("Big Paddle has been deactivated automatically after duration.")


def on_receive_hi(address, *args):
    global opponent_said_hi, player_said_hi, game_running
    print("> Opponent says hi!")
    subprocess.run('say "Your opponent says hi!"', shell=True)
    opponent_said_hi = True
    if player_said_hi and not game_running:
        client.send_message('/setgame', 1)
        print("Both players have said hi. Starting the game.")
        subprocess.run(['say', 'Both players have said hi. Starting the game.'])


dispatcher_player = dispatcher.Dispatcher()
dispatcher_player.map("/hi", on_receive_hi)
dispatcher_player.map("/game", on_receive_game)
dispatcher_player.map("/ball", on_receive_ball)
dispatcher_player.map("/paddle", on_receive_paddle)
dispatcher_player.map("/ballout", on_receive_ballout)
dispatcher_player.map("/ballbounce", on_receive_ballbounce)
dispatcher_player.map("/hitpaddle", on_receive_hitpaddle)
dispatcher_player.map("/scores", on_receive_scores)
dispatcher_player.map("/level", on_receive_level)
dispatcher_player.map("/powerup", on_receive_powerup)
dispatcher_player.map("/p1bigpaddle", on_receive_p1_bigpaddle)
dispatcher_player.map("/p2bigpaddle", on_receive_p2_bigpaddle)
# -------------------------------------#
# CONTROL

# TODO add your audio control so you can play the game eyes free and hands free! add function like "client.send_message()" to control the host game
# We provided two examples to use audio input, but you don't have to use these. You are welcome to use any other library/program, as long as it respects the OSC protocol from our host (which you cannot change)

# example 1: speech recognition functions using google api
# -------------------------------------#
def provide_instructions():
    instructions = f"""
    Welcome to the Hands-Free Pong Game!

    Paddle Control
      Say "up" to move your paddle up.
      Say "down" to move your paddle down.

    Game Mechanics
      Match the height of the ball by listening to the sound of the ball.
      As the ball moves further away the volume gets lower, the higher the ball
      the higher the frequency, the lower the ball, the lower the frequency.

    Scoring
      Each time the ball goes past your paddle, your opponent scores a point.
      The current score will be announced after each point.

    Power-Ups
      There are 2 power-ups each player can receive:
        Frozen: When you are frozen, you cannot move your paddle for the next 10 seconds.
        Big Paddle: When you receive the Big Paddle power-up, say "big" to activate it, which makes your paddle larger.

    Game Control
      Say "pause" to pause the game.
      If you have paused the game, say "resume" to resume it.
      To change the game's difficulty during a pause, say "easy", "hard", or "insane".
      To check the difficulty during pause say "difficulty"

    Starting the Game
      Say "hi" to begin the game or "help" to receive these instructions again.

    Enjoy the game!
    """
    print("[Instructions]")
    print(instructions)
    subprocess.run(['say', instructions])


def listen_to_speech():
    global quit, difficulty_selection, player_said_hi, opponent_said_hi, game_running
    global level_confirmed, mode, big_paddle_available, big_paddle_active
    global player_paddle_position, paused_by_player, game_paused, current_level
    difficulty_levels = {"easy": 1, "hard": 2, "insane": 3}

    player_paddle_position = 225
    r = sr.Recognizer()

    while not quit:
        if difficulty_selection:
            on_receive_level(None)
            time.sleep(0.1)
            continue
        if not level_confirmed:
            time.sleep(0.1)
            continue

        # Handle pre-game commands
        if not game_running and not player_said_hi:
            with sr.Microphone() as source:
                print("[speech recognition] Say 'hi' to begin or 'help' for instructions:")
                subprocess.run(['say', 'Say hi to begin or help for instructions'])
                audio = r.listen(source)
            try:
                recog_results = r.recognize_google(audio)
                print(f"[speech recognition] Google Speech Recognition thinks you said \"{recog_results}\"")
                command = recog_results.lower()
                if command == "hi":
                    player_said_hi = True
                    client.send_message('/hi', 0)
                    print("You said hi!")
                    subprocess.run(['say', 'Hi!'])
                    if opponent_said_hi and not game_running:
                        client.send_message('/setgame', 1)
                        print("Both players said hi. Starting the game.")
                        subprocess.run(['say', 'Both players have said hi. Starting the game.'])
                elif command == "help":
                    provide_instructions()
                else:
                    print(f"Command '{command}' not recognized.")
                    subprocess.run(['say', 'Command not recognized. Please say hi to begin or help for instructions.'])
            except sr.UnknownValueError:
                print("[speech recognition] Could not understand audio")
                subprocess.run(['say', 'Could not understand. Please say hi to begin or help for instructions.'])
            except sr.RequestError as e:
                print(f"[speech recognition] Could not request results; {e}")
                subprocess.run(['say', 'Speech recognition error.'])
            except Exception as e:
                print(f"[speech recognition] Unexpected error: {e}")
                subprocess.run(['say', 'An unexpected error occurred. Please try again.'])
            continue
        elif not game_running and player_said_hi:
            print("[info] Waiting for the opponent to say hi...")
            subprocess.run(['say', 'Waiting for your opponent to join.'])
            time.sleep(1)
            continue
        else:
            with sr.Microphone() as source:
                # print("[speech recognition] Say 'up', 'down', 'pause', 'resume', or 'change difficulty':")
                # subprocess.run(['say', 'Say up to move your paddle up, down to move it down, pause to pause the game, resume to resume the game, or change difficulty to adjust the game difficulty.'])
                audio = r.listen(source)
            try:
                recog_results = r.recognize_google(audio)
                print(f"[speech recognition] Google Speech Recognition thinks you said \"{recog_results}\"")
                command = recog_results.lower()

                if game_paused:
                    if paused_by_player == mode:
                        if command == "resume":
                            client.send_message('/setgame', 1)
                            game_paused = False
                            paused_by_player = None
                            print("You resumed the game.")
                            subprocess.run(['say', 'Game has been resumed'])
                        elif command in difficulty_levels:
                            new_difficulty = command
                            level = difficulty_levels[new_difficulty]
                            client.send_message('/setlevel', level)
                            print(f"You changed the difficulty to {new_difficulty}.")
                            subprocess.run(['say', f'Difficulty has been changed to {new_difficulty}'])
                        elif command == "difficulty":
                            subprocess.run(['say', f'The difficulty is {current_level}'])
                        else:
                            print("Game is paused. Please say 'resume' or 'change difficulty followed by the difficulty level'.")
                            subprocess.run(['say', 'Game is paused. Please say resume or change difficulty.'])
                    else:
                        # Other player cannot move paddles, just announce the game is paused
                        if command in ["up", "down"]:
                            print("Game is paused. You cannot move the paddle.")
                            subprocess.run(['say', 'Game is paused. You cannot move the paddle.'])
                        elif command == "resume":
                            print("You cannot resume the game. It was paused by the other player.")
                            subprocess.run(['say', 'You cannot resume the game. It was paused by the other player.'])
                        elif command.startswith("change difficulty"):
                            print("You cannot change the difficulty. You did not pause the game.")
                            subprocess.run(['say', 'You cannot change the difficulty. You did not pause the game.'])
                        else:
                            print("Game is paused. Please wait until the pausing player resumes.")
                            subprocess.run(['say', 'Game is paused. Please wait until the pausing player resumes.'])
                else:
                    if command == "up":
                        with paddle_position_lock:
                            new_paddle_position = player_paddle_position - 50
                            new_paddle_position = max(new_paddle_position, 0)
                            player_paddle_position = new_paddle_position
                        client.send_message('/setpaddle', player_paddle_position)
                        print(f"Paddle moved up to position {player_paddle_position}.")
                        subprocess.run(['say', 'Paddle moving up.'])
                    elif command == "down":
                        with paddle_position_lock:
                            new_paddle_position = player_paddle_position + 50
                            new_paddle_position = min(new_paddle_position, 450)
                            player_paddle_position = new_paddle_position
                        client.send_message('/setpaddle', player_paddle_position)
                        print(f"Paddle moved down to position {player_paddle_position}.")
                        subprocess.run(['say', 'Paddle moving down.'])
                    elif command == "pause":
                        client.send_message('/setgame', 0)
                        game_paused = True
                        paused_by_player = mode
                        print("You have paused the game.")
                        subprocess.run(['say', 'Game has been paused'])
                    elif command == "big":
                        client.send_message('/setbigpaddle', 0)
                        subprocess.run(['say', 'Big Paddle Activated'])
                    elif command == "resume":
                        print("You cannot resume the game because you did not pause it.")
                        subprocess.run(['say', 'You cannot resume the game because you did not pause it.'])
                    elif command == "help":
                        provide_instructions()
                    else:
                        print(f"Command '{command}' not recognized.")
                        subprocess.run(['say', 'Command not recognized. Please say up, down, pause, resume, or change difficulty.'])
            except sr.UnknownValueError:
                print("[speech recognition] Could not understand audio")
                subprocess.run(['say', 'Could not understand. Please say a valid command.'])
            except sr.RequestError as e:
                print(f"[speech recognition] Could not request results; {e}")
                subprocess.run(['say', 'Speech recognition error.'])
            except Exception as e:
                print(f"[speech recognition] Unexpected error: {e}")
                subprocess.run(['say', 'An unexpected error occurred. Please try again.'])


# -------------------------------------#

# example 2: pitch & volume detection
# -------------------------------------#
# PyAudio object.
p = pyaudio.PyAudio()
# Open output stream
stream_out = p.open(format=pyaudio.paFloat32,
                    channels=1,
                    rate=fs,
                    output=True,
                    stream_callback=audio_callback)

# Open input stream
stream_in = p.open(format=pyaudio.paFloat32,
                   channels=1,
                   rate=44100,
                   input=True,
                   frames_per_buffer=1024)


# Aubio's pitch detection.
pDetection = aubio.pitch("default", 2048,
    2048//2, 44100)
# Set unit.
pDetection.set_unit("Hz")
pDetection.set_silence(-40)

def sense_microphone():
    global quit, debug, current_freq, paddle_position, ball_y_position
    acceptable_error = 50
    paddle_position = 225

    while not quit:
        data = stream_in.read(1024, exception_on_overflow=False)
        samples = num.frombuffer(data, dtype=aubio.float_type)

        detected_pitch = pDetection(samples)[0]
        volume = num.sum(samples**2) / len(samples)

        if debug:
            print("Detected pitch: {:.2f} Hz, Volume: {:.6f}".format(detected_pitch, volume))

        if detected_pitch > 0:
            with freq_lock:
                freq = current_freq

            pitch_difference = abs(detected_pitch - freq)

            if pitch_difference < acceptable_error:
                with ball_position_lock:
                    y = ball_y_position

                paddle_position = y
            else:
                pass

            paddle_position = max(min(paddle_position, 450), 0)
            client.send_message('/p', paddle_position)


# -------------------------------------#


# speech recognition thread
# -------------------------------------#
# start a thread to listen to speech
speech_thread = threading.Thread(target=listen_to_speech, args=())
speech_thread.daemon = True
speech_thread.start()

# pitch & volume detection
# -------------------------------------#
# start a thread to detect pitch and volume
"""microphone_thread = threading.Thread(target=sense_microphone, args=())
microphone_thread.daemon = True
microphone_thread.start()"""
# -------------------------------------#

# Play some fun sounds?
# -------------------------------------#
def hit():
    playsound('hit.wav', False)
# -------------------------------------#

# OSC connection
# -------------------------------------#
# used to send messages to host
if mode == 'p1':
    host_port = host_port_1
if mode == 'p2':
    host_port = host_port_2

if (mode == 'p1') or (mode == 'p2'):
    client = udp_client.SimpleUDPClient(host_ip, host_port)
    print("> connected to server at "+host_ip+":"+str(host_port))

# OSC thread
# -------------------------------------#
# Player OSC port
if mode == 'p1':
    player_port = player_1_port
if mode == 'p2':
    player_port = player_2_port

player_server = osc_server.ThreadingOSCUDPServer((player_ip, player_port), dispatcher_player)
player_server_thread = threading.Thread(target=player_server.serve_forever)
player_server_thread.daemon = True
player_server_thread.start()
# -------------------------------------#
client.send_message("/connect", player_ip)


# MAIN LOOP
# manual input for debugging
# -------------------------------------#
while True:
    m = input("> send: ")
    cmd = m.split(' ')
    if len(cmd) == 2:
        client.send_message("/"+cmd[0], int(cmd[1]))
    if len(cmd) == 1:
        client.send_message("/"+cmd[0], 0)

    # this is how client send messages to server
    # send paddle position 200 (it should be between 0 - 450):
    # client.send_message('/p', 200)
    # set level to 3:
    # client.send_message('/l', 3)
    # start the game:
    # client.send_message('/g', 1)
    # pause the game:
    # client.send_message('/g', 0)
    # big paddle if received power up:
    # client.send_message('/b', 0)

# Implement player controls
# Implement big paddle