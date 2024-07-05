# syntax=docker/dockerfile:1

FROM python:3.9-slim-buster

EXPOSE 5000

WORKDIR /python-docker

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

ENV FLASK_APP=api_v3.py

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]