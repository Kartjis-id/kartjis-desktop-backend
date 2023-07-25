from fastapi import APIRouter, Response, HTTPException
from sqlalchemy import text
from config.db import engine
from starlette.websockets import WebSocket
from typing import List
import datetime

ticket = APIRouter()

websocket_connections: List[WebSocket] = []

async def send_notification(data: dict):
    for connection in websocket_connections:
        await connection.send_json(data)

@ticket.websocket("/api/ws/tickets")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    finally:
        websocket_connections.remove(websocket)

@ticket.get('/api/tickets')
async def read_data(response: Response):
    try:
        async with engine.begin() as conn:
            query = """
            SELECT od.id AS invoiceId, tv.hash AS hash, tv.isScanned AS isVerified, od.NAME AS customerName,
            od.email AS customerEmail, t.name AS ticketType, tv.updatedAt as verifiedAt
            FROM ticketverification AS tv
            INNER JOIN orderdetails AS od ON tv.orderDetailId=od.id
            INNER JOIN tickets AS t ON od.ticketId=t.id
            WHERE t.name = 'Regular'
            """
            result_proxy = await conn.execute(text(query))
            data = result_proxy.fetchall()

            formatted_data = []
            for row in data:
                row_dict = dict(row)
                if 'verifiedAt' in row_dict:
                    row_dict['verifiedAt'] = row_dict['verifiedAt'].strftime('%Y-%m-%d %H:%M:%S')
                formatted_data.append(row_dict)

            return {
                "success": True,
                "data": formatted_data,
            }
    except Exception as e:
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
        }

@ticket.get('/api/tickets/{hash}/verification')
async def check_verification(hash: str, response: Response):
    try:
        async with engine.begin() as conn:
            query = """
                SELECT tv.isScanned
                FROM ticketverification AS tv
                INNER JOIN orderdetails AS od ON tv.orderDetailId=od.id
                INNER JOIN tickets AS t ON od.ticketId=t.id
                WHERE tv.hash = :hash AND t.name = 'Regular'
            """
            result = await conn.execute(text(query), {"hash": hash})
            data = result.fetchone()

            if data is None:
                raise HTTPException(status_code=404, detail="Ticket not found")

            is_verified = data[0]
            return {
                "success": True,
                "isVerified": is_verified,
            }
    except Exception as e:
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
        }

@ticket.put('/api/tickets/{hash}/verification')
async def update_verification(hash: str, response: Response):
    try:
        async with engine.begin() as conn:
            query_update = """
                UPDATE ticketverification AS tv
                INNER JOIN orderdetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                SET tv.isScanned = 1, tv.updatedAt = :current_datetime
                WHERE tv.HASH = :hash AND tv.isScanned = 0 AND t.name = 'Regular'
            """

            current_datetime = datetime.datetime.now()

            result = await conn.execute(text(query_update), {"hash": hash, "current_datetime": current_datetime})
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Ticket not found or already scanned")

            if result.rowcount > 0:
                # Notify subscribed clients about the ticket verification update
                await send_notification({"message": "Ticket verification updated.", "event": "verification"})

            return {
                "success": True,
                "message": "Ticket verification updated successfully.",
            }
    except Exception as e:
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
        }
