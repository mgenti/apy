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


import logging
log = logging.getLogger(__name__)


class Deferred(object):
  """
  A return-value construct supporting asynchronous programming.
  This is a concept borrowed from the Twisted framework, designed to be a return
  value from a non-blocking method call, to which callbacks may be attached.
  """
  def __init__(self):
    if __debug__:
      self.fn, self.lno, self.func = log.findCaller()
    self.callback = None
    self.errback = None

  def __call__(self, *args, **kwargs):
    self.runCallback(*args, **kwargs)

  def addCallbacks(self, callback, errback = None):
    self.callback = callback
    self.errback = errback

  def runCallback(self, *args, **kwargs):
    if callable(self.callback):    
      self.callback(*args, **kwargs)

  def runErrback(self, *args, **kwargs):
    if callable(self.errback):
      self.errback(*args, **kwargs)
    else:
      log.error(str(args[0]))
      if __debug__: log.exception('errback is not callbable')
