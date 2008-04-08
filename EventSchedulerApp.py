# (c) Copyright 2007, Synapse
"""Combines EventScheduler, asyncore, and wxPython App"""


import time, timeit, asyncore
import wx
import EventScheduler


class EventSchedulerApp(wx.App):
    def __init__(self, *args, **kwargs):
        self.evScheduler = EventScheduler.EventScheduler()
        wx.App.__init__(self, *args, **kwargs)

    def MainLoop(self):
        # Create an event loop and make it active
        evtloop = wx.EventLoop()
        old = wx.EventLoop.GetActive()
        wx.EventLoop.SetActive(evtloop)
        tSlice = 0.001 #sec

        # This outer loop determines when to exit the application
        while self.frame:
            # At this point in the outer loop you could do
            # whatever you implemented your own MainLoop for.  It
            # should be quick and non-blocking, otherwise your GUI
            # will freeze.  

            # call_your_code_here()
            startTime = timeit.default_timer()

            asyncore.poll(0.001)
            self.evScheduler.poll()

            #asyncore won't block for timeout if it's not waiting on anything
            sleepTime = tSlice - (startTime - timeit.default_timer())
            time.sleep(sleepTime if sleepTime > tSlice else 0)

            # This inner loop will process any GUI events
            # until there are no more waiting.
            while evtloop.Pending():
                evtloop.Dispatch()

            #There are some things internal to wx that are triggered
            #from the ProcessIdle method besides the idle events
            self.ProcessIdle()

        wx.EventLoop.SetActive(old)


if __name__ == '__main__':
    app = EventSchedulerApp()
    app.frame = wx.Frame(None)
    app.frame.Show()
    app.MainLoop()
