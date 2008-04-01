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


import sys
from code import InteractiveInterpreter
from Deferred import *
from PostThread import *
from EventScheduler import *

class AsynConsole(InteractiveInterpreter):
    """Closely emulate the behavior of the interactive Python interpreter.

    This class builds on InteractiveInterpreter and adds prompting
    using the familiar sys.ps1 and sys.ps2, and input buffering.

    """

    def __init__(self, evScheduler, locals=None, filename="<console>"):
        """Constructor.

        The optional locals argument will be passed to the
        InteractiveInterpreter base class.

        The optional filename argument should specify the (file)name
        of the input stream; it will show up in tracebacks.

        """
        InteractiveInterpreter.__init__(self, locals)
        self.filename = filename
        self.resetbuffer()
        
        #my stuff
        try:
            sys.ps1
        except AttributeError:
            sys.ps1 = ">>> "
        try:
            sys.ps2
        except AttributeError:
            sys.ps2 = "... "

        self.more = 0
        self.loop = False
        self.evScheduler = evScheduler
        self.postThread = PostThread()

    def resetbuffer(self):
        """Reset the input buffer."""
        self.buffer = []

    def _getLine(self):
      """Uses PostThread to wait for a line from raw_input"""
      if self.more:
        prompt = sys.ps2
      else:
        prompt = sys.ps1

      self.postThread.post(self.evScheduler, raw_input, [prompt]).addCallbacks(self._gotLine, self._errGotLine)

    def _gotLine(self, line):
      """Callback for successfully reading a line"""
      self.more = self.push(line)
      if self.loop:
        self.evScheduler.scheduleEvent(self._getLine)

    def _errGotLine(self, returnResult):
      """Callback if an exception occurrs while reading a line"""
      if returnResult[0] == EOFError:
        self.write("\n")
#        print "caught EOF"
      else:
        print "Unknown Error:", returnResult

    def stopInteract(self):
      """Stop the interactive console"""
      self.loop = False

    def interact(self, banner=None):
        """Closely emulate the interactive Python console.

        The optional banner argument specify the banner to print
        before the first interaction; by default it prints a banner
        similar to the one printed by the real Python interpreter,
        followed by the current class name in parentheses (so as not
        to confuse this with the real interpreter -- since it's so
        close!).

        """
        if not self.loop:
          cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
          if banner is None:
            self.write("Python %s on %s\n%s\n(%s)\n" %
                       (sys.version, sys.platform, cprt,
                        self.__class__.__name__))
          else:
            self.write("%s\n" % str(banner))
          self.loop = True
          self.evScheduler.scheduleEvent(self._getLine)

    def push(self, line):
        """Push a line to the interpreter.

        The line should not have a trailing newline; it may have
        internal newlines.  The line is appended to a buffer and the
        interpreter's runsource() method is called with the
        concatenated contents of the buffer as source.  If this
        indicates that the command was executed or invalid, the buffer
        is reset; otherwise, the command is incomplete, and the buffer
        is left as it was after the line was appended.  The return
        value is 1 if more input is required, 0 if the line was dealt
        with in some way (this is the same as runsource()).

        """
        self.buffer.append(line)
        source = "\n".join(self.buffer)
        more = self.runsource(source, self.filename)
        if not more:
            self.resetbuffer()
        return more

if __name__ == '__main__':
  import time

  localTest = 5

  evScheduler = EventScheduler()
  myConsole = AsynConsole(evScheduler, locals()).interact()

  print "Now in event loop..."
  while True:
    evScheduler.poll()
    time.sleep(0.01)
