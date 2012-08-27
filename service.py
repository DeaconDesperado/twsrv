from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource
from twisted.web import static,server,vhost,script
from twisted.internet import reactor
from twisted.python import log
import sys,os
import json

log.startLogging(sys.stdout)

root = vhost.NameVirtualHost()
ssl_root = vhost.NameVirtualHost()

def setup(configuration):
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


