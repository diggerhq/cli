aws_key = "{{aws_key}}"
aws_secret = "{{aws_secret}}"


app = "{{app_name}}"
environment = "{{environment}}"
# aws_profile = "default"
container_port = "{{container_port}}"
# replicas = "1"
health_check = "/health"
tags = {
  application   = "{{app_name}}"
  environment   = "{{environment}}"
  team          = "{{app_name}}-team"
  customer      = "{{app_name}}-customer"
  contact-email = "me@domain.com"
}

internal = false

launch_type = "{{launch_type}}"