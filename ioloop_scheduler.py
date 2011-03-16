"""Emulates the apy EventScheduler API for use with tornado.ioloop"""


import time

import tornado.ioloop


class IOLoopEventElement(object):
    def __init__(self, func, delay=0.0, *args, **kwargs):
        self.func = func
        self.orig_func = func
        self.args = args
        self.kwargs = kwargs
        self.delay = delay
        self._running = True
        self._ioloop_timeout = None

    def run(self):
        value = self.func(*self.args, **self.kwargs)
        self._running = False
        if isinstance(value, bool):
            # bool inherits from int
            if value:
                tornado.ioloop.IOLoop.instance().add_timeout(time.time() + self.delay, self.run)
                self._running = True
        elif isinstance(value, float) or isinstance(value, int):
            self.delay = value
            tornado.ioloop.IOLoop.instance().add_timeout(time.time() + self.delay, self.run)
            self._running = True

    def start(self):
        tornado.ioloop.IOLoop.instance().add_timeout(time.time() + self.delay, self.run)
        self._running = True
        self.func = self.orig_func

    def Stop(self, *args, **kwargs):
        self.func = self.Stop
        self._running = False

    stop = Stop


def schedule(delay, callable, *args, **kwargs):
    """Emulates the EventScheduler.schedule API"""
    event = IOLoopEventElement(callable, delay, *args, **kwargs)
    self._ioloop_timeout = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + delay, event.run)
    return event


class IOLoopScheduler(object):
    def schedule(self, delay, callable, *args, **kwargs):
        """Emulates the EventScheduler.schedule API"""
        event = IOLoopEventElement(callable, delay, *args, **kwargs)
        tornado.ioloop.IOLoop.instance().add_timeout(time.time() + delay, event.run)
        return event

    @classmethod
    def instance(cls):
        """Returns a global IOLoopScheduler instance."""
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance
