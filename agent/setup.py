#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name='kraken-agent',
    version='0.0.1',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'kkagent = kraken.agent.agent:main',
        ],
    },
)
