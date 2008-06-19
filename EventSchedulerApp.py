# (c) Copyright 2007, Synapse
"""Combines EventScheduler, asyncore, and wxPython App"""


import time, timeit, asyncore
import wx
import EventScheduler


class EventSchedulerApp(wx.App):
    def __init__(self, *args, **kwargs):
        self.evScheduler = EventScheduler.EventScheduler()
        self._yielding = False
        wx.App.__init__(self, *args, **kwargs)
        wx.CallAfter(self.eventLoop)
        self._chkTimer = wx.PyTimer(self._checkYield)

    def _checkYield(self):
        if self._yielding:
            #print "saw yielding"
            self.runFuncs()
            self._chkTimer.Start(2, True)

    def runFuncs(self, tSlice=0.001):
        startTime = timeit.default_timer()

        asyncore.poll(0.001)
        self.evScheduler.poll()

        #asyncore won't block for timeout if it's not waiting on anything
        sleepTime = tSlice - (startTime - timeit.default_timer())
        time.sleep(sleepTime if sleepTime > tSlice else 0)

    def eventLoop(self):
        self.runFuncs()

        self._yielding = True
        self._chkTimer.Start(5, True)
        self.Yield(True)
        self._yielding = False
        self.ProcessIdle()

        if self.GetTopWindow() is not None:
            wx.CallAfter(self.eventLoop)


if __name__ == '__main__':
    app = EventSchedulerApp()
    app.frame = wx.Frame(None)
    app.frame.Show()
    app.MainLoop()
