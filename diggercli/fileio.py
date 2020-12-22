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

def download_terraform_files(projectName, environment, destinationDir):
    response = api.download_terraform_async(projectName, environment)
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

