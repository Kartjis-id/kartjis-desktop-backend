from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from config.db import engine
from starlette.websockets import WebSocket
from typing import List
import datetime

ticket = APIRouter()

# websocket_connections: List[WebSocket] = []


# async def send_notification(data: dict):
#     for connection in websocket_connections:
#         await connection.send_json(data)


# @ticket.websocket("/api/ws/tickets")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     websocket_connections.append(websocket)
#     try:
#         while True:
#             await websocket.receive_text()
#     finally:
#         websocket_connections.remove(websocket)


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
            WHERE t.eventId = 'e0306093-b0ce-4f31-bb1e-ab8d1089095e' 
            order by od.NAME
            """
            result_proxy = await conn.execute(text(query))
            data = result_proxy.fetchall()

            formatted_data = []
            for row in data:
                row_dict = dict(row)
                if 'verifiedAt' in row_dict:
                    row_dict['verifiedAt'] = row_dict['verifiedAt'].strftime(
                        '%Y-%m-%d %H:%M:%S')
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


class TicketVerification(BaseModel):
    isVerify: bool

@ticket.put('/api/tickets/{hash}/verification')
async def update_verification(hash: str, ticket_verification: TicketVerification, response: Response):
    try:
        async with engine.begin() as conn:
            is_verify = ticket_verification.isVerify

            # Check if ticket is already verified for verification, or not verified for unverification
            check_query = """
                SELECT tv.isScanned, od.name, od.email, od.ticketId, tv.hash, t.name, od.orderId, tv.updatedAt
                FROM ticketverification AS tv
                INNER JOIN orderdetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                WHERE tv.HASH = :hash AND t.eventId = 'e0306093-b0ce-4f31-bb1e-ab8d1089095e'
            """

            check_result = await conn.execute(text(check_query), {"hash": hash})
            row = check_result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404, detail="Ticket not found"
                )

            verification_status = row[0]  # Mengambil nilai pertama dari baris hasil query
            ticket_info = row[1:]

            if is_verify:
                if verification_status == 1:
                    raise HTTPException(
                        status_code=400, detail={
                            "message": "Error Ticket already verified",
                             "ticket": {
                                "customerName": ticket_info[0],
                                "customerEmail": ticket_info[1],
                                "invoiceId": ticket_info[2],
                                "hash" :  ticket_info[3],
                                "verifiedAt": ticket_info[6].isoformat(),
                                "ticketType": ticket_info[4]

                            }
                        }
                    )
            else:
                if verification_status == 0:
                    raise HTTPException(
                        status_code=400, detail={
                            "message" : "Error Ticket is not verified", 
                            "ticket": {
                                "customerName": ticket_info[0],
                                "customerEmail": ticket_info[1],
                                "invoiceId": ticket_info[2],
                                "hash" :  ticket_info[3],
                                "verifiedAt": ticket_info[6].isoformat(),
                                "ticketType": ticket_info[4]
                            }
                        }
                    )
                
            get_num_query = """
                SELECT tv.hash FROM tickets t
                JOIN orderdetails AS od ON od.ticketId = t.id
                JOIN ticketverification AS tv ON tv.orderDetailId = od.id
                WHERE od.orderId = :orderId;
            """

            temp = await conn.execute(text(get_num_query), {"orderId": ticket_info[5]})
            list_data = temp.fetchall()
            ticket_num = 1

            for i, row in enumerate(list_data):
                if row[0] == ticket_info[3]:
                    ticket_num = i+1
                    break


            # Update verification status based on isVerify parameter
            query_update = """
                UPDATE ticketverification AS tv
                INNER JOIN orderdetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                SET tv.isScanned = :is_verified, tv.updatedAt = :current_datetime
                WHERE tv.HASH = :hash AND t.eventId = 'e0306093-b0ce-4f31-bb1e-ab8d1089095e'
            """

            current_datetime = datetime.datetime.now()

            result = await conn.execute(text(query_update), {"hash": hash, "is_verified": int(is_verify), "current_datetime": current_datetime})
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404, data="Ticket not found or already scanned"
                )

            # await send_notification({"message": "Ticket verification updated.", "event": "verification" if is_verify else "unverification"})

            # Construct data response including ticket information
            data = {
                "success": True,
                "message": "Success verify ticket" if is_verify else "Success unverify ticket",
                "ticket": {
                    "customerName": ticket_info[0],
                    "customerEmail": ticket_info[1],
                    "invoiceId": ticket_info[2],
                    "verifiedAt" : current_datetime,
                    "ticketType": ticket_info[4],
                    "isVerified" : int(is_verify),
                    "hash" :  ticket_info[3],
                    "ticketNum" : ticket_num
                }
            }

            return data

    except HTTPException as http_error:
        raise http_error  # Re-raise HTTPException to return the defined HTTP error response
    except Exception as e:
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
            "ticket": {}  # Empty ticket data in case of error
        }

@ticket.get('/api/tickets/{hash}/verification')
async def check_verification(hash: str, response: Response):
    try:
        async with engine.begin() as conn:
            query = """
                SELECT od.name, od.email, od.ticketId, tv.hash, t.name, od.orderId, tv.updatedAt, tv.isScanned
                FROM ticketverification AS tv
                INNER JOIN orderdetails AS od ON tv.orderDetailId=od.id
                INNER JOIN tickets AS t ON od.ticketId=t.id
                WHERE tv.hash = :hash AND t.eventId = 'e0306093-b0ce-4f31-bb1e-ab8d1089095e'
            """
            result = await conn.execute(text(query), {"hash": hash})
            data = result.fetchone()

            if data is None:
                raise HTTPException(status_code=404, detail="Ticket not found")
        
            get_num_query = """
                SELECT tv.hash FROM tickets t
                JOIN orderdetails AS od ON od.ticketId = t.id
                JOIN ticketverification AS tv ON tv.orderDetailId = od.id
                WHERE od.orderId = :orderId;
            """

            temp = await conn.execute(text(get_num_query), {"orderId": data[5]})
            list_data = temp.fetchall()
            ticket_num = 1

            for i, row in enumerate(list_data):
                if row[0] == data[3]:
                    ticket_num = i+1
                    break

            return {
                "success": True,
                "ticket": {
                    "customerName": data[0],
                    "customerEmail": data[1],
                    "invoiceId": data[2],
                    "verifiedAt" : data[6].isoformat(),
                    "ticketType": data[4],
                    "isVerified" : int(data[7]),
                    "hash" :  data[3],
                    "ticketNum" : ticket_num
                }
            }
    except Exception as e:
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
        }
