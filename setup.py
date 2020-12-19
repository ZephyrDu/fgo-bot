from setuptools import setup, find_packages

setup(
    name='fgo-bot',
    version='0.5',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'opencv-python<=4.3.0.38',
        'numpy<=1.17.5',
        'matplotlib'
    ],
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
    ]
)