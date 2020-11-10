from __future__ import print_function, unicode_literals
import os
import sys
import time
import json
import configparser
import random
from environs import Env
import requests
import click
from pathlib import Path
from collections import OrderedDict
import subprocess
import webbrowser
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
from halo import Halo
from PyInquirer import prompt, Separator
from exceptions import CouldNotDetermineDockerLocation


def get_base_path():
    # for pyinstaller binaries we use sys.MEIPASS otherwise fetch from __file__
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.abspath(os.path.dirname(__file__))

# TODO: use pkg_resources_insead of __file__ since latter will not work for egg
BASE_PATH = get_base_path()
HOMEDIR_PATH = str(Path.home())
DIGGERHOME_PATH = os.path.join(HOMEDIR_PATH, ".digger/")
env = Env()
env.read_env(f"{BASE_PATH}/env/.env", recurse=False)
BACKEND_ENDPOINT = env("BACKEND_ENDPOINT")

PROJECT = {}

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    OKPINK = '\033[35m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @classmethod
    def print(cls, msg, ctype):
        print(f"{ctype}{msg}{cls.ENDC}")

    @classmethod
    def header(cls, msg):
        cls.print(msg, cls.HEADER)

    @classmethod
    def okblue(cls, msg):
        cls.print(msg, cls.OKBLUE)

    @classmethod
    def okgreen(cls, msg):
        cls.print(msg, cls.OKGREEN)

    @classmethod
    def warn(cls, msg):
        cls.print(msg, cls.WARN)

    @classmethod
    def fail(cls, msg):
        cls.print(msg, cls.FAIL)

    @classmethod
    def endc(cls, msg):
        cls.print(msg, cls.ENDC)

    @classmethod
    def bold(cls, msg):
        cls.print(msg, cls.BOLD)

    @classmethod
    def underline(cls, msg):
        cls.print(msg, cls.UNDERLINE)

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
    return diggerconfig[diggerProfileName]

def retreive_aws_creds(projectName, environment):
    global DIGGERHOME_PATH
    Path(DIGGERHOME_PATH).mkdir(parents=True, exist_ok=True)
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


def clone_repo(url):
    subprocess.Popen(["git", "clone", url]).communicate()

def spin(t, msg, mode='dots'):
    spinner = Halo(text=msg, spinner=mode)
    spinner.start()
    time.sleep(t)
    spinner.stop()

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
    # print("Hello from " + string)

@cli.command()
def version():
    """
        Print the current cli version
    """
    print("0.1")

@cli.command()
def auth():
    webbrowser.open("file:///Users/mohamedsayed/Documents/dgr-auth/auth.html")

@cli.command()
def up():
    """
        Spin up an environment
    """
    spin(2, "Generating docker-compose ...")
    print("docker-compose.yml generated")

@cli.command()
@click.argument("action", nargs=-1, required=True)
def env(action):
    """
        Configure a new environment
    """
    if action[0] == "list":
        settings = get_project_settings()
        spin(1, "Loading environment list ...")
        for env in settings["environments"].keys():
            print(f">> {env}")

    elif action[0] == "create":
        targets = get_targets()
        env_name = action[1]
        settings = get_project_settings()
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
            bcolors.fail("This option is currently unsupported! Please try again")
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

        
        response = requests.post(f"{BACKEND_ENDPOINT}/api/create", data={
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
            statusResponse = requests.get(f"{BACKEND_ENDPOINT}/api/jobs/{job['job_id']}/status")
            print(statusResponse.content)
            jobStatus = json.loads(statusResponse.content)
            if jobStatus["status"] == "COMPLETED":
                break
            time.sleep(2)

        spinner.stop()

        # aws profile creation
        spinner = Halo(text="creating aws profile ...", spinner="dots")
        profile_name = "digger-" + project_name
        spinner.start()
        awscredsFile = f"{os.getenv('HOME')}/.aws/credentials"
        awsconfig = configparser.ConfigParser()
        awsconfig.read(awscredsFile)

        uniq_profile_name = profile_name
        while uniq_profile_name in awsconfig:
            uniq_profile_name = profile_name + str(random.randint(1,10000))
        profile_name = uniq_profile_name

        awsconfig[profile_name] = {}
        awsconfig[profile_name]["aws_access_key_id"] = jobStatus["access_key"]
        awsconfig[profile_name]["aws_secret_access_key"] = jobStatus["secret_id"]

        with open(awscredsFile, 'w') as f:
            awsconfig.write(f)
        spinner.stop()

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
    
    elif action[0] == "build":
        env_name = action[1]

        settings = get_project_settings()
        project_name = settings["project"]["name"]
        docker_registry = settings["project"]["docker_registry"]
        # for service in settings["services"]:
        #     service_name = service["name"]
        
        # TODO: replace with service name here
        first_service = next(iter(settings["services"].values()))
        service_name = first_service["name"]
        subprocess.Popen(["docker", "build", "-t", project_name, f"{service_name}/"]).communicate()

        subprocess.Popen(["docker", "tag", f"{project_name}:latest", f"{docker_registry}:latest"]).communicate()

    elif action[0] == "push":
        env_name = action[1]
        settings = get_project_settings()     
        profile_name = settings["project"]["aws_profile"]
        docker_registry = settings["project"]["docker_registry"]
        registry_endpoint = docker_registry.split("/")[0]
        proc = subprocess.run(["aws", "ecr", "get-login-password", "--region", "us-east-1", "--profile", profile_name,], capture_output=True)
        docker_auth = proc.stdout.decode("utf-8")
        subprocess.Popen(["docker", "login", "--username", "AWS", "--password", docker_auth, registry_endpoint]).communicate()
        subprocess.Popen(["docker", "push", f"{docker_registry}:latest"]).communicate()

    elif action[0] == "deploy":
        env_name = action[1]

        settings = get_project_settings()
        target = settings["environments"][env_name]["target"]
        lb_url = settings["environments"][env_name]["lb_url"]
        docker_registry = settings["project"]["docker_registry"]
        first_service = next(iter(settings["services"].values()))
        project_name = settings["project"]["name"]

        diggerProfile = get_digger_profile(project_name, env_name)
        awsKey = diggerProfile.get("aws_access_key_id", None)
        awsSecret = diggerProfile.get("aws_secret_access_key", None)

        response = requests.post(f"{BACKEND_ENDPOINT}/api/deploy", data={
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


    elif action[0] == "destroy":

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
            bcolors.fail("aborting")
            return

        settings = get_project_settings()
        project_name = settings["project"]["name"]
        diggerProfile = get_digger_profile(project_name, env_name)
        awsKey = diggerProfile.get("aws_access_key_id", None)
        awsSecret = diggerProfile.get("aws_secret_access_key", None)
        project_name = settings["project"]["name"]

        first_service = next(iter(settings["services"].values()))

        response = requests.post(f"{BACKEND_ENDPOINT}/api/destroy", data={
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
            statusResponse = requests.get(f"{BACKEND_ENDPOINT}/api/destroy_jobs/{job['job_id']}/status")
            print(statusResponse.content)
            jobStatus = json.loads(statusResponse.content)
            if jobStatus["status"] == "COMPLETED":
                break
            time.sleep(2)

        spinner.stop()        
        bcolors.okgreen("Infrasructure destroyed successfully")

    elif action[0] == "history":
        print(f"""
{bcolors.OKCYAN}commit b5b15d4d{bcolors.ENDC} fix monolith
{bcolors.OKCYAN}commit 9b402a4c{bcolors.ENDC} fix downstream calls
{bcolors.OKBLUE}infra e3f9ab4c8{bcolors.ENDC} initial infra apply
{bcolors.OKCYAN}commit 8be5fe36{bcolors.ENDC} fix flask
{bcolors.OKPINK}config 2cc5a979{bcolors.ENDC} update postgres_host
""")
    elif action[0] == "apply":
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

    elif action[0] == "rollback":
        env_name = action[1]
        commit_id = action[2]
        spin(2, 'Performing rollback ...')
        print("Rollback completed!")
        print(f"{bcolors.OKCYAN}your deployment URL:{bcolors.ENDC} http://digger-mvp.s3-website-{env_name}.us-east-2.amazonaws.com")

    elif action[0] == "revert":
        env_name = action[1]
        commit_id = action[2]
        spin(2, f'Performing revert of {commit_id}...')
        print("Revert completed!")
        print(f"{bcolors.OKCYAN}your deployment URL:{bcolors.ENDC} http://digger-mvp.s3-website-{env_name}.us-east-2.amazonaws.com")

    elif action[0] == "up":
        env_name = action[1]
        if env_name == "local-docker":
            subprocess.Popen(["docker-compose", "-f", "digger-master/local-docker/docker-compose.yml", "up"]).communicate()


@cli.command()
@click.argument("action")
def target(action):
    """
        Configure a new target
    """


@cli.command()
@click.argument("action")
def project(action):
    """
        Configure a new project
    """
    if action == "init":
        questions = [
            {
                'type': 'input',
                'name': 'project_name',
                'message': 'Enter project name',
            },
        ]

        answers = prompt(questions)

        project_name = answers["project_name"]

        spinner = Halo(text='Initializing project: ' + project_name, spinner='dots')
        spinner.start()
        time.sleep(2)
        spinner.stop()

        Path("digger-master").mkdir(parents=True, exist_ok=True)

        settings = OrderedDict()
        settings["project"] = {
                "name": project_name
        }
        settings["environments"] = settings.get("environments", {})
        settings["environments"]["local-docker"] = {
            "target": "docker"
        }

        update_digger_yaml(settings)

        print("project initiated successfully")


@cli.command()
@click.argument("action")
# @click.argument("service_name")
def service(action):
    """
        Configure a new service
    """

    if action == "create":

        questions = [
            {
                'type': 'list',
                'name': 'language',
                'message': 'What language is the service?',
                'choices': [
                    'Python',
                    'Javascript (Node.js)',
                    'Ruby',
                ]
            },
            {
                'type': 'list',
                'name': 'server_type',
                'message': 'Select template',
                'choices': [
                    'Flask',
                    'Django',
                ]
            },
            {
                'type': 'list',
                'name': 'server_type',
                'message': 'Mode?',
                'choices': [
                    'Serverless',
                    'Containers',
                ]
            },
        ]

        answers = prompt(questions)

        server_type = answers["server_type"]

        spin(2, "Initializing repositories ... ")

        print("Service repositories created")

    elif action == "add":
        
        # service_names = get_service_names()
        service_names = filter(lambda x: x != "digger-master" and os.path.isdir(x), os.listdir(os.getcwd()))

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

        questions = [
            {
                'type': 'list',
                'name': 'language',
                'message': 'What language is the service?',
                'choices': [
                    'Python',
                    'Javascript (Node.js)',
                    'Ruby',
                ]
            },
            {
                'type': 'list',
                'name': 'server_type',
                'message': 'Select template',
                'choices': [
                    'Flask',
                    'Django',
                ]
            },
            
            {
                'type': 'list',
                'name': 'server_type',
                'message': 'Mode?',
                'choices': [
                    'Serverless',
                    'Containers',
                ]
            },
        ]

        answers = prompt(questions)

        server_type = answers["server_type"]

        spinner = Halo(text='Initializing repositories ... ', spinner='dots')
        spinner.start()
        time.sleep(2)
        spinner.stop()

        print("Service repositories created")

    elif action == "add":

        service_names = get_service_names()
        questions = [
            {
                'type': 'input',
                'name': 'webapp_name',
                'message': 'What is the webapp name?',
            },
            {
                'type': 'list',
                'name': 'repo',
                'message': 'select repository',
                'choices': service_names
            },

        ]

        answers = prompt(questions)

        spin(1, "Updating DGL config ... ")

        repo = answers["repo"]
        service = services()[service_names.index(repo)]
        service_url = service["service_url"]
        service_name = service["service_name"]
        settings = get_project_settings()
        settings["frontends"] = settings.get("frontends", {})
        settings["frontends"][service_name] = {
            "publicly_accissible": True,
            "paths": ["/"],
        }
        update_digger_yaml(settings)
        clone_repo(service_url)

        print("Service added succesfully")


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

    else:
        bcolors.warn(f"Error, unkonwn action {action}")





# exec main function if frozen binary   
if getattr(sys, 'frozen', False):
    cli(sys.argv[1:])