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

log.startLogging(sys.stdout)
root = vhost.NameVirtualHost()

class SSLFactory(ContextFactory):
    
    def __call__(self,connection):
        try:
            print 'Servername: %s' % connection.get_servername()
            key,cert = self.certificates[connection.get_servername()]
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
        path,module,app = (configuration[host]['path'],configuration[host]['module'],configuration[host]['app'])
        try:
            aliases = configuration[host]['aliases']
        except KeyError:
            aliases = []

        ssl = bool(configuration[host].get('secure',False))
        sys.path.append('/srv')
        sys.path.append(path)
        exec("from %s import %s" % (module,app))
        log.msg('Setting up host %s' % server_name)
        root.addHost(server_name,WSGIResource(reactor,reactor.getThreadPool(),app))
        if ssl:
            ssl_root.addHost(server_name,WSGIResource(reactor,reactor.getThreadPool(),app))
        for alias in aliases:
            aliased = '%s.%s' % (alias,server_name)
            log.msg('Setting up alias %s' % aliased)
            root.addHost(aliased,WSGIResource(reactor,reactor.getThreadPool(),app))

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
