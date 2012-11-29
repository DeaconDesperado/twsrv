import json
from twsrv import setup
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
