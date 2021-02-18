import os
import webbrowser
import random
import click
import requests
from functools import update_wrapper
from diggercli.utils.pprint import Bcolors
from diggercli.constants import (
    GITHUB_LOGIN_ENDPOINT,
    WEBAPP_ENDPOINT,
    DIGGERTOKEN_FILE_PATH
)
from diggercli.server import start_server

def save_github_token(token):
    f = open(DIGGERTOKEN_FILE_PATH, "w")
    f.write(token)
    f.close()

def fetch_github_token_with_cli_callback(temporaryProjectId):
    """
        Simlar to fetch_github_token but also spins up a local
        server to receive the callback from the webui
    """
    print('starting server ...')
    port = random.randint(8000, 60000)
    webapp_redirect = f"{WEBAPP_ENDPOINT}#/init/{temporaryProjectId}"
    webbrowser.open(f"{GITHUB_LOGIN_ENDPOINT}?redirect_uri={webapp_redirect}&cli_callback=http://localhost:{port}")
    start_server(port, save_github_token)

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
        if not os.path.exists(DIGGERTOKEN_FILE_PATH):
            Bcolors.fail("Authentication required, please run `dg auth`")
            return
        # TODO: figure out why such ctx is not working
        # return ctx.invoke(func, ctx.obj, *args, **kwargs)
        return func(*args, **kwargs)
    return update_wrapper(wrapper, func)

def get_github_token():
    if not os.path.exists(DIGGERTOKEN_FILE_PATH):
        return None
    f = open(DIGGERTOKEN_FILE_PATH, 'r')
    token = f.readline().strip()
    return token
