#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name='kraken-agent',
    version='0.0.1',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'kkagent = kraken.agent.agent:main',
            'kktool = kraken.agent.tool:main',
        ],
        'kraken.tools': [
            'git = kraken.agent.kraken_git',
            'pytest = kraken.agent.kraken_pytest',
            'rndtest = kraken.agent.kraken_rndtest',
            'shell = kraken.agent.kraken_shell',
            'pylint = kraken.agent.kraken_pylint',
            'cloc = kraken.agent.kraken_cloc',
            'nglint = kraken.agent.kraken_nglint',
        ]
    },
)
