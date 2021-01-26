import re
from PyInquirer import prompt, Validator, ValidationError
from prompt_toolkit import document

def project_name_validate(projectName):
    if len(projectName) > 10:
        raise ValueError('Project name should at most 10 characters')
    ok=re.fullmatch(r'^[a-z0-9\-]+$', projectName)
    if not ok:
        raise ValueError('Project name should only contain lowercase letters, numbers and hiphen (-)')

class ProjectNameValidator(Validator):
    def validate(self, document: document.Document) -> None:
        try:
            project_name_validate(document.text)
        except ValueError as e:
            raise ValidationError(message=str(e), cursor_position=len(document.text))

def env_name_validate(envName):
    if len(envName) > 10:
        raise ValueError('Environment name should at most 10 characters')
    ok=re.fullmatch(r'^[a-z0-9\-]+$', envName)
    if not ok:
        raise ValueError('Environment name should only contain lowercase letters, numbers and hiphen (-)')
