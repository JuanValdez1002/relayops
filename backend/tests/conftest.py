from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

TEST_ENV_FILE = Path(__file__).resolve().parent.parent / ".env.test"

load_dotenv(TEST_ENV_FILE, override=True)

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from database import Base
import models

Base.metadata.create_all(bind=create_engine(
    __import__("os").environ["DATABASE_URL"]
))