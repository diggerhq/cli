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
    aws_secret
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

    functionName=f"{project_name}-{env_name}-{service_name}"
    client = boto3.client("lambda", aws_access_key_id=aws_key, aws_secret_access_key=aws_secret, region_name=region)

    client.update_function_configuration(
        FunctionName=functionName,
        Handler=handler
    )

    # ensure the lambda status is "Successful" before proceeding
    cnt = 1
    while True:
        func_details = client.get_function(
            FunctionName=functionName
        )
        state = func_details["Configuration"]["LastUpdateStatus"]
        if state != "InProgress" or cnt > 20:
            break
        cnt += 1
        time.sleep(5)

    response = client.update_function_code(
        FunctionName=functionName,
        ZipFile=buf.getvalue(),
        Publish=True,
        DryRun=False,
    )

    return response