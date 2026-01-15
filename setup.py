#!/usr/bin/env python3
"""
Setup script for PRISM (Psychological Research Information Standard for Metadata)
"""

from setuptools import setup
import os


# Read the README file
def read_file(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), encoding="utf-8") as f:
        return f.read()


# Read requirements
def read_requirements(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


setup(
    name="prism",
    version="1.8.3",
    description="PRISM - BIDS-inspired validation and tools for psychological research datasets",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    author="MRI-Lab-Graz",
    author_email="contact@mri-lab-graz.at",
    url="https://github.com/MRI-Lab-Graz/prism-studio",
    packages=["src"],
    package_dir={"src": "src"},
    package_data={
        "": ["schemas/*.json", "schemas/mri/*.json"],
    },
    include_package_data=True,
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        "dev": ["pytest", "pytest-cov", "black", "flake8"],
        "full": ["bidsschematools", "nibabel"],
        "demo": ["Pillow", "numpy", "matplotlib"],
    },
    scripts=[
        "prism.py",
        "prism-studio.py",
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
