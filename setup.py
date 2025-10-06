#!/usr/bin/env python3
"""
Setup script for psycho-validator
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_file(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), encoding='utf-8') as f:
        return f.read()

# Read requirements
def read_requirements(filename):
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="psycho-validator",
    version="1.3.0",
    description="BIDS-inspired validation tool for psychological research datasets",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    author="MRI-Lab-Graz",
    author_email="contact@mri-lab-graz.at",
    url="https://github.com/MRI-Lab-Graz/psycho-validator",
    packages=['src'],
    package_dir={'src': 'src'},
    package_data={
        '': ['schemas/*.json', 'schemas/mri/*.json'],
    },
    include_package_data=True,
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        'dev': ['pytest', 'pytest-cov', 'black', 'flake8'],
        'full': ['bidsschematools', 'nibabel'],
        'demo': ['Pillow', 'numpy', 'matplotlib'],
    },
    scripts=[
        'psycho-validator.py',
        'psycho-validator-streamlined.py',
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    keywords="bids validation psychology neuroscience research data",
)