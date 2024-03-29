import os
import json
import requests
from requests import Request, Session
from diggercli.constants import BACKEND_ENDPOINT, DIGGERTOKEN_FILE_PATH, DIGGER_ENV_TOKEN_NAME
from diggercli.exceptions import ApiRequestException
from diggercli.utils.pprint import Bcolors


def get_github_token():
    env_token = os.environ.get(DIGGER_ENV_TOKEN_NAME, None)
    if env_token is not None:
        return env_token

    if not os.path.exists(DIGGERTOKEN_FILE_PATH):
        return None
    f = open(DIGGERTOKEN_FILE_PATH, 'r')
    token = f.readline().strip()
    return token

def do_api(method, endpoint, data, stream=False, auth_token=None):
    if auth_token is not None:
        headers = {
            "Authorization": f"Token {auth_token}"
        }
    else:
        headers={}
    response = requests.request(
        method=method, 
        stream=stream,
        url=endpoint, 
        json=data, 
        headers=headers
    )
    if response.status_code//100 != 2:
        Bcolors.fail("Request failed")
        raise ApiRequestException(response.content)
    return response

def check_project_name(projectName):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/check_project_name",
        {"project_name": projectName},
        auth_token=token
    )


def list_services(projectName):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/services/",
        {},
        auth_token=token
    )

def get_service_by_name(projectName, serviceName):
    response = list_services(projectName)
    service_list = json.loads(response.content)["results"]
    for service in service_list:
        if service["name"] == serviceName:
            return service
    raise ApiRequestException("Service not found")


def get_service(projectName, servicePk):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/services/{servicePk}/",
        {},
        auth_token=token
    )


def create_service(projectName, data):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/services/",
        data,
        auth_token=token
    )


def update_service(projectName, serviceName, data):
    token = get_github_token()
    return do_api(
        "PUT",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/services/{serviceName}/",
        data,
        auth_token=token
    )

def sync_services(projectName, data):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/services/sync/",
        data,
        auth_token=token
    )


def create_project(projectName):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/projects/",
        {"name": projectName},
        auth_token=token
    )

def generate_project(projectName):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/diggeryml/",
        {},
        auth_token=token
    )


def generate_tmp_project(data):
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/tmpProjects/",
        data
    )

def get_signed_url_for_code_upload(uuid, data):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/tmpProjects/{uuid}/code_upload_sign/",
        data,
        auth_token=token
    )    

def get_project_environments(projectName):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/",
        {},
        auth_token=token
    )

def get_environment_details(projectName, environmentName):
    response = get_project_environments(projectName)
    env_list = json.loads(response.content)["results"]
    for env in env_list:
        if env["name"] == environmentName:
            return env
    raise ApiRequestException("Environment not found")

def create_environment(projectName, data):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/",
        data,
        auth_token=token
    )

def update_environment(projectName, environmentId, data):
    token = get_github_token()
    return do_api(
        "PUT",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/{environmentId}/",
        data,
        auth_token=token
    )

def apply_environment(projectName, environmentId):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/{environmentId}/apply/",
        {},
        auth_token=token
    )


def plan_environment(projectName, environmentId):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/{environmentId}/plan/",
        {},
        auth_token=token
    )

def estimate_cost(projectName, environmentId):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/{environmentId}/estimate_cost/",
        {},
        auth_token=token
    )


def environment_vars_list(projectName, environmentId):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/{environmentId}/configs/",
        {},
        auth_token=token
    )


def environment_vars_create(projectName, environmentId, name, value, servicePk, overwrite=False):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/{environmentId}/configs/",
        {
            "name": name,
            "value": value,
            "service": servicePk,
            "overwrite": overwrite,
        },
        auth_token=token
    )


def destroy_environment(projectName, environmentId, data):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/{environmentId}/destroy/",
        data,
        auth_token=token
    )

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

def get_infra_deployment_info(projectName, deploymentId):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/deployments/{deploymentId}/",
        {},
        auth_token=token
    )

def get_deployment_logs(projectName, deploymentId, limit=5000, nextToken=None):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/deployments/{deploymentId}/logs?limit={limit}" + (f"&nextToken={nextToken}" if nextToken else ""),
        {},
        auth_token=token
    )

def stream_deployment_logs(projectName, deploymentId):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/stream_deployment_logs/{deploymentId}/",
        {},
        stream=True,
        auth_token=token
    )


def perform_service_deploy(projectName, environmentId, serviceId):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/{environmentId}/services/{serviceId}/deploy",
        {},
        auth_token=token
    )
    

def get_infra_destroy_job_info(projectName, deploymentId):
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/destroy_jobs/{deploymentId}/",
        {},
        auth_token=token
    )    

def get_last_infra_deployment_info(projectName, environmetId):
    """
        Retrieves the details of the last deployment for this project + env
    """
    token = get_github_token()
    return do_api(
        "GET",
        f"{BACKEND_ENDPOINT}/api/projects/{projectName}/environments/{environmetId}/last_deployment/",
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

def download_terraform_async(projectName, environment, region, target, services):
    token = get_github_token()
    return do_api(
        "POST",
        f"{BACKEND_ENDPOINT}/api/download_terraform",
        {
            "project_name": projectName,
            "environment": environment,
            "region": region,
            "target": target,
            "services": json.dumps(services)
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
