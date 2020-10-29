from __future__ import print_function, unicode_literals
import os
from pathlib import Path
from collections import OrderedDict
import subprocess
import webbrowser
import time
import json
from oyaml import load as yload, dump as ydump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
import click
from halo import Halo
from PyInquirer import prompt, Separator


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
        for env in settings["environments"]:
            print(f">> {env}")

    elif action[0] == "create":
        env_name = action[1]
        questions = [
            {
                'type': 'list',
                'name': 'target',
                'message': 'Select target',
                'choices': [
                    "AWS ECS Fargagte",
                    "AWS EKS",
                    "AWS EC2 docker-compose",
                    "Google Cloud Run",
                    "Google GKE",
                ]
            },
        ]

        answers = prompt(questions)

        target = answers["target"]

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


        spin(2, 'Loading creds from ~/.aws/creds')
        spin(2, 'Generating terraform packages ...')
        spin(2, 'Applying infrastructure ...')
        spin(2, 'deploying packages ...')

        settings = get_project_settings()
        environments = settings["environments"]
        if env_name not in environments:
            environments.append(env_name)
        update_digger_yaml(settings)


        print("Deplyment successful!")
        print(f"your deployment URL: http://digger-mvp.s3-website-{env_name}.us-east-2.amazonaws.com")

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


        # f"""
        # {bcolors.OKCYAN}commit b5b15d4dcd4e989a98d411627fa99441a68eeb15{bcolors.ENDC}
        # Author: motatoes <moe.habib9@gmail.com>
        # Date:   Thu Oct 29 09:58:23 2020 +0000

        #     fix monolith

        # {bcolors.OKCYAN}commit 9b402a4c3802cca46a4764815a2650111c780967{bcolors.ENDC}
        # Author: motatoes <moe.habib9@gmail.com>
        # Date:   Tue Oct 6 11:56:49 2020 +0100

        #     fix downstream calls

        # {bcolors.OKBLUE}infra e3f9ab4c852aecfa86c540cd3787f16a8c8882ff{bcolors.ENDC}
        # Author: motatoes <moe.habib9@gmail.com>
        # Date:   Tue Oct 6 09:00:25 2020 +0100

        #     initial infrastructure

        # {bcolors.OKCYAN}commit 8be5fe360cbd4d7949d157b90776fa7c76fd8601{bcolors.ENDC}
        # Author: motatoes <moe.habib9@gmail.com>
        # Date:   Thu Oct 1 10:47:54 2020 +0100

        #     fix flask

        # {bcolors.OKPINK}config 2cc5a97928643c04fe95e1d076d463986d964394{bcolors.ENDC}
        # Merge: a0d1514 976f059
        # Author: motatoes <moe.habib9@gmail.com>
        # Date:   Mon Nov 4 17:08:19 2019 +0000

        #     update config for postgres_user, postgres_host

        # {bcolors.OKCYAN}commit 976f0591213334f78cbaa156222aa443bd4a8ef5{bcolors.ENDC}
        # Author: motatoes <moe.habib9@gmail.com>
        # Date:   Sat Nov 2 20:55:04 2019 +0000    
        # """


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
        settings["environments"] = [
            "local-docker"
        ]

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
        
        service_names = get_service_names()
        questions = [
            {
                'type': 'input',
                'name': 'service_name',
                'message': 'What is the service name?',
            },
            # {
            #     'type': 'list',
            #     'name': 'server_type',
            #     'message': 'Mode?',
            #     'choices': [
            #         'Serverless',
            #         'Containers',
            #     ]
            # },
            {
                'type': 'list',
                'name': 'repo',
                'message': 'select repository',
                'choices': service_names
            },
        ]

        answers = prompt(questions)

        repo = answers["repo"]
        service = services()[service_names.index(repo)]
        service_url = service["service_url"]
        service_name = service["service_name"]
        clone_repo(service_url)

        spin(1, "determining service type ...")
        bcolors.warn("Could not determine if Container or Serverless .. Assuming Monorepo")
        bcolors.bold("Identified the following folder structure")
        bcolors.okblue(f"{bcolors.BOLD}/monlith{bcolors.ENDC} [Container:/monlith/Dockerfile]")
        bcolors.okblue(f"{bcolors.BOLD}/functions{bcolors.ENDC} [Serverless:/functions/serverless.yml]")
        bcolors.warn(f"Is this correct? {bcolors.BOLD}[Y/N]{bcolors.ENDC}")
        input()


        settings = get_project_settings()

        # services:
        #    - backend:
        #       repo: my-backend
        #       locator: /backend
        #    - functions:
        #       repo: my-backend
        #       locator: /functions

        settings["services"] = settings.get("services", {})
        settings["services"][service_name + ".monolith"] = {
            "publicly_accissible": True,
            "type": "container",
            "path": "/monolith",
            "resources": {},
            "dependencies": {},
        }
        settings["services"][service_name + ".functions"] = {
            "publicly_accissible": True,
            "type": "serverless",
            "path": "/functions",
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
                    'Postgres',
                    'MySql',
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
            "type": "database",
            "engine": engine,
        }
        update_digger_yaml(settings)
        spin(2, "updating configuration ...")

        print("DGL Config updated")


