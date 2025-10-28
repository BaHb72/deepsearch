"""
DeepSearch 安装配置
"""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

try:
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        requirements = [
            line.strip()
            for line in fh
            if line.strip() and not line.startswith("#")
        ]
except FileNotFoundError:
    requirements = []

setup(
    name="deepsearch",
    version="0.1.0",
    author="DeepSearch Team",
    description="智能量化交易系统",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/deepsearch",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.13",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
            "pytest-cov>=4.0",
            "black>=23.0",
            "isort>=5.12",
            "flake8>=6.0",
            "mypy>=1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "deepsearch=deepsearch.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "deepsearch": [
            "webui/frontend/dist/**/*",
            "settings/*.yaml",
            "settings/*.yml",
        ],
    },
)
