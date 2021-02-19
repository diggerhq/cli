import os
import json
import zipfile
import time
import requests
import tempfile
from diggercli import api


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


def zipdir(path, ziph):
    # ziph is zipfile handle
    lenDirPath = len(path)
    for root, dirs, files in os.walk(path):
        for file in files:
            filePath = os.path.join(root, file)
            # the second argument ensures accurate tree structure in the zip file
            ziph.write(filePath, filePath[lenDirPath:])

def upload_code(tmp_project_uuid, service_name, path):

    response = api.get_signed_url_for_code_upload(tmp_project_uuid, {
        "service_name": service_name
    })
    content = json.loads(response.content)

    # create the zip path
    zip_path = tempfile.mkdtemp()
    zip_path = os.path.join(zip_path, "code.zip")
    ziph = zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED)
    zipdir(path, ziph)
    ziph.close()

    with open(zip_path, 'rb') as zipf:
        # uploading the object
        object_name = content["fields"]["key"]
        files = {'file': (object_name, zipf)}
        upload_response = requests.post(content['url'], data=content['fields'], files=files)
        print(upload_response.status_code)
        assert upload_response.status_code//100 == 2

