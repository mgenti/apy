from distutils.core import setup
import apy


setup(name='apy',
      author='David Ewing, Mark Guagenti', 
      url='http://sourceforge.net/projects/apy', 
      maintainer='Mark Guagenti', 
      version=str(apy.__version__), 
      package_dir={'apy': ''}, 
      packages=['apy'], 
      )
