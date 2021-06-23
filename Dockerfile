FROM python:3

WORKDIR /app

COPY requirements.txt .
COPY Pipfile .
COPY Pipfile.lock .

RUN pip install -r requirements.txt

COPY . .

ENV SLACK_TEAM=""
ENV SLACK_COOKIE=""
ENV SLACK_API_TOKEN=""
ENV CONCURRENT_REQUESTS=5

VOLUME /emoji

ENTRYPOINT ["python"]
CMD upload.py /emoji/*