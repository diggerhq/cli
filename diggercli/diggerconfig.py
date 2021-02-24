import os
from oyaml import load as yload, dump as ydump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from diggercli.utils.pprint import Bcolors

class Service:
    def __init__(self, serviceType, configpath):
        self.type = serviceType
        self.configpath = configpath

class ProjectDetector:
    DIGGER = "digger"
    DOCKER = "docker"
    FRONTEND = "frontend"
    UNKNOWN = "unknown"

    def digger_test(self, path):
        files = os.listdir(path)
        
        if "digger.yml" in files:
            return Service(self.DIGGER, "digger.yml")
        return False

    def docker_test(self, path):
        files = os.listdir(path)
        if "dockerfile" in list(map(lambda x: x.lower(), files)):
            return Service(self.DOCKER,  "Dockerfile")
        return False

    def javascript_test(self, path):
        files = os.listdir(path)
        if "package.json" in files:
            return Service(self.FRONTEND, "package.json")
        return False

    def detect_service(self, path):

        Bcolors.warn("... Searching for digger.yml")
        dgtest = self.digger_test(path)
        if dgtest != False:
            Bcolors.okgreen("digger.yml file found .. loading settings")
            return dgtest
        Bcolors.warn("[x] digger.yml not found")

        Bcolors.warn("... Searching for dockerfile")
        dockertest = self.docker_test(path)
        if dockertest != False:
            return dockertest
        Bcolors.warn("[x] dockerfile not found")

        Bcolors.warn("... Searching for package.json")
        jstest = self.javascript_test(path)
        if jstest != False:
            return jstest
        Bcolors.warn("[x] package.json not found")


        return Service(self.UNKNOWN, None)


class Generator():

    def __init__(self, services):
        self.state = {
            "version": "1.0.0",
            "services": {}
        }
        self.services = services
        self.update_state()

    def dump_yaml(self):
        f = open("digger.yml", "w")
        ydump(self.state, f)

    @classmethod
    def load_yaml(cls):
        return yload(open("digger.yml"), Loader=Loader)


    def update_state(self):
        for service in self.services:
            if service.type == ProjectDetector.DOCKER:
                self.generate_docker(service)
            elif service.type == ProjectDetector.FRONTEND:
                self.generate_frontend(service)
            else:
                Bcolors.warn(f"Unknown type {service.type}")


    def generate_frontend(self, service):
        self.state["services"]["frontend"] = {
            "service_name": "frontend",
            "root": ".",
            "build_cmd": "npm run build",
            "dist_path": "dist",
            "publicly_accissible": True,
            "packagejson": service.configpath,
        }

    def generate_docker(self, service):
        self.state["services"]["backend"] = {
            "service_name": "backend",
            "root": ".",
            # "env_files": [],
            "publicly_accissible": True,
            "type": "container",
            "container_port": 3000,
            "health_check": "/",
            "dockerfile": service.configpath,
            "resources": {},
            "dependencies": {},
        }

