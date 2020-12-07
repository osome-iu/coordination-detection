from distutils.core import setup



setup(
    name='tcd',
    version='0.1.0',
    author='Pik-Mai Hui',
    packages=['tcd'],
    #license='LICENSE.txt',
    description='package for the twitter coordination detection',
    #long_description=open('README.txt').read(),
    install_requires=[
        "pandas >= 0.1",
        "numpy >= 0.1"
    ],
)
