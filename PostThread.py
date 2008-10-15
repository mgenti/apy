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

"""Run a function in a new thread, posting deferred results back to an Event Queue.
   Transforms a blocking API into an event-driven one!

Usage:
------
Assuming a blocking function:  waitForIt(p1, p2), returning some value.  We want to run this function
in its own thread, and get a callback event (in our thread) with the return value when it's done.

evQ = our EventScheduler
cb = our callback function

PostThread().post(evQ, waitForIt, [p1,p2]).addCallbacks(cb)

"""

import Deferred
import EventScheduler
import threading
import Queue
import time
import sys
import logging

class PostThreadTerminated(Exception):
  """PostThread has been terminated."""
  pass

class PostThread(object):
  """Post callables to a separate thread, sending deferred results back to an Event Queue.
     Transforms a blocking API into an event-driven one!
  """
  def __init__(self):
    """Create a new thread to which requests may be posted"""
    self.serviceRequests = True
    self.reqQ = Queue.Queue()
    self.thread = threading.Thread(target=self._doRun)
    self.thread.setDaemon(True)
    self.thread.start()

  def post(self, evQ, func, params = []):
    """Post the callable 'func' to be run in the PostThread.
       Returns Deferred object to which a callback may attached.
       Deferred callback is posted to the given event queue with the return value of 'func'.
       
       evQ -- Event Queue to which 'results' callback will be posted
       func -- Function to execute in PostThread context
       params -- arguments to func() (default [])
    """
    if not self.serviceRequests:
      raise PostThreadTerminated
    
    d = Deferred.Deferred()
    request = (evQ, func, params, d)
    self.reqQ.put_nowait(request)
    return d
  
  def kill(self):
    """Allow this thread to die, after pending requests are satisfied"""
    # No more requests allowed in reqQ
    self.serviceRequests = False
    # Null element on reqQ terminates processing
    self.reqQ.put_nowait(None)

  def _doRun(self):
    """Thread main function"""
    while True:
      # Block, waiting on work request
      request = self.reqQ.get()
      if request:
        (evQ, func, params, d) = request
      else:
        # Terminate thread
        return
      
      try:
        rv = func(*params)
        err = False
      except:
        rv = sys.exc_info()
        err = True
      evQ.scheduleEvent(self._qResult, [d, rv, err])
  
  def _qResult(self, d, rv, err):  
    """Callback executor posted to the Event Queue"""
    if err:
      d.runErrback(rv)
    else:
      d.runCallback(rv)
    
    
#---------------------------------------------------------------------------------------------------
if __name__=='__main__':
  logging.basicConfig()
  evQ = EventScheduler.EventScheduler()

  def foo(p1, p2):
    print "This is done in another thread!  params: %s, %s" % (p1, p2)
    return "Foo Returns!"

  def bar(p1, p2):
    print "This is done in the same thread as the first one!  params: %s, %s" % (p1, p2)
    raise RuntimeError 
    return "Bar Returns!"



  pt1 = PostThread()
  
  def pt1cb(rv):
    print "pt1 callback: rv = %s" % (rv)
  
  d1 = pt1.post(evQ, foo, ['param1', 'param2'])
  d1.addCallbacks(pt1cb)
  d2 = pt1.post(evQ, bar, ['param1', 'param2'])
  d2.addCallbacks(pt1cb)

  pt1.kill()
  #pt1.post(evQ, foo, ['mo_param1', 'mo_param2']).addCallbacks(pt1cb)

  while True:
    evQ.poll()
    time.sleep(0.1)


#---------------------------------------------------------------------------------------------------
