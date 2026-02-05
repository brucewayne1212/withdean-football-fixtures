import sys
import os
from flask import Flask

# Add project root to path
sys.path.append(os.getcwd())

from routes.imports import process_sheet_fixtures
import inspect

print(f"Function: {process_sheet_fixtures}")
print(f"File: {inspect.getfile(process_sheet_fixtures)}")
