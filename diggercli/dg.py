from __future__ import print_function, unicode_literals
import os
from datetime import datetime
import threading
import shutil
import sys
import time
import json
import configparser
import random
import requests
import click
from pathlib import Path
from collections import OrderedDict
import subprocess
from jinja2 import Template
from oyaml import load as yload, dump as ydump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
try:
    import importlib.resources as pkg_resources
except ImportError:
    # Try backported to PY<37 `importlib_resources`.
    import importlib_resources as pkg_resources

from PyInquirer import prompt as pyprompt, Separator
from diggercli import api
from diggercli.fileio import download_terraform_files
from diggercli.auth import fetch_github_token, require_auth
from diggercli.exceptions import CouldNotDetermineDockerLocation
from diggercli._version import __version__
from diggercli.constants import (
    DIGGER_SPLASH,
    DIGGERHOME_PATH,
    BACKEND_ENDPOINT,
    GITHUB_LOGIN_ENDPOINT,
    HOMEDIR_PATH,
    AWS_HOME_PATH,
    AWSCREDS_FILE_PATH,
    AWS_REGIONS,
)
from diggercli.utils.pprint import Bcolors, Halo, spin

# TODO: use pkg_resources_insead of __file__ since latter will not work for egg


PROJECT = {}


def digger_yaml():
    return "digger-master/digger.yml"

def get_project_settings():
    return yload(open(digger_yaml()), Loader=Loader)
    return PROJECT

def update_digger_yaml(d):
    global PROJECT
    f = open(digger_yaml(), "w")
    ydump(d, f)
    PROJECT = d

def find_dockerfile(path):
    files =  os.listdir(path)
    if "Dockerfile" in files:
        return os.path.join(path, "Dockerfile")
    raise CouldNotDetermineDockerLocation("Could not find dockerfile")

def dockerfile_manual_entry():
    while True:
        print("Please enter path to Dockerfile directly")
        path = input()
        if os.path.exists(path):
            return path
        else:
            print("error, dockerfile not found")

def prompt_for_aws_keys(currentAwsKey, currentAwsSecret):
    if currentAwsKey is None or currentAwsSecret is None:
        questions = [
            {
                'type': 'input',
                'name': 'aws_key',
                'message': f'Your AWS Key',
                'validate': lambda x: len(x) > 0
            },
            {
                'type': 'input',
                'name': 'aws_secret',
                'message': f'Your AWS Secret',
                'validate': lambda x: len(x) > 0
            },
        ]
        answers = pyprompt(questions)
    else:
        maskedAwsKey = currentAwsKey[:4]
        maskedAwsSecret = currentAwsSecret[:4]

        questions = [
            {
                'type': 'input',
                'name': 'aws_key',
                'message': f'Your AWS Key ({maskedAwsKey}***)',
            },
            {
                'type': 'input',
                'name': 'aws_secret',
                'message': f'Your AWS Secret ({maskedAwsSecret}***)'
            },
        ]

        answers = pyprompt(questions)
        answers["aws_key"] = currentAwsKey if answers["aws_key"] == "" else answers["aws_key"]
        answers["aws_secret"] = currentAwsSecret if answers["aws_secret"] == "" else answers["aws_secret"]

    return answers


def get_env_vars(envName, serviceName):
    settings = get_project_settings()
    envVars = settings["environments"][envName].get("config_vars", {})
    serviceEnvVars = settings["services"][serviceName].get("config_vars", {}).get(envName, {})
    envVars.update(serviceEnvVars)
    return envVars

def retreive_aws_creds(projectName, environment, prompt=True):
    diggercredsFile = os.path.join(DIGGERHOME_PATH, "credentials")
    profileName = f"{projectName}-{environment}"
    diggerconfig = configparser.ConfigParser()
    diggerconfig.read(diggercredsFile)

    if profileName not in diggerconfig:
        diggerconfig[profileName] = {}
    
    currentAwsKey = diggerconfig[profileName].get("aws_access_key_id", None)
    currentAwsSecret = diggerconfig[profileName].get("aws_secret_access_key", None)

    if prompt or (currentAwsKey is None or currentAwsSecret is None):
        answers = prompt_for_aws_keys(currentAwsKey, currentAwsSecret)
        newAwsKey = answers["aws_key"]
        newAwsSecret = answers["aws_secret"]
    else:        
        newAwsKey = currentAwsKey
        newAwsSecret = currentAwsSecret

    diggerconfig[profileName]["aws_access_key_id"] = newAwsKey
    diggerconfig[profileName]["aws_secret_access_key"] = newAwsSecret

    with open(diggercredsFile, 'w') as f:
        diggerconfig.write(f)

    return {
        "aws_key": newAwsKey,
        "aws_secret": newAwsSecret
    }

def generate_docker_compose_file():
    settings = get_project_settings()
    services = settings["services"].values()
    composeFile = pkg_resources.open_text("templates.environments.local-docker", 'docker-compose.yml')
    composeContent = composeFile.read()
    composeTemplate = Template(composeContent)

    # generate environment files
    for service in settings["services"].values():
        for resource in service["resources"].values():
            env_path = "digger-master/local-docker/"
            env_file = f"{service['name']}_{resource['name']}.env"
            # assuming its a database
            envFile = pkg_resources.open_text("templates.environments.local-docker", f".{resource['engine'].lower()}.env")
            envContent = envFile.read()
            envTemplate = Template(envContent)
            envContentRendered = envTemplate.render({
                "dbhost": resource["name"],
                "dbname": resource["name"],
                "dbuser": resource["engine"],
                "dbpassword": "password",
            })

            envFile = open(f"{env_path}{env_file}", "w")
            envFile.write(envContentRendered)
            envFile.close()

            resource["env_file"] = env_file
            service["env_files"] = service.get("env_files", [])
            service["env_files"].append(env_file)

    composeContentRendered = composeTemplate.render({
        "services": services
    })

    composeFile = open("digger-master/local-docker/docker-compose.yml", "w")
    composeFile.write(composeContentRendered)
    composeFile.close()

def init_project(project_name):

        Path("digger-master").mkdir(parents=True, exist_ok=True)

        settings = OrderedDict()
        settings["project"] = {
                "name": project_name
        }
        settings["environments"] = settings.get("environments", {})
        settings["environments"]["local-docker"] = {
            "target": "docker"
        }
        settings["services"] = {}

        return settings


def clone_repo(url):
    subprocess.Popen(["git", "clone", url]).communicate()


def repos():
    return [
        'todo-backend',
        'todo-frontend',
        'todo-reminder',
    ]

def services():
    return [
        {
            "service_name": 'todo-backend',
            "service_type": "container",
            "service_url": "https://github.com/diggerhq/todo-backend",
        },
        {
            "service_name": 'todo-frontend',
            "service_type": "serverless",
            "service_url": "https://github.com/diggerhq/todo-frontend",
        },
        # {
        #     "service_name": 'todo-reminder',
        #     "service_type": "serverless",
        #     "service_url": "https://github.com/diggerhq/todo-reminders",
        # }
    ]

def get_targets():
    return {
        "Digger Paas": "digger_paas",
        "AWS ECS Fargate": "aws_fargate",
        "(soon!) AWS EKS": "aws_eks",
        "(soon!) AWS EC2 docker-compose": "aws_ec2_compose",
        "(soon!) Google Cloud Run": "gcp_cloudrun",
        "(soon!) Google GKE": "gcp_gke",
    }

def get_service_names():
    return list(map(lambda x: x["service_name"], services()))

def modes():
    return [
        'Serverless',
        'Containers',
    ]

def report_async(payload, settings=None, status="start"):
    if settings is not None:
        payload.update({
            "settings": json.dumps(settings),
        })
    payload.update({"status": status})
    x = threading.Thread(target=api.cli_report, args=(payload,))
    x.start()

def print_version(ctx, param, value):
    if value == True:
        click.echo(f"dg cli v{__version__}")
        ctx.exit()

class SpecialEpilog(click.Group):
    def format_epilog(self, ctx, formatter):
        if self.epilog:
            formatter.write_paragraph()
            for line in self.epilog.split('\n'):
                formatter.write_text(line)

@click.group(cls=SpecialEpilog, epilog=DIGGER_SPLASH)
@click.option('--version', is_flag=True, is_eager=True,
                expose_value=False, callback=print_version)
def cli():

    Path(DIGGERHOME_PATH).mkdir(parents=True, exist_ok=True)
    Path(AWS_HOME_PATH).mkdir(parents=True, exist_ok=True)

@cli.command()
def version():
    """
        Print the current cli version
    """
    print("0.1")

@cli.command()
def auth():
    # report_async({"command": f"dg auth"}, status="start")    
    fetch_github_token()
    report_async({"command": f"dg auth"}, status="complete")


@cli.group()
@require_auth
def env():
    """
        Configure a new environment
    """


@env.command(name="list")
def env_list():
    settings = get_project_settings()

    report_async({"command": f"dg env list"}, settings=settings, status="start")

    spin(1, "Loading environment list ...")
    for env in settings["environments"].keys():
        print(f">> {env}")

    report_async({"command": f"dg env list"}, settings=settings, status="complete")


@env.command(name="create")
@click.argument("env_name", nargs=1, required=True)
@click.option("--target", "-t", required=False)
@click.option("--region", "-r", required=False)
@click.option('--prompt/--no-prompt', default=True)
def env_create(env_name, target=None, region=None, prompt=True):

    targets = get_targets()
    settings = get_project_settings()
    report_async({"command": f"dg env create"}, settings=settings, status="start")
    project_name = settings["project"]["name"]

    if target is None:
        questions = [
            {
                'type': 'list',
                'name': 'target',
                'message': 'Select target',
                'choices': targets.keys()
            },
        ]

        answers = pyprompt(questions)
        target = answers["target"]


    if target not in ["AWS ECS Fargate", "Digger Paas"]:
        Bcolors.fail("This option is currently unsupported! Please try again")
        return

    if region is None:
        questions = [
            {
                'type': 'list',
                'name': 'region',
                'message': 'Select region',
                'choices': AWS_REGIONS,
                'default': "us-east-1"
            },
        ]
        answers = pyprompt(questions)
        region = answers["region"]        

    if region not in AWS_REGIONS:
        Bcolors.fail("This region is not valid! Please try again")
        return

    if target == "AWS ECS Fargate":
        credentials = retreive_aws_creds(project_name, env_name, prompt=prompt)
    elif target == "Digger Paas":
        credentials = {
            "aws_key": None,
            "aws_secret": None
        }


    # spin(2, 'Loading creds from ~/.aws/creds')
    # spin(2, 'Generating terraform packages ...')
    # spin(2, 'Applying infrastructure ...')
    # spin(2, 'deploying packages ...')

    first_service = next(iter(settings["services"].values()))

    create_infra_api = lambda: api.create_infra({
        "aws_key": credentials["aws_key"],
        "aws_secret": credentials["aws_secret"],
        "project_name": project_name,
        "service_name": first_service["name"],
        "environment": env_name,
        "project_type": targets[target],
        "backend_bucket_name": "digger-terraform-states",
        "backend_bucket_region": "eu-west-1",
        "backend_bucket_key": f"{project_name}/project",
        "container_port": first_service["port"],
        "health_check": first_service.get("health_check", "/"),
        "region": region,
    })
    response = create_infra_api()
    job = json.loads(response.content)

    # loading until infra status is complete
    spinner = Halo(text="creating infrastructure ...", spinner="dots")
    spinner.start()
    while True:
        statusResponse = api.get_job_info(job['job_id'])
        print(statusResponse.content)
        jobStatus = json.loads(statusResponse.content)
        if jobStatus["status"] == "COMPLETED":
            # this is a hack to fix https://github.com/diggerhq/cli-backend/issues/8
            if jobStatus["docker_registry"] == "":
                response = create_infra_api()
                job = json.loads(response.content)
            else:
                break
        elif jobStatus["status"] == "FAILED":
            Bcolors.fail("Could not create infrastructure")
            print(jobStatus["fail_message"])
            return
        time.sleep(2)

    spinner.stop()

    environments = settings["environments"]
    environments[env_name] = {
        "target": targets[target],
        "region": region,
        "lb_url": jobStatus["lb_url"],
        "docker_registry": jobStatus["docker_registry"],
    }

    update_digger_yaml(settings)

    # create a directory for this environment (for environments and secrets)
    env_path = f"digger-master/{env_name}"
    tform_path = f"{env_path}/terraform"
    Path(env_path).mkdir(parents=True, exist_ok=True)
    Path(tform_path).mkdir(parents=True, exist_ok=True)
    shutil.rmtree(tform_path)        

    # tform generation
    spinner = Halo(text="Updating terraform ...", spinner="dots")
    spinner.start()
    download_terraform_files(project_name, env_name, tform_path)
    spinner.stop()

    print("Deplyment successful!")
    print(f"your deployment URL: http://{jobStatus['lb_url']}")

    report_async({"command": f"dg env create"}, settings=settings, status="complete")

@env.command(name="sync-tform")
@click.argument("env_name", nargs=1, required=True)
def env_sync_tform(env_name):
    settings = get_project_settings()
    report_async({"command": f"dg env sync-tform"}, settings=settings, status="start")
    project_name = settings["project"]["name"]
    env_path = f"digger-master/{env_name}"
    tform_path = f"{env_path}/terraform"
    Path(env_path).mkdir(parents=True, exist_ok=True)
    Path(tform_path).mkdir(parents=True, exist_ok=True)
    shutil.rmtree(tform_path) 
    # tform generation
    spinner = Halo(text="Updating terraform ...", spinner="dots")
    spinner.start()
    download_terraform_files(project_name, env_name, tform_path)
    spinner.stop()
    Bcolors.okgreen("Terraform updated successfully")        
    report_async({"command": f"dg env sync-tform"}, settings=settings, status="complete")

@env.command(name="build")
@click.argument("env_name", nargs=1, required=True)
def env_build(env_name):  
    action = "build"
    settings = get_project_settings()
    report_async({"command": f"dg env {action}"}, settings=settings, status="start")
    project_name = settings["project"]["name"]
    docker_registry = settings["environments"][env_name]["docker_registry"]
    # for service in settings["services"]:
    #     service_name = service["name"]
    
    # TODO: replace with service name here
    first_service = next(iter(settings["services"].values()))
    service_name = first_service["name"]
    subprocess.Popen(["docker", "build", "-t", project_name, f"{service_name}/"]).communicate()

    subprocess.Popen(["docker", "tag", f"{project_name}:latest", f"{docker_registry}:latest"]).communicate()
    report_async({"command": f"dg env {action}"}, settings=settings, status="complete")

@env.command(name="push")
@click.argument("env_name", nargs=1, required=True)
@click.option('--prompt/--no-prompt', default=False)
def env_push(env_name, prompt=False):
    action = "push"
    settings = get_project_settings()    
    report_async({"command": f"dg env {action}"}, settings=settings, status="start")
    project_name = settings["project"]["name"]
    docker_registry = settings["environments"][env_name]["docker_registry"]
    registry_endpoint = docker_registry.split("/")[0]
    credentials = retreive_aws_creds(project_name, env_name, prompt=prompt)
    os.environ["AWS_ACCESS_KEY_ID"] = credentials["aws_key"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = credentials["aws_secret"]
    proc = subprocess.run(["aws", "ecr", "get-login-password", "--region", "us-east-1", ], capture_output=True)
    docker_auth = proc.stdout.decode("utf-8")
    subprocess.Popen(["docker", "login", "--username", "AWS", "--password", docker_auth, registry_endpoint]).communicate()
    subprocess.Popen(["docker", "push", f"{docker_registry}:latest"]).communicate()
    report_async({"command": f"dg env {action}"}, settings=settings, status="complete")

@env.command(name="deploy")
@click.argument("env_name", nargs=1, required=True)
@click.option('--prompt/--no-prompt', default=False)
def env_deploy(env_name, prompt=False):
    action = "deploy"
    settings = get_project_settings()
    report_async({"command": f"dg env {action}"}, settings=settings, status="start")
    target = settings["environments"][env_name]["target"]
    lb_url = settings["environments"][env_name]["lb_url"]
    docker_registry = settings["environments"][env_name]["docker_registry"]
    first_service = next(iter(settings["services"].values()))
    project_name = settings["project"]["name"]

    if target == "aws_fargate":
        credentials = retreive_aws_creds(project_name, env_name, prompt=prompt)
        awsKey = credentials["aws_key"]
        awsSecret = credentials["aws_secret"]
    else:
        awsKey = None
        awsSecret = None

    envVars = get_env_vars(env_name, first_service["name"])

    response = api.deploy_to_infra({
        "cluster_name": f"{project_name}-{env_name}",
        "service_name": f"{project_name}-{env_name}-{first_service['name']}",
        "image_url": f"{docker_registry}:latest",
        "aws_key": awsKey,
        "aws_secret": awsSecret,
        "env_vars": json.dumps(envVars)
    })

    spinner = Halo(text="deploying ...", spinner="dots")
    spinner.start()
    output = json.loads(response.content)
    spinner.stop()

    print(output["msg"])
    print(f"your deployment URL: http://{lb_url}")
    report_async({"command": f"dg env {action}"}, settings=settings, status="complete")

@env.command(name="destroy")
@click.argument("env_name", nargs=1, required=True)
@click.option('--prompt/--no-prompt', default=False)
def env_destroy(env_name, prompt=False):
    action = "destroy"
    report_async({"command": f"dg env {action}"}, status="start")

    questions = [
        {
            'type': 'input',
            'name': 'sure',
            'message': 'Are you sure (Y/N)?'
        },
    ]

    answers = pyprompt(questions)
    if answers["sure"] != "Y":
        Bcolors.fail("aborting")
        return

    settings = get_project_settings()
    project_name = settings["project"]["name"]
    target = settings["environments"][env_name]["target"]
    
    if target == "aws_fargate":
        credentials = retreive_aws_creds(project_name, env_name, prompt=prompt)
        awsKey = credentials["aws_key"]
        awsSecret = credentials["aws_secret"]
    else:
        awsKey = None
        awsSecret = None


    first_service = next(iter(settings["services"].values()))

    response = api.destroy_infra({
        "aws_key": awsKey,
        "aws_secret": awsSecret,
        "project_name": project_name,
        "environment": env_name,
        "backend_bucket_name": "digger-terraform-states",
        "backend_bucket_region": "eu-west-1",
        "container_port": first_service["port"]
    })
    
    job = json.loads(response.content)

    # loading until infra status is complete
    spinner = Halo(text="destroying infrastructure ...", spinner="dots")
    spinner.start()
    while True:
        statusResponse = api.get_job_info(job['job_id'])
        print(statusResponse.content)
        jobStatus = json.loads(statusResponse.content)
        if jobStatus["status"] == "DESTROYED":
            break
        elif jobStatus["status"] == "FAILED":
            Bcolors.fail("Could not destroy infrastructure")
            print(jobStatus["fail_message"])
            return
        time.sleep(2)

    spinner.stop()
    Bcolors.okgreen("Infrasructure destroyed successfully")
    report_async({"command": f"dg env {action}"}, settings=settings, status="complete")

@env.command(name="history")
def env_history():
    action = "history"
    print("Not implemented yet")

@env.command(name="apply")
@click.argument("env_name", nargs=1, required=True, default="local-docker")
def env_apply(env_name):
    action = "apply"
    report_async({"command": f"dg env {action}"}, status="start")
    Path(f"digger-master/{env_name}").mkdir(parents=True, exist_ok=True)
    if env_name == "local-docker":
        generate_docker_compose_file()
        spin(2, 'Updating local environment ...')
        print("Local environment generated!")
        print("Use `dg env up local-docker` to run your stack locally")
    else:
        print("Not implemented yet")
    report_async({"command": f"dg env {action}"}, status="complete")

@env.command(name="up")
@click.argument("env_name", nargs=1, default="local-docker")
def env_up(env_name):
    action = "up"
    report_async({"command": f"dg env {action}"}, status="start")
    if env_name == "local-docker":
        subprocess.Popen(["docker-compose", "-f", "digger-master/local-docker/docker-compose.yml", "up"]).communicate()
    else:
        print("Not implemented yet")
    report_async({"command": f"dg env {action}"}, status="complete")


def validate_project_name(ctx, param, value):
    if value is None:
        return value
    if len(value) > 0:
        return value
    else:
        raise click.BadParameter("Project name required")

@cli.group()
@require_auth
def project():
    """
        Configure a new project
    """

@project.command(name="init")
@click.option("--name", nargs=1, required=False, callback=validate_project_name)
def project_init(name=None):
    action = "init"
    report_async({"command": f"dg project init"}, status="start")

    if name is None:
        defaultProjectName = os.path.basename(os.getcwd())
        questions = [
            {
                'type': 'input',
                'name': 'project_name',
                'message': 'Enter project name',
                'default': defaultProjectName,
                'validate': lambda x: len(x) > 0
            },
        ]

        answers = pyprompt(questions)

        project_name = answers["project_name"]
    else:
        project_name = name

    # This will throw error if project name is invalid (e.g. project exists)
    api.check_project_name(project_name)

    spinner = Halo(text='Initializing project: ' + project_name, spinner='dots')
    spinner.start()
    settings = init_project(project_name)
    update_digger_yaml(settings)  
    spinner.stop()


    print("project initiated successfully")
    report_async({"command": f"dg project init"}, settings=settings, status="copmlete")


@cli.group()
@require_auth
def service():
    """
        Configure a new service
    """

@service.command(name="create")
def service_create():
    print("not implemented yet")


@service.command(name="add")
def service_add():
    action = "add"
    report_async({"command": f"dg service add"}, status="start")
    # service_names = get_service_names()
    service_names = list(filter(lambda x: x != "digger-master" and os.path.isdir(x) and not x.startswith("."), os.listdir(os.getcwd())))

    if len(service_names) == 0:
        Bcolors.fail("No service directories found, try cloning a repo in here!")
        return

    questions = [
        {
            'type': 'list',
            'name': 'service_name',
            'message': 'select repository',
            'choices': service_names
        },
    ]

    answers = pyprompt(questions)
    service_name = answers["service_name"]
    service_path = os.path.abspath(service_name)

    settings = get_project_settings()

    try:
        dockerfile_path = find_dockerfile(service_name)
    except CouldNotDetermineDockerLocation as e:
        print("Could not find dockerfile in root")
        dockerfile_path = dockerfile_manual_entry()
    dockerfile_path = os.path.abspath(dockerfile_path)

    settings["services"] = settings.get("services", {})
    settings["services"][service_name] = {
        "name": service_name,
        "path": service_path,
        "env_files": [],
        "publicly_accissible": True,
        "type": "container",
        "port": 8080,
        "health_check": "/",
        "dockerfile": dockerfile_path,
        "resources": {},
        "dependencies": {},
    }

    update_digger_yaml(settings)
    spin(1, "Updating DGL config ... ")

    print("Service added succesfully")
    report_async({"command": f"dg service add"}, settings=settings, status="complete")

@cli.command()
@click.argument("folder_name")
@click.option("--region", default="us-east-1", help="Stack region")
@require_auth
def create(folder_name, region):
    if os.path.exists(folder_name):
        Bcolors.fail("Error: folder exists")
        return
    response = api.create_infra_quick({"region": region})
    report_async({"command": f"dg create"}, status="start")

    spinner = Halo(text="creating project", spinner="dots")
    spinner.start()

    contentJson = json.loads(response.content)
    os.mkdir(folder_name)
    os.chdir(folder_name)
    project_name = contentJson["project_name"]
    settings = init_project(project_name)
    # create profile
    profile_name = create_aws_profile(project_name, contentJson["access_key"], contentJson["secret_id"])

    settings["project"]["lb_url"] = contentJson["lb_url"]
    settings["project"]["region"] = contentJson["region"]
    settings["project"]["aws_profile"] = profile_name

    settings["environments"]["prod"] = {
        "target": "digger_paas",
        "lb_url": contentJson["lb_url"],
        "docker_registry": contentJson["docker_registry"],
        "aws_profile": profile_name,
    }

    anodePath = os.path.join(os.getcwd(), "a-nodeapp")
    settings["services"]["a-nodeapp"] = {
        "name": "a-nodeapp",
        "path": anodePath,
        "env_files":  [],
        "publicly_accissible": True,
        "type": "container",
        "port": 8080,
        "dockerfile":  os.path.join(anodePath, "Dockerfile"),
        "resources": {}
    }

    update_digger_yaml(settings)
    clone_repo("https://github.com/diggerhq/a-nodeapp")
    shutil.rmtree("a-nodeapp/.git")
    os.chdir("..")
    spinner.stop()

    Bcolors.okgreen("Project created successfully")
    print(f"Your site is hosted on the following url: {contentJson['lb_url']}")
    report_async({"command": f"dg create"}, settings=settings, status="complete")


@cli.command()
@click.argument("service_name")
# @click.argument("webapp_name")
def logs(service_name):
    """
        Configure a web application (frontend)
    """
    settings = get_project_settings()
    projectName = settings["project"]["name"]
    response = api.get_logs(projectName)
    content = json.loads(response.content)
    for record in content:
        time = datetime.fromtimestamp(record["timestamp"]/1000).strftime("%Y-%m-%d %H:%M")
        print(f'[[{time}]]', record["message"])


@cli.command()
@click.argument("action")
# @click.argument("webapp_name")
def webapp(action):
    """
        Configure a web application (frontend)
    """

    if action == "create":
        pass

    elif action == "add":
        pass

@cli.group()
def resource():
    """
        Configure a resource
    """

@resource.command(name="create")
@click.argument("resource_type", required=True,)
@click.argument("name", required=False)
def resource_create(resource_type, name=None):
    action = "create"

    settings = get_project_settings()
    report_async({"command": f"dg resource create"}, settings=settings, status="start")

    service_names = settings["services"].keys()

    questions = [
    ]

    if name is None:
        questions.append({
            'type': 'input',
            'name': 'resource_name',
            'message': 'What is the resource name?',
        })

    if resource_type == "database":
        questions.append({
            'type': 'list',
            'name': 'engine',
            'message': 'Which Engine',
            'choices': [
                'postgres',
                'mysql',
            ]
        })
    elif resource_type == "email":
        questions.append({
                'type': 'list',
                'name': 'frequency',
                'message': 'How often do you want it to run?',
                'choices': [
                    "minutely",
                    "hourly",
                    "daily",
                    "weekly",
                    "monthly",
                ]
        })

    questions.append({
        'type': 'list',
        'name': 'service_name',
        'message': 'which service?',
        'choices': service_names
    })

    answers = pyprompt(questions)
    service_name = answers["service_name"]
    resource_name = answers["resource_name"]
    engine = answers["engine"]

    settings["services"][service_name]["resources"][resource_name] = {
        "name": resource_name,
        "type": "database",
        "engine": engine,
    }
    update_digger_yaml(settings)
    spin(2, "updating configuration ...")

    print("DGL Config updated")
    report_async({"command": f"dg resource create"}, settings=settings, status="complete")




# exec main function if frozen binary   
if getattr(sys, 'frozen', False):
    cli(sys.argv[1:])