from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource
from twisted.web import static,server,vhost,script
from twisted.internet import reactor
import sys,os


root = vhost.NameVirtualHost()

hosts = {
    'blog.deacondesperado.com':('../deacondesperado','server','app')
}

for host in hosts:
    server_name = host
    path,module,app = hosts[host]
    sys.path.append(path)
    exec("from %s import %s" % (module,app))

    root.addHost(server_name,WSGIResource(reactor,reactor.getThreadPool(),app))

reactor.listenTCP(80,Site(root))
reactor.run()

