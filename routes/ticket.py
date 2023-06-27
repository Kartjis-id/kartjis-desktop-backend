from fastapi import APIRouter, Response, HTTPException
from sqlalchemy import text
from config.db import engine
from starlette.websockets import WebSocket
from typing import List

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
async def readData(response: Response):
    try:
        async with engine.begin() as conn:
            query = """
            SELECT t.id AS invoiceId, tv.hash AS hash, tv.isScanned AS isVerified, od.NAME AS customerName,
            od.email AS customerEmail, t.name AS ticketType
            FROM ticketverification AS tv
            INNER JOIN orderdetails AS od ON tv.orderDetailId=od.id
            INNER JOIN tickets AS t ON od.ticketId=t.id
            WHERE t.name = 'Regular'
             """
            result_proxy = await conn.execute(text(query))
            data = result_proxy.fetchall()

            if not data:
                raise HTTPException(status_code=404, detail="No tickets found")

            return {
                "success": True,
                "data": [dict(row) for row in data],
            }
    except Exception as e:
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
        }


@ticket.get('/api/tickets/{hash}/verification')
async def checkVerification(hash: str, response: Response):
    try:
        async with engine.begin() as conn:
            query = """
                SELECT isScanned
                FROM ticketverification
                WHERE hash = :hash
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
async def updateVerification(hash: str, response: Response):
    try:
        async with engine.begin() as conn:
            query_update = """
                UPDATE ticketverification
                SET isScanned = 1
                WHERE hash = :hash AND isScanned = 0
            """

            result = await conn.execute(text(query_update), {"hash": hash})
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
