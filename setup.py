#!/usr/bin/env python3
import logging
import re
import subprocess
import sys
from os.path import exists

from setuptools import setup, find_packages

logging.basicConfig(level=logging.INFO)
NAME = 'pymeterreader'


def update_version():
    out = subprocess.Popen(['git', 'describe', '--tags'], stdout=subprocess.PIPE)
    stdout = out.communicate()
    full_version = str(stdout[0].strip())
    match = re.search(r'(\d+.\d+.\d+)', full_version)
    new_version = "0.0.0"
    if match:
        new_version = match.group(0).replace("-", ".")
    elif exists('PKG-INFO'):
        with open('PKG-INFO', 'r') as pkg_file:
            match = None
            for line in pkg_file.readlines():
                match = re.match(r'Version: (\d+.\d+.\d+)', line)
                if match:
                    new_version = match[1]
                    print(f"Read version {new_version} from PKG-INFO")
                    break
            if match is None:
                print("Cannot find version in PKG-INFO!", file=sys.stderr)
    else:
        print("Neither GIT nor VERSION file available!", file=sys.stderr)
    return new_version


def get_requirements():
    if exists('requirements.txt'):
        file_name = 'requirements.txt'
    elif exists('PyMeterReader.egg-info/requires.txt'):
        file_name = 'PyMeterReader.egg-info/requires.txt'
    else:
        print("Cannot find requirements.txt", file=sys.stderr)
        sys.exit(2)
    requirements = []
    with open(file_name, 'r') as req_file:
        for req in req_file.readlines():
            req = req.strip()
            if req:
                requirements.append(req)
            elif "[test]" in req:
                break
    return requirements


setup(name=NAME,
      version=update_version(),
      description='pymeterreader is a service to poll smart meters and sensors.'
                  'It supports uploading to volkszaehler middleware via its REST API.',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'License :: OSI Approved :: BSD License',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 3.7'
      ],
      url='https://github.com/Schwaneberg/pymeterreader',
      author='Oliver Schwaneberg',
      author_email='Oliver.Schwaneberg@gmail.com',
      license='BSD-2-Clause',
      entry_points={
          'console_scripts': ['pymeterreader=pymeterreader:main',
                              'pymeterreader-wizard=pymeterreader.wizard.ncui:Wizard']},
      include_package_data=True,
      packages=find_packages('.'),
      data_files=[('.', ['example_configuration.yaml',
                         'requirements.txt'])],
      install_requires=get_requirements(),
      test_suite='nose.collector',
      extras_require=
      {
          'test': [
              'nose',
              'prospector'
          ]
      })
