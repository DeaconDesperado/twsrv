# Twisted WSGI Virtual Hosts

A simple example of using Twisted's virtual hosts handler to host multiple WSGI instances for maximum performance.

The service defines hosts as a simple json dictionary that is decoded to split off wsgi instances on several different domains.

This can be used with twistd as a simpler alternative to apache/mod_wsgi where threading is a concern.
