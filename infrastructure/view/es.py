'''
An elasticsearch query pass-through.
Has auth control, so it is better than exposing your ES index directly.
'''

import requests

from flask import Blueprint, Response, stream_with_context, abort, make_response
from flask.ext.login import current_user

from infrastructure import accounts as accounts


blueprint = Blueprint('es', __name__)
    

@blueprint.route('/backups')
@blueprint.route('/backups/<path:path>', methods=['GET','PUT','POST','DELETE'])
def backups():
    if request.method == 'GET':
        pass # show the backups settings for indices the user has permission to know about
    elif request.method == 'POST':
        pass # trigger a backup if the user has permission
    elif request.method == 'PUT':
        pass # add an index to the backup schedule
    elif request.method == 'DELETE':
        pass # remove an index from the backup schedule


@blueprint.route('/stream/<index>/<itype>/<key>')
def stream(index,itype,key,size=1000,raw=False):
    # check user permissions to the stream route
    if not isinstance(key,list):
        keys = key.split(',')
    else:
        keys = key

    qry = {'query':{'match_all':{}}}
    if 'q' in request.values:
        q = request.values['q']
        if not q.endswith("*"): q += "*"
        if not q.startswith("*"): q = "*" + q
    elif 'source' in request.values:
        qry = source
    elif request.json:
        qry = request.json
    
    qry['size'] = 0
    qry['facets'] = {}
    for ky in keys:
        qry['facets'][ky] = {"terms":{"field":ky+app.config['FACET_FIELD'],"order":request.values.get('order','term'), "size":request.values.get('size',size)}}
    
    r = requests.post(app.config['ES_URL'] + '/' + index + '/' + key, data=qry)
    
    res = []
    if request.values.get('counts',False):
        for k in keys:
            res = res + [[i['term'],i['count']] for i in r.json()['facets'][k]["terms"]]
    else:
        for k in keys:
            res = res + [i['term'] for i in r.json()['facets'][k]["terms"]]

    if raw:
        return res
    else:
        resp = make_response( json.dumps(res) )
        resp.mimetype = "application/json"
        return resp


# just a shortcut to the _search endpoint
@blueprint.route('/query/<path:path>', methods=['GET','POST'])
def query():
    return communicate(request, path + '/_search')

    
@blueprint.route('/<path:path>', methods=['GET','POST','PUT','DELETE'])
@blueprint.route('/', methods=['GET','POST','PUT','DELETE'])
def es():
    if not verify(user,path=path,action=request.method):
        abort(401)
    else:
        return communicate(request,path,stream=True)


def communicate(request,path,stream=False):
    if request.method == 'GET':
        req = requests.get(app.config['ES_URL'] + path, headers=request.headers, data=request.values, stream=stream)
    elif request.method == 'POST':
        values = request.json if request.json else request.values
        req = requests.post(app.config['ES_URL'] + path, headers=request.headers, data=values, stream=stream)
    elif request.method == 'PUT':
        values = request.json if request.json else request.values
        req = requests.put(app.config['ES_URL'] + path, headers=request.headers, data=values, stream=stream)
    elif request.method == 'DELETE':
        req = requests.delete(app.config['ES_URL'] + path, headers=request.headers, stream=stream)

    if stream:
        return Response(stream_with_context(req.iter_content()), content_type = req.headers['content-type'])
    else:
        return req.json()


