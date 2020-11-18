import sys 
import os
from pathlib import Path
from environs import Env

def get_base_path():
    # for pyinstaller binaries we use sys.MEIPASS otherwise fetch from __file__
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.abspath(os.path.dirname(__file__))


BASE_PATH = get_base_path()
HOMEDIR_PATH = str(Path.home())
AWS_HOME_PATH = f"{HOMEDIR_PATH}/.aws"
AWSCREDS_FILE_PATH = f"{AWS_HOME_PATH}/credentials"
DIGGERHOME_PATH = os.path.join(HOMEDIR_PATH, ".digger/")
DIGGERTOKEN_FILE_PATH = f"{DIGGERHOME_PATH}/token"
env = Env()
env.read_env(f"{BASE_PATH}/env/.env", recurse=False)
BACKEND_ENDPOINT = env("BACKEND_ENDPOINT")
GITHUB_LOGIN_ENDPOINT = BACKEND_ENDPOINT + "/login/github/"