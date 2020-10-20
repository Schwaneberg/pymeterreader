#!/usr/bin/env python3
from os.path import exists
from logging import info, error
from subprocess import run
from setuptools import setup, find_packages
import subprocess
import re
import os
import sys

NAME = 'PyMeterReader'
VERSION_FILE = 'VERSION'
DATA_PATH = "misc"
SERVICE_TEMPLATE_FILE = "pymeterreader.service.template"

def update_version():
    out = subprocess.Popen(['git', 'describe', '--tags'], stdout=subprocess.PIPE)
    stdout = out.communicate()
    full_version = str(stdout[0].strip())
    matches = re.search(r'(\d+.\d+.\d+)', full_version)
    new_version = "0.0.0"
    version_file_path = os.sep.join([DATA_PATH, VERSION_FILE])
    if matches:
        new_version = matches.group(0).replace("-", ".")
        with open(version_file_path, 'w') as version_file:
            version_file.write(new_version)
    elif exists(version_file_path):
        with open(version_file_path, 'r') as version_file:
            new_version = version_file.readline().strip()
    else:
        error("Neither GIT nor VERSION file available!")
    return new_version


def register_systemd_service():
    info("Installing service")
    run('sudo systemctl stop pymeterreader',  # pylint: disable=subprocess-run-check
        universal_newlines=True,
        shell=True)

    template_path = os.sep.join([DATA_PATH, SERVICE_TEMPLATE_FILE])
    target_service_file = "/etc/systemd/system/pymeterreader.service"

    with open(template_path, "r") as templateService:
        service_template_str = templateService.read()

    output = o = run('which python3',
                     universal_newlines=True,
                     shell=True, capture_output=True)
    python3_path = output.stdout.strip()
    service_str = service_template_str.format(f'{python3_path} /usr/local/bin/pymeterreader -c /etc/pymeterreader.yaml')
    try:
        with open(target_service_file, 'w') as target_file:
            target_file.write(service_str)
        run('systemctl daemon-reload',  # pylint: disable=subprocess-run-check
            universal_newlines=True,
            shell=True)
    except OSError as err:
        if isinstance(err, PermissionError):
            error("Cannot write service file to /etc/systemd/system. Run as root (sudo) to solve this.")


def get_requirements():
    with open('requirements.txt', 'r') as req_file:
        requirements = [req.strip() for req in req_file.readlines() if req]
    return requirements


setup(name=NAME,
      version=update_version(),
      description='PyMeterReader is a service to poll smart meters and sensors.'
                  'It supports uploading to volkszaehler middleware via its REST API.',
      classifiers=[
          'License :: BSD-2-Clause',
          'Programming Language :: Python :: 3.7',
          'Topic :: Volkszaehler.org :: Smart Meters'
      ],
      url='https://github.com/Schwaneberg/pymeterreader',
      author='Oliver Schwaneberg',
      author_email='Oliver.Schwaneberg@gmail.com',
      license='BSD-2-Clause',
      include_package_data=True,
      packages=find_packages(),
      data_files=[(DATA_PATH, [SERVICE_TEMPLATE_FILE,
                               VERSION_FILE]),
                  ('.', 'requirements.txt')],
      install_requires=get_requirements(),
      zip_safe=False,
      test_suite='nose.collector',
      extras_require=
      {
          'test': [
              'nose',
              'prospector'
          ]
      })

if sys.argv[1] == 'install':
    register_systemd_service()
