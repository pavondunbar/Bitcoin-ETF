
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install kafka-python psycopg2-binary
CMD ["python", "app.py"]
