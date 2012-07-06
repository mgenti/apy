"""Emulates the apy EventScheduler API for use with tornado.ioloop"""


import time

import wx


class WxLoopEventElement(object):
    def __init__(self, func, delay=0.0, *args, **kwargs):
        self.func = func
        self.orig_func = func
        self.args = args
        self.kwargs = kwargs
        self.delay = delay
        self._running = True
        self._ioloop_timeout = None
        self._wx_event = None

    def run(self):
        value = self.func(*self.args, **self.kwargs)
        self._running = False
        if isinstance(value, bool):
            # bool inherits from int
            if value:
                self._wx_event = wx.CallLater(self.delay*1000, self.run)
                self._running = True
        elif isinstance(value, float) or isinstance(value, int):
            self.delay = value
            self._wx_event = wx.CallLater(self.delay*1000, self.run)
            self._running = True

    def start(self):
        self._wx_event = wx.CallLater(self.delay*1000, self.run)
        self._running = True
        self.func = self.orig_func

    def Stop(self, *args, **kwargs):
        self._wx_event.Stop()
        self._running = False

    stop = Stop


def schedule(delay, callable, *args, **kwargs):
    """Emulates the EventScheduler.schedule API"""
    event = IOLoopEventElement(callable, delay, *args, **kwargs)
    wx.CallLater(time.time() + delay, event.run)
    return event


class WxLoopScheduler(object):
    def schedule(self, delay, callable, *args, **kwargs):
        """Emulates the EventScheduler.schedule API"""
        event = WxLoopEventElement(callable, delay, *args, **kwargs)
        if delay == 0.0:
            event._wx_event = wx.CallAfter(event.run)
        else:
            event._wx_event = wx.CallLater(delay*1000, event.run)
        return event

    def scheduleEvent(self, func, params=[], delay=0.0):
        """Emulates the EventScheduler.scheduleEvent API"""
        event = WxLoopEventElement(func, delay, *params)
        if delay == 0.0:
            event._wx_event = wx.CallAfter(event.run)
        else:
            event._wx_event = wx.CallLater(delay*1000, event.run)
        return event

    @classmethod
    def instance(cls):
        """Returns a global WxLoopScheduler instance."""
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance
