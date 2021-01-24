import re

def transform_service_name(serviceName):
    """
        transforms an invalid service name into a valid one by capping length
        and replacing all invalid characters
    """
    serviceName = re.sub(r"[\ \_]", "-", serviceName)
    serviceName = serviceName.lower()
    serviceName = serviceName[:10]
    return serviceName
