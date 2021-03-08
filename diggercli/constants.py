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


DIGGER_SPLASH = """
        🚀 Digger: Deploy with confidence 🚀

           ______                    
          (, /    ) ,                
            /    /    _   _    _  __ 
          _/___ /__(_(_/_(_/__(/_/ (_
        (_/___ /    .-/ .-/          
                   (_/ (_/            
"""

DIGGER_ENV_TOKEN_NAME = "DIGGER_TOKEN"
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
WEBAPP_ENDPOINT = env("WEBAPP_ENDPOINT")
PAAS_TARGET = "diggerhq/target-fargate@v1.0.0"
AWS_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "af-south-1",
    "ap-east-1",
    "ap-south-1",
    "ap-northeast-3",
    "ap-northeast-2",
    "ap-northeast-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ca-central-1",
    "cn-north-1",
    "cn-northwest-1",
    "eu-central-1",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-north-1",
    "eu-south-1",
    "me-south-1",
    "sa-east-1",
    "us-gov-east-1",
    "us-gov-west-1",
]