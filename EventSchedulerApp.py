# (c) Copyright 2007, Synapse
"""Combines EventScheduler, asyncore, and wxPython App"""


import time, asyncore
import wx
import EventScheduler


class EventSchedulerApp(wx.App):
    def __init__(self, *args, **kwargs):
        self.evScheduler = EventScheduler.EventScheduler()
        self._yielding = False
        wx.App.__init__(self, *args, **kwargs)
        #Start calling out own event loop
        wx.CallAfter(self.eventLoop)
        #This timer is used to make sure that we continue to call our functions
        #even when we are stuck processing GUI event(s) like ShowModal
        self._chkTimer = wx.PyTimer(self._checkYield)

    def _checkYield(self):
        if self._yielding:
            #print "saw yielding"
            self.runFuncs()
            self._chkTimer.Start(2, True)

    def runFuncs(self, tSlice=0.001):
        asyncore.poll(tSlice)
        self.evScheduler.poll()

        #asyncore won't block for timeout if it's not waiting on anything
        if not asyncore.socket_map:
            time.sleep(tSlice)

    def eventLoop(self):
        self.runFuncs()

        self._yielding = True
        self._chkTimer.Start(5, True)
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
