import re
import subprocess
import os
import signal
import logging

from threading import Thread
from config import get_cfg
additonal_omxplayer_args = get_cfg('additonal_omxplayer_args')
zoom = float(get_cfg('zoom'))


class OMXPlayer(object):

    _STATUS_REXP = re.compile(r"[MV]\s*:\s*(?P<position>[\d]+).*")

    _LAUNCH_CMD = 'nice -n -1 /usr/bin/omxplayer -s "%s" %s < /tmp/cmd \n'
    _PAUSE_CMD = 'p'
    _TOGGLE_SUB_CMD = 's'
    _QUIT_CMD = 'q'
    _VOLUP_CMD = '+'
    _VOLDOWN_CMD = '-'

    _SCRIPT_NAME = '/tmp/play.sh'

    def __init__(self, currentVideo, screenWidth=0, screenHeight=0):
        self.currentVideo = currentVideo
        self.screenWidth = screenWidth
        self.screenHeight = screenHeight
        self._process = None

    def play(self):
        args = self.getArgs(self.screenWidth, self.screenHeight)
        if additonal_omxplayer_args:
            args += " %s" % additonal_omxplayer_args
        cmd = self._LAUNCH_CMD % (self.currentVideo.playUrl, args)
        with open(self._SCRIPT_NAME, 'w') as f:
            if self.currentVideo.download_args:
                f.write("{\n %s \n} &\n" % self.currentVideo.download_args)
            f.write('echo . > /tmp/cmd &\n')
            f.write(cmd)
        subprocess.call(["chmod", "+x", self._SCRIPT_NAME])
        self._process = subprocess.Popen(self._SCRIPT_NAME, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
        self.position = 0
        self._position_thread = Thread(target=self._get_position)
        self._position_thread.start()

    def getArgs(self, screenWidth, screenHeight):
        args = "-o hdmi"
        try:
            if screenWidth and screenHeight:
                width, height = (0, 0)
                try:
                    width, height = self.currentVideo.getResolution()
                except:
                    logging.exception("Exception catched")
                if width and height:
                    logging.debug("screenWidth = %s, screenHeight = %s, width = %s, height = %s" % (screenWidth, screenHeight, width, height))
                    w_rate = screenWidth / width
                    h_rate = screenHeight / height
                    rate = min(w_rate, h_rate)
                    showWidth = rate * width * zoom
                    showHeight = rate * height * zoom
                    widthOff = int((screenWidth - showWidth) / 2)
                    heightOff = int((screenHeight - showHeight) / 2)
                    args += ' --win "%s %s %s %s"' % (0 + widthOff, 0 + heightOff, screenWidth - widthOff, screenHeight - heightOff)
            logging.debug("args = %s", args)
        except:
            logging.exception("Got exception")
        return args

    def isalive(self):
        if self._process and self._process.poll() is None:
            return True
        return False

    def volup(self):
        self._send_cmd(self._VOLUP_CMD)

    def voldown(self):
        self._send_cmd(self._VOLDOWN_CMD)

    def _get_position(self):
        while self.isalive():
            out = self._process.stdout.read(20000)
            if out:
                r = self._STATUS_REXP.search(out)
                if r:
                    self.position = float(r.group('position'))

    def _send_cmd(self, cmd, wait=False):
        if self.isalive():
            logging.debug("Sending %s", cmd)
            if wait:
                subprocess.call("echo -n %s > /tmp/cmd" % cmd, shell=True)
            else:
                subprocess.Popen("echo -n %s > /tmp/cmd" % cmd, shell=True)

    def toggle_pause(self):
        self._send_cmd(self._PAUSE_CMD)

    def toggle_subtitles(self):
        self._send_cmd(self._TOGGLE_SUB_CMD)

    def stop(self):
        self._send_cmd(self._QUIT_CMD, True)
        if self._process:
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
            except:
                logging.exception("Got exception")
        self.currentVideo = None

    def set_speed(self):
        raise NotImplementedError

    def set_audiochannel(self, channel_idx):
        raise NotImplementedError

    def set_subtitles(self, sub_idx):
        raise NotImplementedError

    def set_chapter(self, chapter_idx):
        raise NotImplementedError

    def set_volume(self, volume):
        raise NotImplementedError

    def seek(self, minutes):
        raise NotImplementedError
