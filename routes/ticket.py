from fastapi import APIRouter, Response, HTTPException
from config.db import conn
import json

ticket = APIRouter()
 
@ticket.get('/api/tickets')
async def readData(response: Response):
    try:
        query = """
            SELECT t.id AS invoiceId, tv.hash AS hash, tv.isScanned AS isVerified, od.NAME AS customerName,
            od.email AS customerEmail, t.name AS ticketType
            FROM ticketverification AS tv
            INNER JOIN orderdetails AS od ON tv.orderDetailId=od.id
            INNER JOIN tickets AS t ON od.ticketId=t.id
            WHERE t.name = 'Regular'
        """
        data = conn.execute(query).fetchall()

        if not data:
            raise HTTPException(status_code=404, detail="No tickets found")

        return {
            "success": True,
            "data": json.dumps([dict(row) for row in data]),
        }
    except HTTPException as e:
        response.status_code = e.status_code
        return {
            "success": False,
            "error": str(e.detail),
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
        query = """
            SELECT isScanned
            FROM ticketverification
            WHERE hash = %s
        """
        result = conn.execute(query, (hash,)).fetchone()

        if result is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        is_verified = result[0]
        return {
            "success": True,
            "isVerified": is_verified,
        }
    except HTTPException as e:
        response.status_code = e.status_code
        return {
            "success": False,
            "error": str(e.detail),
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
        query_update = """
            UPDATE ticketverification
            SET isScanned = 1
            WHERE hash = %s
        """
        result = conn.execute(query_update, (hash,))

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Ticket not found")

        return {
            "success": True,
            "message": "Ticket verification updated successfully.",
        }
    except HTTPException as e:
        response.status_code = e.status_code
        return {
            "success": False,
            "error": str(e.detail),
        }
    except Exception as e:
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
        }
