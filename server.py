#!/usr/bin/python
# -*- coding: utf8 -*-
from bottle import route, run, template, request, static_file, post, get, redirect
from database import *
from webparser import Video, QQWebParser, QQWebParserMP4, YoukuWebParser, YoutubeWebParser
from string import Template
import subprocess
import platform
import sys
import time
from threading import Thread
from Queue import Queue

websites = {
    "qq": {
        "title": "腾讯视频(flv)",
        "url": "http://v.qq.com",
        "parser": QQWebParser,
        "icon": "http://v.qq.com/favicon.ico",
        "info": "flv格式，不分段，但不能选择清晰度。"
    },
    "qqmp4": {
        "title": "腾讯视频(mp4)",
        "url": "http://v.qq.com",
        "parser": QQWebParserMP4,
        "icon": "http://v.qq.com/favicon.ico",
        "info": "mp4格式，分段，可选择清晰度。"
    },
    "youku": {
        "title": "优酷视频",
        "url": "http://www.youku.com",
        "parser": YoukuWebParser,
        "icon": "http://www.youku.com/favicon.ico",
        "info": "mp4格式，分段，可选择清晰度。"
    },
    "youtube": {
        "title": "Youtube",
        "url": "http://www.youtube.com",
        "parser": YoutubeWebParser,
        "icon": "http://www.youtube.com/favicon.ico",
        "info": "mp4格式，分段，可选择清晰度。"
    },
}

current_website = None
currentVideo = None
currentPlatform = platform.system()
currentPlayerApp = None

player = None
playThread = None
playQueue = Queue()

actionToKey = {
    'pause': 'p',
    'stop': 'q',
    'volup': '+',
    'voldown': '-',
    'f30': '\x1B[D',
    'b30': '\x1B[C',
    'f600': '\x1B[A',
    'b600': '\x1B[B',
    'showinfo': 'z',
    'speedup': '1',
    'speeddown': '2',
    'togglesub': 's',
}

actionDesc = [
    [
        ('pause', 'Pause'),
        ('stop', 'Stop'),
        ('volup', 'Increase Volume'),
        ('voldown', 'Decrease Volume')
    ],
    [
        ('f30', 'Seek +30'),
        ('b30', 'Seek -30'),
        ('f600', 'Seek +600'),
        ('b600', 'Seek -600')
    ],
    [
        ('showinfo', 'z'),
        ('speedup', '1'),
        ('speeddown', '2'),
        ('togglesub', 's'),
    ]
]

actionToKeyMac = {
    'MPlayerX':
    {
        'pause': '49',
        'stop': '12 using command down',
        'volup': '24',
        'voldown': '27',
        'fullscreen': '3',
    },
    'VLC':
    {
        'pause': '49',
        'stop': '12 using command down',
        'volup': '126 using command down',
        'voldown': '125 using command down',
        'fullscreen': '3 using command down',
    }
}

import logging
logging.basicConfig(format='%(asctime)s %(module)s %(levelname)s: %(message)s',
                    filename='app.log', level=logging.DEBUG)


def exceptionLogger(type, value, tb):
    logging.exception("Uncaught exception: %s", value)


sys.excephook = exceptionLogger


def isProcessAlive(process):
    if process:
        if process.poll() is None:
            return True
    return False


def clearQueue():
    global playQueue
    with playQueue.mutex:
        playQueue.queue.clear()


def fillQueue(url=None):
    global playQueue
    if url:
        playQueue.put(url)
    else:
        with open('playlist.m3u', 'r') as f:
            for v in [v.strip() for v in f.readlines() if v.startswith('http')]:
                playQueue.put(v)


def play_list():
    global player, playQueue
    while True:
        v = playQueue.get()
        logging.info("Play %s", v)
        player = subprocess.Popen(["omxplayer", "-p", "-o", "hdmi", v],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while isProcessAlive(player):
            time.sleep(1)


def play_url():
    global player, currentVideo, currentPlayerApp, playQueue
    clearQueue()
    db_writeHistory(currentVideo)
    if player and isProcessAlive(player):
        logging.warn("Terminate the previous player")
        player.terminate()
        player = None
    logging.info("Playing %s", currentVideo.realUrl)
    if currentVideo.realUrl == 'playlist.m3u':
        if currentPlatform == 'Darwin':
            currentPlayerApp = 'VLC'
            player = subprocess.Popen(["/Applications/VLC.app/Contents/MacOS/VLC",
                                      currentVideo.realUrl, '--fullscreen'],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            # Because omxplayer doesn't support list we have to play one by one.
            global playThread
            if not playThread:
                logging.debug("New a thred to play the list.")
                playThread = Thread(target=play_list)
                playThread.start()
            fillQueue()
    else:
        if currentPlatform == 'Darwin':
            currentPlayerApp = 'MPlayerX'
            player = subprocess.Popen(["/Applications/MPlayerX.app/Contents/MacOS/MPlayerX", '-url',
                                      currentVideo.realUrl, "-StartByFullScreen", "YES"],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            fillQueue(currentVideo.realUrl)
    if currentPlatform == 'Darwin':
        # Try to send it to the second screen
        templateStr = """osascript\
 -e "delay 3"\
 -e "tell application \\"$currentPlayerApp\\""\
 -e "set position of window 1 to {1900, 30}"\
 -e "end tell" """
        executeCmdForMac(templateStr)
    return template("index", title=currentVideo.title, duration=currentVideo.durationToStr(),
                    websites=websites, currentVideo=currentVideo, actionDesc=actionDesc)


def sendKeyForMac(keyString):
    templateStr = """osascript\
 -e "tell application \\"$currentPlayerApp\\""\
 -e "activate"\
 -e "tell application \\"System Events\\" to tell process \\"$currentPlayerApp\\" to key code $keycode"\
 -e "end tell" """
    executeCmdForMac(templateStr, params={"keycode": keyString})


def executeCmdForMac(templateStr, params={}):
    s = Template(templateStr)
    p = {"currentPlayerApp": currentPlayerApp}
    if params:
        for k, v in params.iteritems():
            p[k] = v
    cmd = s.substitute(p)
    logging.info("Execuing command: %s", cmd)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out, err = p.communicate()
    logging.debug("out = %s\nerr = %s\nreturnCode = %s", out, err, p.returncode)


@route('/')
def index():
    global title, duration_str
    if not isProcessAlive(player):
        global currentVideo
        currentVideo = None
    if currentVideo:
        return template("index", title=currentVideo.title, duration=currentVideo.durationToStr(),
                        websites=websites, currentVideo=currentVideo, actionDesc=actionDesc)
    else:
        return template('index', websites=websites, actionDesc=actionDesc)


@route('/play')
def history_play():
    global currentVideo
    currentVideo = db_getById(request.query.id)
    redirect('/forward?site=%s&url=%s&dbid=%s' % (currentVideo.site, currentVideo.url, currentVideo.dbid))


@route('/static/<filename:path>')
def static(filename):
    return static_file(filename, root='static')


@post('/control/<action>')
def control(action):
    global player, currentVideo
    feedback = ""
    if player and isProcessAlive(player):
        if (currentPlatform != 'Darwin' and action in actionToKey) or\
                (currentPlatform == 'Darwin' and action in actionToKeyMac[currentPlayerApp]):
            if action == "stop":
                clearQueue()
            if currentPlatform == 'Darwin':
                logging.info("Send key code: %s", actionToKeyMac[currentPlayerApp][action])
                sendKeyForMac(actionToKeyMac[currentPlayerApp][action])
            else:
                logging.info("Send key code: %s", actionToKey[action])
                player.stdin.write(actionToKey[action])
            if action == "stop":
                player = None
                currentVideo = None
            feedback = "OK"
        else:
            feedback = "Not implemented action: " + action
    else:
        feedback = "Sorry but I can't find any player running."
    return feedback


@get('/history')
def history():
    videos = db_getHistory()
    responseString = ""
    for video in videos:
        responseString += """
                        <li>
                            <a href="/play?id=%s" class="ui-link-inherit" data-ajax="false">
                                <h3>%s</h3>
                                <p>总共%s(%s)</p>
                            </a>
                            <a href="#" onclick="deleteHistory('%s');return false" \
                            data-role="button" data-icon="delete"></a>
                        </li>
                        """ % (video.dbid, video.title, video.durationToStr(),
                               websites[video.site]['title'], video.dbid)
    return responseString


@post('/delete/<id>')
def delete(id):
    db_delete(id)


@post('/clear')
def clear():
    db_delete(-1)


@get('/favicon.ico')
def favicon():
    return static_file('favicon.ico', '.')


@route('/forward')
def forward():
    global vid, title, duration, duration_str, current_website
    format = None
    url = request.query.url
    if current_website == 'youtube' and 'search_query' in request.query:
        url = "%s?%s" % ('http://www.youtube.com/results', request.query_string)
        print url
    if 'site' in request.query:
        current_website = request.query.site
    if 'format' in request.query:
        format = int(request.query.format)
        logging.info("Forwarding to %s", url)
    parser = websites[current_website]['parser'](url, format)
    parseResult = parser.parse()
    if isinstance(parseResult, Video):
        global currentVideo
        currentVideo = parseResult
        if 'dbid' in request.query:
            currentVideo.dbid = request.query.dbid
        return play_url()
    else:
        return parseResult

if currentPlatform == 'Darwin':
    run(host='0.0.0.0', port=8000, reloader=True)
else:
    run(host='0.0.0.0', port=80, reloader=True)
