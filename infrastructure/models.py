
from datetime import datetime

from portality.core import app

from portality.dao import DomainObject as DomainObject

import requests
    
from werkzeug import generate_password_hash, check_password_hash
from flask.ext.login import UserMixin


class Account(DomainObject, UserMixin):
    __type__ = 'account'

    @classmethod
    def pull_by_email(cls,email):
        res = cls.query(q='email:"' + email + '"')
        if res.get('hits',{}).get('total',0) == 1:
            return cls(**res['hits']['hits'][0]['_source'])
        else:
            return None

    def set_password(self, password):
        self.data['password'] = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.data['password'], password)
        
    def permission(user=None,path=None,routes=None,service=None,services=None,action=None):
        def _permissionloop(perms,route,action,hierarchic=True):
            allowables = ['GET','POST','PUT','DELETE','*']
            if route.startswith('_'): route = '_'
            allowances = [i.lower() for i in perms.get(route,perms.get('*',[]))]
            mostallowed = 0
            for allowance in allowances:
                if allowables.index(allowance) > mostallowed:
                    mostallowed = allowables.index(allowance)
            if '*' in allowances or action.lower() in allowances:
                return True
            elif hierarchic and allowables.index(action.lower()) <= mostallowed:
                return True
            else:
                return False

        if user is None:
            user = {
                'id': '', # user record ID
                'username': '', # the username of this user NOT REQUIRED BUT MUST BE UNIQUE IF PRESENT
                'email': '', # the email of this user REQUIRED AND MUST BE UNIQUE
                'api_key': '', # NOT REQUIRED BUT MUST BE UNIQUE IF PRESENT. COULD BE SAME AS RECORD ID BUT CANNOT BE ASSUMED TO BE SAME
                'metadata': {}, # general useful user metadata
                'services': {
                    'index': {
                        'permissions': {
                            'default': ['GET','POST','PUT','DELETE','*'],
                            'routes': [
                                {
                                    '*': ['*'],
                                    '_': ['*'],
                                    'example': ['*'],
                                    'example*': ['GET','POST','PUT','DELETE','*']
                                }
                            ]
                        },
                        'metadata': {} # whatever the service wants to store for the user that is not general useful user data
                    }
                }
            }

        if path is not None:
            routes = [i.replace('____________=_=_','/') for i in path.replace('\/','____________=_=_').split('/')]

        if routes is None:
            routes = []

        if service is not None:
            services = [service]
        elif services is None:
            services = []
        elif isinstance(services,string):
            service = services
            services = [services]

        if action is None:
            action = ''

        permitted = []
        userservices = user.get('services',{}).keys()

        # TODO: routes could be comma-separated accessors to particular index types, so need to check comma-separated permissions
        for srv in services:
            if srv not in userservices and '*' not in userservices:
                permitted.append(False)
            else:
                v = False
                for k, route in enumerate(routes):
                    if srv not in userservices: srv = '*'
                    if k < len(user['services'][srv].get('routes',[])):
                        v = _permissionloop(user['services'][srv]['routes'][k],route,action)
                permitted.append(v)

        if service is not None:
            return permitted[0]
        else:
            return permitted









class DomainObject(UserDict.IterableUserDict):
    __type__ = None # set the type on the model that inherits this

    def __init__(self, **kwargs):
        if '_source' in kwargs:
            self.data = dict(kwargs['_source'])
            self.meta = dict(kwargs)
            del self.meta['_source']
        else:
            self.data = dict(kwargs)
            
    @classmethod
    def target(cls):
        t = str(app.config['ELASTIC_SEARCH_HOST']).rstrip('/') + '/'
        t += app.config['ELASTIC_SEARCH_DB'] + '/' + cls.__type__ + '/'
        return t
    
    @classmethod
    def makeid(cls):
        '''Create a new id for data object
        overwrite this in specific model types if required'''
        return uuid.uuid4().hex

    @property
    def id(self):
        return self.data.get('id', None)
        
    @property
    def version(self):
        return self.meta.get('_version', None)

    @property
    def json(self):
        return json.dumps(self.data)

    def save(self):
        if 'id' in self.data:
            id_ = self.data['id'].strip()
        else:
            id_ = self.makeid()
            self.data['id'] = id_
        
        self.data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H%M")

        if 'created_date' not in self.data:
            self.data['created_date'] = datetime.now().strftime("%Y-%m-%d %H%M")
            
        if 'author' not in self.data:
            try:
                self.data['author'] = current_user.id
            except:
                self.data['author'] = "anonymous"

        return requests.post(self.target() + self.data['id'], data=json.dumps(self.data))

    def save_from_form(self,request):
        newdata = request.json if request.json else request.values
        for k, v in newdata.items():
            if k not in ['submit']:
                self.data[k] = v
        return self.save()

    @classmethod
    def bulk(cls, bibjson_list, idkey='id', refresh=False):
        data = ''
        for r in bibjson_list:
            data += json.dumps( {'index':{'_id':r[idkey]}} ) + '\n'
            data += json.dumps( r ) + '\n'
        r = requests.post(cls.target() + '_bulk', data=data)
        if refresh:
            cls.refresh()
        return r.json()


    @classmethod
    def refresh(cls):
        r = requests.post(cls.target() + '_refresh')
        return r.json()


    @classmethod
    def pull(cls, id_):
        '''Retrieve object by id.'''
        if id_ is None:
            return None
        try:
            out = requests.get(cls.target() + id_)
            if out.status_code == 404:
                return None
            else:
                return cls(**out.json())
        except:
            return None

    @classmethod
    def pull_by_key(cls,key,value):
        res = cls.query(q={"query":{"term":{key+app.config['FACET_FIELD']:value}}})
        if res.get('hits',{}).get('total',0) == 1:
            return cls.pull( res['hits']['hits'][0]['_source']['id'] )
        else:
            return None


    @classmethod
    def keys(cls,mapping=False,prefix=''):
        # return a sorted list of all the keys in the index
        if not mapping:
            mapping = cls.query(endpoint='_mapping')[cls.__type__]['properties']
        keys = []
        for item in mapping:
            if mapping[item].has_key('fields'):
                for item in mapping[item]['fields'].keys():
                    if item != 'exact' and not item.startswith('_'):
                        keys.append(prefix + item + app.config['FACET_FIELD'])
            else:
                keys = keys + cls.keys(mapping=mapping[item]['properties'],prefix=prefix+item+'.')
        keys.sort()
        return keys
        
    @classmethod
    def query(cls, recid='', endpoint='_search', q='', **kwargs):
        '''Perform a query on backend.

        :param recid: needed if endpoint is about a record, e.g. mlt
        :param endpoint: default is _search, but could be _mapping, _mlt, _flt etc.
        :param q: maps to query_string parameter if string, or query dict if dict.
        :param terms: dictionary of terms to filter on. values should be lists. 
        :param facets: dict of facets to return from the query.
        :param kwargs: any keyword args as per
            http://www.elasticsearch.org/guide/reference/api/search/uri-request.html
        '''
        if recid and not recid.endswith('/'): recid += '/'
        if isinstance(q,dict):
            query = q
        elif q:
            query = {
                'query': {
                    'bool': {
                        'must': [
                            {'query_string': { 'query': q }}
                        ]
                    }
                }
            }
        else:
            query = {
                'query': {
                    'match_all': {}
                }
            }

        for k,v in kwargs.items():
            if k == '_from':
                query['from'] = v
            else:
                query[k] = v

        if endpoint in ['_mapping']:
            r = requests.get(cls.target() + recid + endpoint)
        else:
            r = requests.post(cls.target() + recid + endpoint, data=json.dumps(query))
        return r.json()

    def accessed(self):
        if 'last_access' not in self.data:
            self.data['last_access'] = []
        try:
            usr = current_user.id
        except:
            usr = "anonymous"
        self.data['last_access'].insert(0, { 'user':usr, 'date':datetime.now().strftime("%Y-%m-%d %H%M") } )
        r = requests.put(self.target() + self.data['id'], data=json.dumps(self.data))

    def delete(self):        
        r = requests.delete(self.target() + self.id)

    @classmethod
    def delete_all(cls):
        r = requests.delete(cls.target())
        r = requests.put(cls.target() + '_mapping', json.dumps(app.config['MAPPINGS'][cls.__type__]))

