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
"""Asynchronous XML-RPC Server.

This module extends the SimpleXMLRPCServer module, adding true async capability.
Usage of AsyncXMLRPCServer follows the model of that module, so refer to SimpleXMLRPCServer for
examples.  The only real difference is that (as with all asyncore apps) an application must enter
the asyncore.loop() to begin processing network events.

Note:
The asynchronous nature of this library means that separate method
invocations could get executed OUT OF ORDER.  Socket polling will
receive on all active sockets in parallel, so methods could 
complete in any order.

If you need guaranteed order of method invocation, the client should use XMLRPC MultiCall,
or provide event-based interlocks.   The xmlrpclib.MultiCall class provides MultiCall support.
"""


import SimpleAsyncHTTPServer
import SimpleXMLRPCServer
import xmlrpclib #Needs to be at least rev 52790 to marshall new-style objects
import socket
import asyncore
import re
import time
import logging
import Deferred
import sys

log = logging.getLogger(__name__)


class AsyncXMLRPCRequestHandler(asyncore.dispatcher):
  """
  Asynchronous XML-RPC request handler class.

  Handles all HTTP POST requests and attempts to decode them as XML-RPC requests.
  """
  # Rx states
  GETHDR  = 0
  GETDATA = 1

  # Regular expression to match HTTP POST header
  HDREXPR = re.compile(r'^(\w+).*^Content-Length\D+(\d+).*<\?xml', re.MULTILINE | re.IGNORECASE | re.DOTALL)

  def __init__(self, cloneSocket, rpcDispatch):
    self.cloneSocket = cloneSocket    
    self.rpcDispatch = rpcDispatch
    self.rxBuf = ""
    self.txBuf = ""
    self.contentLen = 0
    self.state = self.GETHDR
    asyncore.dispatcher.__init__(self, cloneSocket)

  def dispatchXmlRequest(self, data):
    """Invoke the requested method, and either transmit response immediately or register callback to 
       transmit a Deferred response as required."""
    response = self.rpcDispatch._marshaled_dispatch(data)
    if isinstance(response, Deferred.Deferred):
      response.addCallbacks(self.marshalAndSendResponse)
    else:
      self.sendResponse(response)

  def marshalAndSendResponse(self, response):
    response = (response,)
    response = xmlrpclib.dumps(response, methodresponse=1, allow_none=True, encoding=None)
    self.sendResponse(response)

  def sendResponse(self, response):  
    log.debug("sending response: " + str(response))
    timeStr = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    self.txBuf = "HTTP/1.0 200 OK\r\n"\
                 "Server: AsyncXMLRPC/Python\r\n"\
                 "Date: %s\r\n"\
                 "Content-type: text/xml\r\n"\
                 "Content-length: %d\r\n\r\n"\
                 "%s"  % (timeStr, len(response), response)

  # - - - - - - - - - - - - - asyncore.dispatcher - - - - - - - - - - - - - - -
  def handle_close(self):
    log.debug("Closing connection")
    self.close()

  def handle_read(self):
    # Get raw XML data from HTTP POST
    rcvData = self.recv(8192)
    if rcvData:
      self.rxBuf += rcvData
      if __debug__:
        log.debug("Got %i bytes", len(rcvData))

      # Receive state machine: looking within rxBuf for hdr + data
      while True:
        if self.state == self.GETHDR:
          m = self.HDREXPR.match(self.rxBuf)
          if m:
            requestType = m.group(1)
            self.contentLen = int(m.group(2))
            if __debug__:
              log.debug("Should get %i bytes", self.contentLen)
            # Trim the header from rxBuf
            self.rxBuf = self.rxBuf[m.end()-5:]          
            self.state = self.GETDATA
          elif len(self.rxBuf) > 256:
            # Unknown header, or DOS attack
            self.close()
            break
          else:
            break
        elif self.state == self.GETDATA:
          if len(self.rxBuf) >= self.contentLen:
            data = self.rxBuf[:self.contentLen]
            self.rxBuf = self.rxBuf[self.contentLen:]
            self.dispatchXmlRequest(data)
            self.state = self.GETHDR
            if __debug__:
              log.debug("got all data")
          else:
            # TODO:  Timeout so we don't wait here forever to receive falsely advertised contentLength
            break

  def handle_write(self):
    # When all is sent, we close
    numSent = self.send(self.txBuf)
    self.txBuf = self.txBuf[numSent:]
    if not self.txBuf:
      self.close()

  def writable(self):
    # Ready for connection, or ready to send
    return (not self.connected) or self.txBuf


class AsyncXMLRPCDispatcher(SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
  """
  Overriding _marshaled_dispatch in SimpleXMLRPCDispatcher, to check if 
  response is Deferred before marshalling.
  """
  def __init__(self):
    # Note: we're using the Python 2.5 version of SimpleXMLRPCServer
    SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self, allow_none=True, encoding=None)

  def _marshaled_dispatch(self, data, dispatch_method = None):
    "Copied from SimpleXMLRPCDispatcher._marshaled_dispatch, except for isinstance(response, Deferred)"
    try:
      params, method = xmlrpclib.loads(data)

      # generate response
      if dispatch_method is not None:
        response = dispatch_method(method, params)
      else:
        response = self._dispatch(method, params)

      if isinstance(response, Deferred.Deferred):
        return response

      # wrap response in a singleton tuple
      response = (response,)
      response = xmlrpclib.dumps(response, methodresponse=1,
                                 allow_none=self.allow_none, encoding=self.encoding)
    except xmlrpclib.Fault, fault:
      response = xmlrpclib.dumps(fault, allow_none=self.allow_none,
                                 encoding=self.encoding)
    except:
      # report exception back to server
      response = xmlrpclib.dumps(
          xmlrpclib.Fault(1, "%s:%s" % (sys.exc_type, sys.exc_value)),
          encoding=self.encoding, allow_none=self.allow_none,
          )

    return response


class AsyncXMLRPCServer(asyncore.dispatcher, AsyncXMLRPCDispatcher):
  """Start an XMLRPC listener at given address (ip/port tuple)"""
  def __init__(self, addr):
    asyncore.dispatcher.__init__(self)
    AsyncXMLRPCDispatcher.__init__(self)
    self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
    self.bind(addr)
    self.listen(5)

  def async_loop(self, timeout = 1.0):
    asyncore.loop(timeout)

  def handle_accept(self):
    clonesocket, address = self.accept()
    log.debug("RPC connection from %s", address)
    AsyncXMLRPCRequestHandler(clonesocket, self)


class XMLRPCRequestHandler(SimpleAsyncHTTPServer.RequestHandler):
  def handle_data(self):
    """
    Invoke the requested method, and either transmit response immediately or register callback to 
    transmit a Deferred response as required.
    """
    #log.debug("requesting: %s" % (self.rfile.read()))
    #self.rfile.seek(0)
    if self.path == '/crossdomain.xml':
      domainpolicy = """
<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM "http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
    <allow-access-from domain="*" to-ports="8080" />
</cross-domain-policy>
      """
      self.send_response(200)
      self.send_header("Content-type", 'text/html')
      self.send_header("Content-Length", len(domainpolicy))
      self.end_headers()
      self.outgoing.append(domainpolicy)
      self.outgoing.append(None)
      log.debug("request for: '/crossdomain.xml'")
      return
    response = self.server.xmlRpcDispatch._marshaled_dispatch(self.rfile.read())
    if isinstance(response, Deferred.Deferred):
      response.addCallbacks(self.marshalAndSendResponse)
    else:
      self.sendResponse(response)

  def marshalAndSendResponse(self, response, methodresponse=True):
    if methodresponse == 1:
      response = (response,)
    response = xmlrpclib.dumps(response, methodresponse=methodresponse, allow_none=True, encoding=None)
    self.sendResponse(response)

  def sendResponse(self, response):
    if self.logResponses:
      log.debug("sending response: " + str(response))
    self.send_response(200)
    self.send_header("Server", 'AsyncXMLRPC/Python')
    self.send_header("Date", time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()))
    self.send_header("Content-type", 'text/xml')
    self.send_header("Content-Length", len(response))
    self.end_headers()
    #self.log_request(self.code, len(favicon))
    self.outgoing.append(response)
    self.outgoing.append(None)


class AsyncXMLRPCServer2(AsyncXMLRPCDispatcher, SimpleAsyncHTTPServer.RequestHandler):
  def __init__(self, addr, logResponses=True):
    AsyncXMLRPCDispatcher.__init__(self)
    SimpleAsyncHTTPServer.RequestHandler.logResponses = logResponses
    self.srv = SimpleAsyncHTTPServer.Server(addr[0],addr[1],XMLRPCRequestHandler)
    self.srv.xmlRpcDispatch = self


if __name__ == '__main__':
  srv = AsyncXMLRPCServer2('http://localhost:8080')
