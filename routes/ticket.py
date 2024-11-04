import hashlib
import time
from typing import List, Optional
import uuid
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
            FROM TicketVerification AS tv
            INNER JOIN orderDetails AS od ON tv.orderDetailId=od.id
            INNER JOIN tickets AS t ON od.ticketId=t.id
            inner join orders o on od.orderId = o.id
            WHERE t.eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c' and o.status = "SUCCESS"
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
                FROM TicketVerification AS tv
                INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                inner join orders o on od.orderId = o.id
                WHERE tv.HASH = :hash AND t.eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c' and o.status = "SUCCESS"  
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
                JOIN orderDetails AS od ON od.ticketId = t.id
                JOIN TicketVerification AS tv ON tv.orderDetailId = od.id
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
                UPDATE TicketVerification AS tv
                INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                SET tv.isScanned = :is_verified, tv.updatedAt = :current_datetime
                WHERE tv.HASH = :hash AND t.eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c' 
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
                FROM TicketVerification AS tv
                INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                INNER JOIN orders o ON od.orderId = o.id
                WHERE tv.HASH = :hash AND t.eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c' AND o.status = "SUCCESS"
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
                JOIN orderDetails AS od ON od.ticketId = t.id
                JOIN TicketVerification AS tv ON tv.orderDetailId = od.id
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
                UPDATE TicketVerification AS tv
                INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
                INNER JOIN tickets AS t ON od.ticketId = t.id
                SET tv.isScanned = :is_verified, tv.updatedAt = :current_datetime
                WHERE tv.HASH = :hash AND t.eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c'
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
            FROM orderDetails
            WHERE orderId IN
            (
                SELECT od.orderId
                FROM orders o
                JOIN orderDetails od ON od.orderId = o.id
                JOIN events e ON e.id = o.eventId
                WHERE o.eventId = "ee2e57ed-8447-4cca-9623-6d20378c9a1c"
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


            query2 = '''
                select id, name, price, eventId, stock, createdAt, updatedAt, adminFee from tickets where eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c';
            '''

            online_result2 = await online_session.execute(text(query2))
            online_data2 = online_result2.fetchall()

            for row in online_data2:
                check_ticket_query = "SELECT 1 FROM tickets WHERE id = :ticket_id"
                existing_ticket = await local_session.execute(text(check_ticket_query), {'ticket_id': row['id']})
                ticket_exists = existing_ticket.scalar()

                if not ticket_exists:
                    insert_ticket_query = """
                    INSERT INTO tickets (id, name, price, eventId, stock, createdAt, updatedAt, adminFee) 
                    VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, :adminFee)
                    """
                    await local_session.execute(text(insert_ticket_query), {
                        'id': row['id'],
                        'name': row['name'],
                        'price': row['price'],
                        'eventId': row['eventId'],
                        'stock':row['stock'],
                        'createdAt': row['createdAt'],
                        'updatedAt': row['updatedAt'],
                        'adminFee': row['adminFee'],
                    })



            online_query = """
            SELECT o.id AS orderId, o.status, o.customerId, o.eventId, o.createdAt, o.updatedAt,
                   od.id AS orderDetailId, od.ticketId as ticketId, od.quantity, od.name, od.email, od.birthDate,
                   od.phoneNumber, od.gender, od.address, od.socialMedia, od.location, od.commiteeName,
                   tv.id AS TicketVerificationId, tv.hash, tv.isScanned, tv.updatedAt AS verifiedAt,
                   c.id AS customerId, c.name AS customerName, c.email AS customerEmail, c.gender AS customerGender, c.phoneNumber AS customerPhone, c.createdAt as cCreated, c.updatedAt as cUpdated, c.birthDate as cBirthDate
            FROM orders AS o
            INNER JOIN orderDetails AS od ON o.id = od.orderId
            INNER JOIN TicketVerification AS tv ON od.id = tv.orderDetailId
            LEFT JOIN customers AS c ON o.customerId = c.id
            WHERE o.eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c' 
            """
            online_result = await online_session.execute(text(online_query))
            online_data = online_result.fetchall()
            print(f"Online data fetched: {online_data}")

            # Step 2: Check if order already exists in local DB
            for row in online_data:
                order_id = row['orderId']
                customer_id = row['customerId']
                print(f"Processing order: {order_id}, customer: {customer_id}")

                # Check if order already exists
                check_order_query = "SELECT 1 FROM orders WHERE id = :order_id"
                existing_order = await local_session.execute(text(check_order_query), {'order_id': order_id})
                order_exists = existing_order.scalar()
                print(f"Order exists: {order_exists}")

                # Check if customer already exists
                check_customer_query = "SELECT 1 FROM customers WHERE id = :customer_id"
                existing_customer = await local_session.execute(text(check_customer_query), {'customer_id': customer_id})
                customer_exists = existing_customer.scalar()
                print(f"Customer exists: {customer_id}")

                # Insert customer if not exists
                if not customer_exists and customer_id != None:
                    insert_customer_query = """
                    INSERT INTO customers (id, name, email, birthDate, phoneNumber, gender, createdAt, updatedAt) 
                    VALUES (:customer_id, :customer_name, :customer_email, :birthDate, :phoneNumber, :customer_gender, :createdAt, :updatedAt)
                    """
                    await local_session.execute(text(insert_customer_query), {
                        'customer_id': row['customerId'],
                        'customer_name': row['customerName'],
                        'customer_email': row['customerEmail'],
                        'birthDate': row['cBirthDate'],
                        'phoneNumber': row['customerPhone'],
                        'createdAt': row['cCreated'],
                        'updatedAt': row['cUpdated'],
                        'customer_gender': row['customerGender'],
                    })
                    print(f"Inserted customer: {row['customerName']}")

                # Insert order only if it doesn't exist
                if not order_exists:
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
                    print(f"Inserted order: {row['orderId']}")

                # Check if orderDetail already exists
                check_order_detail_query = "SELECT 1 FROM orderDetails WHERE id = :order_detail_id"
                existing_order_detail = await local_session.execute(text(check_order_detail_query), {'order_detail_id': row['orderDetailId']})
                order_detail_exists = existing_order_detail.scalar()
                print(f"OrderDetail exists: {order_detail_exists}")

                # Insert order details if it doesn't exist
                if not order_detail_exists:
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
                    print(f"Inserted order detail: {row['orderDetailId']}")

                # Check if TicketVerification already exists
                check_tv_query = "SELECT 1 FROM TicketVerification WHERE id = :ticketVerificationId"
                existing_tv = await local_session.execute(text(check_tv_query), {'ticketVerificationId': row['TicketVerificationId']})
                tv_exists = existing_tv.scalar()
                print(f"TicketVerification exists: {tv_exists}")

                if not tv_exists:
                    # Insert into TicketVerification table
                    insert_ticket_verification_query = """
                    INSERT INTO TicketVerification (id, orderDetailId, hash, isScanned, updatedAt) 
                    VALUES (:TicketVerification_id, :orderDetail_id, :hash, :isScanned, :verifiedAt)
                    """
                    await local_session.execute(text(insert_ticket_verification_query), {
                        'TicketVerification_id': row['TicketVerificationId'],
                        'orderDetail_id': row['orderDetailId'],
                        'hash': row['hash'],
                        'isScanned': row['isScanned'],
                        'verifiedAt': row['verifiedAt'],
                    })
                    print(f"Inserted TicketVerification: {row['TicketVerificationId']}")

            # Commit the transaction
            await local_session.commit()
            print("Data synchronization completed successfully.")

        return {"success": True, "message": "Data synchronization completed."}
    
    except Exception as e:
        print(f"Error occurred: {e}")
        await local_session.rollback()  # Rollback if there's an error
        response.status_code = 500  # Internal Server Error
        return {"success": False, "error": str(e)}

class TicketData:
    def __init__(self, name: str, instagram: Optional[str], domisili: Optional[str], phonenumber: str, datebirth: int, gender: str):
        self.name = name
        self.instagram = instagram
        self.domisili = domisili
        self.phonenumber = phonenumber
        self.datebirth = datebirth
        self.gender = gender


# @app.post('/api/ots')
# async def create_tickets(tickets: List[TicketData], response: Response):
#     async with engine.begin() as conn:
#         try:
#             # INSERT INTO `tickets` (`id`, `name`, `price`, `eventId`, `stock`, `createdAt`, `updatedAt`, `adminFee`)
# # VALUES 
# # (UUID(), 'OTS', 0, 'ee2e57ed-8447-4cca-9623-6d20378c9a1c', 100, NOW(3), NOW(3), 0);

# # INSERT INTO `customers` (`id`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `createdAt`, `updatedAt`)
# # VALUES (UUID(), 'TOKU', 'john.doe@example.com', 19900101, '08123456789', 'MALE', NOW(3), NOW(3));


# # INSERT INTO `orders` (`id`, `status`, `createdAt`, `updatedAt`, `customerId`, `billId`, `paymentId`, `eventId`, `billLink`, `billToken`, `paymentType`)
# # VALUES (UUID(), 'SUCCESS', NOW(3), NOW(3), 'd13dbbce-99b6-11ef-8f44-040e3c00a454', null, null, 'ee2e57ed-8447-4cca-9623-6d20378c9a1c', NULL, null, null);


# # INSERT INTO `orderdetails` (`id`, `ticketId`, `quantity`, `orderId`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `address`, `socialMedia`, `location`, `commiteeName`)
# # VALUES (UUID(), 'a50cde6a-99b5-11ef-8f44-040e3c00a454', 1, 'f5200024-99b6-11ef-8f44-040e3c00a454', 'John Doe', 'john.doe@example.com', 19900101, '08123456789', 'MALE', '123 Main St', '@johndoe', 'OTS', 'Committee A');


# # INSERT INTO `ticketverification` (`id`, `hash`, `isScanned`, `createdAt`, `updatedAt`, `orderDetailId`)
# # VALUES (UUID(), MD5('email'), 0, NOW(3), NOW(3), @orderDetailId);
# #             for ticket in tickets:
#                 # # Generate unique ID and hash for each ticket
#                 # ticket_id = str(uuid.uuid4())
#                 # ticket_hash = hashlib.md5(ticket_id.encode()).hexdigest()  # Generate hash from ticket_id

#                 # # Prepare SQL query
#                 # query = text("""
#                 #     INSERT INTO ticketverification (id, hash, isScanned, createdAt, updatedAt, orderDetailId, customer_name, customer_email, customer_birth_date, customer_phone_number, customer_gender)
#                 #     VALUES (:id, :hash, :isScanned, NOW(), NOW(), :orderDetailId, :name, :instagram, :domisili, :phonenumber, :gender)
#                 # """)

#                 # # Execute the query for each ticket
#                 # await conn.execute(query, {
#                 #     'id': ticket_id,
#                 #     'hash': ticket_hash,
#                 #     'isScanned': 0,
#                 #     'orderDetailId': 'some-order-detail-id',  # Ganti dengan orderDetailId yang sesuai
#                 #     'name': ticket.name,
#                 #     'instagram': ticket.instagram,
#                 #     'domisili': ticket.domisili,
#                 #     'phonenumber': ticket.phonenumber,
#                 #     'gender': ticket.gender
#                 # })

#             # return {
#             #     "success": True,
#             #     "message": "Tickets successfully created.",
#             # }
#         except Exception as e:
#             print(e)
#             response.status_code = 500  # Internal Server Error
#             return {
#                 "success": False,
#                 "error": str(e),
#             }


@ticket.post('/api/backup')
async def backup_data(response: Response):
    try:
        async with LocalSession() as local_session, OnlineSession() as online_session:

            # Query data tickets dari local_session
            query_tickets = '''
                SELECT id, name, price, eventId, stock, createdAt, updatedAt, adminFee
                FROM tickets 
                WHERE eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c';
            '''
            local_result_tickets = await local_session.execute(text(query_tickets))
            local_tickets_data = local_result_tickets.fetchall()

            # Sinkronisasi data tickets ke online_session
            for ticket in local_tickets_data:
                check_ticket_query = "SELECT 1 FROM tickets WHERE id = :ticket_id"
                existing_ticket = await online_session.execute(
                    text(check_ticket_query), {'ticket_id': ticket['id']}
                )
                if not existing_ticket.scalar():
                    insert_ticket_query = """
                    INSERT INTO tickets (id, name, price, eventId, stock, createdAt, updatedAt, adminFee) 
                    VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, :adminFee)
                    """
                    await online_session.execute(text(insert_ticket_query), {
                        'id': ticket['id'],
                        'name': ticket['name'],
                        'price': ticket['price'],
                        'eventId': ticket['eventId'],
                        'stock': ticket['stock'],
                        'createdAt': ticket['createdAt'],
                        'updatedAt': ticket['updatedAt'],
                        'adminFee': ticket['adminFee']
                    })

            # First, fetch IDs of orderDetails for a specific event from local data
            order_details_query_1 = '''
            SELECT od.id 
            FROM orderDetails od 
            JOIN orders o ON o.id = od.orderId
            WHERE o.eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c'
            '''

            # Execute the first query to get the local data
            order_details_local = await local_session.execute(text(order_details_query_1))
            local_data = [row.id for row in order_details_local.fetchall()]  # Extract IDs for use in NOT IN

            # Second query: Fetch detailed information for orderDetails not in local_data
            order_details_query_2 = """
            SELECT od.id AS orderDetailId, od.orderId, od.ticketId, od.quantity, od.name, od.email, 
                od.birthDate, od.phoneNumber, od.gender, od.address, od.socialMedia, od.location, 
                od.commiteeName, o.status, o.customerId, o.eventId, o.createdAt AS orderCreatedAt, 
                o.updatedAt AS orderUpdatedAt, c.id AS customerId, c.name AS customerName, 
                c.email AS customerEmail, c.gender AS customerGender, c.phoneNumber AS customerPhone, 
                c.createdAt AS customerCreatedAt, c.updatedAt AS customerUpdatedAt, c.birthDate AS customerBirthDate, 
                tv.id AS TicketVerificationId, tv.hash, tv.isScanned, tv.updatedAt AS verifiedAt
            FROM orderDetails AS od
            INNER JOIN orders AS o ON od.orderId = o.id
            LEFT JOIN customers AS c ON o.customerId = c.id
            LEFT JOIN TicketVerification AS tv ON od.id = tv.orderDetailId
            WHERE o.eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c' AND od.id NOT IN :order_details_local
            """

            # Execute the second query with the list of IDs from the first query
            local_order_details = await local_session.execute(text(order_details_query_2), {'order_details_local': tuple(local_data)})
            order_details_data = local_order_details.fetchall()


            # Sinkronisasi data orderDetails dan relasi terkait ke online_session
            print(order_details_data)
            for row in order_details_data:
                # Sinkronisasi data customer
                if row['customerId']:
                    check_customer_query = "SELECT 1 FROM customers WHERE id = :customer_id"
                    customer_exists = await online_session.execute(
                        text(check_customer_query), {'customer_id': row['customerId']}
                    )
                    if not customer_exists.scalar():
                        insert_customer_query = """
                        INSERT INTO customers (id, name, email, birthDate, phoneNumber, gender, createdAt, updatedAt)
                        VALUES (:id, :name, :email, :birthDate, :phoneNumber, :gender, :createdAt, :updatedAt)
                        """
                        await online_session.execute(text(insert_customer_query), {
                            'id': row['customerId'],
                            'name': row['customerName'],
                            'email': row['customerEmail'],
                            'birthDate': row['customerBirthDate'],
                            'phoneNumber': row['customerPhone'],
                            'gender': row['customerGender'],
                            'createdAt': row['customerCreatedAt'],
                            'updatedAt': row['customerUpdatedAt']
                        })

                # Sinkronisasi data orders
                check_order_query = "SELECT 1 FROM orders WHERE id = :order_id"
                order_exists = await online_session.execute(
                    text(check_order_query), {'order_id': row['orderId']}
                )
                if not order_exists.scalar():
                    insert_order_query = """
                    INSERT INTO orders (id, status, customerId, eventId, createdAt, updatedAt)
                    VALUES (:id, :status, :customerId, :eventId, :createdAt, :updatedAt)
                    """
                    await online_session.execute(text(insert_order_query), {
                        'id': row['orderId'],
                        'status': row['status'],
                        'customerId': row['customerId'],
                        'eventId': row['eventId'],
                        'createdAt': row['orderCreatedAt'],
                        'updatedAt': row['orderUpdatedAt']
                    })

                # Sinkronisasi data orderDetails
                insert_order_detail_query = """
                INSERT INTO orderDetails (id, orderId, ticketId, quantity, name, email, birthDate, phoneNumber, 
                                          gender, address, socialMedia, location, commiteeName)
                VALUES (:id, :orderId, :ticketId, :quantity, :name, :email, :birthDate, :phoneNumber, :gender, 
                        :address, :socialMedia, :location, :commiteeName)
                """
                await online_session.execute(text(insert_order_detail_query), {
                    'id': row['orderDetailId'],
                    'orderId': row['orderId'],
                    'ticketId': row['ticketId'],
                    'quantity': row['quantity'],
                    'name': row['name'],
                    'email': row['email'],
                    'birthDate': row['birthDate'],
                    'phoneNumber': row['phoneNumber'],
                    'gender': row['gender'],
                    'address': row['address'],
                    'socialMedia': row['socialMedia'],
                    'location': row['location'],
                    'commiteeName': row['commiteeName']
                })

                # Sinkronisasi data TicketVerification jika ada
                if row['TicketVerificationId']:
                    check_tv_query = "SELECT 1 FROM TicketVerification WHERE id = :tv_id"
                    tv_exists = await online_session.execute(
                        text(check_tv_query), {'tv_id': row['TicketVerificationId']}
                    )
                    if not tv_exists.scalar():
                        insert_tv_query = """
                        INSERT INTO TicketVerification (id, orderDetailId, hash, isScanned, updatedAt)
                        VALUES (:id, :orderDetailId, :hash, :isScanned, :updatedAt)
                        """
                        await online_session.execute(text(insert_tv_query), {
                            'id': row['TicketVerificationId'],
                            'orderDetailId': row['orderDetailId'],
                            'hash': row['hash'],
                            'isScanned': row['isScanned'],
                            'updatedAt': row['verifiedAt']
                        })


           # Step 1: Fetch all TicketVerification IDs with isScanned = True in the local data
            order_details_query_2 = '''
            SELECT tv.id 
            FROM orderDetails od 
            JOIN orders o ON o.id = od.orderId
            JOIN TicketVerification tv ON tv.orderDetailId = od.id
            WHERE o.eventId = 'ee2e57ed-8447-4cca-9623-6d20378c9a1c' AND tv.isScanned = TRUE
            '''

            # Execute the query to fetch the local TicketVerification IDs
            local_ticket_verifications = await local_session.execute(text(order_details_query_2))
            local_verified_ids = [row.id for row in local_ticket_verifications.fetchall()]

            # Step 2: Update TicketVerification records in the online database
            if local_verified_ids:  # Proceed only if there are IDs to update
                update_query = '''
                UPDATE TicketVerification 
                SET isScanned = TRUE 
                WHERE id IN :verified_ids
                '''

                # Execute the update query in the online session
                await online_session.execute(text(update_query), {'verified_ids': tuple(local_verified_ids)})

            # Commit perubahan di online_session
            await online_session.commit()
            print("Data backup to online completed successfully.")
            return {"success": True, "message": "Data backup to online completed."}

    except Exception as e:
        print(f"Error occurred: {e}")
        await online_session.rollback()
        response.status_code = 500
        return {"success": False, "error": str(e)}



if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)




