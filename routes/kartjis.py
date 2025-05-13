from typing import Optional
from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import create_async_engine
import jwt
import hashlib
import hashlib
import pytz
import random
import uuid
from fastapi import APIRouter, Query, Response, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from config.db import online_engine
from datetime import datetime, timedelta
import uvicorn
import bcrypt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security, Depends
from utils.jwt_utils import verify_jwt_token


ticket = APIRouter()


@ticket.get("/protected")
def protected_route(user_data: dict = Depends(verify_jwt_token)):
    return {"message": "Token valid!", "user": user_data}


@ticket.get("/api/v2/events")
async def get_events(response: Response, user_data: dict = Depends(verify_jwt_token)):
    try:
        async with online_engine.begin() as conn:
            base_query = text(f"""
                            select * from events e 
                            join event_organizers eo on eo.event_id  = e.id
                            where eo.username = :username;
                            """)
            params = {
                "username": user_data['sub'],
            }
            result = await conn.execute(base_query, params)

            events = result.fetchall()

            if not events:
                raise HTTPException(
                    status_code=404, detail="No Event Related to this account"
                )
            event_list = [
                {
                    "id": event.id,
                    "category": event.category,
                    "name": event.name,
                    "detail_image": event.detail_image,
                }
                for event in events
            ]

            return {
                "status": "SUCCESS",
                "message": f"{len(event_list)} Event fetched successfully",
                "data": event_list,
            }
    except HTTPException as e:
        response.status_code = e.status_code
        return {"success": False, "error": e.detail}
    except Exception as e:
        response.status_code = 500
        return {"success": False, "error": "An internal server error occurred"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)
