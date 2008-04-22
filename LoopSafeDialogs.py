# (c) Copyright 2008, Synapse


import wx
from apy import PostThread


class LoopSafeModal(object):
    """
    Base class to use when creating loop safe dialogs
    """
    def ShowModal(self, closeCallback=None):
        assert True #Your supposed to override this

    def _onShowModalComplete(self, *args, **kwargs):
        """Will callback the function passed on ShowModal with result of original blocking ShowModal"""
        if callable(self._closeCallback):
            self._closeCallback(*args, **kwargs)
        elif __debug__ and self._closeCallback is not None:
            assert False
        self.Destroy()
        return False


class FileDialog(wx.FileDialog):
    def ShowModal(self, closeCallback=None):
        """
        Intercept ShowModal and run it in a different thread and call the callback when done

        closeCallback -- The callback to use when dialog is closed
        """
        self._closeCallback = closeCallback
        PostThread.PostThread().post(wx.GetApp().evScheduler, wx.FileDialog.ShowModal, [self]).addCallbacks(self._onShowModalComplete)

    def _onShowModalComplete(self, *args, **kwargs):
        """Will callback the function passed on ShowModal with result of original blocking ShowModal"""
        if callable(self._closeCallback):
            self._closeCallback(self, *args, **kwargs)
        elif __debug__ and self._closeCallback is not None:
            assert False
        self.Destroy()
        return False


class MessageDialog(wx.MessageDialog, LoopSafeModal):
    def ShowModal(self, closeCallback=None):
        """
        Intercept ShowModal and run it in a different thread and call the callback when done

        closeCallback -- The callback to use when dialog is closed
        """
        self._closeCallback = closeCallback
        PostThread.PostThread().post(wx.GetApp().evScheduler, wx.MessageDialog.ShowModal, [self]).addCallbacks(self._onShowModalComplete)


class TextEntryDialog(wx.TextEntryDialog, LoopSafeModal):
    def ShowModal(self, closeCallback=None):
        """
        Intercept ShowModal and run it in a different thread and call the callback when done

        closeCallback -- The callback to use when dialog is closed
        """
        self._closeCallback = closeCallback
        PostThread.PostThread().post(wx.GetApp().evScheduler, wx.FileDialog.ShowModal, [self]).addCallbacks(self._onShowModalComplete)


class TestFrame(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self, parent, -1, "Test Frame", size=(500,500))
        sizer = wx.BoxSizer(wx.VERTICAL)

        btn1 = wx.Button(self, label="MessageDialog")
        self.Bind(wx.EVT_BUTTON, self.showMessageDialog, btn1)
        sizer.Add(btn1)

        btn2 = wx.Button(self, label="FileDialog")
        self.Bind(wx.EVT_BUTTON, self.showFileDialog, btn2)
        sizer.Add(btn2)

        self.SetSizerAndFit(sizer)
        self.CenterOnScreen()

    def showMessageDialog(self, event):
        dlg = MessageDialog(self, 'The value enter was invalid', 'Invalid Value', wx.OK | wx.ICON_ERROR)
        dlg.ShowModal(self.onMessageDialogClose)
        #dlg2 = wx.MessageDialog(self, 'The value enter was invalid', 'Invalid Value', wx.OK | wx.ICON_ERROR)
        #dlg2.ShowModal()

    def showFileDialog(self, event):
        dlg = FileDialog(self)
        dlg.ShowModal(self.onFileDialogClose)
        #import os
        #dlg2 = wx.FileDialog(
                #self, message="Choose a file",
                #defaultDir=os.getcwd(), 
                #defaultFile="",
                #wildcard="All files (*.*)|*.*",
                #style=wx.OPEN | wx.MULTIPLE | wx.CHANGE_DIR
                #)
        #dlg2.ShowModal()

    def onMessageDialogClose(self, result):
        print "Message Dialog closed: %s" % str(result)

    def onFileDialogClose(self, dlg, result):
        print "Message Dialog closed: %s" % str(result)


if __name__ == '__main__':
    from apy import EventSchedulerApp

    app = EventSchedulerApp.EventSchedulerApp()
    app.RestoreStdio()
    app.frame = TestFrame(None)
    app.frame.Show()
    app.MainLoop()
