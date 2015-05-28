import os, json, requests, uuid


class Storage():

    def __init__(self, **kwargs):
        try:
            self.public = public
        except:
            self.public = 'public'
        try:
            self.uid = uid
        except:
            self.uid = uuid.uuid4().hex
        try:
            self.directory = directory
        except:
            self.directory = app.config['STORAGE_FOLDER']
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
    
    def store(self,fn=None,data=None,fh=None,loc=None,url=None):
        # if public save to public store if this storage method differentiates
        # otherwise save to private. Access to private things is handled separately, and the retrieve route 
        # for this storage method should be coded to know how to check it.
        if self.public:
            st = self.directory + '/' + self.public.strip('/') + '/'
        else:
            st = self.directory + '/'
        std = st + uid
        if not os.path.exists(std):
            os.makedirs(std)

        # TODO: check if the target has a file type and if so if it is in the allowed list (if there is an allowed list)

        if loc is not None:
            # TODO: there should be some checks on what files can be moved by this
            # although the process level running the app may control that - don't run this app as root
            target = werkzeug.secure_filename(std + '/' + loc.strip('/').split('/')[-1])
            shutil.copy(loc, target)
        elif fh is not None:
            if fn is None:
                try:
                    fn = fh.name.split('/')[-1]
                except:
                    fn = uuid.uuid4().hex
            target = werkzeug.secure_filename(std + '/' + fn)
            out = open(target, 'w')
            for line in fh:
                out.write(line)
            out.close()
            fh.close()
        elif data is not None or or url is not None:
            if url is not None:
                try:
                    r = requests.get(url)
                    if fn is None:
                        try:
                            fn = url.strip('/').split('/')[-1]
                        except:
                            fn = uuid.uuid4().hex
                    data = r.text
                except:
                    pass
            if fn is None: fn = uuid.uuid4().hex
            target = werkzeug.secure_filename(std + '/' + fn)
            if isinstance(data,dict) or isinstance(data,list): data = json.dumps(data,"","    ")
            out = open(target, 'w')
            out.write(data)
            out.close()

        return {} # on success return filename, folder ID, url if appropriate, and private/public setting 

    def delete(self,path=None):
        try:
            loc = self.directory + '/' + self.uid
            if path is not None: loc += '/' + path.strip('/')
            if os.path.isfile(loc):
                os.remove(loc)
            else:
                shutil.rmtree(loc)
        except:
            pass
        return ''

    def empty(self):
        self.delete()
        os.makedirs(self.directory + '/' + self.uid)
        
    def listing(self,path=None):
        listing = os.listdir( self.directory + '/' )
        # TODO if path is not a directory then retrieve or error
        return sorted(listing, key=str.lower)

    def retrieve(self,filename):
        # TODO what if path is a folder?
        if os.path.isfile(loc):
            return open(storagedir + '/' + path.strip('/'))
        else:
            pass

    def location(self,filename):
        pass # return location of file on local fs if possible

    def url(self,uid,filename):
        pass # return url of item

