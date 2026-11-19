# Your team's container: everything in this folder except what .dockerignore keeps out. It is
# all installed here, at build time: a graded run reaches nothing but the arena and the model.
FROM python:3.14-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
