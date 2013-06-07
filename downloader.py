#!/usr/bin/python
# -*- coding: utf8 -*-

import threading
from urlparse import urlparse
import logging
import time
import signal
import httplib
from threading import Thread
from Queue import Queue


class Worker(Thread):
    """Thread executing tasks from a given tasks queue"""
    def __init__(self, tasks):
        Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.start()

    def run(self):
        while True:
            func, args, kargs = self.tasks.get()
            try:
                func(*args, **kargs)
            except Exception:
                logging.exception("Got exception")
            self.tasks.task_done()


class ThreadPool:
    """Pool of threads consuming tasks from a queue"""
    def __init__(self, num_threads):
        self.tasks = Queue(num_threads)
        for _ in range(num_threads):
            Worker(self.tasks)

    def add_task(self, func, *args, **kargs):
        """Add a task to the queue"""
        self.tasks.put((func, args, kargs))

    def wait_completion(self):
        """Wait for completion of all the tasks in the queue"""
        self.tasks.join()


class Downloader:

    def __init__(self, url, process_num=5, chunk_size=1000000, step_size=10):
        self.url = url
        logging.info("Construct downloader for url %s", self.url)
        self.process_num = process_num
        self.chunk_size = chunk_size
        self.step_size = step_size
        self.result_queue = Queue()
        self.step_done = False
        self.current_step_size = 0
        self.stopped = False
        self.connectionPool = {}
        self.host = None
        self.path = None
        self.total_part = 0
        retries = 20
        for i in range(retries):
            self.getSizeInfo()
            if self.total_part:
                break
        else:
            raise Exception("Can't get size for %s" % self.url)
        self.result_thread = Thread(target=self.handleResult)
        self.download_thread = Thread(target=self.download)
        self.start_time = 0

    def getConnection(self, threadName):
        if threadName in self.connectionPool:
            return self.connectionPool[threadName]
        else:
            p = urlparse(self.url)
            self.host = p.netloc
            self.path = self.url.partition(self.host)[2]
            return httplib.HTTPConnection(self.host)

    def download_part(self, part_num):
        # Content-Range: bytes 0-499/1234
        # Content-Range: bytes 500-999/1234
        start = part_num * self.chunk_size
        threadName = threading.currentThread().getName()
        conn = self.getConnection(threadName)
        end = (part_num + 1) * self.chunk_size - 1
        if end > self.total_length:
            end = self.total_length
        logging.debug("Begin download part %s", part_num)
        headers = {'Range': 'bytes=%s-%s' % (start, end), 'User-Agent': 'Mozilla/5.0'}
        retries = 20
        for i in range(retries):
            try:
                conn.request("GET", self.path, None, headers)
                resp = conn.getresponse()
                if resp.status == 200:
                    self.result_queue.put({part_num: resp.read()})
                    break
            except Exception:
                logging.exception("Got exception")
                logging.info("Retry %s", i)
        else:
            raise Exception("Failed to download part %s" % part_num)
        logging.debug("Completed download part %s", part_num)

    def handleResult(self):
        result = {}
        while not self.stopped:
            r = self.result_queue.get()
            result.update(r)
            if len(result) == self.current_step_size:
                logging.info("Finished step with size %s", self.current_step_size)
                filename = "/tmp/download_part"
                end_time = time.time()
                filesize = 0
                for v in result.itervalues():
                    filesize += len(v)
                logging.debug("The avg speed is %s", self.computeSpeed(filesize, (end_time - self.start_time)))
                logging.debug("Begin write file")
                if not self.stopped:
                    with open(filename, 'a+b') as f:
                        for v in sorted(result):
                            f.write(result[v])
                    logging.debug("End write file")
                result.clear()
                self.step_done = True

    def computeSpeed(self, filesize, duration):
        speed = filesize / duration
        if speed > 1024 * 1024:
            return "%s MB/s" % (speed / (1024 * 1024))
        elif speed > 1024:
            return "%s KB/s" % (speed / 1024)
        else:
            return "%s B/s" % speed

    def getSizeInfo(self):
        threadName = threading.currentThread().getName()
        conn = self.getConnection(threadName)
        headers = {'User-Agent': 'Mozilla/5.0'}
        conn.request('GET', self.path, None, headers)
        logging.info("path = %s", self.path)
        resp = conn.getresponse()
        logging.info("status = %s", resp.status)
        if 300 < resp.status < 400:
            self.url = resp.getheader("location")
            logging.info("Redirect to %s" % self.url)
            self.connectionPool.clear()
            self.getSizeInfo()
        elif resp.status == 200:
            self.total_length = int(resp.getheader("Content-Length"))
            self.total_part = int(self.total_length / self.chunk_size)
            if self.total_length % self.chunk_size > 0:
                self.total_part += 1
            self.file_num = int(self.total_part / self.step_size)
            if self.total_part % self.step_size > 0:
                self.file_num += 1
            logging.info("total_length = %s", self.total_length)
        else:
            raise Exception("Can't get size for url %s" % self.url)

    def start(self):
        self.result_thread.start()
        self.download_thread.start()

    def download(self):
        self.pool = ThreadPool(self.process_num)
        for start in range(0, self.total_part, self.step_size):
            if self.stopped:
                break
            self.step_done = False
            self.start_time = time.time()
            end = start + self.step_size
            if end > self.total_part:
                end = self.total_part
            self.current_step_size = end - start
            for i in range(start, end):
                self.pool.add_task(self.download_part, i)
            while True:
                if self.step_done or self.stopped:
                    break
                else:
                    time.sleep(0.2)
        # logging.debug("Finished part %s-%s", p, p + self.step_size)
        # logging.info("The avg speed is %s" self.computeSpeed(self.chunk_size * self.step_size, end_time - start_time))
        self.pool.wait_completion()
        self.stopped = True
        logging.info("Finished download")

    def stop(self):
        self.stopped = True
        # close all the connections
        for conn in self.connectionPool.itervalues():
            try:
                conn.close()
            except Exception:
                logging.exception("Ignore exception")

    def getCatCmd(self):
        logging.info("Total file_num = %s", self.file_num)
        return "cat %s" % " ".join(['/tmp/download_part' for _ in range(self.file_num)]) 


class MultiDownloader:

    def __init__(self, urls, process_num=5, chunk_size=1000000, step_size=10):
        self.urls = urls
        self.process_num = process_num
        self.chunk_size = chunk_size
        self.step_size = step_size
        self.catCmds = []
        self.downloaders = []
        self.currentDownloader = None
        self.stopped = False
        self.download_thread = Thread(target=self.download)
        for url in self.urls:
            downloader = Downloader(url, process_num, chunk_size, step_size)
            self.downloaders.append(downloader)
            self.catCmds.append(downloader.getCatCmd())

    def start(self):
        self.download_thread.start()

    def download(self):
        for idx, downloader in enumerate(self.downloaders):
            if self.stopped:
                break
            logging.info("Start downloading %s - %s" % (idx + 1, downloader.url))
            self.currentDownloader = downloader
            self.currentDownloader.start()
            while not self.currentDownloader.stopped:
                time.sleep(0.1)

    def stop(self):
        self.stopped = True
        if self.currentDownloader:
            logging.info("Stopping currentDownloader")
            self.currentDownloader.stop()
        self.releaseFiles(['/tmp/download_part'])

    def releaseFiles(self, files):
        def handler(signum, frame):
            raise IOError("Time out")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(1)
        for f in files:
            try:
                with open(f) as f1:
                    f1.read()
            except:
                pass
            finally:
                logging.info("File %s released" % f)
        signal.alarm(0)

    def getCatCmds(self):
        logging.info("catCmds: %s" % self.catCmds)
        return self.catCmds

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(module)s:%(lineno)d %(levelname)s: %(message)s', level=logging.DEBUG)
    downloader = MultiDownloader(['http://f.youku.com/player/getFlvPath/sid/00_00/st/flv/fileid/0300011400511B74719AE2032DBBC7299B4E30-E304-34BD-DD12-0E375AE4E342?K=3f40f9097a3ef7f3261d0bc4'])
    downloader.start()
    time.sleep(25)
    downloader.stop()
    downloader.getCatCmds()
