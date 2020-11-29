from __future__ import print_function, unicode_literals
import os
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
from utils.pprint import Bcolors, Halo, spin
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

from PyInquirer import prompt, Separator
import api
from auth import fetch_github_token, require_auth
from exceptions import CouldNotDetermineDockerLocation
from constants import (
    DIGGERHOME_PATH,
    BACKEND_ENDPOINT,
    GITHUB_LOGIN_ENDPOINT,
    HOMEDIR_PATH,
    AWS_HOME_PATH,
    AWSCREDS_FILE_PATH
)

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
        answers = prompt(questions)
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

        answers = prompt(questions)
        answers["aws_key"] = currentAwsKey if answers["aws_key"] == "" else answers["aws_key"]
        answers["aws_secret"] = currentAwsSecret if answers["aws_secret"] == "" else answers["aws_secret"]

    return answers

def get_digger_profile(projectName, environment):
    global DIGGERHOME_PATH
    diggercredsFile = os.path.join(DIGGERHOME_PATH, "credentials")
    diggerProfileName = f"{projectName}-{environment}"
    diggerconfig = configparser.ConfigParser()
    diggerconfig.read(diggercredsFile)
    if diggerProfileName in diggerconfig:
        return diggerconfig[diggerProfileName]
    else:
        return {}

def retreive_aws_creds(projectName, environment):
    diggercredsFile = os.path.join(DIGGERHOME_PATH, "credentials")
    diggerProfileName = f"{projectName}-{environment}"
    diggerconfig = configparser.ConfigParser()
    diggerconfig.read(diggercredsFile)

    if diggerProfileName not in diggerconfig:
        diggerconfig[diggerProfileName] = {}
    
    currentAwsKey = diggerconfig[diggerProfileName].get("aws_access_key_id", None)
    currentAwsSecret = diggerconfig[diggerProfileName].get("aws_secret_access_key", None)

    answers = prompt_for_aws_keys(currentAwsKey, currentAwsSecret)

    newAwsKey = answers["aws_key"]
    newAwsSecret = answers["aws_secret"]

    diggerconfig[diggerProfileName]["aws_access_key_id"] = newAwsKey
    diggerconfig[diggerProfileName]["aws_secret_access_key"] = newAwsSecret

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

def create_aws_profile(project_name, access_key, secret_id):
    spinner = Halo(text="creating aws profile ...", spinner="dots")
    profile_name = "digger-" + project_name
    spinner.start()
    awscredsFile = AWSCREDS_FILE_PATH
    awsconfig = configparser.ConfigParser()
    awsconfig.read(awscredsFile)

    uniq_profile_name = profile_name
    while uniq_profile_name in awsconfig:
        uniq_profile_name = profile_name + str(random.randint(1,10000))
    profile_name = uniq_profile_name

    awsconfig[profile_name] = {}
    awsconfig[profile_name]["aws_access_key_id"] = access_key
    awsconfig[profile_name]["aws_secret_access_key"] = secret_id

    with open(awscredsFile, 'w') as f:
        awsconfig.write(f)
    spinner.stop()
    return profile_name

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


@click.group()
def cli():
    """
        Digger: Deploy with confidence\n

           ______                    \n
          (, /    ) ,                \n
            /    /    _   _    _  __ \n
          _/___ /__(_(_/_(_/__(/_/ (_\n
        (_/___ /    .-/ .-/          \n
                   (_/ (_/           \n 



    """
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
    report_async({"command": f"dg auth"}, status="start")    
    fetch_github_token()
    report_async({"command": f"dg auth"}, status="complete")


@cli.command()
@click.argument("action", nargs=-1, required=True)
@require_auth
def env(action):
    """
        Configure a new environment
    """
    if action[0] == "list":
        settings = get_project_settings()

        report_async({"command": f"dg env {action}"}, settings=settings, status="start")

        spin(1, "Loading environment list ...")
        for env in settings["environments"].keys():
            print(f">> {env}")

        report_async({"command": f"dg env {action}"}, settings=settings, status="complete")


    elif action[0] == "create":
        targets = get_targets()
        env_name = action[1]
        settings = get_project_settings()
        report_async({"command": f"dg env {action}"}, settings=settings, status="start")
        project_name = settings["project"]["name"]

        questions = [
            {
                'type': 'list',
                'name': 'target',
                'message': 'Select target',
                'choices': targets.keys()
            },
        ]

        answers = prompt(questions)

        target = answers["target"]

        if target not in ["AWS ECS Fargate", "Digger Paas"]:
            Bcolors.fail("This option is currently unsupported! Please try again")
            return

        if target == "AWS EC2 docker-compose":
            questions = [
                {
                    'type': 'list',
                    'name': 'termination',
                    'message': 'When do you want to terminate?',
                    'choices': [
                        "12 hours",
                        "1 day",
                        "never",
                    ]
                },
            ]
            answers = prompt(questions)

        if target == "AWS ECS Fargate":
            credentials = retreive_aws_creds(project_name, env_name)
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

        response = api.create_infra({
            "aws_key": credentials["aws_key"],
            "aws_secret": credentials["aws_secret"],
            "project_name": project_name,
            "project_type": targets[target],
            "backend_bucket_name": "digger-terraform-states",
            "backend_bucket_region": "eu-west-1",
            "backend_bucket_key": f"{project_name}/project",
            "container_port": first_service["port"]
        })
        job = json.loads(response.content)

        # loading until infra status is complete
        spinner = Halo(text="generating infrastructure ...", spinner="dots")
        spinner.start()
        while True:
            statusResponse = api.get_job_info(job['job_id'])
            print(statusResponse.content)
            jobStatus = json.loads(statusResponse.content)
            if jobStatus["status"] == "COMPLETED":
                break
            elif jobStatus["status"] == "FAILED":
                Bcolors.fail("Could not create infrastructure")
                print(jobStatus["fail_message"])
                return
            time.sleep(2)

        spinner.stop()

        # aws profile creation
        profile_name = create_aws_profile(project_name, jobStatus["access_key"], jobStatus["secret_id"])

        environments = settings["environments"]
        environments[env_name] = {
            "target": targets[target],
            "lb_url": jobStatus["lb_url"],
        }
        # TODO: profile should be stored in environment not root file
        settings["project"]["aws_profile"] = profile_name
        settings["project"]["docker_registry"] = jobStatus["docker_registry"]
        update_digger_yaml(settings)

        # create a directory for this environment (for environments and secrets)
        Path(f"digger-master/{env_name}").mkdir(parents=True, exist_ok=True)

        print("Deplyment successful!")
        print(f"your deployment URL: http://{jobStatus['lb_url']}")
        
        report_async({"command": f"dg env {action}"}, settings=settings, status="complete")
        
    elif action[0] == "build":
        env_name = action[1]
        settings = get_project_settings()
        report_async({"command": f"dg env {action}"}, settings=settings, status="start")
        project_name = settings["project"]["name"]
        docker_registry = settings["project"]["docker_registry"]
        # for service in settings["services"]:
        #     service_name = service["name"]
        
        # TODO: replace with service name here
        first_service = next(iter(settings["services"].values()))
        service_name = first_service["name"]
        subprocess.Popen(["docker", "build", "-t", project_name, f"{service_name}/"]).communicate()

        subprocess.Popen(["docker", "tag", f"{project_name}:latest", f"{docker_registry}:latest"]).communicate()
        report_async({"command": f"dg env {action}"}, settings=settings, status="complete")


    elif action[0] == "push":
        env_name = action[1]
        settings = get_project_settings()    
        report_async({"command": f"dg env {action}"}, settings=settings, status="start")
        profile_name = settings["project"]["aws_profile"]
        docker_registry = settings["project"]["docker_registry"]
        registry_endpoint = docker_registry.split("/")[0]
        proc = subprocess.run(["aws", "ecr", "get-login-password", "--region", "us-east-1", "--profile", profile_name,], capture_output=True)
        docker_auth = proc.stdout.decode("utf-8")
        subprocess.Popen(["docker", "login", "--username", "AWS", "--password", docker_auth, registry_endpoint]).communicate()
        subprocess.Popen(["docker", "push", f"{docker_registry}:latest"]).communicate()
        report_async({"command": f"dg env {action}"}, settings=settings, status="complete")

    elif action[0] == "deploy":
        env_name = action[1]
        settings = get_project_settings()
        report_async({"command": f"dg env {action}"}, settings=settings, status="start")
        target = settings["environments"][env_name]["target"]
        lb_url = settings["environments"][env_name]["lb_url"]
        docker_registry = settings["project"]["docker_registry"]
        first_service = next(iter(settings["services"].values()))
        project_name = settings["project"]["name"]

        diggerProfile = get_digger_profile(project_name, env_name)
        awsKey = diggerProfile.get("aws_access_key_id", None)
        awsSecret = diggerProfile.get("aws_secret_access_key", None)

        response = api.deploy_to_infra({
            "cluster_name": f"{project_name}-dev",
            "service_name": f"{project_name}-dev",
            "image_url": f"{docker_registry}:latest",
            "aws_key": awsKey,
            "aws_secret": awsSecret
        })

        spinner = Halo(text="deploying ...", spinner="dots")
        spinner.start()
        output = json.loads(response.content)
        spinner.stop()

        print(output["msg"])
        print(f"your deployment URL: http://{lb_url}")
        report_async({"command": f"dg env {action}"}, settings=settings, status="complete")


    elif action[0] == "destroy":
        report_async({"command": f"dg env {action}"}, settings=settings, status="start")
        env_name = action[1]


        questions = [
            {
                'type': 'input',
                'name': 'sure',
                'message': 'Are you sure (Y/N)?'
            },
        ]

        answers = prompt(questions)
        if answers["sure"] != "Y":
            Bcolors.fail("aborting")
            return

        settings = get_project_settings()
        project_name = settings["project"]["name"]
        diggerProfile = get_digger_profile(project_name, env_name)
        awsKey = diggerProfile.get("aws_access_key_id", None)
        awsSecret = diggerProfile.get("aws_secret_access_key", None)
        project_name = settings["project"]["name"]

        first_service = next(iter(settings["services"].values()))

        response = api.destroy_infra({
            "aws_key": awsKey,
            "aws_secret": awsSecret,
            "project_name": project_name,
            "backend_bucket_name": "digger-terraform-states",
            "backend_bucket_region": "eu-west-1",
            "backend_bucket_key": f"{project_name}/project",
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

    elif action[0] == "history":
        pass

    elif action[0] == "apply":
        report_async({"command": f"dg env {action}"}, status="start")
        env_name = action[1]
        Path(f"digger-master/{env_name}").mkdir(parents=True, exist_ok=True)
        if env_name == "local-docker":
            generate_docker_compose_file()
            spin(2, 'Updating local environment ...')
            print("Local environment generated!")
            print("Use `dg env up local-docker` to run your stack locally")
            return

        spin(2, 'Applying infrastructure ...')
        print("Infrastructure apply completed!")
        print(f"your deployment URL: http://digger-mvp.s3-website-{env_name}.us-east-2.amazonaws.com")
        report_async({"command": f"dg env {action}"}, status="complete")

    elif action[0] == "up":
        report_async({"command": f"dg env {action}"}, status="start")
        env_name = action[1]
        if env_name == "local-docker":
            subprocess.Popen(["docker-compose", "-f", "digger-master/local-docker/docker-compose.yml", "up"]).communicate()
        report_async({"command": f"dg env {action}"}, status="complete")


@cli.command()
@click.argument("action")
def target(action):
    """
        Configure a new target
    """


@cli.command()
@click.argument("action")
@require_auth
def project(action):
    """
        Configure a new project
    """
    if action == "init":
        report_async({"command": f"dg project init"}, status="start")

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

        answers = prompt(questions)

        project_name = answers["project_name"]

        spinner = Halo(text='Initializing project: ' + project_name, spinner='dots')
        spinner.start()
        settings = init_project(project_name)
        update_digger_yaml(settings)  
        spinner.stop()


        print("project initiated successfully")
        report_async({"command": f"dg project init"}, settings=settings, status="copmlete")


@cli.command()
@click.argument("action")
# @click.argument("service_name")
@require_auth
def service(action):
    """
        Configure a new service
    """

    if action == "create":
        pass

    if action == "add":
        report_async({"command": f"dg service add"}, status="complete")
        # service_names = get_service_names()
        service_names = list(filter(lambda x: x != "digger-master" and os.path.isdir(x), os.listdir(os.getcwd())))

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

        answers = prompt(questions)
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

    settings["project"]["docker_registry"] = contentJson["docker_registry"]
    settings["project"]["lb_url"] = contentJson["lb_url"]
    settings["project"]["region"] = contentJson["region"]
    settings["project"]["aws_profile"] = profile_name

    settings["environments"]["prod"] = {
        "target": "digger_paas",
        "lb_url": contentJson["lb_url"]
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
@click.argument("action")
@click.argument("trigger_type")
def trigger(action, trigger_type):
    """
        Configure a trigger for a service
    """



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

@cli.command()
@click.argument("action")
@click.argument("resource_type")
# @click.argument("resource_name")
def resource(action, resource_type):
    """
        Configure a resource
    """
    if action == "create":

        settings = get_project_settings()
        report_async({"command": f"dg resource create"}, settings=settings, status="start")

        service_names = settings["services"].keys()

        questions = [
            {
                'type': 'input',
                'name': 'resource_name',
                'message': 'What is the resource name?',
            }
        ]

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

        answers = prompt(questions)
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


    else:
        Bcolors.warn(f"Error, unkonwn action {action}")





# exec main function if frozen binary   
if getattr(sys, 'frozen', False):
    cli(sys.argv[1:])