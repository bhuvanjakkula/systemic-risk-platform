from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient

@contextmanager
def authenticated_client(app):
    with tempfile.TemporaryDirectory() as folder:
        with patch.dict(os.environ, {'SRP_AUTH_DB': str(Path(folder)/'accounts.sqlite3')}):
            with TestClient(app, headers={'X-SRP-Request':'1'}) as client:
                response=client.post('/auth/signup',json={'mobile':'+15555550199','password':'Test-only passphrase 2026!'})
                assert response.status_code==201, response.text
                assert client.post('/plans/select',json={'plan_id':'professional'}).status_code==200
                yield client
