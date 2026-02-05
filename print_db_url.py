import os
from dotenv import load_dotenv

load_dotenv()
print(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
