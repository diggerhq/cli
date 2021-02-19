import os
import json
from pathlib import Path
from diggercli import api, diggerconfig


def create_temporary_project():
    settings = diggerconfig.Generator.load_yaml()
    services = json.dumps(settings["services"])
    response = api.generate_tmp_project({
        "services": services
    })
    Path(".digger").mkdir(parents=True, exist_ok=True)
    response = json.loads(response.content)
    tmpId = response["id"]
    f = open(".digger/temp.json", "w")
    json.dump({"temp_project_id": tmpId}, f)
    return tmpId

def get_temporary_project_id():
    f = open(".digger/temp.json")
    content = json.load(f)
    return content["temp_project_id"]