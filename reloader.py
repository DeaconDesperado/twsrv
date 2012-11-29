from werkzeug.serving import reloader_loop,restart_with_reloader
import thread
import functools
import os
import sys

def reloader(main_func,extra_files=None,interval=1):
    @functools.wraps(main_func)
    def run_with_reloader(*args):
        """Run the given function in an independent python interpreter."""
        import signal
        signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            thread.start_new_thread(main_func, (args))
            try:
                reloader_loop(extra_files, interval)
            except KeyboardInterrupt:
                return
        try:
            sys.exit(restart_with_reloader())
        except KeyboardInterrupt:
            pass
    return run_with_reloader

