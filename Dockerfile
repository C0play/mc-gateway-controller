FROM python:3.14-alpine

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

RUN apk add --no-cache docker-cli
RUN apk add --no-cache docker-cli docker-cli-compose

WORKDIR /app

COPY src ./src

RUN mkdir containers

EXPOSE 6521

CMD ["python3", "./src/main.py"]
