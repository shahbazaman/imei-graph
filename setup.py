from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as readme:
    long_description = readme.read()

setup(
    name="imei_graph",
    version="0.0.1",
    description="Serial number dispute dependency graph for ERPNext",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Store 11",
    author_email="admin@example.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[],
)

