#!/usr/bin/env python

from setuptools import setup, find_packages

def read_long_description(file_path):
    with open(file_path, "r") as file:
        return file.read()

setup(
    name="scrapy-puppeteer-client",
    version="0.3.1",
    description="A library to use Puppeteer-managed browser in Scrapy spiders",
    long_description=read_long_description("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/ispras/scrapy-puppeteer",
    author="MODIS @ ISP RAS",
    maintainer="Maksim Varlamov",
    maintainer_email="varlamov@ispras.ru",
    packages=find_packages(), 
    install_requires=[
        "scrapy>=2.6",
        "pyppeteer",
        "syncer",
        "bs4"
    ],
    python_requires=">=3.6",
    license="BSD",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Scrapy",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: BSD License",
    ],
)
