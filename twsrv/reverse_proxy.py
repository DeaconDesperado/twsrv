from twisted.web.proxy import ReverseProxyResource
import logging

class ReverseProxy(ReverseProxyResource):

    def __init__(self,*args,**kwargs):
        ReverseProxyResource.__init__(self,*args,**kwargs)

    def render(self,request):
        if self.port == 80:
            host = self.host
        else:
            host = "%s:%d" % (self.host, self.port)
        request.received_headers['host'] = host
        request.content.seek(0, 0)
        qs = urlparse.urlparse(request.uri)[4]
        if qs:
            rest = self.path + '?' + qs
        else:
            rest = self.path

        clientFactory = self.proxyClientFactoryClass(
        request.method, rest, request.clientproto,
        request.getAllHeaders(), request.content.read(), request)
        self.reactor.connectTCP(self.host, self.port, clientFactory)
        return NOT_DONE_YET
