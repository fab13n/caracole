#!/usr/bin/env python
import os
import sys
import socket
import time


def wait_for_postgres():
    """Wait for PostreSQL container to start."""
    dest = (os.environ["POSTGRES_HOST"], int(os.environ["POSTGRES_PORT"]))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    first_loop = True
    while True:
        try:
            s.connect(dest)
            s.close()
            break
        except (socket.error, OSError):
            if first_loop:
                print("Wait for DB", end="")
                first_loop = False
            print(".", end="", flush=True)
            time.sleep(1)


if __name__ == "__main__":
    e = os.environ
    e.setdefault("DJANGO_SETTINGS_MODULE", "solalim.settings")
    if e.get('POSTGRES_DBNAME'):
        wait_for_postgres()
    

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
