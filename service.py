from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource
from twisted.web import static,server,vhost,script
from twisted.internet import reactor
from twisted.python import log
import sys,os
import json
import logging

observer = log.PythonLoggingObserver()
observer.start()

core_log = logging.getLogger('twsrv')
sh = log.handlers.StreamHandler()
core_log.addHandler(sh)

root = vhost.NameVirtualHost()

hosts = {
    'blog.deacondesperado.com':('../deacondesperado','server','app')
}

for host in hosts:
    server_name = host
    path,module,app = hosts[host]
    sys.path.append(path)
    exec("from %s import %s" % (module,app))
    log.msg('Setting up host %s', server_name)
    root.addHost(server_name,WSGIResource(reactor,reactor.getThreadPool(),app))

reactor.listenTCP(80,Site(root))
reactor.run()

