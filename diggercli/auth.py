import os
import webbrowser
import click
import requests
from functools import update_wrapper
from diggercli.utils.pprint import Bcolors
from diggercli.constants import (
    GITHUB_LOGIN_ENDPOINT,
    DIGGERTOKEN_FILE_PATH
)

def fetch_github_token():
    webbrowser.open(GITHUB_LOGIN_ENDPOINT)
    token = ""
    while len(token) < 1:
        Bcolors.warn("Please follow browser and paste token here")
        token = input()
    f = open(DIGGERTOKEN_FILE_PATH, "w")
    f.write(token)
    f.close()
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
