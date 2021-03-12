from setuptools import setup



setup(
    name='Digger CLI',
    # package_dir={
    #     'diggercli': ''
    # },
    install_requires=[
        "certifi==2020.6.20",
        "chardet==3.0.4",
        "click==7.1.2",
        "colorama==0.4.3",
        "docutils==0.15.2",
        "environs==9.0.0",
        "halo==0.0.30",
        "idna==2.10",
        "Jinja2==2.11.2",
        "jmespath==0.10.0",
        "log-symbols==0.0.14",
        "MarkupSafe==1.1.1",
        "marshmallow==3.9.0",
        "oyaml==1.0",
        "prompt_toolkit==1.0.14",
        "pyasn1==0.4.8",
        "Pygments==2.7.1",
        "PyInquirer==1.0.3",
        "python-dateutil==2.8.1",
        "python-dotenv==0.15.0",
        "PyYAML==5.3.1",
        "regex==2020.10.15",
        "requests==2.24.0",
        "rsa==4.5",
        "six==1.15.0",
        "spinners==0.0.24",
        "termcolor==1.1.0",
        "urllib3==1.25.11",
        "wcwidth==0.2.5",
        "boto3==1.17.11",
    ],
    version="1.0",
    py_modules=["diggercli",],
    packages=['diggercli', 'diggercli.utils'],
    entry_points='''
        [console_scripts]
        dg=diggercli.dg:cli
    '''
)
