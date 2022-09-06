from __future__ import print_function, unicode_literals
import os
from pprint import pprint
import re
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
import yaml
from oyaml import load as yload, dump as ydump

from diggercli.deploy import deploy_lambda_function_code, deploy_nextjs_code, assume_role

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
from diggercli.projects import create_temporary_project
from diggercli.auth import (
    fetch_github_token,
    require_auth,
    fetch_github_token_with_cli_callback
)
from diggercli.exceptions import CouldNotDetermineDockerLocation, ApiRequestException
from diggercli import diggerconfig
from diggercli.validators import ProjectNameValidator, env_name_validate
from diggercli.transformers import transform_service_name
from diggercli._version import __version__
from diggercli.constants import (
    PAAS_TARGET,
    DIGGER_SPLASH,
    DOCKER_REMOTE_HOST,
    DIGGERHOME_PATH,
    AWS_HOME_PATH,
    AWS_REGIONS,
    ServiceType,
)
from diggercli.utils.pprint import Bcolors, Halo, spin, SpinnerSegment
from diggercli.utils.misc import (
    compute_env_vars_with_overrides,
    parse_env_config_options, 
    read_env_config_from_file
)

# TODO: use pkg_resources_insead of __file__ since latter will not work for egg


PROJECT = {}


def digger_yaml():
    return "digger.yml"

def get_project_settings():
    return yload(open(digger_yaml()), Loader=Loader)

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

def dockerfile_manual_entry(service_path):
    while True:
        print("Please enter path to Dockerfile directly (relative to root service folder)")
        path = input()
        if os.path.exists(os.path.join(service_path, path)):
            return path
        else:
            print("error, dockerfile not found")

def prompt_for_aws_keys(currentAwsKey, currentAwsSecret):
    if currentAwsKey is None or currentAwsSecret is None:
        questions = [
            {
                'type': 'password',
                'name': 'aws_key',
                'message': f'Your AWS Key',
                'validate': lambda x: len(x) > 0
            },
            {
                'type': 'password',
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
                'type': 'password',
                'name': 'aws_key',
                'message': f'Your AWS Key ({maskedAwsKey}***)',
            },
            {
                'type': 'password',
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

def retreive_aws_creds(projectName, environment, aws_key=None, aws_secret=None, prompt=True):
    diggercredsFile = os.path.join(DIGGERHOME_PATH, "credentials")
    profileName = f"{projectName}"
    diggerconfig = configparser.ConfigParser()
    diggerconfig.read(diggercredsFile)

    if profileName not in diggerconfig:
        diggerconfig[profileName] = {}
    
    if aws_key is not None and aws_secret is not None:
        currentAwsKey = aws_key
        currentAwsSecret = aws_secret
    else:
        currentAwsKey = diggerconfig[profileName].get("aws_access_key_id", aws_key)
        currentAwsSecret = diggerconfig[profileName].get("aws_secret_access_key", aws_secret)

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
    composeFile = pkg_resources.open_text("diggercli.templates.environments.local-docker", 'docker-compose.yml')
    composeContent = composeFile.read()
    composeTemplate = Template(composeContent)

    # generate environment files
    for service in settings["services"].values():
        for resource in service["resources"].values():
            env_path = "digger-master/local-docker/"
            env_file = f"{service['service_name']}_{resource['name']}.env"
            # assuming its a database
            envFile = pkg_resources.open_text("diggercli.templates.environments.local-docker", f".{resource['engine'].lower()}.env")
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

    # including absolute dockerfile path
    for service in settings["services"].values():
        service["dockerfile_absolute"] = os.path.abspath(service["dockerfile"])
        service["path_absolute"] = os.path.abspath(service["path"])
        
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

class DiggerTargets:
    FARGATE = "AWS ECS Fargate"
    LAMBDA = "AWS lambda (experimental)"
    EKS = "(soon!) AWS EKS"
    GCR = "(soon!) Google Cloud Run"
    OTHER = "other"

    TARGETS = {
        FARGATE: "diggerhq/target-fargate@v1.0.4",
        LAMBDA: "diggerhq/target-lambda@master",
        EKS: "aws_eks",
        GCR: "gcp_cloudrun",
        OTHER: "other",
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
            "settings": settings,
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
@click.option('--version', '-v', is_flag=True, is_eager=True,
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
    """
        Authenticate with github
    """
    # report_async({"command": f"dg auth"}, status="start")    
    fetch_github_token()
    report_async({"command": f"dg auth"}, status="complete")


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
                'validate': ProjectNameValidator
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
def env():
    """
        Configure a new environment
    """


@env.command(name="list")
@click.option("--project-name", required=False)
def env_list(project_name=None):
    settings = get_project_settings()
    report_async({"command": f"dg env list"}, settings=settings, status="start")

    if project_name is None:
        if "project" not in settings:
            Bcolors.fail("could not load project name from settings")
            Bcolors.fail("please pass project via --project-name parameter")
            sys.exit(1)
        project_name = settings["project"]["name"]

    response = api.get_project_environments(project_name)
    environments = json.loads(response.content)["results"]

    for env in environments:
        print(f">> {env['name']}")
        print(f"  -> pk={env['pk']}")
        print(f"  -> target={env['target']}")
        print(f"  -> region={env['region']}")
        print(f"  -> config_options={env['config_options']}")
        print(f"  -> aws_key={env['aws_key'][:4]}****{env['aws_key'][-4:]}")
    report_async({"command": f"dg env list"}, settings=settings, status="complete")


@env.command(name="describe")
@click.argument("env_name", nargs=1, required=True)
def env_describe(env_name):
    settings = get_project_settings()
    report_async({"command": f"dg env details"}, settings=settings, status="start")

    project_name = settings["project"]["name"]
    env = api.get_environment_details(project_name, env_name)
    envId = env["pk"]
    response = api.get_last_infra_deployment_info(project_name, envId)
    infraDeploymentDetails = json.loads(response.content)

    print(f">> {env['name']}")
    print(f"  -> pk={env['pk']}")
    print(f"  -> target={env['target']}")
    print(f"  -> region={env['region']}")
    print(f"  -> config_options={env['config_options']}")
    print(f"  -> aws_key={env['aws_key'][:4]}****{env['aws_key'][-4:]}")
    report_async({"command": f"dg env list"}, settings=settings, status="complete")
    pprint(infraDeploymentDetails)
    
    report_async({"command": f"dg env details"}, settings=settings, status="complete")
import subprocess

subprocess.STDOUT

@env.command(name="create")
@click.argument("env_name", nargs=1, required=True)
@click.option("--target", "-t", required=False)
@click.option("--region", "-r", required=False)
@click.option("--config", "-c", multiple=True, required=False)
@click.option("--aws-key", required=False)
@click.option("--aws-secret", required=False)
@click.option('--prompt/--no-prompt', default=True)
def env_create(
    env_name, 
    target=None,
    region=None,
    aws_key=None,
    aws_secret=None,
    config=[],
    prompt=True
):

    try:
        env_name_validate(env_name)
    except ValueError as e:
        Bcolors.warn(str(e))
        sys.exit()

    # parsing config options

    cliOptions = parse_env_config_options(config)
    try:
        configOptions = read_env_config_from_file(env_name, overrideOptions=cliOptions)
    except yaml.YAMLError as ex:
        print(f"Could not read config file: {exc}")
        return

    targets = DiggerTargets.TARGETS
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
        target_key = answers["target"]
        target = targets[target_key]

        if target == "other":

            ok = "n"
            while (ok.lower() != "y"):
                print("Enter target: ", end="")
                target = input()
                print(f"Confirm Target {target} (Y/N)?", end="")
                ok = input()

        elif target_key not in [DiggerTargets.FARGATE, DiggerTargets.LAMBDA]:
            Bcolors.fail("This option is currently unsupported! Please try again")
            return
    else:
        # use target from cli arg
        target = target

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

    credentials = retreive_aws_creds(project_name, env_name, aws_key=aws_key, aws_secret=aws_secret, prompt=prompt)
    aws_key = credentials["aws_key"]
    aws_secret = credentials["aws_secret"]

    spinner = Halo(text="Creating environment", spinner="dots")
    spinner.start()

    response = api.create_environment(project_name, {
        "name": env_name,
        "target": target,
        "region": region,
        "aws_key": aws_key,
        "aws_secret": aws_secret,
        "config_options": configOptions
    })
    spinner.stop()

    Bcolors.okgreen("Environment created successfully")
    Bcolors.okgreen(f"Use this command to run it: dg env apply {env_name}")

@env.command(name="update")
@click.argument("env_name", nargs=1, required=True)
@click.option("--target", "-t", required=False)
@click.option("--config", "-c", multiple=True, required=False)
@click.option("--aws-key", required=False)
@click.option("--aws-secret", required=False)
def env_update(env_name, target=None, config=None, aws_key=None, aws_secret=None):
    settings = get_project_settings()
    report_async({"command": f"dg env update"}, settings=settings, status="start")

    projectName = settings["project"]["name"]
    envDetails = api.get_environment_details(projectName, env_name)
    envPk = envDetails["pk"]

    data = {}
    if target is not None:
        data["target"] = target
    if config is not None:
        data["config_options"] = parse_env_config_options(config)
        cliOptions = parse_env_config_options(config)
        try:
            configOptions = read_env_config_from_file(env_name, overrideOptions=cliOptions)
        except yaml.YAMLError as ex:
            print(f"Could not parse config file: {exc}")
            return
        data["config_options"] = configOptions
        data["config_options"] = data["config_options"]
    if aws_key is not None:
        data["aws_key"] = aws_key
    if aws_secret is not None:
        data["aws_secret"] = aws_secret

    response = api.update_environment(projectName, envPk, data)
    Bcolors.okgreen("environment udpated succesfully")
    report_async({"command": f"dg env update"}, settings=settings, status="stop")


@env.command(name="apply")
@click.argument("env_name", nargs=1, required=True)
@click.option("--verbose/--no-verbose", default=False)
def env_apply(env_name, verbose):

    settings = get_project_settings()
    report_async({"command": f"dg env apply"}, settings=settings, status="start")
    projectName = settings["project"]["name"]
    envDetails = api.get_environment_details(projectName, env_name)
    envPk = envDetails["pk"]
    response = api.apply_environment(projectName, envPk)
    job = json.loads(response.content)

    # loading until infra status is complete
    print("creating infrastructure ...")
    spinner = Halo(text="", spinner="dots")
    spinner.start()

    if verbose:
        with api.stream_deployment_logs(projectName, job['job_id']) as r:
            for line in r.iter_lines():
                line = line.decode("utf-8")
                print(line)

    while True:
        statusResponse = api.get_infra_deployment_info(projectName, job['job_id'])
        print(statusResponse.content)
        jobStatus = json.loads(statusResponse.content)


        if jobStatus["status"] == "COMPLETED":
            break
        elif jobStatus["status"] == "FAILED":
            Bcolors.fail("Could not create infrastructure")
            print(jobStatus["fail_message"])
            sys.exit(1)
        time.sleep(2)
    spinner.stop()


    print("Deployment successful!")
    print(f"your deployment details:")
    pprint(jobStatus["outputs"])

    report_async({"command": f"dg env apply"}, settings=settings, status="complete")


@env.command(name="plan")
@click.argument("env_name", nargs=1, required=True)
def env_plan(env_name):

    settings = get_project_settings()
    report_async({"command": f"dg env plan"}, settings=settings, status="start")
    projectName = settings["project"]["name"]
    envDetails = api.get_environment_details(projectName, env_name)
    envPk = envDetails["pk"]
    spinner = Halo(text="Planning environment ...", spinner="dots")
    spinner.start()
    response = api.plan_environment(projectName, envPk)
    spinner.stop()
    Bcolors.okgreen("Your environment plan is shown below")
    print("--------------------------------")
    data = json.loads(response.content)
    pprint(data["output"])
    report_async({"command": f"dg env plan"}, settings=settings, status="complete")


@env.command(name="cost")
@click.argument("env_name", nargs=1, required=True)
def env_cost(env_name):

    settings = get_project_settings()
    report_async({"command": f"dg env cost"}, settings=settings, status="start")
    projectName = settings["project"]["name"]
    envDetails = api.get_environment_details(projectName, env_name)
    envPk = envDetails["pk"]
    spinner = Halo(text="Estimating environment costs ...", spinner="dots")
    spinner.start()
    response = api.estimate_cost(projectName, envPk)
    spinner.stop()
    Bcolors.okgreen("Your cost estimates are shown below")
    print("--------------------------------")
    pprint(response.content)
    report_async({"command": f"dg env cost"}, settings=settings, status="complete")


@env.command(name="sync-tform")
@click.argument("env_name", nargs=1, required=True)
def env_sync_tform(env_name):
    settings = get_project_settings()
    report_async({"command": f"dg env sync-tform"}, settings=settings, status="start")
    project_name = settings["project"]["name"]
    services = settings["services"]
    env_path = f"digger-master/{env_name}"
    tform_path = f"{env_path}/terraform"
    target = settings["environments"][env_name]["target"]
    region = settings["environments"][env_name]["region"]
    Path(env_path).mkdir(parents=True, exist_ok=True)
    Path(tform_path).mkdir(parents=True, exist_ok=True)
    shutil.rmtree(tform_path) 
    # tform generation
    spinner = Halo(text="Updating terraform ...", spinner="dots")
    spinner.start()
    download_terraform_files(project_name, env_name, region, target, services, tform_path)
    spinner.stop()
    Bcolors.okgreen("Terraform updated successfully")        
    report_async({"command": f"dg env sync-tform"}, settings=settings, status="complete")


@env.command(name="vars:list")
@click.argument("env_name", nargs=1, required=True)
def env_vars_list(env_name):
    """
        List environment variables for an environment
    """
    action = "vars:list"
    settings = get_project_settings()
    report_async({"command": f"dg env {action}"}, settings=settings, status="start")
    project_name = settings["project"]["name"]
    envDetails = api.get_environment_details(project_name, env_name)
    envId = envDetails["pk"]
    envVars = api.environment_vars_list(project_name, envId)
    envVars = json.loads(envVars.content)["results"]
    report_async({"command": f"dg env {action}"}, settings=settings, status="complete")
    pprint(envVars)


@env.command(name="vars:create")
@click.argument("env_name", nargs=1, required=True)
@click.option('--file', required=True)
@click.option('--overwrite/--no-overwrite', default=False)
@click.option('--prompt/--no-prompt', default=True)
def env_vars_create(env_name, file, prompt=True, overwrite=False):
    """
        Update environment variables for an environment based on .yml file
        --overwrite forces overwriting of existing variables
    """
    action = "vars:create"
    if not os.path.exists(file):
        Bcolors.fail("File does not exist")
        sys.exit(1)

    settings = get_project_settings()
    report_async({"command": f"dg env {action}"}, settings=settings, status="start")

    project_name = settings["project"]["name"]
    if prompt and not overwrite:
        Bcolors.warn("Note: Environment update will fail if duplicate variables names exist. Proceed? (Y,N)")
        Bcolors.okgreen("Hint: If you wish to overwrite existing vars use the --overwrite option along with this command")

        answer = input()
        if answer.lower() != "y":
            Bcolors.fail("Aborting ...")
            sys.exit(1)

    try:
        varsToCreate = yload(open(file), Loader=Loader)
    except Exception as e:
        Bcolors.fail("Error while loading vars file")
        print(e)
        sys.exit(1)

    envDetails = api.get_environment_details(project_name, env_name)
    envId = envDetails["pk"]

    services = api.list_services(project_name)
    services = json.loads(services.content)["results"]
    servicesDict = {}
    for s in services:
        servicesDict[s["name"]] = s

    for serviceName, varItems in varsToCreate.items():
        if serviceName == "all":
            servicePk = None
        else:
            if serviceName not in servicesDict.keys():
                Bcolors.fail(f"serviceName not found in backend: {serviceName}")
                sys.exit(1)
            servicePk = servicesDict[serviceName]["pk"]

        Bcolors.okgreen(f"Creating vars for service: {serviceName}:")
        for varName, varValue in varItems.items():
            Bcolors.okgreen(f"> Creating var ({varName}, {varValue}) ...")
            response = api.environment_vars_create(
                project_name, 
                envId, 
                varName, 
                varValue, 
                servicePk,
                overwrite=overwrite
            )
            Bcolors.okgreen(f">> Created!")


    report_async({"command": f"dg env {action}"}, settings=settings, status="complete")


@env.command(name="build")
@click.argument("env_name", nargs=1, required=True)
@click.option('--service', default=None)
@click.option('--remote/--no-remote', default=False)
@click.option('--tag', default="latest")
@click.option('--context', default=None)
def env_build(env_name, service, remote, context=None, tag="latest"):
    action = "build"
    settings = get_project_settings()
    report_async({"command": f"dg env {action}"}, settings=settings, status="start")


    if service is None:
        defaultProjectName = os.path.basename(os.getcwd())
        questions = [
            {
                'type': 'list',
                'name': 'service_name',
                'message': 'Select Service',
                'choices': settings["services"].keys(),
            },
        ]

        answers = pyprompt(questions)

        service_key = answers["service_name"]
    else:
        service_key = service

    project_name = settings["project"]["name"]
    service_name = settings["services"][service_key]["service_name"]
    service_type = settings["services"][service_key]["service_type"]
    webapp_package_manager = settings["services"][service_key]["webapp_package_manager"]
    service_runtime = settings["services"][service_key]["lambda_runtime"]
    service_path = settings["services"][service_key]["path"]
    envDetails = api.get_environment_details(project_name, env_name)
    envId = envDetails["pk"]
    exposeVarsAtBuild = envDetails["inject_env_variables_at_build_time"]

    if context is None:
        context = f"{service_path}/"
    
    envVars = api.environment_vars_list(project_name, envId)
    envVars = json.loads(envVars.content)["results"]
    
    serviceDetails = api.get_service_by_name(project_name, service_name)
    servicePk = serviceDetails["pk"]

    if service_type in [ServiceType.WEBAPP, ServiceType.NEXTJS]:
        build_command = settings["services"][service_key]["build_command"]

        envVarsWithOverrides = compute_env_vars_with_overrides(envVars, servicePk)
        # expose env variables
        for name, value in envVarsWithOverrides.items():
            os.environ[name] = value

        # run it in service context
        if webapp_package_manager == "yarn":
            subprocess.run(["yarn", "install", "--prefix", context], check=True)
        else:
            subprocess.run(["npm", "install", "--prefix", context], check=True)

        print(f"build command to execute: {build_command}")
        # ensure that && separator works as expected
        for cmd in build_command.split("&&"):
            current_cmd = cmd.strip().split(" ")
            if current_cmd[0] == "npm":
                current_cmd = current_cmd + ["--prefix", context]
            subprocess.run(current_cmd, check=True)

        subprocess.run(["pwd"], check=True)
        subprocess.run(["ls", "-a"], check=True)

    elif service_type == ServiceType.CONTAINER or (service_type == ServiceType.SERVERLESS and service_runtime == "Docker"):
        dockerfile = settings["services"][service_key]["dockerfile"]
        response = api.get_last_infra_deployment_info(project_name, envId)
        infraDeploymentDetails = json.loads(response.content)
        docker_registry = infraDeploymentDetails["outputs"]["services"][service_name]["docker_registry"]

        if remote:
            os.environ["DOCKER_HOST"] = DOCKER_REMOTE_HOST

        buildArgs = []
        if exposeVarsAtBuild:
            envVarsWithOverrides = compute_env_vars_with_overrides(envVars, servicePk)

            for name, value in envVarsWithOverrides.items():
                os.environ[name] = value
                buildArgs = buildArgs + ["--build-arg", name]

        docker_build_command = ["docker", "build", "-t", f"{project_name}-{service_name}:{tag}"] + \
                               buildArgs + \
                               ["-f", f"{dockerfile}", context]

        subprocess.run(docker_build_command, check=True)
        subprocess.run(["docker", "tag", f"{project_name}-{service_name}:{tag}", f"{docker_registry}:{tag}"], check=True)
    else:
        Bcolors.warn(f"This service type does not support build phase: {service_type}, skipping ...")
        sys.exit(0)

    report_async({"command": f"dg env {action}"}, settings=settings, status="complete")


@env.command(name="push")
@click.argument("env_name", nargs=1, required=True)
@click.option('--service', default=None)
@click.option("--aws-key", required=False)
@click.option("--aws-secret", required=False)
@click.option("--aws-assume-role-arn", required=False)
@click.option("--aws-assume-external-id", required=False)
@click.option('--remote/--no-remote', default=False)
@click.option('--tag', default="latest")
@click.option('--prompt/--no-prompt', default=False)
def env_push(env_name, service, remote, aws_key=None, aws_secret=None, aws_assume_role_arn=None, aws_assume_external_id=None, tag="latest", prompt=False):
    action = "push"
    settings = get_project_settings()
    report_async({"command": f"dg env {action}"}, settings=settings, status="start")

    if service is None:
        questions = [
            {
                'type': 'list',
                'name': 'service_name',
                'message': 'Select Service',
                'choices': settings["services"].keys(),
            },
        ]

        answers = pyprompt(questions)

        service_key = answers["service_name"]
    else:
        service_key = service

    project_name = settings["project"]["name"]
    service_name = settings["services"][service_key]["service_name"]
    service_type = settings["services"][service_key]["service_type"]
    service_runtime = settings["services"][service_key]["lambda_runtime"]

    if service_type == ServiceType.CONTAINER or (service_type == ServiceType.SERVERLESS and service_runtime == "Docker"):
        envDetails = api.get_environment_details(project_name, env_name)
        envId = envDetails["pk"]
        response = api.get_last_infra_deployment_info(project_name, envId)
        infraDeploymentDetails = json.loads(response.content)

        if remote:
            os.environ["DOCKER_HOST"] = DOCKER_REMOTE_HOST

        docker_registry = infraDeploymentDetails["outputs"]["services"][service_name]["docker_registry"]
        region = infraDeploymentDetails["region"]
        registry_endpoint = docker_registry.split("/")[0]
        if aws_assume_role_arn:
            (access_key, secret_key, session_token) = assume_role(aws_assume_role_arn, aws_assume_external_id)
            os.environ["AWS_ACCESS_KEY_ID"] = access_key
            os.environ["AWS_SECRET_ACCESS_KEY"] = secret_key
            os.environ["AWS_SESSION_TOKEN"] = session_token
        else:
            credentials = retreive_aws_creds(project_name, env_name, aws_key=aws_key, aws_secret=aws_secret, prompt=prompt)
            os.environ["AWS_ACCESS_KEY_ID"] = credentials["aws_key"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = credentials["aws_secret"]
        proc = subprocess.run(["aws", "ecr", "get-login-password", "--region", region, ], capture_output=True)
        docker_auth = proc.stdout.decode("utf-8")
        subprocess.run(["docker", "login", "--username", "AWS", "--password", docker_auth, registry_endpoint], check=True)
        subprocess.run(["docker", "push", f"{docker_registry}:{tag}"], check=True)
    elif service_type == ServiceType.NEXTJS:
        print(f"ServiceType is NextJS, do nothing for now.")
    else:
        Bcolors.warn(f"This service: {service_type} does not support push command, skipping ...")
        sys.exit(0)

    report_async({"command": f"dg env {action}"}, settings=settings, status="complete")


@env.command(name="release")
@click.argument("env_name", nargs=1, required=True)
@click.option('--service', default=None)
@click.option('--all-services/--not-all-services', default=False)
@click.option("--aws-key", required=False)
@click.option("--aws-secret", required=False)
@click.option("--aws-assume-role-arn", required=False)
@click.option("--aws-assume-external-id", required=False)
@click.option('--prompt/--no-prompt', default=False)
@click.option('--tag', default="latest")
def env_release(env_name, service, tag="latest", aws_key=None, aws_secret=None, aws_assume_role_arn=None, aws_assume_external_id=None, all_services=False, prompt=False):


    def perform_release(settings, env_name, service_key):
        project_name = settings["project"]["name"]
        service_name = settings["services"][service_key]["service_name"]
        service_type = settings["services"][service_key]["service_type"]
        service_path = settings["services"][service_key]["path"]
        service_runtime = settings["services"][service_key]["lambda_runtime"]
        envDetails = api.get_environment_details(project_name, env_name)
        envId = envDetails["pk"]
        region = envDetails["region"]

        response = api.get_last_infra_deployment_info(project_name, envId)
        infraDeploymentDetails = json.loads(response.content)

        awsKey, awsSecret = None, None
        if aws_assume_role_arn:
            (access_key, secret_key, session_token) = assume_role(aws_assume_role_arn, aws_assume_external_id)
            os.environ["AWS_ACCESS_KEY_ID"] = access_key
            os.environ["AWS_SECRET_ACCESS_KEY"] = secret_key
            os.environ["AWS_SESSION_TOKEN"] = session_token
        else:
            credentials = retreive_aws_creds(project_name, env_name, aws_key=aws_key, aws_secret=aws_secret,
                                             prompt=prompt)
            awsKey = credentials["aws_key"]
            awsSecret = credentials["aws_secret"]
            os.environ["AWS_ACCESS_KEY_ID"] = awsKey
            os.environ["AWS_SECRET_ACCESS_KEY"] = awsSecret

        envVars = {} #get_env_vars(env_name, service_key)

        spinner = Halo(text=f"deploying {service_name}...", spinner="dots")
        spinner.start()
        if service_type == ServiceType.WEBAPP:
            build_directory = settings["services"][service_key]["build_directory"]
            # TODO: find better way to extract bucket name of webapp
            bucket_name = infraDeploymentDetails["terraform_outputs"][f"{service_name}_bucket_main"]["value"]

            subprocess.run(["aws", "s3", "sync", f"{build_directory}",  f"s3://{bucket_name}"], check=True)

            Bcolors.okgreen("Upload succeeded!")
        elif service_type == ServiceType.CONTAINER or (service_type == ServiceType.SERVERLESS and service_runtime == "Docker"):
            docker_registry = infraDeploymentDetails["outputs"]["services"][service_name]["docker_registry"]
            lb_url = infraDeploymentDetails["outputs"]["services"][service_name]["lb_url"]
            region = infraDeploymentDetails["region"]

            response = api.deploy_to_infra({
                "environment_pk": f"{envId}",
                "cluster_name": f"{project_name}-{env_name}",
                "service_name": f"{service_name}",
                "task_name": f"{project_name}-{env_name}-{service_name}",
                "region": region,
                "image_url": f"{docker_registry}:{tag}",
                "tag": tag,
                "aws_key": awsKey,
                "aws_secret": awsSecret,
                "aws_assume_role_arn": aws_assume_role_arn,
                "aws_assume_external_id": aws_assume_external_id,
                "env_vars": envVars
            })

            output = json.loads(response.content)

            print(output["msg"])
            print(f"your deployment URL: http://{lb_url}")
        elif service_type == ServiceType.SERVERLESS and service_runtime != "Docker":
            # perform deployment for lambda functions that are not using docker runtime
            if service_runtime == "Node.js":
                print("Installing packages ...")
                # we pass the `--only-production` flag to avoid installing dev dependencies
                subprocess.run(["npm", "i", "--only=production", "--prefix", service_path])
            elif service_runtime == "Python3.9":
                print("Installing packages ...")
                # needs more work .. we need to include python requirements folder into the zip path
                reqs_path = os.path.join(service_path, "requirements.txt")
                deps_path = service_path
                subprocess.run(["pip", "install", "--target", deps_path, "-r", reqs_path])

            serviceDetails = api.get_service_by_name(project_name, service_name)
            servicePk = serviceDetails["pk"]
            envVars = api.environment_vars_list(project_name, envId)
            envVars = json.loads(envVars.content)["results"]
            envVarsWithOverrides = compute_env_vars_with_overrides(envVars, servicePk)

            lambda_handler = settings["services"][service_key]["lambda_handler"]
            response = deploy_lambda_function_code(
                project_name,
                env_name,
                service_name,
                region,
                service_path,
                lambda_handler,
                awsKey,
                awsSecret,
                aws_assume_role_arn,
                aws_assume_external_id,
                env_vars=envVarsWithOverrides
            )
            print(f"lambda deployed successfully {response}")
        elif service_type == ServiceType.NEXTJS:
            nextjs_deployment_name = infraDeploymentDetails["terraform_outputs"]["nextjs_deployment_name"]["value"]
            nextjs_build_dir = settings["services"][service_key]["build_directory"]

            response = deploy_nextjs_code(
                nextjs_deployment_name,
                nextjs_build_dir,
                region,
                awsKey,
                awsSecret,
            )
            print(f"nextjs app deployed successfully {response}")

        else:
            Bcolors.warn(f"Service type: {service_type} does not support release command, skipping ...")

        spinner.stop()

    action = "deploy"
    settings = get_project_settings()
    report_async({"command": f"dg env {action}"}, settings=settings, status="start")

    if all_services:
        service_keys = list(settings["services"].keys())
    elif service is not None:
        service_keys = [service]
    else:
        defaultProjectName = os.path.basename(os.getcwd())
        questions = [
            {
                'type': 'list',
                'name': 'service_name',
                'message': 'Select Service',
                'choices': settings["services"].keys(),
            },
        ]

        answers = pyprompt(questions)

        service_keys = [answers["service_name"]]

    for service_key in service_keys:
        perform_release(settings, env_name, service_key)

    report_async({"command": f"dg env {action}"}, settings=settings, status="complete")

@env.command(name="service_deploy")
@click.argument("env_name", nargs=1, required=True)
@click.option('--service', default=None)
@click.option('--prompt/--no-prompt', default=False)
def env_service_deploy(env_name, service, prompt=False):
    settings = get_project_settings()
    if service is None:        
        questions = [
            {
                'type': 'list',
                'name': 'service_name',
                'message': 'Select Service',
                'choices': settings["services"].keys(),
            },
        ]

        answers = pyprompt(questions)
        service_key = answers["service_name"]
    else:
        service_key = service

    
    projectName = settings["project"]["name"]
    envDetails = api.get_environment_details(projectName, env_name)
    environmentId = envDetails["pk"]
    serviceDetails = api.get_service_by_name(projectName, service_key)
    serviceId = serviceDetails["pk"]

    with SpinnerSegment(f"Triggering software deploy ..."):
        response = api.perform_service_deploy(projectName, environmentId, serviceId)
        data = json.loads(response.content)
        deploymentId = data["job_id"]

    # streaming logs until deployment is completed
    nextToken = None
    monitoring_max_retries = 60
    monitoring_current_retry_count = 1
    with SpinnerSegment(f"Streaming logs ..."):
        while True:
            details_response = api.get_infra_deployment_info(projectName, deploymentId)
            details_data = json.loads(details_response.content)
            status = details_data["status"]

            logs_response = api.get_deployment_logs(projectName, deploymentId, limit=5000, nextToken=nextToken)
            logs_data = json.loads(logs_response.content)
            for log_record in logs_data["events"]:
                sys.stdout.write(log_record["message"])

            nextToken = logs_data.get("nextToken", None)

            if status in ["LIVE", "COMPLETED", "FAILED"] or monitoring_current_retry_count > monitoring_max_retries:
                break

            monitoring_current_retry_count += 1
            time.sleep(1)

    live_max_retries = 60
    live_current_retry_count = 1
    with SpinnerSegment("waiting for deployment to be live ..."):
        while True:
            Bcolors.warn("... still waiting for deployment to be live ...")
            details_response = api.get_infra_deployment_info(projectName, deploymentId)
            details_data = json.loads(details_response.content)
            status = details_data["status"]


            if status == "LIVE" or live_current_retry_count > live_max_retries:
                break

            live_current_retry_count += 1
            time.sleep(10)
        
    if status == "LIVE":
        Bcolors.okgreen("** SUCCESS! Your service is now live :) **")
    else:
        Bcolors.fail("Deployment status didn't go live in time :( Please check logs in digger dashboard")



@env.command(name="destroy")
@click.argument("env_name", nargs=1, required=True)
@click.option("--project-name", required=False)
@click.option("--aws-key", required=False)
@click.option("--aws-secret", required=False)
@click.option('--prompt/--no-prompt', default=True)
def env_destroy(env_name, project_name=None, aws_key=None, aws_secret=None, prompt=True):

    settings = get_project_settings()
    report_async({"command": f"dg env destroy"}, settings=settings, status="start")
    projectName = settings["project"]["name"]
    envDetails = api.get_environment_details(projectName, env_name)
    envPk = envDetails["pk"]
    response = api.destroy_environment(projectName, envPk, {
        "aws_key": aws_key,
        "aws_secret": aws_secret
    })
    job = json.loads(response.content)


    if prompt:
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
            sys.exit(1)

    # loading until infra status is complete
    spinner = Halo(text="destroying infrastructure ...", spinner="dots")
    spinner.start()
    while True:
        statusResponse = api.get_infra_destroy_job_info(projectName, job['job_id'])
        print(statusResponse.content)
        jobStatus = json.loads(statusResponse.content)
        if jobStatus["status"] == "DESTROYED":
            break
        elif jobStatus["status"] == "FAILED":
            Bcolors.fail("Could not destroy infrastructure")
            print(jobStatus["fail_message"])
            sys.exit(1)
        time.sleep(2)
    spinner.stop()


    print(f"Environment destroyed succesfully")
    report_async({"command": f"dg env destroy"}, settings=settings, status="complete")


@env.command(name="history")
def env_history():
    action = "history"
    print("Not implemented yet")

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

    update_existing_yaml = False
    if os.path.exists("digger.yml"):
        Bcolors.warn("digger.yml found, would you like to initialize new project (Y/N)? ")
        answer = input()
        if answer.lower() == "n":
            Bcolors.fail("aborting ...")
            sys.exit(1)
        else:
            update_existing_yaml = True

    if name is None:
        defaultProjectName = os.path.basename(os.getcwd())
        questions = [
            {
                'type': 'input',
                'name': 'project_name',
                'message': 'Enter project name',
                'default': defaultProjectName,
                'validate': ProjectNameValidator
            },
        ]

        answers = pyprompt(questions)

        project_name = answers["project_name"]
    else:
        project_name = name

    # This will throw error if project name is invalid (e.g. project exists)
    api.create_project(project_name)

    spinner = Halo(text='Initializing project: ' + project_name, spinner='dots')
    spinner.start()
    if update_existing_yaml:
        settings = get_project_settings()
        settings["project"]["name"] = project_name
    else:
        settings = init_project(project_name)
    update_digger_yaml(settings)  
    spinner.stop()


    print("project initiated successfully")
    report_async({"command": f"dg project init"}, settings=settings, status="copmlete")



@project.command(name="generate")
@click.option("--name", nargs=1, required=False, callback=validate_project_name)
def project_generate_yml(name=None):
    action = "init"
    report_async({"command": f"dg project generate"}, status="start")

    update_existing_yaml = False
    if os.path.exists("digger.yml"):
        Bcolors.fail("digger.yml found, please remove before running command")
        sys.exit(1)

    if name is None:
        defaultProjectName = os.path.basename(os.getcwd())
        questions = [
            {
                'type': 'input',
                'name': 'project_name',
                'message': 'Enter project name',
                'default': defaultProjectName,
                'validate': ProjectNameValidator
            },
        ]

        answers = pyprompt(questions)

        project_name = answers["project_name"]
    else:
        project_name = name

    spinner = Halo(text='Generating project: ' + project_name, spinner='dots')
    spinner.start()
    response = api.generate_project(project_name)
    settings = json.loads(response.content)
    f = open(digger_yaml(), "w")
    ydump(settings, f)
    spinner.stop()

    print("project generated successfully")
    report_async({"command": f"dg project generate"}, settings=settings, status="complete")



@cli.group()
@require_auth
def service():
    """
        Configure a new service
    """


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
    service_key = service_name

    service_path = service_name
    serviceNameOk = re.fullmatch(r'', service_name)
    if not serviceNameOk:
        Bcolors.warn("service names should be lowercase letters, hiphens and at most 10 characters")
        service_name = transform_service_name(service_name)
        Bcolors.warn(f"Updating name to: {service_name}")

    settings = get_project_settings()

    try:
        dockerfile_path = find_dockerfile(service_path)
    except CouldNotDetermineDockerLocation as e:
        print("Could not find dockerfile in root")
        dockerfile_path = dockerfile_manual_entry(service_path)


    settings["services"] = settings.get("services", {})
    settings["services"][service_key] = {
        "service_name": service_name,
        "path": service_path,
        "env_files": [],
        "publicly_accessible": True,
        "service_type": "container",
        "container_port": 8080,
        "health_check": "/",
        "dockerfile": dockerfile_path,
        "resources": {},
        "dependencies": {},
    }

    update_digger_yaml(settings)
    spin(1, "Updating DGL config ... ")

    print("Service added succesfully")
    report_async({"command": f"dg service add"}, settings=settings, status="complete")

              
@cli.command(name="sync")
def sync():
    """
    Sync all current services with backend
    """
    settings = get_project_settings()
    projectName = settings["project"]["name"]
    services = settings["services"]
    for key, service in services.items():
        service["name"] = service["service_name"]
    servicesList = json.dumps(list(services.values()))
    api.sync_services(projectName, {"services": servicesList})
    Bcolors.okgreen("digger.yml services synced with backend successfully")


@cli.command()
@click.argument("service_name")
# @click.argument("webapp_name")
def logs(service_name):
    """
       View the logs of a service
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



# exec main function if frozen binary   
if getattr(sys, 'frozen', False):
    try:
        cli(sys.argv[1:])
    except Exception as e:
        raise e
