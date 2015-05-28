
from flask import Flask, request
from flask.views import View
from flask.ext.login import login_user, current_user

import infrastructure.models as models
from infrastructure.core import app, login_manager

from infrastructure.view.accounts import blueprint as accounts
from infrastructure.view.storage import blueprint as storage
from infrastructure.view.es import blueprint as es


app.register_blueprint(accounts)
app.register_blueprint(storage)
app.register_blueprint(es)


@login_manager.user_loader
def load_account_for_login_manager(userid):
    out = models.Account.pull(userid)
    return out

@app.before_request
def standard_authentication():
    """Check remote_user on a per-request basis."""
    remote_user = request.headers.get('REMOTE_USER', '')
    if remote_user:
        user = models.Account.pull(remote_user)
        if user:
            login_user(user, remember=False)
    # add a check for provision of api key
    elif 'api_key' in request.values or 'api_key' in request.headers:
        apik = request.values['api_key'] if 'api_key' in request.values else request.headers['api_key']
        res = models.Account.query(q='api_key:"' + apik + '"')['hits']['hits']
        if len(res) == 1:
            user = models.Account.pull(res[0]['_source']['id'])
            if user:
                login_user(user, remember=False)


@app.errorhandler(404)
def page_not_found(e):
    return 'File Not Found', 404

@app.errorhandler(401)
def page_not_found(e):
    return 'Unauthorised', 401
        

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=app.config['DEBUG'], port=app.config['PORT'])

