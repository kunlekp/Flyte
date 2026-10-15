# Paste this into the WSGI configuration file PythonAnywhere links to on the
# "Web" tab (replace YOURUSERNAME). See docs/DEPLOYMENT.md, Option A.
import os
import sys

PROJECT = "/home/YOURUSERNAME/flyte"
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

from dotenv import load_dotenv          # reads /home/YOURUSERNAME/flyte/.env
load_dotenv(os.path.join(PROJECT, ".env"))

from app import app as application      # noqa: E402
