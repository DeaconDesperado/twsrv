from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource
from twisted.web import static,server,vhost,script
from twisted.internet import reactor
from twisted.python import log
from twisted.internet.ssl import ContextFactory
import sys,os
import json
from OpenSSL.SSL import Context,TLSv1_METHOD
import OpenSSL
from wsgi_dispatcher import SubdomainDispatcher
from copy import deepcopy
import re

log.startLogging(sys.stdout)
root = vhost.NameVirtualHost()

class SSLFactory(ContextFactory):
    
    def __call__(self,connection):
        try:
            servername = re.sub('^[^.]*\.(?=\w+\.\w+$)','',connection.get_servername())
            print 'Servername: %s' % servername 
            key,cert = self.certificates[servername]
        except KeyError as e:
            print e
        except Exception as e:
            print e
        new_context = Context(TLSv1_METHOD)
        new_context.use_privatekey_file(key)
        new_context.use_certificate_file(cert)
        connection.set_context(new_context)
        print 'returning context'

    def setCerts(self,config):
        self.certificates = {}
        for host in config:
            try:
                self.certificates[host] = config[host]['ssl']
            except KeyError:
                pass

    def getContext(self):
        print 'getting context'
        server_context = Context(TLSv1_METHOD)
        #server_context.use_privatekey_file('/home/mark/projects/myopia_placehold/server.key')
        #server_context.use_certificate_file('/home/mark/projects/myopia_placehold/server.crt')
        server_context.set_tlsext_servername_callback(self)
        return server_context

def setup(configuration):
    ssl_creator = SSLFactory()
    ssl_creator.setCerts(configuration)
    for host in configuration:
        server_name = host
        path,package,module,app = (configuration[host]['path'],configuration[host]['package'],configuration[host]['module'],configuration[host]['app'])
        try:
            aliases = configuration[host]['aliases']
        except KeyError:
            aliases = False

        ssl = bool(configuration[host].get('secure',False))
        sys.path.append('/srv')
        sys.path.append(str(path))
        log.msg(sys.path)
        exec("import %s.%s" % (package,module))
        app = getattr(getattr(locals()[package],module),app)
        log.msg('Setting up host %s' % server_name)
        if aliases:
            #host is aliased
            for alias in aliases:
                aliased = '%s.%s' % (alias,server_name)
                log.msg('Setting up alias %s' % aliased)
                root.addHost(aliased,WSGIResource(reactor,reactor.getThreadPool(),app))
            if ssl:
                ssl_root.addHost(aliased,WSGIResource(reactor,reactor.getThreadPool(),app))

        if ssl:
            ssl_root.addHost(server_name,WSGIResource(reactor,reactor.getThreadPool(),app))
        
        root.addHost(server_name,WSGIResource(reactor,reactor.getThreadPool(),app))
        
    reactor.listenTCP(80,Site(root))
    reactor.listenSSL(443,Site(root),ssl_creator)
    reactor.run()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('config_json')

    args = parser.parse_args()
    try:
        json_file = open(args.config_json)
        config = json.loads(json_file.read())
        setup(config)
    except IOError:
        print 'Could not find config file %s' % args.config_json
