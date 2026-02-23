import os
from dotenv import load_dotenv
load_dotenv()
from database import db_manager

from models import EmailTemplate

def check_templates():
    session = db_manager.get_session()
    templates = session.query(EmailTemplate).all()
    print(f"Found {len(templates)} templates:")
    for t in templates:
        print(f"ID: {t.id}")
        print(f"Name: {t.name}")
        print(f"Type: {t.template_type}")
        print(f"Active: {t.is_active}")
        print(f"Content Length: {len(t.content) if t.content else 0}")
        print(f"Content Start: {t.content[:100] if t.content else 'EMPTY'}")
        print("-" * 20)
    session.close()

if __name__ == "__main__":
    check_templates()
