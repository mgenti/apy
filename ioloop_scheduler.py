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
        self.io_loop = tornado.ioloop.IOLoop.instance()

    def run(self):
        if self.func == self.Stop:
            # Do nothing and delete reference to yourself
            self.func = None
            return

        value = self.func(*self.args, **self.kwargs)
        self._running = False
        if isinstance(value, bool):
            # bool inherits from int
            if value:
                self.io_loop.add_timeout(self.io_loop.timefunc() + self.delay, self.run)
                self._running = True
        elif isinstance(value, float) or isinstance(value, int):
            self.delay = value
            self.io_loop.add_timeout(self.io_loop.timefunc() + self.delay, self.run)
            self._running = True

    def start(self):
        self.io_loop.add_timeout(self.io_loop.timefunc() + self.delay, self.run)
        self._running = True
        self.func = self.orig_func

    def Stop(self, *args, **kwargs):
        self.func = self.Stop
        self._running = False

    stop = Stop


def schedule(delay, callable, *args, **kwargs):
    """Emulates the EventScheduler.schedule API"""
    event = IOLoopEventElement(callable, delay, *args, **kwargs)
    self._ioloop_timeout = tornado.ioloop.IOLoop.instance().add_timeout(tornado.ioloop.IOLoop.instance().timefunc() + delay, event.run)
    return event


class IOLoopScheduler(object):
    def __init__(self, io_loop=None):
        if io_loop is None:
            io_loop = tornado.ioloop.IOLoop.instance()
        self.io_loop = io_loop

    def schedule(self, delay, callable, *args, **kwargs):
        """Emulates the EventScheduler.schedule API"""
        event = IOLoopEventElement(callable, delay, *args, **kwargs)
        event.io_loop = self.io_loop
        deadline = event.io_loop.time_func() + event.delay
        self.io_loop.add_callback(lambda: event.io_loop.add_timeout(deadline, event.run))  # Only add_callback is thread safe
        return event

    @classmethod
    def instance(cls):
        """Returns a global IOLoopScheduler instance."""
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance
