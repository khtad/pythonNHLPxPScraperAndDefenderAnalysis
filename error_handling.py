import datetime

def log_error(error_message):
    with open("error_log.txt", "a") as file:
        file.write(f"{datetime.datetime.now()} - {error_message}\n")
