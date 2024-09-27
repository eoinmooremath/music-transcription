# # Source of this code: 
# # https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-service
# # One minor modification was made in order to make this file compatible with the 
# # Cloud Run setup. See the Readme for more details.

# # Use the official lightweight Python image.
# # https://hub.docker.com/_/python
# FROM python:3.11-slim


# EXPOSE 8501

# # Allow statements and log messages to immediately appear in the logs
# ENV PYTHONUNBUFFERED True

# # Copy local code to the container image.
# ENV APP_HOME /app
# WORKDIR $APP_HOME
# COPY . ./

# # Install production dependencies.
# RUN pip install --no-cache-dir -r requirements.txt

# # Run the web service on container startup. Here we use the gunicorn
# # webserver, with one worker process and 8 threads.
# # For environments with multiple CPU cores, increase the number of workers
# # to be equal to the cores available.
# # Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
# # CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:server


# ENTRYPOINT ["streamlit", "run", "music-lyrics-transcription.py", "--server.port=8501", "--server.address=0.0.0.0"]
# # main:app in the above line was switched to app:server in order to make
# # the code compatible with Cloud Run.


# Use the official Python image from the Docker Hub
FROM python:3.9-slim


# Install required system packages
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app


# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port your app runs on
EXPOSE 8501

# Run the Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
