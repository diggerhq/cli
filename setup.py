from setuptools import setup



setup(
    name='Digger CLI',
    # package_dir={
    #     'diggercli': ''
    # },
    version="1.0",
    py_modules=["diggercli",],
    install_requires=[
        "click",
    ],
    packages=['diggercli', 'diggercli.utils'],
    entry_points='''
        [console_scripts]
        dg=diggercli.dg:cli
    '''
)
