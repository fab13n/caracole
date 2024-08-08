FROM python:3.9

# Set environment varibles
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV LD_LIBRARY_PATH /usr/local/lib
ENV SRC_DIR /root/src
ENV CPLUS_INCLUDE_PATH /usr/include/gdal
ENV C_INCLUDE_PATH /usr/include/gdal

COPY requirements-debian.txt /root/

RUN apt-get update &&\
    apt-get install -y -q $(sed -e 's/#.*$//g' /root/requirements-debian.txt) &&\
    rm -rf /var/lib/apt/lists/*

# TODO extract programmatically
# RUN echo "Set GDAL version in requirements-python.txt as follows:"; ogrinfo --version; exit 1

# TODO check whether libgrib-api-dev is required
RUN pip install -U pip
COPY requirements-python.txt /root/
RUN pip install -r /root/requirements-python.txt

# Because there's s bug in setuptools/gdal compat
# (https://stackoverflow.com/questions/69123406/error-building-pygdal-unknown-distribution-option-use-2to3-fixers-and-use-2)
RUN pip install setuptools==57.5.0

# Needs to be the same version as returned by libgdal-dev
RUN pip install GDAL==$(gdal-config --version)

RUN pip install gunicorn

WORKDIR /home/solalim/