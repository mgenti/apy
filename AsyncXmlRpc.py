#Copyright (c) 2008 David Ewing Mark Guagenti

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


import sys, xmlrpclib, SimpleXMLRPCServer, logging, binascii

import Deferred

from medusa import http_server, logger, status_handler, counter, producers


#Monkey patch for SimpleXMLRPCServer.SimpleXMLRPCDispatcher._marshaled_dispatch to support deferreds
def _marshaled_dispatch(self, data, dispatch_method = None):
    """Dispatches an XML-RPC method from marshalled (XML) data.

    XML-RPC methods are dispatched from the marshalled (XML) data
    using the _dispatch method and the result is returned as
    marshalled data. For backwards compatibility, a dispatch
    function can be provided as an argument (see comment in
    SimpleXMLRPCRequestHandler.do_POST) but overriding the
    existing method through subclassing is the prefered means
    of changing method dispatch behavior.

    Copied from SimpleXMLRPCDispatcher._marshaled_dispatch, except for isinstance(response, Deferred)
    """
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

SimpleXMLRPCServer.SimpleXMLRPCDispatcher._marshaled_dispatch = _marshaled_dispatch


class MedusaXmlRpcHandler(SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
    """Gets installed into Medusa http_server to handle XML-RPC requests"""
    def __init__(self, logger_object=None, logResponses=True, logRequests=True):
        SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self, allow_none=True, encoding=None)
        self.requestCntr = counter.counter()
        self.logger = logger_object
        self.logRequests = logRequests
        self.logResponses = logResponses
        self.closeCallbacks = []

    def dispatchRequest(self, data, collector):
        #Called by a collector
        assert isinstance(collector, MedusaXmlRpcCollector)

        if self.logRequests:
            try:
                params, method = xmlrpclib.loads(data)
                msg = '%s(' % (method)
                for param in params:
                    if isinstance(param, xmlrpclib.Binary):
                        msg += "%s, " % (binascii.hexlify(param.data))
                    else:
                        msg += "%s, " % (param)
                self.logger.log("%s)" % (msg))
            except:
                pass

        response = self._marshaled_dispatch(data)
        if isinstance(response, Deferred.Deferred):
            response.addCallbacks(collector.marshalAndSendResponse)

            def onClose(self=self, channel=collector.request.channel, deferred=response):
                channel.close()
                for callback in self.closeCallbacks:
                    try:
                        callback(deferred)
                    except:
                        self.logger.log("An error occurred while notifying a callback of a close event")

            collector.request.channel.handle_close = onClose
        else:
            # got a valid XML RPC response
            collector.sendResponse(response)

    def handle_request (self, request):
        #Called by medusa http_server
        assert isinstance(request, http_server.http_request)

        request.split_uri()

        if request.command.upper() == 'POST':
            request.collector = MedusaXmlRpcCollector(self, request, self.logger, self.logResponses)
            self.requestCntr.increment()
        else:
            request.error(400)

    def match(self, request):
        #Called by medusa http_server
        assert isinstance(request, http_server.http_request)

        if request.uri[:5] in ('/RPC2', '/'):
            return True

        return False

    def registerCloseCallbacks(self, callback):
        """
        Register for callbacks when a socket gets closed

        callback -- A callable expecting a single parameter filled in with a deferred
        """
        if callable(callback):
            self.closeCallbacks.append(callback)

    def status(self):
        return producers.simple_producer (
                '<li>XML-RPC <b>Requests</b> : %s' % self.requestCntr
                )


class MedusaXmlRpcCollector(object):
    def __init__(self, handler, request, logger_object=None, logResponses=True):
        assert isinstance(handler, MedusaXmlRpcHandler)
        assert isinstance(request, http_server.http_request)
        self.handler = handler
        self.request = request
        self.data = []
        self.logger = logger_object
        self.logResponses = logResponses

        # make sure there's a content-length header
        cl = request.get_header('content-length')

        if not cl:
            request.error(411)
        else:
            cl = int(cl)
            # using a 'numeric' terminator
            self.request.channel.set_terminator(cl)

    def collect_incoming_data(self, data):
        self.data.append(data)

    def found_terminator(self):
        # set the terminator back to the default
        self.request.channel.set_terminator('\r\n\r\n')
        self.handler.dispatchRequest("".join(self.data), self)

    def marshalAndSendResponse(self, response, methodresponse=True):
        if methodresponse == 1:
            response = (response,)
        response = xmlrpclib.dumps(response, methodresponse=methodresponse, 
                                   allow_none=True, encoding=None)
        self.sendResponse(response)

    def sendResponse(self, response):
        self.request['Content-Type'] = 'text/xml'
        self.request.push(response)
        self.request.done()
        if self.logResponses and self.logger is not None:
            self.logger.log(response)


class HttpXmlRpcServer(object):
    def __init__(self, addr, logHttp=True, logResponses=True, logRequests=True, status=False):
        if not logHttp:
            _level = logging.ERROR
        else:
            _level = logging.INFO

        self.httpSrv = http_server.http_server(addr[0], addr[1], logger_object=logger.python_logger(level=_level))
        self.xmlRpcDispatcher = MedusaXmlRpcHandler(logger_object=logger.python_logger(level=_level), logRequests=logRequests, logResponses=logResponses)
        self.httpSrv.install_handler(self.xmlRpcDispatcher)
        if status:
            sh = status_handler.status_extension([self.httpSrv, self.xmlRpcDispatcher])
            self.httpSrv.install_handler(sh)


def _test(scheduler):
    class testMethods(object):
        def __init__(self, scheduler):
            self.scheduler = scheduler
            self.deferred = Deferred.Deferred()

        def printer(self, text):
            print text
            return text

        def printNow(self, text):
            print text
            self.deferred(text)

        def printLater(self, text, later=0.0):
            self.scheduler.schedule(later, self.printNow, text)
            self.deferred = Deferred.Deferred()
            return self.deferred

        def stopLoop(self, *args):
            global looping
            looping = False


    import AsyncXMLRPCTransport

    srv = HttpXmlRpcServer(('localhost', 8080))
    srv.xmlRpcDispatcher.register_instance(testMethods(scheduler))

    client = xmlrpclib.ServerProxy("http://localhost:8080", AsyncXMLRPCTransport.AsyncXMLRPCTransport())
    scheduler.schedule(0.0, client.printer, "test")
    scheduler.schedule(0.2, client.printLater, "test2", 0.2)
    scheduler.schedule(0.5, client.stopLoop)


if __name__ == '__main__':
    global looping

    import asyncore
    import EventScheduler

    scheduler = EventScheduler.EventScheduler()
    _test(scheduler)
    looping = True

    while looping:
        asyncore.poll(0.001)
        scheduler.poll()

    #Some timing code: (last we got 0.003417978594)
    #import timeit


    #setup = """\
    #from xmlrpclib import ServerProxy, Error

    #server = ServerProxy('http://localhost:8080')
    #"""

    #t = timeit.Timer(stmt="server.printer('test')", setup=setup)

    #print t.timeit(number=100000)/100000
