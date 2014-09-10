from setuptools import setup


import __init__


setup(name='apy',
      author='David Ewing, Mark Guagenti', 
      url='http://sourceforge.net/projects/apy', 
      maintainer='Mark Guagenti', 
      version=str(__init__.__version__), 
      package_dir={'apy': ''}, 
      packages=['apy'], 
      )
