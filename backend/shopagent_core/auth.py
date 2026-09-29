import os
import secrets

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

_bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    expected_key = os.environ.get("SHOPAGENT_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=500, detail="Server API key is not configured."
        )

    if credentials is None or not secrets.compare_digest(
        credentials.credentials, expected_key
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    return credentials.credentials
