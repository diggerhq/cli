import os
import subprocess
import json
import zipfile
import time
from pathlib import Path

import requests
import tempfile
from diggercli import api
from diggercli.exceptions import FileTooLargeError


def download_file(url, path):
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                #if chunk:
                f.write(chunk)

def download_terraform_files(projectName, environment, region, target, services, destinationDir):
    response = api.download_terraform_async(projectName, environment, region, target, services)
    job = json.loads(response.content)

    while True:
        jobResponse = api.terraform_generate_status(job["terraform_job_id"])
        jobStatus = json.loads(jobResponse.content)

        status = jobStatus["status"]

        if status == "COMPLETED":
            break

        time.sleep(2)

    fileUrl = jobStatus["file_url"]

    tmpZipPath = os.path.join(tempfile.mkdtemp(), next(tempfile._get_candidate_names()))
    download_file(fileUrl, tmpZipPath)
    with zipfile.ZipFile(tmpZipPath, 'r') as zip_ref:
        zip_ref.extractall(destinationDir)


def zipdir(ziph):
    # ziph is zipfile handle
    path = os.getcwd()
    lenDirPath = len(path)
    for root, dirs, files in os.walk(path):
        for file in files:
            if root.endswith("node_modules"): continue
            filePath = os.path.join(root, file)
            # the second argument ensures accurate tree structure in the zip file
            ziph.write(filePath, filePath[lenDirPath:])

def git_zip(zippath):
    subprocess.run([
        "git", 
        "archive", 
        "--format", "zip",  
        "--output", zippath, 
        "master",
    ], check=True)

def git_exists():
    devnull = open(os.devnull, 'w')
    try:
        subprocess.run(["git", "status"], stdout=devnull, stderr=devnull, check=True)
        return True
    except subprocess.CalledProcessError as grepexc:                                                                                                   
        return False

def git_zip_or_zipdir(zippath):

    if ".git" in os.listdir() and git_exists():
        git_zip(zippath)
        return

    # create the zip path
    ziph = zipfile.ZipFile(zippath, "w", compression=zipfile.ZIP_DEFLATED)
    zipdir(ziph)
    ziph.close()

def upload_code(tmp_project_uuid, service_name):

    response = api.get_signed_url_for_code_upload(tmp_project_uuid, {
        "service_name": service_name
    })
    content = json.loads(response.content)

    zippath = tempfile.mkdtemp()
    zippath = os.path.join(zippath, "code.zip")
    # create the zip path
    ziph = zipfile.ZipFile(zippath, "w", compression=zipfile.ZIP_DEFLATED)
    zipdir(ziph)
    ziph.close()

    file_size  = Path(zippath).stat().st_size
    if file_size > 100 * 1024  *  1024:
        raise FileTooLargeError("Code size exceeds 100MB")

    with open(zippath, 'rb') as zipf:
        # uploading the object
        object_name = content["fields"]["key"]
        files = {'file': (object_name, zipf)}
        upload_response = requests.post(content['url'], data=content['fields'], files=files)
        print(upload_response.status_code)
        assert upload_response.status_code//100 == 2

