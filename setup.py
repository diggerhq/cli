from setuptools import setup



setup(
    name='Digger CLI',
    package_dir={
        'dg': 'dg'
    },
    version="1.0",
    py_modules=["dg",],
    install_requires=[
        "click",
    ],
    packages=['diggercli', 'diggercli.utils'],
    entry_points='''
        [console_scripts]
        dg=dg.dg:cli
    '''
)
