#!/usr/bin/env python

from setuptools import setup

with open("README.md", "r") as readme:
    long_description = readme.read()

setup(
    name='scrapy-puppeteer-client',
    version='0.1.4',
    description='A library to use Puppeteer-managed browser in Scrapy spiders',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/ispras/scrapy-puppeteer',
    author='MODIS @ ISP RAS',
    maintainer='Maksim Varlamov',
    maintainer_email='varlamov@ispras.ru',
    packages=['scrapypuppeteer'],
    install_requires=['scrapy>=2.6'],
    python_requires='>=3.6',
    license='BSD',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Framework :: Scrapy',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: BSD License'
    ]
)
