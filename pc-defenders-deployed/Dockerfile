FROM python:3.9.16
COPY ./requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
COPY ./src/. /app
ENTRYPOINT [ "python" ]
CMD ["app.py" ]