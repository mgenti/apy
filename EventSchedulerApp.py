# (c) Copyright 2007, Synapse
"""Combines EventScheduler and wxPython App"""


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

        # This outer loop determines when to exit the application
        while self.frame:
            # At this point in the outer loop you could do
            # whatever you implemented your own MainLoop for.  It
            # should be quick and non-blocking, otherwise your GUI
            # will freeze.  

            # call_your_code_here()
            self.evScheduler.poll()

            # This inner loop will process any GUI events
            # until there are no more waiting.
            while evtloop.Pending():
                evtloop.Dispatch()

            #There are some things internal to wx that are triggered
            #from the ProcessIdle method besides the idle events
            self.ProcessIdle()

        wx.EventLoop.SetActive(old)
