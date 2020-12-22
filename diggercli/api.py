import requests
from requests import Request, Session
from diggercli.auth import get_github_token
from diggercli.constants import BACKEND_ENDPOINT
from diggercli.exceptions import ApiRequestException
from diggercli.utils.pprint import Bcolors


def do_api(method, endpoint, data, auth_token=None):
    response = requests.request(
        method=method, 
        url=endpoint, 
        data=data, 
        headers={
            "Authorization": f"Token {auth_token}"
        }
    )
    if response.status_code != 200:
        Bcolors.fail("Request failed")
        raise ApiRequestException(response.content)
    return response

def create_infra(data):
    token = get_github_token()
    return do_api(
        "POST", 
        f"{BACKEND_ENDPOINT}/api/create", 
        data, 
        auth_token=token
    )

def create_infra_quick(data):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/create_quick", 
        data,
        auth_token=token
    )

def destroy_infra(data):
    token = get_github_token()
    return do_api(
        "POST", 
        f"{BACKEND_ENDPOINT}/api/destroy", 
        data, 
        auth_token=token
    )


def deploy_to_infra(data):
    token = get_github_token()
    return do_api(
        "POST", 
        f"{BACKEND_ENDPOINT}/api/deploy", 
        data, 
        auth_token=token
    )

def get_job_info(job_id):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/jobs/{job_id}/status",
        {},
        auth_token=token
    )

def get_logs(projectName):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/logs",
        {"project_name": projectName},
        auth_token=token
    )

def download_terraform_async(projectName, environment):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/download_terraform",
        {
            "project_name": projectName,
            "environment": environment
        },
        auth_token=token
    )

def terraform_generate_status(terraformJobId):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/terraform_s3_jobs/{terraformJobId}/status",
        {},
        auth_token=token
    )

def cli_report(payload):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/cli_reporting",
        payload,
        auth_token=token
    )
