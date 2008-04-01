#Copyright (c) 2007 David Ewing Mark Guagenti

#Permission is hereby granted, free of charge, to any person
#obtaining a copy of this software and associated documentation
#files (the "Software"), to deal in the Software without
#restriction, including without limitation the rights to use,
#copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the
#Software is furnished to do so, subject to the following
#conditions:

#The above copyright notice and this permission notice shall be
#included in all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
#OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#OTHER DEALINGS IN THE SOFTWARE."""


from threading import *
from PostThread import *
from Deferred import *
import EventScheduler

class AsyncThreadEvent(object):
  """Wraps a threading event object so that you can get a callback"""
  def __init__(self):
    pass

  def getThreadEvent(self, evScheduler, callback, errCallback=None, timeout=None):
    """Returns a threading.Event object

    evScheduler -- The event scheduler to use
    callback -- The method to callback when the thread event has completed
    """
    event = Event()
    defer = Deferred()
    defer.addCallbacks(callback, errCallback)
    threading.Thread(target=self._waiter, args=(event, evScheduler, defer, timeout)).start()
    return event

  def _waiter(self, event, evScheduler, defer, timeout=None):
    event.wait(timeout)

    if event.isSet():
      evScheduler.scheduleEvent(self._waiterDone, [defer])
    else:
      evScheduler.scheduleEvent(self._waiterTimeout, [defer])

  def _waiterDone(self, defer):
    """Callback executor posted to the Event Queue"""
    defer.runCallback(None)
    #if err:
      #defer.runErrback(None)
    #else:
      #defer.runCallback(None)
#    self.postThread.post(self.evScheduler, self._waiter, []).addCallbacks(self.callback, self.errCallback)

  def _waiterTimeout(self, defer):
    """Callback executor posted to the Event Queue if a timeout occurs"""
    defer.runErrback(None)
    #if err:
      #defer.runErrback(None)
    #else:
      #defer.runCallback(None)
#    self.postThread.post(self.evScheduler, self._waiter, []).addCallbacks(self.callback, self.errCallback)

def test_callback(returnResult):
  print "got callback"

def test_thread(event, sleepTime=1):
  time.sleep(sleepTime)
  print "sleep done", sleepTime
  event.set()
  event.clear()

def test_errThread(event):
  raise Exception, "test except"
  event.set()
  event.clear()

def test_schedThread(ate):
  threading.Thread(target=test_errThread, args=(ate.getThreadEvent(evScheduler, test_callback),)).start()

if __name__ == '__main__':
  import time, logging

  logging.basicConfig(level=logging.DEBUG,
                  format='%(asctime)s %(name)-20s %(levelname)-8s %(message)s\n',
                  datefmt='%H:%M:%S',)

  evScheduler = EventScheduler.EventScheduler()
  ate = AsyncThreadEvent()
  threading.Thread(target=test_thread, args=(ate.getThreadEvent(evScheduler, test_callback), 1)).start()
  threading.Thread(target=test_thread, args=(ate.getThreadEvent(evScheduler, test_callback), 5)).start()
  threading.Thread(target=test_thread, args=(ate.getThreadEvent(evScheduler, test_callback), 3)).start()
  evScheduler.scheduleEvent(test_schedThread, [ate], 2)

  print "In Event Loop..."
  while True:
    evScheduler.poll()
    time.sleep(0.01)
  
