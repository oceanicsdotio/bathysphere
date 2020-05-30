from setuptools import setup, find_packages

setup(
    name='bathysphere',
    version='1.6',
    description='Marine geospatial data and analytics services',
    url='https://graph.oceanics.io',
    author='Oceanicsdotio',
    author_email='business@oceanics.io',
    packages=["bathysphere"],
    include_package_data=True,
    license='MIT',
    install_requires=[
        "flask",
        "flask_cors",
        "gunicorn",
        "connexion",
        "neo4j-driver",
        "itsdangerous",
        "passlib",
        "pyyaml",
        "requests",
        "retry",
        "redis",
        "pg8000",
        "bidict",
        "prance",
        "rq",
        "attrs",
        "click>=6.7",
        "colorama",
        "minio",
        "Jinja2",
        "MarkupSafe",
        "pip",
        "setuptools",
        "Werkzeug",
        "wheel",
        "sqlalchemy",
        "google-cloud-secret-manager",
        "pytz",
        "urllib3<1.25,>=1.21.1",

        "pytest", # TODO: comment out once extra_require bugs are fixed
        "pytest_dependency",
        "pytest-cov",
        "docker-compose",
        "colorama",
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
        "tensorflow",
        "pyshp",
        "pyproj",
        "netCDF4",
        "pillow",
        "scikit-learn",
        "rdp",
  
    ],
    entry_points="""
        [console_scripts]
        bathysphere=cli:cli
    """,
    zip_safe=False,
    # extra_requires={
    #     "dev": [
    #         "pytest", 
    #         "pytest_dependency",
    #         "pytest-cov",
    #         "docker-compose",
    #         "colorama"
    #     ],
    #     "numerical": [
    #         "numpy",
    #         "scipy",
    #         "pandas",
    #         "matplotlib",
    #         "tensorflow",
    #         "pyshp",
    #         "pyproj",
    #         "netCDF4",
    #         "pillow",
    #         "scikit-learn",
    #         "rdp",
    #     ]
    # }
    )
