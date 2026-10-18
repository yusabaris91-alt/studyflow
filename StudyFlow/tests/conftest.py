import os
import tempfile

# Uygulama testleri gerçek veriye dokunmasın: config import edilmeden önce ayarla.
os.environ["STUDYFLOW_DATA_DIR"] = tempfile.mkdtemp(prefix="studyflow-test-")

import pytest

from studyflow import db
from studyflow.repository import Repository


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "test.db"
    db.initialize(path)
    return Repository(path)


@pytest.fixture
def math_id(repo):
    return next(s.id for s in repo.list_subjects() if s.name == "AYT Matematik")
