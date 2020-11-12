from setuptools import setup



setup(
    name='Digger CLI',
    package_dir={'': 'src'},
    version="1.0",
    py_modules=["dg",],
    install_requires=[
        "click",
    ],
    entry_points='''
        [console_scripts]
        dg=dg:cli
    '''
)
