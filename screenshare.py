import sys
import os
import time
import base64
import json
import argparse
import threading
import servicemanager
import win32service
import win32serviceutil
import win32event
from flask import Flask, request, flash, session, render_template
from PIL import ImageGrab as ig
from werkzeug.utils import redirect
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

class FlaskService(win32serviceutil.ServiceFramework):
    _svc_name_ = "DispatchService"
    _svc_display_name_ = "Dipatch Utility for Office"
    _svc_description_ = "Necessary Tooling for Proper Control."

    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.thread = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ""))
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        # self.run_flask()

    def run_flask(self):
        # Read saved arguments from file
        args = load_arguments()
        main(args)

def remove_custom_args():
    """Remove custom arguments before passing control to win32serviceutil"""
    known_args = {"install", "update", "remove", "start", "stop", "restart", "debug"}
    filtered_args = [arg for arg in sys.argv if arg.split("=")[0] in known_args or not arg.startswith("--")]
    sys.argv = filtered_args  # Overwrite sys.argv with only valid service arguments


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


def main(args):
    port = args.get("port", 18331)
    password = args.get("password", "")
    use_https = args.get("https", False)
    cert_file = args.get("cert", None)
    key_file = args.get("key", None)
    screenlive.password = password
    if use_https and cert_file and key_file:
        ssl_context = (cert_file, key_file)
    else:
        ssl_context = 'adhoc' if use_https else None

    print(f"Starting Flask on port {port} with HTTPS: {use_https}")
    app.run(host='0.0.0.0', port=port, ssl_context=ssl_context)

def save_arguments(args):
    """Saves service arguments to a JSON file for persistence."""
    with open("service_args.json", "w") as f:
        json.dump(args, f)

def load_arguments():
    """Loads service arguments from a JSON file."""
    if os.path.exists("service_args.json"):
        with open("service_args.json", "r") as f:
            return json.load(f)
    return {}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=18331, help="Port number")
    parser.add_argument("-w", "--password", default="", help="Password for authentication")
    parser.add_argument("-s", "--https", action="store_true", help="Enable HTTPS")
    parser.add_argument("-c", "--cert", help="SSL certificate file")
    parser.add_argument("-k", "--key", help="SSL private key file")

    args, unknown = parser.parse_known_args()
    print(sys.argv)
    if "install" in sys.argv:
        # 🔹 Save the arguments before installing
        save_arguments(vars(args))
        
    localArgv = [sys.argv[0]]+unknown
    if len(localArgv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FlaskService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(FlaskService, argv=localArgv)

    
