# setup.py
from setuptools import setup, find_packages

setup(
    name="glue",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "click>=8.0.0",
        "python-dotenv>=0.19.0",
        "aiohttp>=3.8.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "glue=glue.cli:cli",  # Updated to use cli instead of main
        ],
    },
    python_requires=">=3.9",
    author="Paradise Labs",
    description="GLUE Framework - GenAI Linking & Unification Engine",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
