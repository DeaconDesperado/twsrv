# (c) 2005 Ian Bicking and contributors; written for Paste (http://pythonpaste.org)
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
#
import threading
import os
import socket
import logging
import atexit
import signal
import time
import posixpath
import subprocess
from paste import fileapp
from paste.request import construct_url
from paste.httpexceptions import HTTPMovedPermanently, HTTPNotFound
from wphp import fcgi_app

here = os.path.dirname(__file__)
default_php_ini = os.path.join(here, 'default-php.ini')

class PHPApp(object):

    def __init__(self, base_dir, 
                 php_script='php-cgi',
                 php_ini=None,
                 php_options=None,
                 fcgi_port=None,
                 search_fcgi_port_starting=10000,
                 logger='wphp',
                 log_level=None):
        """
        Create a WSGI wrapper around a PHP application.

        `base_dir` is the root of the PHP application.  This
        contains .php files, and potentially other static files. (@@:
        Currently there is no way to indicate files that should not be
        served, like ``.inc`` files or certain directories)

        `php_script` is the path to the ``php-cgi`` script you want
        to use.  By default it just looks on the ``$PATH`` for that
        file.

        `php_ini` is the path to the ``php.ini`` file you want to use.
        An example (taken from the default PHP file) is in
        ``wphp/default-php.ini``.  This allows you to customize the
        language environment that the PHP files run in.

        `php_options` is a dictionary of config-name: value, of
        specific overrides for PHP options.  For instance,
        ``{'magic_quotes_gpc': 'Off'}`` will turn off magic quotes.

        PHP is started as a long-running FastCGI process.  PHP (from
        what I can tell) only supports listening over IP sockets, so
        we must get a port for it.  You may provide a specific port
        (with `fcgi_port`) or give a starting port number (default
        10000), and the first free port will be used.
        """
        self.base_dir = base_dir
        self.fcgi_port = fcgi_port
        self.php_script = php_script
        self.php_ini = php_ini
        if php_options is None:
            php_options = {}
        self.php_options = php_options
        self.search_fcgi_port_starting = search_fcgi_port_starting
        if log_level:
            log_level = logging._levelNames[log_level]
        if logger == 'stdout':
            # Special case...
            logger = logging.getLogger('wphp')
            console = logging.StreamHandler()
            #console.setLevel(log_level)
            console.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
            logger.addHandler(console)
        if isinstance(logger, basestring):
            logger = logging.getLogger(logger)
        if log_level:
            logger.setLevel(log_level)
        
        self.logger = logger
        
        self.lock = threading.Lock()
        self.child_pid = None
        self.fcgi_app = None

    # These are the filenames of "index" files:
    index_names = ['index.html', 'index.htm', 'index.php']

    def __call__(self, environ, start_response):
        if 'REQUEST_URI' not in environ:
            # PHP likes to have this variable
            environ['REQUEST_URI'] = (
                environ.get('SCRIPT_NAME', '')
                + environ.get('PATH_INFO', ''))
            if environ.get('QUERY_STRING'):
                environ['REQUEST_URI'] += '?'+environ['QUERY_STRING']
        if self.child_pid is None:
            if environ['wsgi.multiprocess']:
                environ['wsgi.errors'].write(
                    "wphp doesn't support multiprocess apps very well yet")
            self.create_child()
        path_info = environ.get('PATH_INFO', '').lstrip('/')
        full_path = os.path.join(self.base_dir, path_info)
        if (os.path.isdir(full_path)
            and not environ.get('PATH_INFO', '').endswith('/')):
            # We need to do a redirect
            new_url = construct_url(environ) + '/'
            redir = HTTPMovedPermanently(headers=[('location', new_url)])
            return redir.wsgi_application(environ, start_response)
        script_filename, path_info = self.find_script(self.base_dir, path_info)
        if script_filename is None:
            exc = HTTPNotFound()
            return exc(environ, start_response)
        script_name = posixpath.join(environ.get('SCRIPT_NAME', ''), script_filename)
        script_filename = posixpath.join(self.base_dir, script_filename)
        environ['SCRIPT_NAME'] = script_name
        environ['SCRIPT_FILENAME'] = os.path.join(self.base_dir, script_filename)
        environ['PATH_INFO'] = path_info
        ext = posixpath.splitext(script_filename)[1]
        if ext != '.php':
            if self.logger:
                self.logger.debug(
                    'Found static file at %s',
                    script_filename)
            app = fileapp.FileApp(script_filename)
            return app(environ, start_response)
        if self.logger:
            self.logger.debug(
                'Found script at %s', script_filename)
        if (environ['REQUEST_METHOD'] == 'POST'
            and not environ.get('CONTENT_TYPE')):
            environ['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        app_iter = self.fcgi_app(environ, start_response)
        return app_iter

    def find_script(self, base, path):
        """
        Given a path, finds the file the path points to, and the extra
        portion of the path (PATH_INFO).
        """
        
        full_path = os.path.join(base, path)
        if os.path.exists(full_path) and os.path.isdir(full_path):
            for index_name in self.index_names:
                found = os.path.join(full_path, index_name)
                if os.path.exists(found):
                    return found, ''
            if self.logger:
                self.logger.info(
                    'No index file in directory %s',
                    full_path)
            return None, None
            
        path_info = ''
        orig_path = path
        while 1:
            full_path = os.path.join(base, path)
            if not os.path.exists(full_path):
                if not path:
                    return None, None
                path_info = '/' + os.path.basename(path) + path_info
                path = os.path.dirname(path)
            elif os.path.isdir(full_path):
                if self.logger:
                    self.logger.info(
                        'Traversed up to directory (404) for %r', '/'+orig_path)
                return None, None
            else:
                return path, path_info

    def create_child(self):
        """
        Creates the PHP subprocess, with some locking and whatnot, and
        creates the WSGI application wrapper around that.
        """
        self.lock.acquire()
        try:
            if self.child_pid:
                return
            if self.logger:
                self.logger.info('Spawning PHP process')
            if self.fcgi_port is None:
                self.fcgi_port = self.find_port()
            self.spawn_php(self.fcgi_port)
            self.fcgi_app = fcgi_app.FCGIApp(
                connect=('127.0.0.1', self.fcgi_port),
                filterEnviron=False)
        finally:
            self.lock.release()

    def spawn_php(self, port):
        """
        Creates a PHP process that listens for FastCGI requests on the
        given port.
        """
        cmd = [self.php_script,
               '-b',
               '127.0.0.1:%s' % self.fcgi_port]
        if self.php_ini:
            cmd.extend([
                '-c', self.php_ini])
        for name, value in self.php_options.items():
            cmd.extend([
                '-d', '%s=%s' % (name, value)])
        env = os.environ.copy()
        env['PHP_FCGI_CHILDREN'] = '1'
        proc = subprocess.Popen(cmd, env=env)
        self.child_pid = proc.pid
        if self.logger:
            self.logger.info(
                'PHP process spawned in PID %s, port %s'
                % (self.child_pid, self.fcgi_port))
        atexit.register(self.close)
        # PHP doesn't start up *quite* right away, so we give it a
        # moment to be ready to accept connections
        while 1:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(('127.0.0.1', self.fcgi_port))
            except socket.error, e:
                pass
            else:
                sock.close()
                return

    def find_port(self):
        """
        Finds a free port.
        """
        host = '127.0.0.1'
        port = self.search_fcgi_port_starting
        while 1:
            s = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind((host, port))
            except socket.error, e:
                port += 1
            else:
                s.close()
                return port

    def close(self):
        """
        Kills the PHP subprocess.  Registered with atexit, so the
        subprocess is killed when this process dies.
        """
        # @@: Note, in a multiprocess setup this cannot
        # be handled this way
        if self.child_pid:
            if self.logger:
                self.logger.info(
                    "Killing PHP subprocess %s"
                    % self.child_pid)
            os.kill(self.child_pid, signal.SIGKILL)

def make_app(global_conf, **kw):
    """
    Create a PHP application (with Paste Deploy).
    """
    if 'fcgi_port' in kw:
        kw['fcgi_port'] = int(kw['fcgi_port'])
    if 'search_fcgi_port_starting' in kw:
        kw['search_fcgi_port_starting'] = int(kw['search_fcgi_port_starting'])
    kw.setdefault('php_options', {})
    for name, value in kw.items():
        if name.startswith('option '):
            optname = name[len('option '):].strip()
            kw['php_options'][optname] = value
            del kw[name]
    if 'base_dir' not in kw:
        raise ValueError(
            "base_dir option is required")
    return PHPApp(**kw)

