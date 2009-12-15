#Copyright (c) 2009 Mark Guagenti

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
__docformat__ = "plaintext en"


import asyncore
import socket


class MulticastListener(asyncore.dispatcher):
    """Start a listener for multicast packets"""
    def __init__(self, mcast_addr, port, loopback=1):
        self.mcast_addr = mcast_addr
        asyncore.dispatcher.__init__(self)
        self.intf = socket.gethostbyname(socket.gethostname())

        #Setup socket
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass #Not all versions of Python have SO_REUSEPORT
        #self.socket.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, 255) # Don't think we need this since we are just a listener
        self.socket.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, loopback)

        #Zeroconf has try around next line
        self.bind(('', port))

        self.socket.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.intf) + socket.inet_aton('0.0.0.0'))
        self.socket.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(mcast_addr) + socket.inet_aton('0.0.0.0'))

    def handle_close(self):
        self.socket.setsockopt(socket.SOL_IP, socket.IP_DROP_MEMBERSHIP, socket.inet_aton(self.mcast_addr) + socket.inet_aton('0.0.0.0'))
        self.close()

    def handle_connect(self):
        pass

    #def handle_read(self):
        #data = self.recv(8192)
        #if data:
            #print data

    def writable(self):
        return False
