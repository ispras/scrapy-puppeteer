#!/usr/bin/env python

from setuptools import setup

with open("README.md", "r") as readme:
    long_description = readme.read()

setup(
    name='scrapy-puppeteer-client',
    version='0.0.3',
    description='A library to use Puppeteer-managed browser in Scrapy spiders',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/ispras/scrapy-puppeteer',
    author='MODIS @ ISP RAS',
    maintainer='Maksim Varlamov',
    maintainer_email='varlamov@ispras.ru',
    packages=['scrapypuppeteer'],
    requires=['scrapy'],
    python_requires='>=3.5',
    license='BSD',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Framework :: Scrapy',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: BSD License'
    ]
)
