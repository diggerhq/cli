from __future__ import print_function, unicode_literals
import webbrowser
import time
import json
import click
from halo import Halo
from PyInquirer import prompt, Separator


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

def services(type=None):
    return [
        {
            "service_name": 'todo-backend',
            "service_type": "container"
        },
        {
            "service_name": 'todo-frontend',
            "service_type": "serverless"
        },
        {
            "service_name": 'todo-reminder',
            "service_type": "serverless"
        }
    ]

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

        spin(1, "Loading environment list ...")

        print(">> local-docker")

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

        print("Deplyment successful!")
        print(f"your deployment URL: http://digger-mvp.s3-website-{env_name}.us-east-2.amazonaws.com")

    elif action[0] == "apply":
        env_name = action[1]
        spin(2, 'Applying infrastructure ...')
        print("Infrastructure apply completed!")
        print(f"your deployment URL: http://digger-mvp.s3-website-{env_name}.us-east-2.amazonaws.com")


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

        # print(project_name) 
        # print(answers)

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

        questions = [
            {
                'type': 'input',
                'name': 'service_name',
                'message': 'What is the service name?',
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
            {
                'type': 'list',
                'name': 'repo',
                'message': 'select repository',
                'choices': repos()
            },

        ]

        answers = prompt(questions)
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
                'choices': repos()
            },

        ]

        answers = prompt(questions)
        spin(1, "Updating DGL config ... ")
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
        'choices': list(map(lambda x: x["service_name"], services()))
        })

        answers = prompt(questions)

        spin(2, "updating configuration ...")

        print("Config updated")


