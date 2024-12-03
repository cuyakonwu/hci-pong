# hci-pong
Initializing venv
``` bash
pip install -r requirements-host.txt

pip install -r requirements-player.txt

source pong/bin/activate

pip3 install numpy
pip3 install PyObjC
pip3 install python-osc
pip3 install SpeechRecognition
pip3 install pyglet==1.5.21
pip3 install PyAudio
pip3 install playsound
pip3 install aubio
```
For hosting
``` bash
python pong-audio-host-do-not-edit.py
```
Player connect
``` bash
python pong-audio-player.py p1
```
