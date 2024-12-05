# hci-pong
Initializing venv
``` bash
brew install python@3.11

python3.11 -m venv pong
```

``` bash
source pong/bin/activate

pip install -r requirements-host.txt

pip install -r requirements-player.txt

pip3 install numpy
pip3 install PyObjC
pip3 install python-osc
pip3 install SpeechRecognition
pip3 install pyglet==1.5.21
pip3 install PyAudio
pip3 install playsound
pip install git+https://git.aubio.org/aubio/aubio/
```

For hosting
``` bash
python pong-audio-host-do-not-edit.py
```
Player connect
``` bash
python pong-audio-player.py p1
```
