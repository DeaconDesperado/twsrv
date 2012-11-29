"""
Parses default-php.ini for variables, and gives metadata.

Not really used in any interesting way currently.
"""
import os

php_ini_location = os.path.join(os.path.dirname(__file__),
                                'default-php.ini')

f = open(php_ini_location)

class Option(object):

    def __init__(self, name, section, default, description):
        self.name = name
        self.default = default
        self.description = description
        self.section = section

options = []
options_by_name = {}

show_ignored = False

def read_data():
    last_description = []
    last_section = None
    for line in f:
        line = line.strip()
        if not line:
            if show_ignored and last_description:
                print 'ignoring description:'
                print '\n'.join(['  '+l for l in last_description])
            last_description = []
            continue
        if line.startswith('['):
            line = line[1:]
            if line.endswith(']'):
                line = line[:-1]
            line = line.strip()
            last_section = line
            last_description = []
            continue
        if line.startswith(';'):
            line = line.strip('; ')
            if last_description or line:
                last_description.append(line)
            continue
        name, value = line.split('=', 1)
        name = name.strip()
        value = value.strip()
        op = Option(name, last_section, value, '\n'.join(last_description))
        last_description = []
        options.append(op)
        options_by_name[op.name] = op

if __name__ == '__main__':
    import sys
    last_section = None
    if '-v' in sys.argv[1:]:
        show_ignored = True
    read_data()

    for op in options:
        if last_section != op.section:
            print '\n\n[%s]\n' % op.section
            last_section = op.section
        print '%s (default: %s)' % (op.name, op.default or 'none')
        if op.description:
            print '\n'.join(
                ['  '+l for l in op.description.splitlines()])
            print

else:
    read_data()
