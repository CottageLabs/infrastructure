'''
An auth-controlled access and retrieval mechanism for file storage
'''

from flask import Blueprint, request, abort, make_response

from infrastructure.core import app, rjson
from infrastructure.storage import Storage as Storage


blueprint = Blueprint('storage', __name__)


@rjson
@blueprint.route('/<path:path>', methods=['GET','POST','PUT','DELETE'])
def storage(path=None):
    if path is None:
        return store.listing()
    else:
        uid = path.split('/')[-1]
        store = Storage(uid=uid)
    if request.method == 'DELETE' or ( request.method == 'POST' and request.form.get('submit',False).lower() == 'delete' ):
        return store.delete()
    elif request.method in ['POST','PUT'] or (request.method == 'GET' and request.args.get('url',False)):
        vals = request.json if request.json else request.values
        if request.data:
            data = request.data
        if request.data: vals['data'] = request.data
        return store.store(**vals)
    elif request.method == 'GET':
        # NOTE: for anything that is publicly accessible it would be best to use the web server layer
        # to serve or redirect to the files. Just do this simply by putting public stuff under a /public route.
        # Otherwise check the permission and serve the file if allowed.
        try:
            return store.listing(path)
        except:
            try:
                resp = make_response(store.retrieve(path).read())
                response.headers["Content-type"] = "image"
                return response
            except:
                abort(404)
    else:
        abort(401)


        
        
        

    
    