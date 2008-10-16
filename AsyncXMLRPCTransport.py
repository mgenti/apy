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
import sys
import os
import logging
import xml.parsers
import httplib
import cStringIO


log = logging.getLogger(__name__)


class HttpLibFakeSocket(object):
  def __init__(self, data):
    self._data = data

  def makefile(self, *args, **kwargs):
    return self._data


class Keep_Alive_Session(asyncore.dispatcher):
  def __init__(self, host, transport, close_callable=None):
    asyncore.dispatcher.__init__(self)
    self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
    self.host = host
    self.getparser = transport.getparser
    self.close_callable = close_callable
    self.deferred = None
    self.waiting_on_response = False
    self.rx_buf = ""
    self.tx_buf = ""

    # Connect to host and POST request
    self.connect(urllib.splitnport(host, 80))

    #log.debug("New Keep_Alive_Session Created")

  def dispatchXmlResponse(self, response):
      p, u = self.getparser()
      try:
        #log.debug("Dispatching response")
        p.feed(response)
        p.close()
        result = u.close()

        # Post this result to the Deferred object bound to this response
        self.deferred.runCallback(result[0])

      # Catch XMLRPC "faultCode" response parsing (raised by the 'close' method)
      except (xmlrpclib.Fault, xml.parsers.expat.ExpatError), e:
        self.deferred.runErrback(e)

  def handle_close(self):
    #This seems to be only called when the other side closes the connection
    self.close()
    if callable(self.close_callable):
      self.close_callable(self)

  def handle_connect(self):
    #Try to start sending once connected
    self.handle_write()

  def handle_error(self):
    t, v, nil = sys.exc_info()
    self.deferred.runErrback(
      xmlrpclib.ProtocolError(self.host, '500',
                              "Socket Error (%s:%s)" % (t, v) , {})
    )
    self.close()

  def handle_expt(self):
    #From EffBot:
    #Called when a connection fails (Windows), or when out-of-band data arrives (Unix)

    #Since we aren't doing OOB
    err = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
    if err:
      msg = os.strerror(err)
      if msg == 'Unknown error':
        msg += ' - '
        msg += str(err)
      self.deferred.runErrback(socket.error((err, msg)))
      log.error(msg) #Using error instead of exception since there is not a stack trace
      self.close()

  def handle_read(self):
    recv_data = self.recv(4096)
    if recv_data:
      #log.debug("Received data: %s" % rcvData)
      self.rx_buf += recv_data
      if self.rx_buf.find("</methodResponse>") > -1:
        self.waiting_on_response = False
        resp = httplib.HTTPResponse(HttpLibFakeSocket(cStringIO.StringIO(self.rx_buf)))
        resp.begin()
        if resp.status == httplib.OK:
          if resp.chunked:
            #Skip the chunk lengths
            self.dispatchXmlResponse(''.join(resp.fp.readlines()[1:-2]))
          else:
            self.dispatchXmlResponse(resp.fp.read())
        else:
          self.deferred.runErrback(xmlrpclib.ProtocolError(self.host, str(resp.status), resp.reason, {}))
        self.rx_buf = ""

  def handle_write(self):
    numSent = self.send(self.tx_buf)
    self.tx_buf = self.tx_buf[numSent:]
    #if __debug__ and numSent:
      #log.debug("Sent data: %s" % self.tx_buf[:numSent])
      #log.debug("Still %i bytes left" % (len(self.tx_buf)))

  def send_request(self, request_body):
    #print "send_request CALLED"
    assert not self.closing
    if self.waiting_on_response:
      raise Exception("BAD!!!")

    keep_alive = "\r\n"
    if not self.connected:
      keep_alive = "Connection: Keep-Alive\r\n\r\n"
    self.tx_buf += "POST /RPC2 HTTP/1.1\r\n" \
        "Content-Type: text/xml\r\n" \
        "User-Agent: AsyncXMLRPC/Python\r\n" \
        "Host: %s\r\n" \
        "Content-length: %d\r\n" \
        "%s%s" % (self.host, len(request_body), keep_alive, request_body)
    #If we have data to send than we will be waiting on a response
    self.waiting_on_response = True
    self.deferred = Deferred.Deferred()
    return self.deferred

  def writable(self):
    # Ready to send
    return self.tx_buf


class Keep_Alive_Transport(xmlrpclib.Transport):
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
  def __init__(self, *args, **kwargs):
    xmlrpclib.Transport.__init__(self, *args, **kwargs)
    self.sessions = []

  def on_close(self, session):
    self.sessions.remove(session)

  def request(self, host, handler, request_body, verbose=0):
    """Send a complete request, and parse the response.
       Return a Deferred response object.       
    """
    #From the comments in the Transport class it appears that there will only be one host
    session = None
    for session in self.sessions:
      if not session.waiting_on_response:
        break

    if session is None or session.waiting_on_response:
      session = Keep_Alive_Session(host, self, self.on_close)
      self.sessions.append(session)

    return (session.send_request(request_body),)


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
      #Try to start sending once connected
      self.handle_write()

    def handle_read(self):
      rcvData = self.recv(4096)
      if rcvData:
        #log.debug("Received data: %s" % rcvData)
        self.rxBuf += rcvData
        if self.rxBuf.find("</methodResponse>") > -1:
          resp = httplib.HTTPResponse(HttpLibFakeSocket(cStringIO.StringIO(self.rxBuf)))
          resp.begin()
          if resp.status == httplib.OK:
            self.dispatchXmlResponse(resp.fp.read())
            assert resp.will_close
          else:
            self.deferred.runErrback(xmlrpclib.ProtocolError(self.host, str(resp.status), resp.reason, {}))
          self.close()
        else:
          log.debug("methodResponse not found")

    def writable(self):
      # Ready to send
      return self.txBuf

    def handle_write(self):
      numSent = self.send(self.txBuf)
      #if __debug__ and numSent:
        #log.debug("Sent data: %s" % self.txBuf[:numSent])
      self.txBuf = self.txBuf[numSent:]

    def handle_close(self):
      #This seems to be only called when the other side closes the connection
      self.close()
      self.deferred.runErrback(xmlrpclib.ProtocolError(self.host, '500', 'Socket Closed', {}))

    def handle_error(self):
      t, v, nil = sys.exc_info()
      self.deferred.runErrback(
        xmlrpclib.ProtocolError(self.host, '500',
                                "Socket Error (%s:%s)" % (t, v) , {})
      )
      self.close()

    def handle_expt(self):
      #From EffBot:
      #Called when a connection fails (Windows), or when out-of-band data arrives (Unix)

      #Since we aren't doing OOB
      err = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
      if err:
        msg = os.strerror(err)
        if msg == 'Unknown error':
          msg += ' - '
          msg += str(err)
        self.deferred.runErrback(socket.error((err, msg)))
        log.error(msg) #Using error instead of exception since there is not a stack trace
        self.close()

    def dispatchXmlResponse(self, response):
      p, u = self.parser
      try:
        #log.debug("Dispatching response")
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

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG, format='%(asctime)s:%(msecs)03d %(levelname)-8s %(name)-8s %(message)s', datefmt='%H:%M:%S')

  #srv_async = xmlrpclib.ServerProxy("http://192.168.1.66:8080", Keep_Alive_Transport())
  srv_async = xmlrpclib.ServerProxy("http://localhost:8080", Keep_Alive_Transport())

  def on_result(result):
    print result
    srv_async.gatewayVersion()

  srv_async.gatewayVersion().addCallbacks(on_result)

  while True:
    asyncore.poll(0.001)
