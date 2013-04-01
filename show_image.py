#!/usr/bin/python
# -*- coding: utf8 -*-

from threading import Thread
import time
import subprocess
import logging
from Queue import Queue

LOADING = "loading"
FINISHED = "finished"
TIMEOUT = "timout"


class Img:

    def __init__(self, what, delay, filenames):
        self.what = what
        self.delay = delay
        self.filenames = filenames

    def __str__(self):
        return "show %s for %s with delay %s" % (self.filenames, self.what, self.delay)


class ImgService:

    def __init__(self):
        self.stop = False
        self.imgQueue = Queue()
        thread = Thread(target=self._show_thread)
        thread.start()

    def begin(self, what):
        try:
            self._clear()
            self.stop = False
            if what == LOADING:
                filenames = ["static/img/loading/frame%s.png" % (i + 1) for i in range(12)]
                img = Img(what, 0.2, filenames)
            else:
                filenames = ["static/img/%s.jpg" % what]
                img = Img(what, 0, filenames)
            logging.debug("Enqueue: %s", img)
            self.imgQueue.put(img)
        except:
            logging.exception("Exception catched")

    def _show_thread(self):
        while True:
            img = self.imgQueue.get()
            self._clear()
            if img.delay == 0:
                self._show_image(img)
            while (img.delay > 0) and (not self.stop):
                self._show_image(img)

    def _show_image(self, img):
        for filename in img.filenames:
            if self.stop:
                break
            cmd = "/usr/bin/fbv -i %s" % filename
            subprocess.call(cmd, shell=True)
            if img.delay > 0:
                time.sleep(img.delay)

    def _clear(self):
        subprocess.call(["/usr/bin/dd", "if=/dev/zero", "of=/dev/fb0"])

    def end(self):
        self.stop = True
        self._clear()


if __name__ == '__main__':
    service = ImgService()
    service.begin(LOADING)
    time.sleep(5)
    service.end()
    service.begin(FINISHED)
    time.sleep(1)
    service.begin(TIMEOUT)