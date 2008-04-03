"""Wraps wxPython and EventScheduler"""


def NotifyPatch(self):
    """Modifies wx.CallLAter.Notify to support restrating based on result"""
    if self.callable and getattr(self.callable, 'im_self', True):
        self.runCount += 1
        self.running = False
        self.result = self.callable(*self.args, **self.kwargs)
        if self.result:
            self.Restart()
    self.hasRun = True
    if not self.running:
        # if it wasn't restarted, then cleanup
        wx.CallAfter(self.Stop)


class Scheduler(object):
    def __init__(self):
        try:
            globals()['wx']
            self._hasWx = True
            import wx
            wx.CallLater.Notify = NotifyPatch
        except KeyError:
            self._hasWx = False
            import EventScheduler
            self._scheduler = EventScheduler.EventScheduler()
        
    def schedule(self, millis, callable, *args, **kwargs):
        if self._hasWx:
            import wx
            wx.CallLater(millis, callable, *args, **kwargs)
        else:
            assert len(kwargs) == 0
            self._scheduler.scheduleEvent(callable, args, millis/1000)

    def start(self, sleepTime=0.01):
        if self._hasWx:
            wx.GetApp().MainLoop()
        else:
            import time
            while True:
                self._scheduler.poll()
                time.sleep(0.01)


def _test(a, *args, **kwargs):
    print "I got called"
    return True


if __name__ == '__main__':
    #import wx
    #app = wx.App()
    #frame = wx.Frame(None)

    sked = Scheduler()
    sked.schedule(100, _test, 10)

    sked.start()
