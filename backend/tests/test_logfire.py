import logfire
import os
from dotenv import load_dotenv

load_dotenv()
logfire_token = os.getenv("LOGFIRE_TOKEN")
logfire.configure(token=logfire_token)
logfire.info("Hello from mvpbot!")
