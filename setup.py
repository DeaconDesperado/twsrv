#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright © 2012 Spotify Ltd

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

NAME = "dcnsrv"
VERSION = "0.9"

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name=NAME,
    version=VERSION,
    author=[
        "Mark Grey",
    ],
    author_email=[
        "mark.asperia@gmail.com",
    ],
    license="BSD",
    packages=[
        "twsrv",
        "wphp"
    ],
    scripts=[
        "bin/dcnsrv"
    ],
    install_requires=required,
    dependency_links = [
        "http://svn.pythonpaste.org/Paste/wphp/trunk#egg=wphp-dev"
    ],
    extras_require = {
        "php_support": ["wphp"]
    },
    entry_points={
        "console_scripts":[
            "dcnsrv=twsrv:main"
            ]
        }
)
