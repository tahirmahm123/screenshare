from flask import Flask, request, flash, session
from flask.templating import render_template
import json, argparse
from werkzeug.utils import redirect
import threading, time, base64, sys, os

secret_key = u'f71b10b68b1bc00019cfc50d6ee817e75d5441bd5db0bd83453b398225cede69'


ver = sys.version_info.major
if ver==2:
    import StringIO as io
elif ver==3:
    import io

if sys.platform in ["win32", "darwin"]:
    from PIL import ImageGrab as ig
else:
    import pyscreenshot as ig
    bkend = "pygdk3"


class Screen():
    def __init__(self):
        self.FPS = 10
        self.screenbuf = ""
        self.password = ""
        if ver==2:
            self.screenfile = io.StringIO()
        elif ver==3:
            self.screenfile = io.BytesIO()
        threading.Thread(target=self.getframes).start()

    def __del__(self):
        self.screenfile.close()

    def getframes(self):
        while True:
            if sys.platform in ["win32", "darwin"]:
                im = ig.grab()
            else:
                im = ig.grab(childprocess=False,backend=bkend)
            self.screenfile.seek(0)
            self.screenfile.truncate(0)
            im_converted = im.convert("RGB")
            im_converted.save(self.screenfile, format="jpeg", quality=75, progressive=True)
            self.screenbuf = base64.b64encode(self.screenfile.getvalue())
            time.sleep(1.0/self.FPS)
    
    def gen(self):
        s = ''
        if ver==2:
            s = self.screenbuf
        elif ver==3:
            s = self.screenbuf.decode()
        return s

screenlive = Screen()

def get_base_path():
    """Returns the correct base path when running as a PyInstaller executable."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS  # PyInstaller extracts files here
    return os.path.abspath(".")

app = Flask(__name__)
app.secret_key = secret_key
# Set Flask's template and static folder paths
app.template_folder = os.path.join(get_base_path(), "templates")
app.static_folder = os.path.join(get_base_path(), "static")

###### general ##########################################
@app.route('/')
def welcome():
    session.clear()
    if len(screenlive.password) == 0 :
        session['access'] = True
        return render_template("screen.html")
    else :
        return render_template("login.html")

@app.route('/login', methods = ['POST'])
def login():
    # password is not required
    session.clear()
    if len(screenlive.password) == 0 :
        session['access'] = True
        return render_template("screen.html")

    p = request.form["password"]
    if p == screenlive.password :
        session['access'] = True
        return render_template("screen.html")
    else :
        session.clear()
        flash("Wrong password")
        return render_template("login.html")

@app.route('/screenfeed/', methods=["POST"])
def screenfeed():
    if 'access' in session and session['access']:
        return json.dumps([True, screenlive.gen()])
    else:
        redirect('/')

### main ###
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="port, default 18331", type=int, default=18331)
    parser.add_argument("-w", "--password", help="password, default no password", default="")
    parser.add_argument("-s", "--https", help="enable https, default http", action="store_true")
    parser.add_argument("-c", "--cert", help="certificate file")
    parser.add_argument("-k", "--key", help="private key file")

    parser.print_help()
    args = parser.parse_args()
    port = args.port
    screenlive.password = args.password
    
    try:
        if args.https:
            if args.cert and args.key:
                app.run(host='0.0.0.0', port=port, threaded=True, ssl_context=(args.cert, args.key))
            else:
                app.run(host='0.0.0.0', port=port, threaded=True, ssl_context='adhoc')
        else:
            app.run(host='0.0.0.0', port=port, threaded=True)
    except Exception as e:
        print(e.message)
        print("Some errors in the command, fall back to the default http screen sharing!!!\n")
        app.run(host='0.0.0.0', port=port, threaded=True)
