import time
from fastapi import APIRouter, Response, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from config.db import engine, online_engine
from starlette.websockets import WebSocket
import datetime
import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

ticket = APIRouter()

websocket_clients = []

@ticket.post("/rfid")
async def receive_rfid(request: Request):
    body = await request.json()
    rfid = body.get("rfid").strip().replace(" ", "")

    try:
        verification_data = await update_verification2(rfid)
        if verification_data:
            # Broadcast ke semua klien WebSocket
            await broadcast(verification_data)
            return {"message": "RFID processed successfully"}
        else:
            return JSONResponse(status_code=400, content={"data": None, "message": "RFID not found"})
    except HTTPException as e:
        raise e
    except Exception as e:
        return JSONResponse(status_code=500, content={"data": None, "message": str(e)})

# Fungsi untuk broadcast data ke semua klien WebSocket yang terhubung
async def broadcast(data):
    for client in websocket_clients:
        try:
            await client.send_json(data)
        except WebSocketDisconnect:
            websocket_clients.remove(client)

# Endpoint WebSocket untuk mengelola koneksi WebSocket
@ticket.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)

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
            inner join orders o on od.orderId = o.id
            WHERE t.eventId = '25bdff39-fdd0-4a8f-9435-c69bb5370d3a' and o.status = "SUCCESS"
            order by od.NAME
            """
            result_proxy = await conn.execute(text(query))
            data = result_proxy.fetchall()

            formatted_data = []
            for row in data:
                row_dict = dict(row)
                if 'verifiedAt' in row_dict:
                    row_dict['verifiedAt'] = row_dict['verifiedAt'].isoformat()
                formatted_data.append(row_dict)

        return {
            "success": True,
            "data": formatted_data,
        }
    except Exception as e:
        print(e)
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
        }


async def update_verification2(hash: str):
    try:
        async with engine.begin() as conn:
            # Check if ticket is already verified for verification, or not verified for unverification
            check_query = """
                SELECT tv.isScanned, od.name, od.email, od.ticketId, tv.hash, t.name, od.orderId, tv.updatedAt
                FROM ticketverification AS tv
                INNER JOIN orderdetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                inner join orders o on od.orderId = o.id
                WHERE tv.HASH = :hash AND t.eventId = '25bdff39-fdd0-4a8f-9435-c69bb5370d3a' and o.status = "SUCCESS"
            """

            check_result = await conn.execute(text(check_query), {"hash": hash})
            row = check_result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404, detail="Ticket not found"
                )

            verification_status = row[0]  # Mengambil nilai pertama dari baris hasil query
            ticket_info = row[1:]

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

            is_verified = 1 if int(verification_status) == 0 else 0


            # Update verification status based on isVerify parameter
            query_update = """
                UPDATE ticketverification AS tv
                INNER JOIN orderdetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                SET tv.isScanned = :is_verified, tv.updatedAt = :current_datetime
                WHERE tv.HASH = :hash AND t.eventId = '25bdff39-fdd0-4a8f-9435-c69bb5370d3a'
            """

            current_datetime = datetime.datetime.now()

            result = await conn.execute(text(query_update), {"hash": hash, "is_verified": is_verified, "current_datetime": current_datetime})
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404, data="Ticket not found or already scanned"
                )

            # await send_notification({"message": "Ticket verification updated.", "event": "verification" if is_verify else "unverification"})

            # Construct data response including ticket information
            data = {
                "success": True,
                "message": "Success verify ticket" if verification_status else "Success unverify ticket",
                "ticket": {
                    "customerName": ticket_info[0],
                    "customerEmail": ticket_info[1],
                    "invoiceId": ticket_info[2],
                    "verifiedAt" : current_datetime.isoformat(),
                    "ticketType": ticket_info[4],
                    "isVerified" : int(verification_status),
                    "hash" :  ticket_info[3],
                    "ticketNum" : ticket_num
                }
            }

            return data

    except HTTPException as http_error:
        raise http_error  # Re-raise HTTPException to return the defined HTTP error response
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "ticket": {}  # Empty ticket data in case of error
        }
@ticket.put('/api/tickets/{hash}/verification')
async def update_verification(hash: str, request: Request, response: Response):
    try:
        # Ambil data dari body request
        body = await request.json()
        isVerify = body.get('isVerify')  # Mengambil nilai isVerify dari body

        async with engine.begin() as conn:
            # Check if ticket is already verified or not
            check_query = """
                SELECT tv.isScanned, od.name, od.email, od.ticketId, tv.hash, t.name, od.orderId, tv.updatedAt
                FROM ticketverification AS tv
                INNER JOIN orderdetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                INNER JOIN orders o ON od.orderId = o.id
                WHERE tv.HASH = :hash AND t.eventId = '25bdff39-fdd0-4a8f-9435-c69bb5370d3a' AND o.status = "SUCCESS"
            """

            check_result = await conn.execute(text(check_query), {"hash": hash})
            row = check_result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404, detail="Ticket not found"
                )

            verification_status = row[0]  # Mengambil nilai isScanned dari hasil query
            ticket_info = row[1:]

            # Jika isVerify True dan tiket sudah diverifikasi, kembalikan error 400
            if isVerify and verification_status:
                response.status_code = 400  # Set status code 400
                return {
                    "success": False,
                    "error": "Ticket already verified",
                    "ticket": {
                        "customerName": ticket_info[0],
                        "customerEmail": ticket_info[1],
                        "invoiceId": ticket_info[2],
                        "verifiedAt": row[7],  # Menggunakan updatedAt dari data sebelumnya
                        "ticketType": ticket_info[4],
                        "isVerified": int(verification_status),
                        "hash": ticket_info[3],
                        "ticketNum": 1  # Asumsikan ticketNum tetap sama, bisa disesuaikan sesuai logika
                    }
                }

            # Jika isVerify False dan tiket sudah diverifikasi, ubah isScanned menjadi False
            if not isVerify and verification_status:
                is_verified = 0  # Membatalkan verifikasi
            else:
                is_verified = 1 if isVerify else 0  # Mengatur nilai isScanned sesuai isVerify

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

            # Update verification status
            query_update = """
                UPDATE ticketverification AS tv
                INNER JOIN orderdetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                SET tv.isScanned = :is_verified, tv.updatedAt = :current_datetime
                WHERE tv.HASH = :hash AND t.eventId = '25bdff39-fdd0-4a8f-9435-c69bb5370d3a'
            """

            current_datetime = datetime.datetime.now()

            result = await conn.execute(text(query_update), {"hash": hash, "is_verified": is_verified, "current_datetime": current_datetime})

            # Construct data response including ticket information
            data = {
                "success": True,
                "message": "Success verify ticket" if isVerify else "Success unverify ticket",
                "ticket": {
                    "customerName": ticket_info[0],
                    "customerEmail": ticket_info[1],
                    "invoiceId": ticket_info[2],
                    "verifiedAt": current_datetime if isVerify else None,
                    "ticketType": ticket_info[4],
                    "isVerified": is_verified,
                    "hash": ticket_info[3],
                    "ticketNum": ticket_num
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
    

@ticket.get('/api/outlier')
async def read_data(response: Response):
    try:
        async with engine.begin() as conn:
            query = """
           SELECT email AS emails
            FROM orderdetails
            WHERE orderId IN
            (
                SELECT od.orderId
                FROM orders o
                JOIN orderdetails od ON od.orderId = o.id
                JOIN events e ON e.id = o.eventId
                WHERE o.eventId = "25bdff39-fdd0-4a8f-9435-c69bb5370d3a"
                GROUP BY od.orderId
                HAVING COUNT(DISTINCT od.email) > 1
            );
            """
            result_proxy = await conn.execute(text(query))
            data = result_proxy.fetchall()

        return {
            "success": True,
            "data": data,
        }
    except Exception as e:
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
        }
    




# Sessionmaker for local and online databases
LocalSession = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
OnlineSession = sessionmaker(online_engine, expire_on_commit=False, class_=AsyncSession)

@ticket.post('/api/sinkron')
async def sync_data(response: Response):
    try:
        async with LocalSession() as local_session, OnlineSession() as online_session:
            # Step 1: Get new data from online DB (orders with status 'SUCCESS' and the given eventId)
            online_query = """
            SELECT o.id AS orderId, o.status, o.customerId, o.eventId, o.createdAt, o.updatedAt,
                   od.id AS orderDetailId, od.ticketId, od.quantity, od.name, od.email, od.birthDate,
                   od.phoneNumber, od.gender, od.address, od.socialMedia, od.location, od.commiteeName,
                   tv.id AS ticketVerificationId, tv.hash, tv.isScanned, tv.updatedAt AS verifiedAt,
                   c.id AS customerId, c.name AS customerName, c.email AS customerEmail, c.gender AS customerGender, c.phoneNumber AS customerPhone, c.createdAt as cCreated, c.updatedAt as cUpdated, c.birthDate as cBirthDate
            FROM orders AS o
            inner JOIN orderDetails AS od ON o.id = od.orderId
            inner JOIN TicketVerification AS tv ON od.id = tv.orderDetailId
            inner JOIN customers AS c ON o.customerId = c.id
            WHERE o.eventId = '25bdff39-fdd0-4a8f-9435-c69bb5370d3a'
            """
            online_result = await online_session.execute(text(online_query))
            online_data = online_result.fetchall()

            # Step 2: Check if order already exists in local DB
            for row in online_data:
                order_id = row['orderId']
                check_query = "SELECT 1 FROM orders WHERE id = :order_id"
                existing_order = await local_session.execute(text(check_query), {'order_id': order_id})
                order_exists = existing_order.scalar()

                # Step 3: Insert data into local DB if order doesn't exist
                if not order_exists:
                    # Insert into customers table if customer doesn't exist
                    customer_id = row['customerId']
                    check_customer_query = "SELECT 1 FROM customers WHERE id = :customer_id"
                    existing_customer = await local_session.execute(text(check_customer_query), {'customer_id': customer_id})
                    customer_exists = existing_customer.scalar()

                    if not customer_exists:
                        insert_customer_query = """
                        INSERT INTO customers (id, name, email, birthDate, phoneNumber, gender, createdAt, updatedAt) 
                        VALUES (:customer_id, :customer_name, :customer_email, :birthDate, :phoneNumber,   :customer_gender, :createdAt, :updatedAt)
                        """
                        await local_session.execute(text(insert_customer_query), {
                            'customer_id': row['customerId'],
                            
                            'customer_name': row['customerName'],
                            'customer_email': row['customerEmail'],
                            'birthDate': row['cBirthDate'],
                            'phoneNumber': row['customerPhone'],
                            'createdAt': row['cCreated'],
                            'updatedAt' : row['cUpdated'],
                            'customer_gender': row['customerGender'],
                        })

                    # Insert into orders table
                    insert_order_query = """
                    INSERT INTO orders (id, status, customerId, eventId, createdAt, updatedAt) 
                    VALUES (:order_id, :status, :customer_id, :event_id, :created_at, :updated_at)
                    """
                    await local_session.execute(text(insert_order_query), {
                        'order_id': row['orderId'],
                        'status': row['status'],
                        'customer_id': row['customerId'],
                        'event_id': row['eventId'],
                        'created_at': row['createdAt'],
                        'updated_at': row['updatedAt'],
                    })

                    # Insert into orderDetails table
                    insert_order_details_query = """
                    INSERT INTO orderDetails (id, orderId, ticketId, quantity, name, email, birthDate, phoneNumber, gender, address, socialMedia, location, commiteeName) 
                    VALUES (:orderDetail_id, :order_id, :ticket_id, :quantity, :name, :email, :birthDate, :phoneNumber, :gender, :address, :socialMedia, :location, :commiteeName)
                    """
                    await local_session.execute(text(insert_order_details_query), {
                        'orderDetail_id': row['orderDetailId'],
                        'order_id': row['orderId'],
                        'ticket_id': row['ticketId'],
                        'quantity': row['quantity'],
                        'name': row['name'],
                        'email': row['email'],
                        'birthDate': row['birthDate'],
                        'phoneNumber': row['phoneNumber'],
                        'gender': row['gender'],
                        'address': row['address'],
                        'socialMedia': row['socialMedia'],
                        'location': row['location'],
                        'commiteeName': row['commiteeName'],
                    })

                    # Insert into ticketVerification table
                    insert_ticket_verification_query = """
                    INSERT INTO ticketVerification (id, orderDetailId, hash, isScanned, updatedAt) 
                    VALUES (:ticketVerification_id, :orderDetail_id, :hash, :isScanned, :verifiedAt)
                    """
                    await local_session.execute(text(insert_ticket_verification_query), {
                        'ticketVerification_id': row['ticketVerificationId'],
                        'orderDetail_id': row['orderDetailId'],
                        'hash': row['hash'],
                        'isScanned': row['isScanned'],
                        'verifiedAt': row['verifiedAt'],
                    })

            # Commit the transaction
            await local_session.commit()

        return {"success": True, "message": "Data synchronization completed."}
    
    except Exception as e:
        print(e)
        response.status_code = 500  # Internal Server Error
        return {"success": False, "error": str(e)}




if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)




