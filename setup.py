#!/usr/bin/env python3
from os import system, uname, geteuid
from os.path import exists
import logging
from subprocess import run
from setuptools import setup, find_packages
from setuptools.command.install import install
import subprocess
import re
import sys

logging.basicConfig(level=logging.INFO)
NAME = 'pymeterreader'
SERVICE_TEMPLATE = '[Unit]\n' \
                   'Description=pymeterreader\n' \
                   'After=network.target\n' \
                   'StartLimitIntervalSec=0\n' \
                   '\n' \
                   '[Service]\n' \
                   'Type=simple\n' \
                   'Restart=always\n' \
                   'RestartSec=5\n' \
                   'User=root\n' \
                   'ExecStart={}\n' \
                   '\n' \
                   '[Install]\n' \
                   'WantedBy=multi-user.target\n'

LOG = []


def info(msg):
    LOG.append((lambda msg: system(f'echo "INFO {msg}"'), msg))


def error(msg):
    LOG.append((lambda msg: system(f'echo "ERROR {msg}"'), msg))


class PostInstallCommand(install):
    """
    Post-installation for installation mode.
    Prints output from this script, but only in verbose mode
    """
    def run(self):
        install.run(self)
        for log_fn, msg in LOG:
            log_fn(msg)


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
                    info(f"Read version {new_version} from PKG-INFO")
                    break
            if match is None:
                error("Cannot find version in PKG-INFO!")
    else:
        error("Neither GIT nor VERSION file available!")
    return new_version


def register_systemd_service():
    info("Installing service")
    run('sudo systemctl stop pymeterreader',  # pylint: disable=subprocess-run-check
        universal_newlines=True,
        shell=True)

    target_service_file = "/etc/systemd/system/pymeterreader.service"

    service_str = SERVICE_TEMPLATE.format('pymeterreader -c /etc/pymeterreader.yaml')
    try:
        with open(target_service_file, 'w') as target_file:
            target_file.write(service_str)
        run('systemctl daemon-reload',  # pylint: disable=subprocess-run-check
            universal_newlines=True,
            shell=True)
        if not exists('/etc/pymeterreader.yaml'):
            info("Copy example configuration file to '/etc/pymeterreader.yaml'")
            with open('example_configuration.yaml', 'r') as file:
                example_config = file.read()
            with open('/etc/pymeterreader.yaml', 'w') as file:
                file.write(example_config)
        info("Registered pymeterreader as servicee.\n"
             "Enable with 'sudo systemctl enable pymeterreader'\n."
             "IMPORTANT: Create configuration file '/etc/pymeterreader.yaml'")
    except OSError as err:
        if isinstance(err, PermissionError):
            error("Cannot write service file to /etc/systemd/system. Run as root (sudo) to solve this.")


def get_requirements():
    if exists('requirements.txt'):
        file_name = 'requirements.txt'
    elif exists('PyMeterReader.egg-info/requires.txt'):
        file_name = 'PyMeterReader.egg-info/requires.txt'
    else:
        error("Cannot find requirements.txt")
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
        'console_scripts': ['pymeterreader=pymeterreader:main']},
      include_package_data=True,
      packages=find_packages('.'),
      data_files=[('.', ['example_configuration.yaml',
                         'requirements.txt'])],
      install_requires=get_requirements(),
      test_suite='nose.collector',
      cmdclass={
        'install': PostInstallCommand,
      },
      extras_require=
      {
          'test': [
              'nose',
              'prospector'
          ]
      })

if uname().sysname == 'Linux' and geteuid() == 0:
    register_systemd_service()
else:
    info("Skipping service registration.")
