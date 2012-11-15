from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource
from twisted.web import static,server,vhost,script
from twisted.web.util import Redirect,redirectTo
from twisted.internet import reactor
from twisted.python import log
from twisted.internet.ssl import ContextFactory
import sys,os
import json
from OpenSSL.SSL import Context,TLSv1_METHOD
import OpenSSL
from copy import deepcopy
import re
import threading

root = vhost.NameVirtualHost()

class SSLFactory(ContextFactory):
    
    def __call__(self,connection):
        try:
            servername = re.sub('^[^.]*\.(?=\w+\.\w+$)','',connection.get_servername())
            key,cert = self.certificates[servername]
        except KeyError as e:
            print e
        except Exception as e:
            print e
        new_context = Context(TLSv1_METHOD)
        new_context.use_privatekey_file(key)
        new_context.use_certificate_file(cert)
        connection.set_context(new_context)

    def setCerts(self,config):
        self.certificates = {}
        for host in config['hosts']:
            try:
                self.certificates[host] = config['hosts'][host]['ssl']
            except KeyError:
                pass

    def getContext(self):
        server_context = Context(TLSv1_METHOD)
        server_context.set_tlsext_servername_callback(self)
        return server_context

class DomainRedirector(Redirect):

    def render(self,request):
        host_port = request.getHost().port
        if host_port == 80:
            host_port = ''
        else:
            host_port = ':%s' % host_port
        return redirectTo('%s%s%s' % (self.url,host_port,request.path),request)

def setup(configuration):
    ssl_creator = SSLFactory()
    ssl_creator.setCerts(configuration)
    host_def = configuration.get('hosts',{})
    for host in host_def:
        server_name = host
        path,package,module,app = (host_def[host]['path'],host_def[host]['package'],host_def[host]['module'],host_def[host]['app'])
        try:
            aliases = host_def[host]['aliases']
        except KeyError:
            aliases = False

        ssl = bool(host_def[host].get('secure',False))
        sys.path.append('/srv')
        sys.path.append(str(path))
        exec("import %s.%s" % (package,module))
        app = getattr(getattr(locals()[package],module),app)
        log.msg('Setting up host %s' % server_name)
        if aliases:
            #redirect any aliased hosts to the intended
            for alias in aliases:
                aliased = '%s.%s' % (alias,server_name)
                log.msg('Setting up alias %s' % aliased)
                root.addHost(aliased,Site(DomainRedirector(str('http://%s' % server_name))))
            if ssl:
                root.addHost(aliased,Site(DomainRedirector(str('https://%s' % server_name))))
        if ssl:
            ssl_root.addHost(server_name,WSGIResource(reactor,reactor.getThreadPool(),app))
        
        root.addHost(server_name,WSGIResource(reactor,reactor.getThreadPool(),app))
        
    reactor.listenTCP(configuration.get('http_port',80),Site(root))
    reactor.listenSSL(configuration.get('ssl_port',443),Site(root),ssl_creator)
    reactor.run()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('config_json')

    args = parser.parse_args()
    try:
        json_file = open(args.config_json)
        config = json.loads(json_file.read())
        log.startLogging(sys.stdout)
        setup(config)
    except IOError:
        print 'Could not find config file %s' % args.config_json
