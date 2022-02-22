import json
import os
import io
import time
import zipfile
import boto3
from diggercli.fileio import zipdir


def deploy_lambda_function_code(
    project_name,
    env_name,
    service_name,
    region,
    path,
    handler,
    aws_key,
    aws_secret,
    env_vars={}
):
    buf = io.BytesIO()
    ziph = zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED)

    cwd = os.getcwd()
    os.chdir(path)
    try:
        zipdir(ziph)
        ziph.close()
    except Exception as e:
        raise e
    finally:
        os.chdir(cwd)

    function_name=f"{project_name}-{env_name}-{service_name}"
    response = update_handler_and_deploy_lambda(buf.getvalue(), function_name, handler, aws_key, aws_secret, region, env_vars=env_vars)
    return response


def update_handler_and_deploy_lambda(zip_contents, function_name, handler, aws_key, aws_secret, region, env_vars):
    client = boto3.client("lambda", aws_access_key_id=aws_key, aws_secret_access_key=aws_secret, region_name=region)

    client.update_function_configuration(
        FunctionName=function_name,
        Environment={
            "Variables": env_vars
        },
        Handler=handler
    )

    # ensure the lambda status is "Successful" before proceeding
    cnt = 1
    while True:
        func_details = client.get_function(
            FunctionName=function_name
        )
        state = func_details["Configuration"]["LastUpdateStatus"]
        if state != "InProgress" or cnt > 20:
            break
        cnt += 1
        time.sleep(5)

    response = client.update_function_code(
        FunctionName=function_name,
        ZipFile=zip_contents,
        Publish=True,
        DryRun=False,
    )
    return response


def deploy_nextjs_code(
    nextjs_deployment_name,
    nextjs_build_dir,
    region,
    aws_key,
    aws_secret,
    env_vars={}
):
    config_file = os.path.join(nextjs_build_dir, "config.json")
    f = open(config_file, "r")
    config = json.loads(f.read())

    first_key = next(iter(config["lambdas"].keys()))
    first_value = next(iter(config["lambdas"].values()))
    lambda_key = first_key
    lambda_handler = first_value["handler"]
    lambda_zip_path = os.path.join(nextjs_build_dir, first_value["filename"])
    lambda_function_name = f"{nextjs_deployment_name}_{lambda_key}"
    zip_contents = open(lambda_zip_path, "rb").read()
    response = update_handler_and_deploy_lambda(zip_contents, lambda_function_name, lambda_handler, aws_key, aws_secret, region, env_vars=env_vars)
    return response
