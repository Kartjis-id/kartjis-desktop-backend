from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()


def get_public_key():
    with open("utils/public.pem", "r") as f:
        return f.read()


def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        decoded = jwt.decode(
            token,
            get_public_key(),
            algorithms=["RS256"],  # atau sesuai dengan yang kamu pakai
            options={"verify_aud": False}  # jika kamu tidak memakai 'aud'
        )
        return decoded  # kembalikan isi payload JWT
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
