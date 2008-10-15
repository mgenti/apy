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


import xmlrpclib
import socket
import asyncore
import urllib
import Deferred
import re
import sys
import logging
import xml.parsers

log = logging.getLogger(__name__)

class AsyncXMLRPCTransport(xmlrpclib.Transport):
  """Asynchronously handles an HTTP transaction to an XML-RPC server.
      Designed to be passed to the xmlrpclib.ServerProxy ctor.
      
      Standard XMLRPC HTTP Transport uses the TCP session context to
      correlate command/response.  Therefore, a new session must be created
      for each method call, and is closed when the response is complete.
      This class is a factory of TCP sessions to handle these method calls.

      A ServerProxy instance will create a single instance of this Transport
      implementation.  Each method call results in a 'request' call.  We create
      a new MethodSession for each request.

      Note:
      The asynchronous nature of this library means that separate method
      invocations could get executed OUT OF ORDER.  The method call data is 
      posted to the sockets library in call-order, but each method gets its own socket.
      Socket polling will send on all active sockets in parallel, so methods could 
      complete in any order.
      
      If you need guaranteed order of method invocation, the client should use XMLRPC MultiCall,
      or provide event-based interlocks.  An asynchronous compatible MultiCall adaptation
      based on xmlrpclib.MultiCall is provided in this module (see below).
  """
  
  #- - - xmlrpclib.Transport - - -
  def request(self, host, handler, request_body, verbose=0):
    """Send a complete request, and parse the response.
        Return a Deferred response object.       
    """
    return (AsyncXMLRPCTransport.MethodSession(host, request_body, self).deferred,)

  class MethodSession(asyncore.dispatcher):
    "TCP Session context for a single XMLRPC method call"

    # Rx states
    GETHDR  = 0
    GETDATA = 1
    
    def __init__(self, host, request_body, transport):
      asyncore.dispatcher.__init__(self) 
      self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
      self.rxBuf = ""
      self.contentLen = 0
      self.state = self.GETHDR
      self.host = host
      self.parser = transport.getparser()
      self.request = request_body  # for debug
      
      # Regular expression to match HTTP Response header
      self.hdrExpr = re.compile(r'^HTTP/([\d.]+)\s+(\w+)\s+([\w ]*).*^Content-Length\D+(\d+).*<\?xml', re.MULTILINE | re.IGNORECASE | re.DOTALL)

      hdr = "POST /RPC2 HTTP/1.0\r\n"\
            "User-Agent: AsyncXMLRPC/Python\r\n"\
            "Content-Type: text/xml\r\n"\
            "Content-length: %d\r\n\r\n" % (len(request_body))
      self.txBuf = hdr + request_body
      
      # Setup async response handler
      self.deferred = Deferred.Deferred()
      
      # Connect to host and POST request       
      self.connect(urllib.splitnport(host, 80))
      
        
    #- - - asyncore.dispatcher - - -
    def handle_connect(self):
      # Active connection succeeded
      pass
      
    def handle_read(self):
#      log.debug("in handle_read")
      # Get raw XML data from HTTP Response
      rcvData = self.recv(8192)
      if rcvData:
        self.rxBuf += rcvData
  
        # Receive state machine: looking within rxBuf for hdr + data
        while True:
          if self.state == self.GETHDR:
            m = self.hdrExpr.match(self.rxBuf)
            if m:
              httpVersion = m.group(1)
              httpResponseCode = m.group(2)
              httpResponseMsg  = m.group(3)
              self.contentLen  = int(m.group(4))
              
              if httpResponseCode != '200':
                self.deferred.runErrback(xmlrpclib.ProtocolError(self.host, httpResponseCode, httpRespMsg, {}))
                self.close()
                return
              
              # Trim the header from rxBuf
              self.rxBuf = self.rxBuf[m.end()-5:]
              self.state = self.GETDATA
            elif len(self.rxBuf) > 256:
              # Unknown header, or DOS attack
              self.deferred.runErrback(xmlrpclib.ProtocolError(self.host, '500', "Unknown header", {}))
              self.close()
              break
            else:
              break
          elif self.state == self.GETDATA:
            if len(self.rxBuf) >= self.contentLen:
              data = self.rxBuf[:self.contentLen]
              self.rxBuf = self.rxBuf[self.contentLen:]
              self.dispatchXmlResponse(data)
              self.close()
              self.state = self.GETHDR
            else:
              # TODO:  Timeout so we don't wait here forever to receive falsely advertised contentLength
              break
#      log.debug('out handle_read')

    def writable(self):
      # Ready to send
      return self.txBuf
  
    def handle_write(self):
      numSent = self.send(self.txBuf)
      self.txBuf = self.txBuf[numSent:]

    def handle_close(self):
      self.close()

    def handle_error(self):
      t, v, nil = sys.exc_info()
      self.deferred.runErrback(
        xmlrpclib.ProtocolError(self.host, '500',
                                "Socket Error (%s:%s)" % (t, v) , {})
      )
      self.close()
      
    def handle_expt(self):
      # TODO:  On Windows, find out why we get here when server goes away.
      #        This is supposed to be for OOB data!
      self.handle_error()
    
    def dispatchXmlResponse(self, response):
      p, u = self.parser
      try:
#        log.debug("Dispatching response")
        p.feed(response)
        p.close()
        result = u.close()
        
        # Post this result to the Deferred object bound to this response
        self.deferred.runCallback(result[0])
  
      # Catch XMLRPC "faultCode" response parsing (raised by the 'close' method)
      except (xmlrpclib.Fault, xml.parsers.expat.ExpatError), e:
        self.deferred.runErrback(e)


class MultiCall(xmlrpclib.MultiCall):
  """Multicall with async support.
      Call method returns a deferred result, to which callbacks may be attached.
      Callback.func may then use xmlrpclib.MultiCallIterator(results) to iterate
      over the results as returned by the blocking version.
          
      Note:  ResultList posted to callback function is a list of lists, so - if 
            accessing without using MultiCallIterator - be mindful that the results
            are as resultList[0][0], resultList[1][0],...
  """
  def __init__(self, server):
    xmlrpclib.MultiCall.__init__(self, server)
    
  def __call__(self):
    """Invoke system.multicall() method.
        Returns a Deferred to which callbacks may be attached.
    """
    mcIter = xmlrpclib.MultiCall.__call__(self)
    return mcIter.results
