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


import time
import threading
import bisect
import operator
#import sys


class EventElement(object):
  def __init__(self, func, delay=0.0, *args, **kwargs):
    self.func = func
    self.params = args
    self.kwargs = kwargs
    self.delay = delay
    self.fireTime = time.time() + delay

  def sortKey(self):
    return self.fireTime

  def __lt__(self, other):
    #Used when bisecting the current event queue
    return operator.lt(self.fireTime, other.fireTime)

  def Stop(self, *args, **kwargs):
    #if self.func != self.Stop:
      #print "Stopped %s" % self.func.im_func.func_name
    self.func = self.Stop


#---------------------------------------------------------------------------------------------------
class EventScheduler(object):
  """Event queue mechanism, asynchronously polled, dispatching bound methods with optional delay."""
  def __init__(self):
    self.eventQueue = []
    self.lock = threading.RLock()

  def schedule(self, delay, callable, *args, **kwargs):
    """Order of parameters is like wx.CallLater and supports keyword arguments unlike scheduleEvent"""
    #print "%s scheduled %s" % (sys._getframe(1).f_code.co_name, callable.im_func.func_name)
    event = EventElement(callable, delay, *args, **kwargs)
    self.lock.acquire()
    self.eventQueue.append(event)
    self.lock.release()
    #event.creator = sys._getframe(1).f_code.co_name
    return event

  def scheduleEvent(self, func, params=[], delay=0.0):
    """Schedule event:
         func is a bound method or callable object, return True to reschedule,
         return float value to set new delay AND reschedule;
         params is a list of parameters to func;
         delay is in seconds
    """
    #print "%s scheduled event %s" % (sys._getframe(0).f_code.co_name, func.im_func.func_name)
    self.lock.acquire()
    self.eventQueue.append(EventElement(func, delay, *params))
    self.lock.release()

  def scheduleEvents(self, eventList):
    """Schedule a list of EventElements:
         This is an alternative to discrete scheduleEvent() calls, but accomplishes the same thing.
         It takes the thread-lock fewer times, but may not actually be faster than discrete calls
         to scheduleEvent() if the average size of the eventQueue is large.
    """
    self.lock.acquire()
    self.eventQueue.extend(eventList)
    self.lock.release()

  def poll(self):
    """Run the event scheduler, return the number of events called"""
    self.lock.acquire()
    self.eventQueue.sort(key=EventElement.sortKey)
    i = bisect.bisect_right(self.eventQueue, EventElement(None, 0))
    workq = self.eventQueue[:i]
    self.eventQueue = self.eventQueue[i:]
    self.lock.release()

    for e in workq:
      rv = e.func(*e.params, **e.kwargs)
      if isinstance(rv, bool):
        if rv:
          reschedule = rv
      elif isinstance(rv, float) or isinstance(rv, int):
        e.delay = rv
        reschedule = True
      else:
        reschedule = False
      if reschedule:
        e.fireTime = time.time() + e.delay
        #e.fireTime += e.delay     # If we wanted accurate periodicity, versus accurate intervals
        self.lock.acquire()
        self.eventQueue.append(e)
        self.lock.release()

    return i

  def printQueue(self):
    """Debugging helper"""
    for mye in self.eventQueue:
      try:
        print mye.params[0], mye.fireTime, mye.delay
      except IndexError:
        print "no params", mye.fireTime, mye.delay

  def unschedule(self, event):
    """Removes the scheduled event from the queue"""
    self.lock.acquire()
    self.eventQueue.remove(event)
    self.lock.release()


#---------------------------------------------------------------------------------------------------
if __name__=='__main__':
  sked = EventScheduler()
  
  class Test:
    "Test EventScheduler with bound methods"
    def a(self):
      print "a - rescheduled"
      return True

    def b(self, p1, p2):
      print "b" + p1 + p2
      sked.scheduleEvent(self.c)
      return False

    def c(self):
      print "c"

    def d(self):
      raise Exception("I SHOULDN'T RUN")


  class C:
    "Test EventScheduler with a callable instance"
    def __call__(self):
      print "C - not rescheduled"
      return False


  x = Test()  
  sked.scheduleEvent(x.a, delay = 3.0)
  sked.scheduleEvent(x.b, [" demo ", "parameter"], delay = 10.0)
  sked.scheduleEvent(C())
  sked.schedule(0.0, x.b, "arg", p2="keyword")
  event = sked.schedule(0.1, x.d)
  sked.unschedule(event)
  event = sked.schedule(0.2, x.d)
  event.Stop()

  # Check speed of scheduling lots of events at once
  immediateCount = 0
  def immediateFunc():
    global immediateCount
    immediateCount += 1
    if immediateCount % 1000 == 0:
      print "immediateCount: %d" % immediateCount

  import timeit
  t = timeit.Timer("sked.scheduleEvent(immediateFunc)", "from __main__ import sked, immediateFunc")
  print t.timeit(10000)

  # Now test the "en mass" version of scheduling
  evs = []
  for i in range(10000):
    evs.insert(0, EventElement(immediateFunc))

  t = timeit.Timer("sked.scheduleEvents(evs)", "from __main__ import sked, evs")
  print t.timeit(1)


  while True:
    sked.poll()
    time.sleep(0.1)


#---------------------------------------------------------------------------------------------------
