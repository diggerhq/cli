import os
import zipfile
import boto3
from diggercli.fileio import zipdir


def make_zip_file_bytes(path):
    buf = os.io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for full_path, archive_name in files_to_zip(path=path):
            z.write(full_path, archive_name)
    return buf.getvalue()

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
    buf = os.io.BytesIO()
    ziph = zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED)

    cwd = os.getcwd()
    os.chdir(path)
    try:
        zipdir(ziph)
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

    response = client.update_function_code(
        FunctionName=functionName,
        ZipFile=buf.getvalue(),
        Publish=True,
        DryRun=False,
    )

    return response