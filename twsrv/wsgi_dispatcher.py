from threading import Lock

class SubdomainDispatcher():

    def __init__(self,domain,create_app):
        self.domain = domain
        self.create_app = create_app
        self.lock = Lock()
        self.instances = []

    def get_application(self,host):
        host = host.split(':')[0]
        assert host.endswith(self.domain), 'Conf error'
        subdomain = host[:-len(self.domain)].rstrip('.')
        with self.lock:
            app = self.isntances.get(subdomain)
            if app is None:
                app = self.create_app(subdomain)
                self.instances[subdomain] = app
            return app

    def __call__(self,environ,start_response):
        app = self.get_application(environ['HTTP_HOST'])
        return app(environ,start_response)
