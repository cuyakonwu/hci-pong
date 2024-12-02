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
# TODO: add audio output so you know what's going on in the game

def on_receive_game(address, *args):
    # 0: menu, 1: game starts
    game_state = args[0]
    global game_running
    if game_state == 1:
        print("> Game stated")
        game_running = True
        subprocess.run('say "The game has started"', shell=True)
    elif game_state == 0:
        print("> Returned to menu")
        game_running = False
        subprocess.run('say "The game is back in the menu"', shell=True)
    else:
        print(f"> Unkown game state: {game_state}")
        subprocess.run('say "Received unknown game state"', shell=True)


# Ball Sound Variables
current_freq = 440.0  # Startig frequency
volume = 0.5          # Volume (0.0 - 1.0)
fs = 44100            # Hz
freq_lock = threading.Lock()
volume_lock = threading.Lock()

def audio_callback(in_data, frame_count, time_info, status):
    global current_freq, current_volume
    with freq_lock:
        freq = current_freq
    with volume_lock:
        vol = current_volume
    t = (np.arange(frame_count) + audio_callback.frame_index) / fs
    data = (np.sin(2 * np.pi * freq * t)).astype(np.float32)
    audio_callback.frame_index += frame_count
    return (vol * data.tobytes(), pyaudio.paContinue)


audio_callback.frame_index = 0
p_out = pyaudio.PyAudio()
stream_out = p_out.open(format=pyaudio.paFloat32,
                        channels=1,
                        rate=fs,
                        output=True,
                        stream_callback=audio_callback)

stream_out.start_stream()

def on_receive_ball(address, *args):
    # print("> ball position: (" + str(args[0]) + ", " + str(args[1]) + ")")
    global current_freq, current_volume
    y = args[1]
    x = args[0]

    min_freq = 200.0
    max_freq = 1000.0
    # Adjust below
    min_y = 0.0
    max_y = 450.0

    min_volume = 0.1
    max_volume = 1.0
    # Adjust below
    min_x = 0.0
    max_x = 800.0

    new_freq = min_freq + (max_y - y) * (max_freq - min_freq) / (max_y - min_y)

    if player_side == 'left':
        # Player 1: Volume decreases as x increases
        new_volume = min_volume + (max_x - x) * (max_volume - min_volume) / (max_x - min_x)
    else:
        # Player 2: Volume increases as x increases
        new_volume = min_volume + (x - min_x) * (max_volume - min_volume) / (max_x - min_x)

    # Clamp volume between min_volume and max_volume
    new_volume = max(min(new_volume, max_volume), min_volume)

    # Update the global variables with thread safety
    with freq_lock:
        current_freq = new_freq
    with volume_lock:
        current_volume = new_volume


def on_receive_paddle(address, *args):
    # print("> paddle position: (" + str(args[0]) + ", " + str(args[1]) + ")")
    paddle_x = args[0]
    paddle_y = args[1]


def on_receive_hitpaddle(address, *args):
    # example sound
    hit()
    print("> ball hit at paddle " + str(args[0]) )

def on_receive_ballout(address, *args):
    print("> ball went out on left/right side: " + str(args[0]) )

def on_receive_ballbounce(address, *args):
    # example sound
    hit()
    print("> ball bounced on up/down side: " + str(args[0]) )

prev_score_p1 = 0
prev_score_p2 = 0
score_lock = threading.Lock()

def on_receive_scores(address, *args):
    global prev_score_p1, prev_score_p2
    score_p1 = args[0]
    score_p2 = args[1]
    print(f"> scores now: {score_p1} vs. {score_p2}")

    with score_lock:
        if score_p1 > prev_score_p1:
            # Player 1 scored
            message = "Player 1 scored"
            subprocess.run(f'say "{message}"', shell=True)
        elif score_p2 > prev_score_p2:
            # Player 2 scored
            message = "Player 2 scored"
            subprocess.run(f'say "{message}"', shell=True)

        prev_score_p1 = score_p1
        prev_score_p2 = score_p2

    message = f"The score is {score_p1} to {score_p2}"
    subprocess.run(f'say "{message}"', shell=True)


def on_receive_level(address, *args):
    level = args[0]
    print(f"> level now: {level}")
    message = f"The difficulty level is {level}"
    subprocess.run(f'say "{message}"', shell=True)


def on_receive_powerup(address, *args):
    print("> powerup now: " + str(args[0]))
    # 1 - freeze p1
    # 2 - freeze p2
    # 3 - adds a big paddle to p1, not use
    # 4 - adds a big paddle to p2, not use

def on_receive_p1_bigpaddle(address, *args):
    print("> p1 has a big paddle now")
    # when p1 activates their big paddle

def on_receive_p2_bigpaddle(address, *args):
    print("> p2 has a big paddle now")
    # when p2 activates their big paddle

def on_receive_hi(address, *args):
    print("> opponent says hi!")

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
def listen_to_speech():
    global quit
    while not quit:
        # obtain audio from the microphone
        r = sr.Recognizer()
        with sr.Microphone() as source:
            print("[speech recognition] Say something!")
            audio = r.listen(source)
        # recognize speech using Google Speech Recognition
        try:
            # for testing purposes, we're just using the default API key
            # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
            # instead of `r.recognize_google(audio)`
            recog_results = r.recognize_google(audio)
            print("[speech recognition] Google Speech Recognition thinks you said \"" + recog_results + "\"")
            # if recognizing quit and exit then exit the program
            if recog_results == "play" or recog_results == "start":
                client.send_message('/g', 1)
        except sr.UnknownValueError:
            print("[speech recognition] Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print("[speech recognition] Could not request results from Google Speech Recognition service; {0}".format(e))
# -------------------------------------#

# example 2: pitch & volume detection
# -------------------------------------#
# PyAudio object.
p = pyaudio.PyAudio()
# Open stream.
stream = p.open(format=pyaudio.paFloat32,
    channels=1, rate=44100, input=True,
    frames_per_buffer=1024)
# Aubio's pitch detection.
pDetection = aubio.pitch("default", 2048,
    2048//2, 44100)
# Set unit.
pDetection.set_unit("Hz")
pDetection.set_silence(-40)

def sense_microphone():
    global quit
    global debug
    while not quit:
        data = stream.read(1024,exception_on_overflow=False)
        samples = num.fromstring(data,
            dtype=aubio.float_type)

        # Compute the pitch of the microphone input
        pitch = pDetection(samples)[0]
        # Compute the energy (volume) of the mic input
        volume = num.sum(samples**2)/len(samples)
        # Format the volume output so that at most
        # it has six decimal numbers.
        volume = "{:.6f}".format(volume)

        # uncomment these lines if you want pitch or volume
        if debug:
            print("pitch "+str(pitch)+" volume "+str(volume))
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
microphone_thread = threading.Thread(target=sense_microphone, args=())
microphone_thread.daemon = True
microphone_thread.start()
# -------------------------------------#

# Play some fun sounds?
# -------------------------------------#
def hit():
    playsound('hit.wav', False)

hit()
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

"""
TO DO

Add a method to track the location of the ball
Add a method to control the paddle
Send hi to start the game
Select difficulty

"""