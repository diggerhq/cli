import requests
from requests import Request, Session
from auth import get_github_token
from constants import BACKEND_ENDPOINT
from exceptions import ApiRequestException
from utils.pprint import Bcolors


def do_api(method, endpoint, data, auth_token=None):
    response = requests.request(
        method=method, 
        url=endpoint, 
        data=data, 
        headers={
            "Authorization": f"Token: {auth_token}"
        }
    )
    if response.status_code != 200:
        Bcolors.fail("Request failed")
        raise ApiRequestException(response.content)
    return response

def create_infra(data):
    token = get_github_token()
    return do_api(
        "post", 
        f"{BACKEND_ENDPOINT}/api/create", 
        data, 
        auth_token=token
    )

