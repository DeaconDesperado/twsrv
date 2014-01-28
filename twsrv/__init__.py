from twisted.web.server import Site
from twisted.web.static import File
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
from shared_root import SharedRootWSGI
from wphp import PHPApp
from reloader import reloader
import logging
from reverse_proxy import ReverseProxy
from twisted.python.logfile import DailyLogFile


version = "0.9"
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
    log.startLogging(DailyLogFile.fromFullPath(configuration.get('log_path','dcnsrv.log')))
    ssl_creator = SSLFactory()
    ssl_creator.setCerts(configuration)
    rload = configuration.get('reloader',False)
    host_def = configuration.get('hosts',{})
    for host in host_def:
        server_name = host
        path,package,module,app = (host_def[host].get('path',None),host_def[host].get('package'),host_def[host].get('module'),host_def[host].get('app'))
        try:
            aliases = host_def[host]['aliases']
        except KeyError:
            aliases = False

        ssl = bool(host_def[host].get('secure',False))
        sys.path.append('/srv')

        log.msg('Setting up host %s' % server_name)
        if host_def[host].get('type','wsgi') == 'wsgi':
            sys.path.append(str(path))
            if package and module:
                exec("import %s.%s" % (package,module))
                app = getattr(getattr(locals()[package],module),app)
            elif package:
                exec("import %s" % package)
                app = getattr(locals()[package],app)
            wsgi_resource = WSGIResource(reactor,reactor.getThreadPool(),app)
            host_resource = SharedRootWSGI()
            host_resource.setApp(wsgi_resource)
        elif host_def[host].get('type','wsgi') == 'dir':
            log.msg('path: %s' % path)
            host_resource = File(str(path))
        elif host_def[host].get('type','wsgi')=='php':
            log.msg('path: %s' % path)
            app = PHPApp(str(path),php_options=host_def[host].get('opts',{}),logger='twisted',log_level=logging.DEBUG)
            host_resource = WSGIResource(reactor,reactor.getThreadPool(),app)
        elif host_def[host].get('type','wsgi')=='rev_proxy':
            proxy_host,proxy_port = (str(host_def[host].get('proxy_host',host)),host_def[host].get('port',80))
            print proxy_host,proxy_port,path
            host_resource = ReverseProxy(proxy_host,host_def[host].get('port',80),str(path),reactor)

        static_paths = host_def[host].get('static_paths',{})
        for s_route,s_path in static_paths.items():
            host_resource.putChild(s_route.strip('/'),File(str(s_path)))

        if aliases:
            #redirect any aliased hosts to the intended
            for alias in aliases:
                aliased = '%s.%s' % (alias,server_name)
                log.msg('Setting up alias %s' % aliased)
                root.addHost(aliased,Site(DomainRedirector(str('http://%s' % server_name))))
            if ssl:
                log.msg('Setting up https alias for %s' % aliased)
                root.addHost(aliased,Site(DomainRedirector(str('https://%s' % server_name))))
        
        root.addHost(server_name,host_resource)
   
    http_site = Site(root)

    reactor.listenTCP(configuration.get('http_port',80),http_site)
    reactor.listenSSL(configuration.get('ssl_port',443),http_site,ssl_creator)
    if rload:
        reactor.run(installSignalHandlers=0)
    else:
        reactor.run()


def main():
    import argparse
    from reloader import reloader
    parser = argparse.ArgumentParser()
    parser.add_argument('config_json')
    args = parser.parse_args()
    try:
        json_file = open(args.config_json)
        print json_file
        config = json.loads(json_file.read())
        rload = config.get('reloader',False)
        setup(config)
    except IOError, e:
        print e
        print 'Could not find config file %s' % args.config_json
