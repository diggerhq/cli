from setuptools import setup



setup(
    name='Digger CLI',
    package_dir={
        '': 'src'
        '': 'tst',
    },
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
