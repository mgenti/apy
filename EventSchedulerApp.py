# (c) Copyright 2007-2012, Synapse Wireless, Inc.
"""Combines EventScheduler, asyncore, and wx.App"""


import time, asyncore
import wx
import EventScheduler


SLEEP_TIME = 0.001
IN_CHECK_YIELD_TIME = 2
EVENT_LOOP_CHECK_TIME = 5
if wx.Platform != '__WXMSW__':
    SLEEP_TIME = 0.025
    IN_CHECK_YIELD_TIME = 25
    EVENT_LOOP_CHECK_TIME = 250


class EventSchedulerApp(wx.App):
    def __init__(self, *args, **kwargs):
        self.evScheduler = EventScheduler.EventScheduler()
        self._yielding = False
        wx.App.__init__(self, *args, **kwargs)

        # Start calling our own event loop
        wx.CallAfter(self.eventLoop)
        # This timer is used to make sure that we continue to call our functions
        # even when we are stuck processing GUI event(s) like ShowModal
        self._chkTimer = wx.PyTimer(self._checkYield)

    def _checkYield(self):
        if self._yielding:
            #print "saw yielding"
            self.runFuncs()
            self._chkTimer.Start(IN_CHECK_YIELD_TIME, True)

    def runFuncs(self, tSlice=SLEEP_TIME):
        asyncore.poll(tSlice)
        self.evScheduler.poll()

        # asyncore won't block for timeout if it's not waiting on anything
        if not asyncore.socket_map:
            time.sleep(tSlice)

    def eventLoop(self):
        self.runFuncs()

        self._yielding = True
        self._chkTimer.Start(EVENT_LOOP_CHECK_TIME, True)
        self.Yield(True)
        self._yielding = False
        #This may eventually need to go within the _yielding but right now
        #there isn't much called from idle
        self.ProcessIdle()

        if self.GetTopWindow() is not None:
            wx.CallAfter(self.eventLoop)


if __name__ == '__main__':
    app = EventSchedulerApp()
    app.frame = wx.Frame(None)
    app.frame.Show()
    app.MainLoop()
