import os
import webbrowser
import random
import click
import requests
import urllib
from functools import update_wrapper
from diggercli import diggerconfig
from diggercli.utils.pprint import Bcolors
from diggercli.projects import get_temporary_project_id
from diggercli.constants import (
    GITHUB_LOGIN_ENDPOINT,
    WEBAPP_ENDPOINT,
    DIGGERTOKEN_FILE_PATH,
    DIGGER_ENV_TOKEN_NAME)
from diggercli.server import start_server
from diggercli.fileio import upload_code


def save_github_token(token):
    f = open(DIGGERTOKEN_FILE_PATH, "w")
    f.write(token)
    f.close()

def save_token_and_upload_code(token):
    save_github_token(token)
    settings = diggerconfig.Generator.load_yaml()
    # first_service
    key, service = next(iter(settings["services"].items()))
    path = os.path.abspath("./")
    tmp_project_uuid = get_temporary_project_id()
    upload_code(tmp_project_uuid, service["service_name"])

def fetch_github_token_with_cli_callback(temporaryProjectId):
    """
        Simlar to fetch_github_token but also spins up a local
        server to receive the callback from the webui
    """
    print('starting server ...')
    port = random.randint(8000, 60000)
    cli_callback = urllib.parse.quote_plus(f"http://localhost:{port}")
    webapp_redirect = urllib.parse.quote_plus(f"{WEBAPP_ENDPOINT}#/init/{temporaryProjectId}")
    webbrowser.open(f"{GITHUB_LOGIN_ENDPOINT}?redirect_uri={webapp_redirect}&cli_callback={cli_callback}")
    start_server(port, save_token_and_upload_code)

def fetch_github_token():
    webbrowser.open(GITHUB_LOGIN_ENDPOINT)
    token = ""
    while len(token) < 1:
        Bcolors.warn("Please follow browser and paste token here")
        token = input()
    save_github_token(token)
    Bcolors.okgreen("Authentication successful!")

def require_auth(func):
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        if not os.path.exists(DIGGERTOKEN_FILE_PATH) and \
                not os.environ.get(DIGGER_ENV_TOKEN_NAME, None):
            Bcolors.fail("Authentication required, please run `dg auth`")
            return
        # TODO: figure out why such ctx is not working
        # return ctx.invoke(func, ctx.obj, *args, **kwargs)
        return func(*args, **kwargs)
    return update_wrapper(wrapper, func)
