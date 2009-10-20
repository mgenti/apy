# (c) Copyright 2007, Synapse
"""Combines EventScheduler, asyncore, and wxPython App"""


import time, asyncore
import wx
import EventScheduler


MAINLOOP_PLATFORMS = ['__WXGTK__']

SLEEP_TIME = 0.001
if wx.Platform != '__WXMSW__':
    SLEEP_TIME = 0.03


class EventSchedulerApp(wx.App):
    def __init__(self, *args, **kwargs):
        self.evScheduler = EventScheduler.EventScheduler()
        self._yielding = False
        wx.App.__init__(self, *args, **kwargs)
        #Start calling out own event loop
        if wx.Platform not in MAINLOOP_PLATFORMS:
            wx.CallAfter(self.eventLoop)
            #This timer is used to make sure that we continue to call our functions
            #even when we are stuck processing GUI event(s) like ShowModal
            self._chkTimer = wx.PyTimer(self._checkYield)

    def _checkYield(self):
        if self._yielding:
            #print "saw yielding"
            self.runFuncs()
            self._chkTimer.Start(2, True)

    def runFuncs(self, tSlice=SLEEP_TIME):
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

    def MainLoop(self):
        if wx.Platform not in MAINLOOP_PLATFORMS:
            return wx.App.MainLoop(self)

        # Create an event loop and make it active.  If you are
        # only going to temporarily have a nested event loop then
        # you should get a reference to the old one and set it as
        # the active event loop when you are done with this one...
        evtloop = wx.EventLoop()
        old = wx.EventLoop.GetActive()
        wx.EventLoop.SetActive(evtloop)

        # This outer loop determines when to exit the application,
        # for this example we let the main frame reset this flag
        # when it closes.
        while self.GetTopWindow() is not None:
            # At this point in the outer loop you could do
            # whatever you implemented your own MainLoop for.  It
            # should be quick and non-blocking, otherwise your GUI
            # will freeze.  

            self.runFuncs()


            # This inner loop will process any GUI events
            # until there are no more waiting.
            while evtloop.Pending():
                evtloop.Dispatch()

            # Send idle events to idle handlers.  You may want to
            # throttle this back a bit somehow so there is not too
            # much CPU time spent in the idle handlers.  For this
            # example, I'll just snooze a little...
            self.ProcessIdle()

        wx.EventLoop.SetActive(old)


if __name__ == '__main__':
    app = EventSchedulerApp()
    app.frame = wx.Frame(None)
    app.frame.Show()
    app.MainLoop()
