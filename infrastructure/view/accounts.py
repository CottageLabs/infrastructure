import uuid, json

from flask import Blueprint, request, url_for, flash, redirect, make_response
from flask import render_template, abort
from flask.ext.login import login_user, logout_user, current_user
from flask_wtf import Form
from wtforms.fields import TextField, TextAreaField, SelectField, HiddenField, PasswordField
from wtforms import validators, ValidationError

from portality.core import app
import portality.models as models
import portality.util as util

blueprint = Blueprint('accounts', __name__)

'''
create accounts - user, group, service
anyone can register an account
but groups can only be joined by those that have permission to join
unless the group allows public join
trying to do something that is not allowed may show that it is possible to request the action
this will store the requested change and alert the relevant group owner to allow it

an account authenticates by provision of password, api key, or token received via email link (nmpje)

anyone can create user accounts
anyone can create group accounts except for those prefixed by the name of another account
prefixed accounts can only be created by owners or group members of the account named with said prefix
only sysadmin can create service accounts

an authenticated account can try to perform an action on something in a service
a check will be made for a service account that defines actions, and who can perform them
without one the defaults will be used
if the account is in a group that allows the action on the something, it is allowed
if not allowed but request to perform the action is configured, then request will be offered

to check permission
check if account is in sudo or root group - overrides anything else

check if account is service
check if service has a group
check if account is in service group
if no service group then only GET is allowed
if not then only GET of public stuff would be allowed
check for membership of group service.action
check for special control group on the something

on trying to join group
check if group is public
request permission to join group

on trying to edit account data - this is an action on something in the account service:
GET own account data allowed
GET of another account gives only public info
POST/PUT to own account allowed except for group memberships
POST/PUT to other accounts not allowed unless in account.admin or account.POST group
POST/PUT by user to join new group triggers a group join request
POST/PUT by user in group.ADMIN or group.AUTH to offer join to other user is allowed
POST/PUT to remove from group is allowed
DELETE to own account allowed but actually does a disable



'''



@blueprint.route('/permission',methods=['GET','POST'])
def getpermission():
    if request.method == 'GET':
        # return information about the current user
    else:
        # check that the current user has permission to request permissions about other users
        values = request.json if request.json else request.values
        return permission(**values)

def _permissionloop(perms,route,action,hierarchic=True):
    allowables = ['GET','POST','PUT','PUBLISH','DELETE','*']
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
        
def permission(user=None,path=None,routes=None,service=None,services=None,action=None):
    if user is None:
        user = {
            'services': {
                'index': {
                    'hierarchic': False, # detault is True, so only set this if hierarchy of actions is not desired
                    'routes': [
                        {
                            '*': ['*'],
                            '_': ['*'],
                            'example': ['*'],
                            'example*': ['GET','POST','PUT','PUBLISH','DELETE','*']
                        }
                    ]
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


    
    

@blueprint.route('/')
def index():
    if current_user.is_anonymous():
        abort(401)
    users = models.Account.query() #{"sort":{'id':{'order':'asc'}}},size=1000000
    if users['hits']['total'] != 0:
        accs = [models.Account.pull(i['_source']['id']) for i in users['hits']['hits']]
        # explicitly mapped to ensure no leakage of sensitive data. augment as necessary
        users = []
        for acc in accs:
            user = {'id':acc.id}
            if 'created_date' in acc.data:
                user['created_date'] = acc.data['created_date']
            users.append(user)
    if util.request_wants_json():
        resp = make_response( json.dumps(users, sort_keys=True, indent=4) )
        resp.mimetype = "application/json"
        return resp
    else:
        return render_template('account/users.html', users=users)

@blueprint.route('/<username>', methods=['GET','POST', 'DELETE'])
def username(username):
    acc = models.Account.pull(username)

    if acc is None:
        abort(404)
    elif ( request.method == 'DELETE' or 
            ( request.method == 'POST' and 
            request.values.get('submit','').lower() == 'delete' ) ):
        acc.delete()
        flash('Account ' + acc.id + ' deleted')
        return redirect(url_for('.index'))
    elif request.method == 'POST':
        newdata = request.json if request.json else request.values
        if newdata.get('id',False):
            if newdata['id'] != username:
                acc = models.Account.pull(newdata['id'])
            else:
                newdata['api_key'] = acc.data['api_key']
        for k, v in newdata.items():
            if k not in ['submit','password']:
                acc.data[k] = v
        if 'password' in newdata and not newdata['password'].startswith('sha1'):
            acc.set_password(newdata['password'])
        acc.save()
        flash("Record updated")
        return render_template('account/view.html', account=acc)
    else:
        if util.request_wants_json():
            resp = make_response( 
                json.dumps(acc.data, sort_keys=True, indent=4) )
            resp.mimetype = "application/json"
            return resp
        else:
            return render_template('account/view.html', account=acc)


def nextdirect(default):
    for target in request.args.get('next'), request.referrer:
        if not target:
            continue
        if target == util.is_safe_url(target):
            return target
        else:
            return redirect(default)

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and form.validate():
        password = form.password.data
        username = form.username.data
        user = models.Account.pull(username)
        if user is None:
            user = models.Account.pull_by_email(username)
        if user is not None and user.check_password(password):
            login_user(user, remember=True)
            return '' # TODO return json success info
        else:
            return '' # TODO return json error info
    elif request.method == 'POST' and not form.validate():
        return '' # TODO return json error info
    else:
        return render_template('account/login.html')

@blueprint.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        un = request.form.get('un',"")
        account = models.Account.pull(un)
        if account is None: account = models.Account.pull_by_email(un)
        if account is None:
            flash('Sorry, your account username / email address is not recognised. Please contact us.')
        else:
            newpass = util.generate_password()
            account.set_password(newpass)
            account.save()

            to = [account.data['email'],app.config['ADMIN_EMAIL']]
            fro = app.config['ADMIN_EMAIL']
            subject = app.config.get("SERVICE_NAME","") + "password reset"
            text = "A password reset request for account " + account.id + " has been received and processed.\n\n"
            text += "The new password for this account is " + newpass + ".\n\n"
            text += "If you are the user " + account.id + " and you requested this change, please login now and change the password again to something of your preference.\n\n"
            
            text += "If you are the user " + account.id + " and you did NOT request this change, please contact us immediately.\n\n"
            try:
                util.send_mail(to=to, fro=fro, subject=subject, text=text)
                flash('Your password has been reset. Please check your emails.')
                if app.config.get('DEBUG',False):
                    flash('Debug mode - new password was set to ' + newpass)
            except:
                flash('Email failed.')
                if app.config.get('DEBUG',False):
                    flash('Debug mode - new password was set to ' + newpass)

    return render_template('account/forgot.html')


@blueprint.route('/logout')
def logout():
    logout_user()
    return ''

@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST' and 'email' in request.form:
        testname = models.Account.pull_by_name(request.form.get('name',''))
        if testname is not None:
            flash('Sorry, there is already an account with that name. Please try another.')
            return render_template('account/register.html',name=request.form.get('name',''),request.form['email'])
        testemail = models.Account.pull_by_email(request.form['email'])
        if testemail is not None:
            flash('Sorry, there is already an account with that email address. Please try another.')
            return render_template('account/register.html',name=request.form.get('name',''),request.form['email'])
        api_key = str(uuid.uuid4())
        account = models.Account(
            name=request.form.get('name',request.form['email']), 
            email=request.form['email'],
            api_key=api_key
        )
        account.set_password(api_key[0:9])
        account.save()
        flash('Account created for ' + account.id, 'success')
        return redirect('/account')
    if 'email' not in request.form:
        flash('Sorry, you must provide at least an email address.')
    return render_template('account/register.html',name='',email='')






















// javascript server code for managing user registration/login/logout

var loginCodes = new Meteor.Collection("logincodes");
var Future = Npm.require('fibers/future');

function remove_expired_login_codes() {
    loginCodes.remove({ timeout: { $lt: (new Date()).valueOf() } });
}

function login_only_gets_one_chance(email) {
    loginCodes.remove({email:email});
}

function login_or_register_user_with_new_password(callbackObj,email) {
    var user = Meteor.users.findOne({'emails.address':email})
    var password = Random.hexString(30);
    var userId;
    if ( !user ) {
        userId = Accounts.createUser({email:email,password:password});
        console.log("CREATED userId = " + userId);
    } else {
        userId = user._id;
        console.log("FOUND userId = " + userId);
        Accounts.setPassword(userId,password);
    }

    callbackObj.setUserId(userId);

    return password;
}

Meteor.methods({

    enter_email: function (email,ssl) {
        check(email,String);
        check(ssl,Boolean);
        console.log("enter_email for email address: " + email);
        email = email.toLowerCase();

        // determine if this email address is already a user in the system
        var user = Meteor.users.findOne({'emails.address':email})
        console.log(email + " user = " + user);

        // create a loginCodes record, with a new LOGIN_CODE_LENGTH-digit code, to expire in LOGIN_CODE_TIMEOUT_MINUTES
        // make the code be LOGIN_CODE_LENGTH digits, not start with a 0, and not have any repeating digits
        var random_code = "";
        for ( ; random_code.length < LOGIN_CODE_LENGTH; ) {
            var chr = Random.choice("0123456789");
            if ( random_code.length === 0 ) {
                if ( (chr === "0") ) {
                    continue;
                }
            } else {
                if ( chr === random_code.charAt(random_code.length-1) ) {
                    continue;
                }
            }
            random_code += chr;
        }
        console.log(email + " random code = " + random_code);

        // for those who prefer to login with a link, also create a random string SECURITY_CODE_HASH_LENGTH
        // characters long
        var random_hash = "";
        for ( ; random_hash.length < SECURITY_CODE_HASH_LENGTH; ) {
            var chr = Random.choice("23456789ABCDEFGHJKLMNPQESTUVWXYZ");
            if ( random_hash.length !== 0 ) {
                if ( chr === random_hash.charAt(random_hash.length-1) ) {
                    continue;
                }
            }
            random_hash += chr;
        }
        var login_link_url = (ssl ? 'https' : 'http') + "://" + MY_DOMAIN + "/#" + random_hash;

        // add new record to timeout in LOGIN_CODE_TIMEOUT_MINUTES
        var timeout = (new Date()).valueOf() + (LOGIN_CODE_TIMEOUT_MINUTES * 60 * 1000);
        loginCodes.upsert({email:email},{email:email,code:random_code,hash:random_hash,timeout:timeout});
        var codeType = user ? "login" : "registration";


        Email.send({
            from: ADMIN_ACCOUNT_ID,
            to: email,
            subject: "NoMorePasswordsJustEmail " + codeType + " security code",
            text: ( "Your NoMorePasswordsJustEmail " + codeType + " security code is:\r\n\r\n      " + random_code + "\r\n\r\n" +
                    "or use this link:\r\n\r\n      " + login_link_url + "\r\n\r\n" +
                    "note: this single-use code is only valid for " + LOGIN_CODE_TIMEOUT_MINUTES + " minutes." ),
            html: ( "<html><body>" +
                    '<p>Your <b><i>NoMorePasswordsJustEmail</i></b> ' + codeType + ' security code is:</p>' +
                    '<p style="margin-left:2em;"><font size="+1"><b>' + random_code + '</b></font></p>' +
                    '<p>or click on this link</p>' +
                    '<p style="margin-left:2em;"><font size="-1"><a href="' + login_link_url + '">' + login_link_url + '</a></font></p>' +
                    '<p><font size="-1">note: this single-use code is only valid for ' + LOGIN_CODE_TIMEOUT_MINUTES + ' minutes.</font></p>' +
                    '</body></html>' )
        });

        var ret = { known:(user !== undefined) };
        return ret;
    },

    enter_security_code: function (email,code) {
        check(email,String);
        check(code,String);
        console.log("enter_security_code for email address: " + email + " - code: " + code);
        email = email.toLowerCase();

        // delete any login codes that have timed out yet
        remove_expired_login_codes();

        // If can find this record in login codes then all is well, else it failed
        var loginCode = loginCodes.findOne({email:email,code:code});
        login_only_gets_one_chance(email);
        if ( !loginCode ) {
            throw "failed to log in";
        }

        var password = login_or_register_user_with_new_password(this,email);

        return password;
    },

    cancel_login_code: function (email) {
        check(email,String);
        console.log("cancel_login_code for email address: " + email);
        email = email.toLowerCase();

        // delete any existing record for this user login codes
        login_only_gets_one_chance(email);

        return "ok";
    },

    login_via_url: function (hash) {
        check(hash,String);
        console.log("login_via_url for hash: " + hash);

        var loginCode = loginCodes.findOne({hash:hash});
        if ( loginCode ) {
            login_only_gets_one_chance(loginCode.email);
        }

        // I don't want bots just brute-force attacking the server to guess the login access. To prevent
        // that I'll force a minor little delay, minor enough to not bother a real user but enough to
        // relay annoy a billion bots. The make-it-look-synchronous part of this delate is taken from
        // what I learned at: https://gist.github.com/possibilities/3443021
        var future = new Future();
        setTimeout(function() { future.return(); }, 333);
        future.wait();

        if ( !loginCode ) {
            throw "blech; invalid code"
        }
        return {email:loginCode.email,pwd:login_or_register_user_with_new_password(this,loginCode.email)};
    }

});

Meteor.startup(function () {
    if ( Meteor.settings.MAIL_URL ) {
        process.env.MAIL_URL = Meteor.settings.MAIL_URL;
    }
});
