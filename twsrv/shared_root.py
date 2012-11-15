from twisted.web.resource import Resource

class SharedRootWSGI(Resource):
    WSGI = None

    def setApp(self,app):
        self.WSGI = app

    def getChild(self,child,request):
        request.prepath.pop()
        request.postpath.insert(0,child)
        return self.WSGI
