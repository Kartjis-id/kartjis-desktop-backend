# from fastapi import HTTPException, Request, Response
# import hashlib
# import pytz
# import random
# import time
# from typing import List, Optional
# import uuid
# from fastapi import APIRouter, Query, Response, HTTPException, Request, WebSocket, WebSocketDisconnect
# from fastapi.responses import JSONResponse
# from pydantic import BaseModel
# from sqlalchemy import text
# from config.db import engine, online_engine, auth_engine
# from starlette.websockets import WebSocket
# from datetime import datetime
# import uvicorn
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.orm import sessionmaker
# import bcrypt

# ticket = APIRouter()

# websocket_clients = []


# @ticket.post("/rfid")
# async def receive_rfid(request: Request):
#     body = await request.json()
#     rfid = body.get("rfid").strip().replace(" ", "")

#     try:
#         verification_data = await update_verification2(rfid)
#         if verification_data:
#             # Broadcast ke semua klien WebSocket
#             await broadcast(verification_data)
#             return {"message": "RFID processed successfully"}
#         else:
#             return JSONResponse(status_code=400, content={"data": None, "message": "RFID not found"})
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"data": None, "message": str(e)})

# # Fungsi untuk broadcast data ke semua klien WebSocket yang terhubung


# async def broadcast(data):
#     for client in websocket_clients:
#         try:
#             await client.send_json(data)
#         except WebSocketDisconnect:
#             websocket_clients.remove(client)

# # Endpoint WebSocket untuk mengelola koneksi WebSocket


# @ticket.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     websocket_clients.append(websocket)
#     try:
#         while True:
#             await websocket.receive_text()
#     except WebSocketDisconnect:
#         websocket_clients.remove(websocket)


# @ticket.get('/api/events/{event_id}/master')
# async def read_data(event_id: str, response: Response):
#     try:
#         async with engine.begin() as conn:
#             # Optimized query with COUNT for ticketCount and ROW_NUMBER() for ticketNum
#             base_query = """
#             SELECT od.address as address, od.birthDate as birthDate,  
#             od.email AS email, od.gender as gender, od.id as id, 
#             od.location as location, od.NAME AS name, o.id as orderId, od.phoneNumber as phoneNumber, 
#             od.socialMedia as socialMedia, 
#             t.id as ticketId, t.name as ticketName, t.price as ticketPrice,
#             o.createdAt as orderCreatedAt,
#             tv.hash AS hash, tv.isScanned AS isVerified, tv.id as tvId,
#             ROW_NUMBER() OVER (PARTITION BY od.orderId ORDER BY od.NAME) AS ticketNum,
#             COUNT(*) OVER (PARTITION BY od.orderId) AS ticketCount
#             FROM TicketVerification AS tv
#             INNER JOIN orderDetails AS od ON tv.orderDetailId=od.id
#             INNER JOIN tickets AS t ON od.ticketId=t.id
#             INNER JOIN orders o ON od.orderId = o.id
#             WHERE t.eventId = :event_id and o.status = "SUCCESS"
#             ORDER BY od.NAME
#             """

#             # Execute the query
#             result_proxy = await conn.execute(text(base_query), {'event_id': event_id})
#             data = result_proxy.fetchall()

#             formatted_data = []

#             for row in data:
#                 row_dict = dict(row)

#                 # Mapping the fields to the required structure
#                 row_dict['ticket'] = {
#                     'id': row_dict['ticketId'],
#                     'name': row_dict['ticketName'],
#                     'price': row_dict['ticketPrice']
#                 }
#                 row_dict['order'] = {
#                     'id': row_dict['orderId'],
#                     'createdAt': row_dict['orderCreatedAt']
#                 }
#                 row_dict['ticketVerification'] = {
#                     'isScanned': bool(row_dict['isVerified']),
#                     'hash': row_dict['hash'],
#                     'id': row_dict['tvId']
#                 }

#                 # Add ticketNum and ticketCount directly from SQL
#                 row_dict['ticketNum'] = row_dict['ticketNum']
#                 row_dict['ticketCount'] = row_dict['ticketCount']

#                 # Clean up the data (remove the original fields that are no longer needed)
#                 del row_dict['ticketName']
#                 del row_dict['ticketPrice']
#                 del row_dict['ticketId']
#                 del row_dict['orderCreatedAt']
#                 del row_dict['isVerified']
#                 del row_dict['hash']
#                 del row_dict['tvId']

#                 # Append the updated row to the formatted_data list
#                 formatted_data.append(row_dict)

#         return {
#             "status": "",
#             "data": formatted_data
#         }

#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "error": str(e),
#         }


# @ticket.get('/api/tickets')
# async def read_data(response: Response):
#     try:
#         async with engine.begin() as conn:
#             query = """
#             SELECT od.id AS invoiceId, tv.hash AS hash, tv.isScanned AS isVerified, od.NAME AS customerName,
#             od.email AS customerEmail, t.name AS ticketType, tv.updatedAt as verifiedAt
#             FROM TicketVerification AS tv
#             INNER JOIN orderDetails AS od ON tv.orderDetailId=od.id
#             INNER JOIN tickets AS t ON od.ticketId=t.id
#             inner join orders o on od.orderId = o.id
#             WHERE t.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2' and o.status = "SUCCESS"
#             order by od.NAME
#             """
#             result_proxy = await conn.execute(text(query))
#             data = result_proxy.fetchall()

#             formatted_data = []
#             for row in data:
#                 row_dict = dict(row)
#                 if 'verifiedAt' in row_dict:
#                     row_dict['verifiedAt'] = row_dict['verifiedAt'].isoformat()
#                 formatted_data.append(row_dict)

#         return {
#             "success": True,
#             "data": formatted_data,
#         }
#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "error": str(e),
#         }


# async def update_verification2(hash: str):
#     try:
#         async with engine.begin() as conn:
#             # Check if ticket is already verified for verification, or not verified for unverification
#             check_query = """
#                 SELECT tv.isScanned, od.name, od.email, od.ticketId, tv.hash, t.name, od.orderId, tv.updatedAt
#                 FROM TicketVerification AS tv
#                 INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
#                 INNER JOIN tickets AS t ON od.ticketId = t.id
#                 inner join orders o on od.orderId = o.id
#                 WHERE tv.HASH = :hash AND t.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2' and o.status = "SUCCESS"  
#             """

#             check_result = await conn.execute(text(check_query), {"hash": hash})
#             row = check_result.fetchone()

#             if not row:
#                 raise HTTPException(
#                     status_code=404, detail="Ticket not found"
#                 )

#             # Mengambil nilai pertama dari baris hasil query
#             verification_status = row[0]
#             ticket_info = row[1:]

#             get_num_query = """
#                 SELECT tv.hash FROM tickets t
#                 JOIN orderDetails AS od ON od.ticketId = t.id
#                 JOIN TicketVerification AS tv ON tv.orderDetailId = od.id
#                 WHERE od.orderId = :orderId;
#             """

#             temp = await conn.execute(text(get_num_query), {"orderId": ticket_info[5]})
#             list_data = temp.fetchall()
#             ticket_num = 1

#             for i, row in enumerate(list_data):
#                 if row[0] == ticket_info[3]:
#                     ticket_num = i+1
#                     break

#             is_verified = 1 if int(verification_status) == 0 else 0

#             # Update verification status based on isVerify parameter
#             query_update = """
#                 UPDATE TicketVerification AS tv
#                 INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
#                 INNER JOIN tickets AS t ON od.ticketId = t.id
#                 SET tv.isScanned = :is_verified, tv.updatedAt = :current_datetime
#                 WHERE tv.HASH = :hash AND t.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2' 
#             """

#             current_datetime = datetime.now()

#             result = await conn.execute(text(query_update), {"hash": hash, "is_verified": is_verified, "current_datetime": current_datetime})
#             if result.rowcount == 0:
#                 raise HTTPException(
#                     status_code=404, data="Ticket not found or already scanned"
#                 )

#             # await send_notification({"message": "Ticket verification updated.", "event": "verification" if is_verify else "unverification"})

#             # Construct data response including ticket information
#             data = {
#                 "success": True,
#                 "message": "Success verify ticket" if verification_status else "Success unverify ticket",
#                 "ticket": {
#                     "customerName": ticket_info[0],
#                     "customerEmail": ticket_info[1],
#                     "invoiceId": ticket_info[2],
#                     "verifiedAt": current_datetime.isoformat(),
#                     "ticketType": ticket_info[4],
#                     "isVerified": int(verification_status),
#                     "hash":  ticket_info[3],
#                     "ticketNum": ticket_num
#                 }
#             }

#             return data

#     except HTTPException as http_error:
#         raise http_error  # Re-raise HTTPException to return the defined HTTP error response
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e),
#             "ticket": {}  # Empty ticket data in case of error
#         }


# @ticket.put('/api/tickets/{hash}/verification')
# async def update_verification(hash: str, request: Request, response: Response):
#     try:
#         # Ambil data dari body request
#         body = await request.json()
#         isVerify = body.get('isVerify')  # Mengambil nilai isVerify dari body

#         async with engine.begin() as conn:
#             # Check if ticket is already verified or not
#             check_query = """
#                 SELECT tv.isScanned, od.name, od.email, od.ticketId, tv.hash, t.name, od.orderId, tv.updatedAt
#                 FROM TicketVerification AS tv
#                 INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
#                 INNER JOIN tickets AS t ON od.ticketId = t.id
#                 INNER JOIN orders o ON od.orderId = o.id
#                 WHERE tv.HASH = :hash AND t.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2' AND o.status = "SUCCESS"
#             """

#             check_result = await conn.execute(text(check_query), {"hash": hash})
#             row = check_result.fetchone()

#             if not row:
#                 raise HTTPException(
#                     status_code=404, detail="Ticket not found"
#                 )

#             # Mengambil nilai isScanned dari hasil query
#             verification_status = row[0]
#             ticket_info = row

#             # Jika isVerify True dan tiket sudah diverifikasi, kembalikan error 400
#             if isVerify and verification_status:
#                 response.status_code = 400  # Set status code 400
#                 return {
#                     "success": False,
#                     "error": "Ticket already verified",
#                     "ticket": {
#                         "customerName": ticket_info[1],
#                         "customerEmail": ticket_info[2],
#                         "invoiceId": ticket_info[3],
#                         # Menggunakan updatedAt dari data sebelumnya
#                         # "verifiedAt": ,
#                         "ticketType": ticket_info[5],
#                         "isVerified": int(verification_status),
#                         "hash": ticket_info[4],
#                         "ticketNum": 1  # Asumsikan ticketNum tetap sama, bisa disesuaikan sesuai logika
#                     }
#                 }

#             # Jika isVerify False dan tiket sudah diverifikasi, ubah isScanned menjadi False
#             if not isVerify and verification_status:
#                 is_verified = 0  # Membatalkan verifikasi
#             else:
#                 is_verified = 1 if isVerify else 0  # Mengatur nilai isScanned sesuai isVerify

#             get_num_query = """
#                 SELECT tv.hash FROM tickets t
#                 JOIN orderDetails AS od ON od.ticketId = t.id
#                 JOIN TicketVerification AS tv ON tv.orderDetailId = od.id
#                 WHERE od.orderId = :orderId;
#             """

#             temp = await conn.execute(text(get_num_query), {"orderId": ticket_info[6]})
#             list_data = temp.fetchall()
#             ticket_num = 1

#             for i, row in enumerate(list_data):
#                 if row[0] == ticket_info[3]:
#                     ticket_num = i+1
#                     break

#             # Update verification status
#             query_update = """
#                 UPDATE TicketVerification AS tv
#                 INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
#                 INNER JOIN tickets AS t ON od.ticketId = t.id
#                 SET tv.isScanned = :is_verified, tv.updatedAt = :current_datetime
#                 WHERE tv.HASH = :hash AND t.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2'
#             """

#             current_datetime = datetime.now()

#             result = await conn.execute(text(query_update), {"hash": hash, "is_verified": is_verified, "current_datetime": current_datetime})

#             # Construct data response including ticket information
#             data = {
#                 "success": True,
#                 "message": "Success verify ticket" if isVerify else "Success unverify ticket",
#                 "ticket": {
#                     "customerName": ticket_info[1],
#                     "customerEmail": ticket_info[2],
#                     "invoiceId": ticket_info[3],
#                     "verifiedAt": current_datetime if isVerify else None,
#                     "ticketType": ticket_info[5],
#                     "isVerified": is_verified,
#                     "hash": ticket_info[4],
#                     "ticketNum": ticket_num
#                 }
#             }

#             return data

#     except HTTPException as http_error:
#         raise http_error  # Re-raise HTTPException to return the defined HTTP error response
#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "error": str(e),
#             "ticket": {}  # Empty ticket data in case of error
#         }


# @ticket.get('/api/outlier')
# async def read_data(response: Response):
#     try:
#         async with engine.begin() as conn:
#             query = """
#            SELECT email AS emails
#             FROM orderDetails
#             WHERE orderId IN
#             (
#                 SELECT od.orderId
#                 FROM orders o
#                 JOIN orderDetails od ON od.orderId = o.id
#                 JOIN events e ON e.id = o.eventId
#                 WHERE o.eventId = "74deeb28-3fea-4f95-bd5d-6866940e35d2"
#                 GROUP BY od.orderId
#                 HAVING COUNT(DISTINCT od.email) > 1
#             );
#             """
#             result_proxy = await conn.execute(text(query))
#             data = result_proxy.fetchall()

#         return {
#             "success": True,
#             "data": data,
#         }
#     except Exception as e:
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "error": str(e),
#         }


# # Sessionmaker for local and online databases
# LocalSession = sessionmaker(
#     engine, expire_on_commit=False, class_=AsyncSession)
# OnlineSession = sessionmaker(
#     online_engine, expire_on_commit=False, class_=AsyncSession)


# @ticket.post('/api/sinkron')
# async def sync_data(response: Response):
#     try:
#         async with LocalSession() as local_session, OnlineSession() as online_session:
#             # Step 1: Get new data from online DB (orders with status 'SUCCESS' and the given eventId)

#             query2 = '''
#                 select id, name, price, eventId, stock, createdAt, updatedAt, adminFee from tickets where eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2';
#             '''

#             online_result2 = await online_session.execute(text(query2))
#             online_data2 = online_result2.fetchall()

#             for row in online_data2:
#                 check_ticket_query = "SELECT 1 FROM tickets WHERE id = :ticket_id"
#                 existing_ticket = await local_session.execute(text(check_ticket_query), {'ticket_id': row['id']})
#                 ticket_exists = existing_ticket.scalar()

#                 if not ticket_exists:
#                     insert_ticket_query = """
#                     INSERT INTO tickets (id, name, price, eventId, stock, createdAt, updatedAt, adminFee) 
#                     VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, :adminFee)
#                     """
#                     await local_session.execute(text(insert_ticket_query), {
#                         'id': row['id'],
#                         'name': row['name'],
#                         'price': row['price'],
#                         'eventId': row['eventId'],
#                         'stock': row['stock'],
#                         'createdAt': row['createdAt'],
#                         'updatedAt': row['updatedAt'],
#                         'adminFee': row['adminFee'],
#                     })

#             online_query = """
#             SELECT o.id AS orderId, o.status, o.customerId, o.eventId, o.createdAt, o.updatedAt,
#                    od.id AS orderDetailId, od.ticketId as ticketId, od.quantity, od.name, od.email, od.birthDate,
#                    od.phoneNumber, od.gender, od.address, od.socialMedia, od.location, od.commiteeName,
#                    tv.id AS TicketVerificationId, tv.hash, tv.isScanned, tv.updatedAt AS verifiedAt,
#                    c.id AS customerId, c.name AS customerName, c.email AS customerEmail, c.gender AS customerGender, c.phoneNumber AS customerPhone, c.createdAt as cCreated, c.updatedAt as cUpdated, c.birthDate as cBirthDate
#             FROM orders AS o
#             INNER JOIN orderDetails AS od ON o.id = od.orderId
#             INNER JOIN TicketVerification AS tv ON od.id = tv.orderDetailId
#             LEFT JOIN customers AS c ON o.customerId = c.id
#             WHERE o.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2' 
#             """
#             online_result = await online_session.execute(text(online_query))
#             online_data = online_result.fetchall()
#             print(f"Online data fetched: {online_data}")

#             # Step 2: Check if order already exists in local DB
#             for row in online_data:
#                 order_id = row['orderId']
#                 customer_id = row['customerId']
#                 print(f"Processing order: {order_id}, customer: {customer_id}")

#                 # Check if order already exists
#                 check_order_query = "SELECT 1 FROM orders WHERE id = :order_id"
#                 existing_order = await local_session.execute(text(check_order_query), {'order_id': order_id})
#                 order_exists = existing_order.scalar()
#                 print(f"Order exists: {order_exists}")

#                 # Check if customer already exists
#                 check_customer_query = "SELECT 1 FROM customers WHERE id = :customer_id"
#                 existing_customer = await local_session.execute(text(check_customer_query), {'customer_id': customer_id})
#                 customer_exists = existing_customer.scalar()
#                 print(f"Customer exists: {customer_id}")

#                 # Insert customer if not exists
#                 if not customer_exists and customer_id != None:
#                     insert_customer_query = """
#                     INSERT INTO customers (id, name, email, birthDate, phoneNumber, gender, createdAt, updatedAt) 
#                     VALUES (:customer_id, :customer_name, :customer_email, :birthDate, :phoneNumber, :customer_gender, :createdAt, :updatedAt)
#                     """
#                     await local_session.execute(text(insert_customer_query), {
#                         'customer_id': row['customerId'],
#                         'customer_name': row['customerName'],
#                         'customer_email': row['customerEmail'],
#                         'birthDate': row['cBirthDate'],
#                         'phoneNumber': row['customerPhone'],
#                         'createdAt': row['cCreated'],
#                         'updatedAt': row['cUpdated'],
#                         'customer_gender': row['customerGender'],
#                     })
#                     print(f"Inserted customer: {row['customerName']}")

#                 # Insert order only if it doesn't exist
#                 if not order_exists:
#                     insert_order_query = """
#                     INSERT INTO orders (id, status, customerId, eventId, createdAt, updatedAt) 
#                     VALUES (:order_id, :status, :customer_id, :event_id, :created_at, :updated_at)
#                     """
#                     await local_session.execute(text(insert_order_query), {
#                         'order_id': row['orderId'],
#                         'status': row['status'],
#                         'customer_id': row['customerId'],
#                         'event_id': row['eventId'],
#                         'created_at': row['createdAt'],
#                         'updated_at': row['updatedAt'],
#                     })
#                     print(f"Inserted order: {row['orderId']}")

#                 # Check if orderDetail already exists
#                 check_order_detail_query = "SELECT 1 FROM orderDetails WHERE id = :order_detail_id"
#                 existing_order_detail = await local_session.execute(text(check_order_detail_query), {'order_detail_id': row['orderDetailId']})
#                 order_detail_exists = existing_order_detail.scalar()
#                 print(f"OrderDetail exists: {order_detail_exists}")

#                 # Insert order details if it doesn't exist
#                 if not order_detail_exists:
#                     insert_order_details_query = """
#                     INSERT INTO orderDetails (id, orderId, ticketId, quantity, name, email, birthDate, phoneNumber, gender, address, socialMedia, location, commiteeName) 
#                     VALUES (:orderDetail_id, :order_id, :ticket_id, :quantity, :name, :email, :birthDate, :phoneNumber, :gender, :address, :socialMedia, :location, :commiteeName)
#                     """
#                     await local_session.execute(text(insert_order_details_query), {
#                         'orderDetail_id': row['orderDetailId'],
#                         'order_id': row['orderId'],
#                         'ticket_id': row['ticketId'],
#                         'quantity': row['quantity'],
#                         'name': row['name'],
#                         'email': row['email'],
#                         'birthDate': row['birthDate'],
#                         'phoneNumber': row['phoneNumber'],
#                         'gender': row['gender'],
#                         'address': row['address'],
#                         'socialMedia': row['socialMedia'],
#                         'location': row['location'],
#                         'commiteeName': row['commiteeName'],
#                     })
#                     print(f"Inserted order detail: {row['orderDetailId']}")

#                 # Check if TicketVerification already exists
#                 check_tv_query = "SELECT 1 FROM TicketVerification WHERE id = :ticketVerificationId"
#                 existing_tv = await local_session.execute(text(check_tv_query), {'ticketVerificationId': row['TicketVerificationId']})
#                 tv_exists = existing_tv.scalar()
#                 print(f"TicketVerification exists: {tv_exists}")

#                 if not tv_exists:
#                     # Insert into TicketVerification table
#                     insert_ticket_verification_query = """
#                     INSERT INTO TicketVerification (id, orderDetailId, hash, isScanned, updatedAt) 
#                     VALUES (:TicketVerification_id, :orderDetail_id, :hash, :isScanned, :verifiedAt)
#                     """
#                     await local_session.execute(text(insert_ticket_verification_query), {
#                         'TicketVerification_id': row['TicketVerificationId'],
#                         'orderDetail_id': row['orderDetailId'],
#                         'hash': row['hash'],
#                         'isScanned': row['isScanned'],
#                         'verifiedAt': row['verifiedAt'],
#                     })
#                     print(f"Inserted TicketVerification: {
#                           row['TicketVerificationId']}")

#             # Step 1: Fetch all TicketVerification IDs with isScanned = True in the local data
#             order_details_query_2 = '''
#             SELECT tv.id 
#             FROM orderDetails od 
#             JOIN orders o ON o.id = od.orderId
#             JOIN TicketVerification tv ON tv.orderDetailId = od.id
#             WHERE o.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2' AND tv.isScanned = TRUE
#             '''

#             # Execute the query to fetch the local TicketVerification IDs
#             local_ticket_verifications = await online_session.execute(text(order_details_query_2))
#             local_verified_ids = [
#                 row.id for row in local_ticket_verifications.fetchall()]

#             # Step 2: Update TicketVerification records in the online database
#             if local_verified_ids:  # Proceed only if there are IDs to update
#                 update_query = '''
#                 UPDATE TicketVerification 
#                 SET isScanned = TRUE 
#                 WHERE id IN :verified_ids
#                 '''

#                 # Execute the update query in the online session
#                 await local_session.execute(text(update_query), {'verified_ids': tuple(local_verified_ids)})

#             # Commit perubahan di online_session
#             # Commit the transaction
#             await local_session.commit()
#             print("Data synchronization completed successfully.")

#         return {"success": True, "message": "Data synchronization completed."}

#     except Exception as e:
#         print(f"Error occurred: {e}")
#         await local_session.rollback()  # Rollback if there's an error
#         response.status_code = 500  # Internal Server Error
#         return {"success": False, "error": str(e)}


# class TicketData(BaseModel):
#     customer_name: str
#     customer_email: str
#     customer_birthdate: int
#     customer_phone: str
#     customer_gender: str
#     address: str
#     social_media: str
#     ticket_name: str

# # Assume `engine` is already defined and connected to the database


# @ticket.post('/api/ots')
# async def create_tickets(tickets: List[TicketData], response: Response):
#     async with engine.begin() as conn:
#         try:
#             for ticket in tickets:
#                 ticket_id = str(uuid.uuid4())
#                 customer_id = str(uuid.uuid4())
#                 order_id = str(uuid.uuid4())
#                 order_detail_id = str(uuid.uuid4())
#                 verification_id = str(uuid.uuid4())
#                 current_time = datetime.utcnow()

#                 result = await conn.execute(
#                     text(
#                         "SELECT id FROM `tickets` WHERE `name` = :name and `eventId` = :eventId"),
#                     {"name": ticket.ticket_name,
#                         "eventId": "74deeb28-3fea-4f95-bd5d-6866940e35d2"}
#                 )
#                 existing_ticket = result.fetchone()

#                 if existing_ticket:
#                     ticket_id = existing_ticket[0]
#                 else:

#                     await conn.execute(
#                         text("""
#                             INSERT INTO `tickets` (`id`, `name`, `price`, `eventId`, `stock`, `createdAt`, `updatedAt`, `adminFee`)
#                             VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, 0)
#                         """),
#                         {
#                             "id": ticket_id,
#                             "name": ticket.ticket_name,
#                             "price": 0,
#                             "eventId": "74deeb28-3fea-4f95-bd5d-6866940e35d2",
#                             "stock": 100,
#                             "createdAt": current_time,
#                             "updatedAt": current_time,
#                         }
#                     )
#                 # Insert into `customers`
#                 await conn.execute(
#                     text("""
#                         INSERT INTO `customers` (`id`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `createdAt`, `updatedAt`)
#                         VALUES (:id, :name, :email, :birthDate, :phoneNumber, :gender, :createdAt, :updatedAt)
#                     """),
#                     {
#                         "id": customer_id,
#                         "name": ticket.customer_name,
#                         "email": ticket.customer_email,
#                         "birthDate": ticket.customer_birthdate,
#                         "phoneNumber": ticket.customer_phone,
#                         "gender": ticket.customer_gender,
#                         "createdAt": current_time,
#                         "updatedAt": current_time,
#                     }
#                 )

#                 # Insert into `orders`
#                 await conn.execute(
#                     text("""
#                         INSERT INTO `orders` (`id`, `status`, `createdAt`, `updatedAt`, `customerId`, `eventId`)
#                         VALUES (:id, 'SUCCESS', :createdAt, :updatedAt, :customerId, :eventId)
#                     """),
#                     {
#                         "id": order_id,
#                         "createdAt": current_time,
#                         "updatedAt": current_time,
#                         "customerId": customer_id,
#                         "eventId": '74deeb28-3fea-4f95-bd5d-6866940e35d2',
#                     }
#                 )

#                 # Insert into `orderdetails`
#                 await conn.execute(
#                     text("""
#                         INSERT INTO `orderdetails` (`id`, `ticketId`, `quantity`, `orderId`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `address`, `socialMedia`, `location`, `commiteeName`)
#                         VALUES (:id, :ticketId, 1, :orderId, :name, :email, :birthDate, :phoneNumber, :gender, :address, :socialMedia, :location, :commiteeName)
#                     """),
#                     {
#                         "id": order_detail_id,
#                         "ticketId": ticket_id,
#                         "orderId": order_id,
#                         "name": ticket.customer_name,
#                         "email": ticket.customer_email,
#                         "birthDate": ticket.customer_birthdate,
#                         "phoneNumber": ticket.customer_phone,
#                         "gender": ticket.customer_gender,
#                         "address": ticket.address,
#                         "socialMedia": ticket.social_media,
#                         "location": ticket.ticket_name,
#                         "commiteeName": None,
#                     }
#                 )

#                 # Menggabungkan nilai email, orderDetailId, dan createdAt
#                 # Menghasilkan angka acak antara 1000 dan 9999
#                 random_number = random.randint(1000, 9999)
#                 combined_string = f"{ticket.customer_email}{
#                     order_detail_id}{current_time}{random_number}"

#                 # Menghasilkan hash MD5
#                 hash_value = hashlib.md5(combined_string.encode()).hexdigest()
#                 await conn.execute(
#                     text("""
#                         INSERT INTO `ticketverification` (`id`, `hash`, `isScanned`, `createdAt`, `updatedAt`, `orderDetailId`)
#                         VALUES (:id, :hash, 1, :createdAt, :updatedAt, :orderDetailId)
#                     """),
#                     {
#                         "id": verification_id,
#                         "hash": hash_value,
#                         "createdAt": current_time,
#                         "updatedAt": current_time,
#                         "orderDetailId": order_detail_id,
#                     }
#                 )

#             return {
#                 "success": True,
#                 "message": "Tickets successfully created.",
#             }

#         except Exception as e:
#             print(e)
#             response.status_code = 500  # Internal Server Error
#             return {
#                 "success": False,
#                 "error": str(e),
#             }


# @ticket.post('/api/backup')
# async def backup_data(response: Response):
#     try:
#         async with LocalSession() as local_session, OnlineSession() as online_session:

#             # Query data tickets dari local_session
#             query_tickets = '''
#                 SELECT id, name, price, eventId, stock, createdAt, updatedAt, adminFee
#                 FROM tickets 
#                 WHERE eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2';
#             '''
#             local_result_tickets = await local_session.execute(text(query_tickets))
#             local_tickets_data = local_result_tickets.fetchall()

#             # Sinkronisasi data tickets ke online_session
#             for ticket in local_tickets_data:
#                 check_ticket_query = "SELECT 1 FROM tickets WHERE id = :ticket_id"
#                 existing_ticket = await online_session.execute(
#                     text(check_ticket_query), {'ticket_id': ticket['id']}
#                 )
#                 if not existing_ticket.scalar():
#                     insert_ticket_query = """
#                     INSERT INTO tickets (id, name, price, eventId, stock, createdAt, updatedAt, adminFee) 
#                     VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, :adminFee)
#                     """
#                     await online_session.execute(text(insert_ticket_query), {
#                         'id': ticket['id'],
#                         'name': ticket['name'],
#                         'price': ticket['price'],
#                         'eventId': ticket['eventId'],
#                         'stock': ticket['stock'],
#                         'createdAt': ticket['createdAt'],
#                         'updatedAt': ticket['updatedAt'],
#                         'adminFee': ticket['adminFee']
#                     })

#                     # Second query: Fetch detailed information for orderDetails not in local_data
#             order_details_query_2 = """
#             SELECT od.id
#             from orderDetails AS od 
#             INNER JOIN tickets AS t ON od.ticketId=t.id
#             inner join orders o on od.orderId = o.id
#             WHERE t.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2' and o.status = "SUCCESS" and (t.name like :ticket_name or t.name = 'Instansi')
#             """

#             # Execute the second query with the list of IDs from the first query
#             local_order_details = await online_session.execute(text(order_details_query_2), {'ticket_name': '%OTS%'})
#             order_details_data = local_order_details.fetchall()
#             order_details_data = [item[0] for item in order_details_data]
#             print(len(order_details_data))

#             order_details_query_3 = """
#                 SELECT od.id AS orderDetailId, od.orderId, od.ticketId, od.quantity, od.name, od.email, 
#                     od.birthDate, od.phoneNumber, od.gender, od.address, od.socialMedia, od.location, 
#                     od.commiteeName, o.status, o.customerId, o.eventId, o.createdAt AS orderCreatedAt, 
#                     o.updatedAt AS orderUpdatedAt, c.id AS customerId, c.name AS customerName, 
#                     c.email AS customerEmail, c.gender AS customerGender, c.phoneNumber AS customerPhone, 
#                     c.createdAt AS customerCreatedAt, c.updatedAt AS customerUpdatedAt, c.birthDate AS customerBirthDate, 
#                     tv.id AS TicketVerificationId, tv.hash, tv.isScanned, tv.updatedAt AS verifiedAt
#                 FROM orderDetails AS od
#                 INNER JOIN orders AS o ON od.orderId = o.id
#                 LEFT JOIN customers AS c ON o.customerId = c.id
#                 INNER JOIN tickets AS t ON od.ticketId = t.id  -- Tambahkan join ke tabel tickets
#                 INNER JOIN TicketVerification AS tv ON od.id = tv.orderDetailId
#                 WHERE od.id NOT IN :online_data 
#                 AND o.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2' 
#                 AND (t.name like :ticket_name or t.name = 'Instansi')
#             """

#             # Persiapkan parameter
#             order_details_data_tuple = tuple(order_details_data) if order_details_data else (
#                 '',)  # Pastikan ini adalah tuple, bahkan jika kosong
#             ticket_name_param = "%OTS%"  # Tambahkan wildcard langsung di parameter

#             # Eksekusi query
#             local_order_details3 = await local_session.execute(
#                 text(order_details_query_3),
#                 {"online_data": order_details_data_tuple,
#                     "ticket_name": ticket_name_param}
#             )
#             order_details_data3 = local_order_details3.fetchall()
#             print(len(order_details_data3))

#             for row in order_details_data3:
#                 # Sinkronisasi data customer
#                 if row['customerId']:
#                     check_customer_query = "SELECT 1 FROM customers WHERE id = :customer_id"
#                     customer_exists = await online_session.execute(
#                         text(check_customer_query), {
#                             'customer_id': row['customerId']}
#                     )
#                     if not customer_exists.scalar():
#                         insert_customer_query = """
#                         INSERT INTO customers (id, name, email, birthDate, phoneNumber, gender, createdAt, updatedAt)
#                         VALUES (:id, :name, :email, :birthDate, :phoneNumber, :gender, :createdAt, :updatedAt)
#                         """
#                         await online_session.execute(text(insert_customer_query), {
#                             'id': row['customerId'],
#                             'name': row['customerName'],
#                             'email': row['customerEmail'],
#                             'birthDate': row['customerBirthDate'],
#                             'phoneNumber': row['customerPhone'],
#                             'gender': row['customerGender'],
#                             'createdAt': row['customerCreatedAt'],
#                             'updatedAt': row['customerUpdatedAt']
#                         })

#                 # Sinkronisasi data orders
#                 check_order_query = "SELECT 1 FROM orders WHERE id = :order_id"
#                 order_exists = await online_session.execute(
#                     text(check_order_query), {'order_id': row['orderId']}
#                 )
#                 if not order_exists.scalar():
#                     insert_order_query = """
#                     INSERT INTO orders (id, status, customerId, eventId, createdAt, updatedAt)
#                     VALUES (:id, :status, :customerId, :eventId, :createdAt, :updatedAt)
#                     """
#                     await online_session.execute(text(insert_order_query), {
#                         'id': row['orderId'],
#                         'status': row['status'],
#                         'customerId': row['customerId'],
#                         'eventId': row['eventId'],
#                         'createdAt': row['orderCreatedAt'],
#                         'updatedAt': row['orderUpdatedAt']
#                     })

#                 # Sinkronisasi data orderDetails
#                 insert_order_detail_query = """
#                 INSERT INTO orderDetails (id, orderId, ticketId, quantity, name, email, birthDate, phoneNumber, 
#                                           gender, address, socialMedia, location, commiteeName)
#                 VALUES (:id, :orderId, :ticketId, :quantity, :name, :email, :birthDate, :phoneNumber, :gender, 
#                         :address, :socialMedia, :location, :commiteeName)
#                 """
#                 await online_session.execute(text(insert_order_detail_query), {
#                     'id': row['orderDetailId'],
#                     'orderId': row['orderId'],
#                     'ticketId': row['ticketId'],
#                     'quantity': row['quantity'],
#                     'name': row['name'],
#                     'email': row['email'],
#                     'birthDate': row['birthDate'],
#                     'phoneNumber': row['phoneNumber'],
#                     'gender': row['gender'],
#                     'address': row['address'],
#                     'socialMedia': row['socialMedia'],
#                     'location': row['location'],
#                     'commiteeName': row['commiteeName']
#                 })

#                 # Sinkronisasi data TicketVerification jika ada
#                 if row['TicketVerificationId']:
#                     check_tv_query = "SELECT 1 FROM TicketVerification WHERE id = :tv_id"
#                     tv_exists = await online_session.execute(
#                         text(check_tv_query), {
#                             'tv_id': row['TicketVerificationId']}
#                     )
#                     if not tv_exists.scalar():
#                         insert_tv_query = """
#                         INSERT INTO TicketVerification (id, orderDetailId, hash, isScanned, updatedAt)
#                         VALUES (:id, :orderDetailId, :hash, :isScanned, :updatedAt)
#                         """
#                         await online_session.execute(text(insert_tv_query), {
#                             'id': row['TicketVerificationId'],
#                             'orderDetailId': row['orderDetailId'],
#                             'hash': row['hash'],
#                             'isScanned': row['isScanned'],
#                             'updatedAt': row['verifiedAt']
#                         })

#            # Step 1: Fetch all TicketVerification IDs with isScanned = True in the local data
#             order_details_query_2 = '''
#             SELECT tv.id 
#             FROM orderDetails od 
#             JOIN orders o ON o.id = od.orderId
#             JOIN TicketVerification tv ON tv.orderDetailId = od.id
#             WHERE o.eventId = '74deeb28-3fea-4f95-bd5d-6866940e35d2' AND tv.isScanned = TRUE
#             '''

#             # Execute the query to fetch the local TicketVerification IDs
#             local_ticket_verifications = await local_session.execute(text(order_details_query_2))
#             local_verified_ids = [
#                 row.id for row in local_ticket_verifications.fetchall()]

#             # Step 2: Update TicketVerification records in the online database
#             if local_verified_ids:  # Proceed only if there are IDs to update
#                 update_query = '''
#                 UPDATE TicketVerification 
#                 SET isScanned = TRUE 
#                 WHERE id IN :verified_ids
#                 '''

#                 # Execute the update query in the online session
#                 await online_session.execute(text(update_query), {'verified_ids': tuple(local_verified_ids)})

#             # Commit perubahan di online_session
#             await online_session.commit()
#             print("Data backup to online completed successfully.")
#             return {"success": True, "message": "Data backup to online completed."}

#     except Exception as e:
#         print(f"Error occurred: {e}")
#         await online_session.rollback()
#         response.status_code = 500
#         return {"success": False, "error": str(e)}


# @ticket.get('/api/events/{event_id}/ticket-type-summary')
# async def ticket_type_summary(
#     event_id: str,
#     response: Response,
# ):
#     try:
#         async with engine.begin() as conn:
#             summary_query = """
#             SELECT 
#                 t.name AS ticketTypeName,
#                 COALESCE(COUNT(od.id), 0) AS totalSold,
#                 COALESCE(SUM(CASE WHEN od.gender = 'Male' THEN 1 ELSE 0 END), 0) AS maleCount,
#                 COALESCE(SUM(CASE WHEN od.gender = 'Female' THEN 1 ELSE 0 END), 0) AS femaleCount,
#                 t.price AS ticketPrice,
#                 t.stock AS stock,
#                 t.adminFee AS adminFee,
#                 COALESCE(t.price * COUNT(od.id), 0) AS totalPrice,
#                 COALESCE((t.price * COUNT(od.id)) + (COUNT(od.id) * t.adminFee), 0) AS revenueAfterAdminFee
#             FROM tickets AS t
#             LEFT JOIN orderDetails AS od ON od.ticketId = t.id
#             LEFT JOIN orders AS o ON od.orderId = o.id AND o.status = 'SUCCESS'
#             WHERE t.eventId = :event_id
#             GROUP BY t.id
#             ORDER BY t.name;
#             """

#             params = {'event_id': event_id}
#             result_proxy = await conn.execute(text(summary_query), params)

#             data = result_proxy.fetchall()

#             summary_data = [
#                 {
#                     "ticketTypeName": row["ticketTypeName"],
#                     "totalSold": row["totalSold"],
#                     "maleCount": row["maleCount"],
#                     "femaleCount": row["femaleCount"],
#                     "ticketPrice": row["ticketPrice"],
#                     "totalPrice": row["totalPrice"],
#                     "adminFee": row["adminFee"],
#                     "stock": row["stock"],
#                     "revenueAfterAdminFee": row["revenueAfterAdminFee"]
#                 }
#                 for row in data
#             ]

#         return {
#             "status": "SUCCESS",
#             "data": summary_data
#         }

#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "error": str(e),
#         }


# @ticket.delete('/api/orders/{id}')
# async def delete_order(id: str, response: Response):
#     try:
#         async with engine.begin() as conn:
#             # Delete query
#             delete_query = "DELETE FROM orders WHERE id = :id"
#             result = await conn.execute(text(delete_query), {'id': id})

#             # Check if any row was deleted
#             if result.rowcount == 0:
#                 raise HTTPException(status_code=404, detail="Order not found")

#         return {"status": "SUCCESS", "message": f"Order with ID {id} deleted successfully"}

#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {"status": "ERROR", "error": str(e)}


# @ticket.get('/api/events/{event_id}/orders')
# async def read_data2(
#     event_id: str,
#     response: Response,
#     search: str = Query(default=None, description="Search by name or email")
# ):
#     try:
#         async with engine.begin() as conn:
#             base_query = """
#             SELECT od.address as address, od.birthDate as birthDate,  
#             od.email AS email, od.gender as gender, od.id as id, 
#             od.location as location, od.NAME AS name, o.id as orderId, od.phoneNumber as phoneNumber, 
#             od.socialMedia as socialMedia, 
#             t.id as ticketId, t.name as ticketName, t.price as ticketPrice,
#             o.createdAt as orderCreatedAt,
#             tv.hash AS hash, tv.isScanned AS isVerified, tv.id as tvId, tv.updatedAt as verifiedAt,
#             ROW_NUMBER() OVER (PARTITION BY od.orderId ORDER BY od.NAME) AS ticketNum,
#             COUNT(*) OVER (PARTITION BY od.orderId) AS ticketCount
#             FROM TicketVerification AS tv
#             INNER JOIN orderDetails AS od ON tv.orderDetailId=od.id
#             INNER JOIN tickets AS t ON od.ticketId=t.id
#             INNER JOIN orders o ON od.orderId = o.id
#             WHERE t.eventId = :event_id and o.status = "SUCCESS"
#             """

#             params = {'event_id': event_id}
#             if search:
#                 base_query += " AND (LOWER(od.name) LIKE LOWER(:search) OR LOWER(od.email) LIKE LOWER(:search))"
#                 params['search'] = f"%{search}%"

#             base_query += " ORDER BY od.NAME"

#             result_proxy = await conn.execute(text(base_query), params)

#             data = result_proxy.fetchall()

#             formatted_data = []

#             for row in data:
#                 row_dict = dict(row)

#                 formatted_row = {
#                     "address": row_dict["address"],
#                     "name": row_dict["name"],
#                     "birthDate": row_dict["birthDate"],
#                     "email": row_dict["email"],
#                     "gender": row_dict["gender"],
#                     "id": row_dict["id"],
#                     "commiteeName": "",  # Placeholder since the field isn't in the query
#                     "orderId": row_dict["orderId"],
#                     "phoneNumber": row_dict["phoneNumber"],
#                     "socialMedia": row_dict["socialMedia"],
#                     "ticketId": row_dict["ticketId"],
#                     "verifiedAt": row_dict["verifiedAt"],
#                     "ticket": {
#                         "id": row_dict["ticketId"],
#                         "name": row_dict["ticketName"],
#                         "eventId": event_id,
#                         "price": row_dict["ticketPrice"]
#                     },
#                     "eventId": event_id,
#                     "orderCreatedAt": row_dict["orderCreatedAt"],
#                     "isScanned": bool(row_dict["isVerified"]),
#                     "hash": row_dict["hash"],
#                     "ticketCount": row_dict["ticketCount"],
#                     "ticketNum": row_dict["ticketNum"]
#                 }

#                 formatted_data.append(formatted_row)

#         return {
#             "status": "SUCCESS",
#             "data": formatted_data
#         }

#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "error": str(e),
#         }


# @ticket.get("/api/events/{event_id}")
# async def get_event_details2(event_id: str, response: Response):
#     try:
#         async with engine.connect() as conn:
#             # Query to fetch event details and associated tickets
#             event_query = """
#             SELECT e.id as eventId, e.name as eventName,
#                    t.id as ticketId, t.name as ticketName, t.price as ticketPrice
#             FROM events e
#             LEFT JOIN tickets t ON e.id = t.eventId
#             WHERE e.id = :event_id
#             """

#             result = await conn.execute(text(event_query), {"event_id": event_id})
#             rows = result.fetchall()

#             if not rows:
#                 response.status_code = 404
#                 return {"status": "NOT_FOUND", "message": "Event not found"}

#             # Extract event details
#             event_data = {
#                 "id": rows[0]["eventId"],
#                 "banner": '',  # Placeholder for banner, update if necessary
#                 "name": rows[0]["eventName"],
#                 "tickets": [
#                     {
#                         "id": row["ticketId"],
#                         "name": row["ticketName"],
#                         "eventId": event_id,
#                         "price": row["ticketPrice"]
#                     } for row in rows if row["ticketId"]
#                 ]
#             }

#         return {
#             "status": "SUCCESS",
#             "data": event_data
#         }

#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {
#             "status": "ERROR",
#             "message": str(e)}


# @ticket.put('/api/events/{event_id}/orders/{hash}')
# async def update_verification3(hash: str, event_id: str, request: Request, response: Response):
#     try:
#         # Ambil data dari body request
#         body = await request.json()
#         isVerify = body.get('isVerify')  # Mengambil nilai isVerify dari body

#         # Set zona waktu lokal (misalnya waktu Jakarta)
#         local_tz = pytz.timezone("Asia/Makassar")

#         async with engine.begin() as conn:
#             # Query untuk mengambil hanya isScanned dan hash
#             check_query = """
#                 SELECT tv.isScanned, tv.hash
#                 FROM TicketVerification AS tv
#                 INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
#                 INNER JOIN tickets AS t ON od.ticketId = t.id
#                 INNER JOIN orders o ON od.orderId = o.id
#                 WHERE tv.HASH = :hash AND t.eventId = :event_id AND o.status = "SUCCESS"
#             """

#             check_result = await conn.execute(text(check_query), {"hash": hash, "event_id": event_id})
#             row = check_result.fetchone()

#             if not row:
#                 # Kembalikan format error 404 dengan response yang lebih spesifik
#                 response.status_code = 404
#                 return {
#                     "success": False,
#                     "statusCode": 404,  # Ganti dengan pesan yang diinginkan
#                     "message": "Kartjis not found",
#                 }

#             # Mengambil nilai isScanned dan hash dari hasil query
#             verification_status = row[0]
#             ticket_hash = row[1]

#             # Jika isVerify True dan tiket sudah diverifikasi, kembalikan error 400
#             if isVerify and verification_status:
#                 response.status_code = 400  # Set status code 400
#                 return {
#                     "success": False,
#                     "statusCode": 400,
#                     "message": "Kartjis already used",
#                 }

#             # Jika isVerify False dan tiket sudah diverifikasi, ubah isScanned menjadi False
#             if not isVerify and verification_status:
#                 is_verified = 0  # Membatalkan verifikasi
#             else:
#                 is_verified = 1 if isVerify else 0  # Mengatur nilai isScanned sesuai isVerify

#             # Update verification status
#             query_update = """
#                 UPDATE TicketVerification AS tv
#                 INNER JOIN orderDetails AS od ON tv.orderDetailId = od.id
#                 INNER JOIN tickets AS t ON od.ticketId = t.id
#                 SET tv.isScanned = :is_verified, tv.updatedAt = :current_datetime
#                 WHERE tv.HASH = :hash AND t.eventId = :event_id
#             """

#             # Ambil waktu lokal saat ini
#             current_datetime = datetime.now(local_tz)

#             await conn.execute(text(query_update), {"hash": hash, "is_verified": is_verified, "current_datetime": current_datetime, "event_id": event_id})

#             # Construct data response
#             data = {
#                 "success": True,
#                 "statusCode": 200 if isVerify else 222,
#                 "message": "Success Verify Kartjis" if isVerify else "Success Unverify Kartjis",
#             }

#             return data

#     except HTTPException as http_error:
#         raise http_error  # Re-raise HTTPException to return the defined HTTP error response
#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "message": str(e),
#             "statusCode": 500,
#         }


# @ticket.post('/api/events/{event_id}/offline-transactions')
# async def ots2(request: dict, event_id: str, response: Response):
#     tickets = request.get("data", [])  # Mengambil array tiket dari key 'data'
#     async with engine.begin() as conn:
#         try:
#             for ticket in tickets:
#                 ticket_id = str(uuid.uuid4())
#                 customer_id = str(uuid.uuid4())
#                 order_id = str(uuid.uuid4())
#                 order_detail_id = str(uuid.uuid4())
#                 verification_id = str(uuid.uuid4())
#                 current_time = datetime.now()

#                 result = await conn.execute(
#                     text(
#                         "SELECT id FROM `tickets` WHERE `name` = :name and `eventId` = :eventId"
#                     ),
#                     {"name": ticket["ticket_name"], "eventId": event_id},
#                 )
#                 existing_ticket = result.fetchone()

#                 if existing_ticket:
#                     ticket_id = existing_ticket[0]
#                 else:
#                     await conn.execute(
#                         text("""
#                             INSERT INTO `tickets` (`id`, `name`, `price`, `eventId`, `stock`, `createdAt`, `updatedAt`, `adminFee`)
#                             VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, 0)
#                         """),
#                         {
#                             "id": ticket_id,
#                             "name": ticket["ticket_name"],
#                             "price": 0,
#                             "eventId": event_id,
#                             "stock": 100,
#                             "createdAt": current_time,
#                             "updatedAt": current_time,
#                         },
#                     )

#                 # Insert into `customers`
#                 await conn.execute(
#                     text("""
#                         INSERT INTO `customers` (`id`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `createdAt`, `updatedAt`)
#                         VALUES (:id, :name, :email, :birthDate, :phoneNumber, :gender, :createdAt, :updatedAt)
#                     """),
#                     {
#                         "id": customer_id,
#                         "name": ticket["customer_name"],
#                         "email": ticket["customer_email"],
#                         "birthDate": ticket["customer_birthdate"],
#                         "phoneNumber": ticket["customer_phone"],
#                         "gender": ticket["customer_gender"],
#                         "createdAt": current_time,
#                         "updatedAt": current_time,
#                     },
#                 )

#                 # Insert into `orders`
#                 await conn.execute(
#                     text("""
#                         INSERT INTO `orders` (`id`, `status`, `createdAt`, `updatedAt`, `customerId`, `eventId`)
#                         VALUES (:id, 'SUCCESS', :createdAt, :updatedAt, :customerId, :eventId)
#                     """),
#                     {
#                         "id": order_id,
#                         "createdAt": current_time,
#                         "updatedAt": current_time,
#                         "customerId": customer_id,
#                         "eventId": event_id,
#                     },
#                 )

#                 # Insert into `orderdetails`
#                 await conn.execute(
#                     text("""
#                         INSERT INTO `orderdetails` (`id`, `ticketId`, `quantity`, `orderId`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `address`, `socialMedia`, `location`, `commiteeName`)
#                         VALUES (:id, :ticketId, 1, :orderId, :name, :email, :birthDate, :phoneNumber, :gender, :address, :socialMedia, :location, :commiteeName)
#                     """),
#                     {
#                         "id": order_detail_id,
#                         "ticketId": ticket_id,
#                         "orderId": order_id,
#                         "name": ticket["customer_name"],
#                         "email": ticket["customer_email"],
#                         "birthDate": ticket["customer_birthdate"],
#                         "phoneNumber": ticket["customer_phone"],
#                         "gender": ticket["customer_gender"],
#                         "address": ticket["address"],
#                         "socialMedia": ticket["social_media"],
#                         "location": ticket["ticket_name"],
#                         "commiteeName": None,
#                     },
#                 )

#                 # Generate MD5 hash for ticket verification
#                 random_number = random.randint(1000, 9999)
#                 combined_string = f"{ticket['customer_email']}{
#                     order_detail_id}{current_time}{random_number}"
#                 hash_value = hashlib.md5(combined_string.encode()).hexdigest()

#                 await conn.execute(
#                     text("""
#                         INSERT INTO `ticketverification` (`id`, `hash`, `isScanned`, `createdAt`, `updatedAt`, `orderDetailId`)
#                         VALUES (:id, :hash, 1, :createdAt, :updatedAt, :orderDetailId)
#                     """),
#                     {
#                         "id": verification_id,
#                         "hash": hash_value,
#                         "createdAt": current_time,
#                         "updatedAt": current_time,
#                         "orderDetailId": order_detail_id,
#                     },
#                 )

#             return {
#                 "success": True,
#                 "message": "Tickets successfully created.",
#             }

#         except Exception as e:
#             print(e)
#             response.status_code = 500  # Internal Server Error
#             return {
#                 "success": False,
#                 "error": str(e),
#             }


# # Pydantic model untuk request body
# class TicketBase(BaseModel):
#     name: str
#     price: float
#     stock: int
#     eventId: str

# # Insert Ticket


# @ticket.post('/api/tickets')
# async def create_ticket(ticket_data: TicketBase, response: Response):
#     try:
#         async with engine.begin() as conn:
#             insert_query = """
#             INSERT INTO tickets (name, price, stock, adminFee, eventId, id, updatedAt)
#             VALUES (:name, :price, :stock, :adminFee, :eventId, :id, :updatedAt)
#             """
#             params = {
#                 "name": ticket_data.name,
#                 "price": ticket_data.price,
#                 "stock": ticket_data.stock,
#                 "adminFee": 10000,
#                 "eventId": ticket_data.eventId,
#                 "id": uuid.uuid4(),
#                 "updatedAt": datetime.now(),
#             }

#             await conn.execute(text(insert_query), params)

#         return {"status": "SUCCESS", "message": "Ticket created successfully"}
#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {"success": False, "error": str(e)}

# # Update Ticket


# @ticket.put('/api/tickets/{ticket_id}')
# async def update_ticket(ticket_id: str, ticket_data: TicketBase, response: Response):
#     try:
#         async with engine.begin() as conn:
#             update_query = """
#             UPDATE tickets
#             SET name = :name, price = :price, stock = :stock
#             WHERE id = :ticket_id
#             """
#             params = {
#                 "name": ticket_data.name,
#                 "price": ticket_data.price,
#                 "stock": ticket_data.stock,

#             }

#             result = await conn.execute(text(update_query), params)

#             if result.rowcount == 0:
#                 response.status_code = 404  # Not Found
#                 return {"success": False, "message": "Ticket not found"}

#         return {"status": "SUCCESS", "message": "Ticket updated successfully"}
#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {"success": False, "error": str(e)}


# class LoginData(BaseModel):
#     username: str
#     password: str


# @ticket.post('/api/login')
# async def login(login_data: LoginData, response: Response):
#     try:
#         async with auth_engine.begin() as conn:
#             # Fetch user by username
#             fetch_query = """
#             SELECT id, username, password, isAdmin, eventId, name, email
#             FROM users WHERE username = :username
#             """
#             result = await conn.execute(text(fetch_query), {"username": login_data.username})
#             user = result.fetchone()

#             if not user:
#                 raise HTTPException(status_code=404, detail="User not found")

#             # Check password
#             stored_password = user.password
#             if not bcrypt.checkpw(login_data.password.encode('utf-8'), stored_password.encode('utf-8')):
#                 raise HTTPException(
#                     status_code=401, detail="Invalid credentials")

#             # Successful login response
#             return {
#                 "status": "SUCCESS",
#                 "message": "Login successful",
#                 "data": {
#                     "id": user.id,
#                     "username": user.username,
#                     "isAdmin": user.isAdmin,
#                     "eventId": user.eventId,
#                     "name": user.name,
#                     "email": user.email,
#                 }
#             }

#     except HTTPException as e:
#         response.status_code = e.status_code
#         return {"success": False, "error": e.detail}
#     except Exception as e:
#         print(e)
#         response.status_code = 500
#         return {"success": False, "error": "An internal server error occurred"}


# @ticket.get('/api/event-organizers/{eventId}')
# async def get_event_organizers(eventId: str, response: Response):
#     try:
#         async with auth_engine.begin() as conn:
#             # Query untuk mendapatkan semua event organizers berdasarkan eventId
#             fetch_query = """
#             SELECT eo.username, eo.name, eo.email, eo.isAdmin
#             FROM users eo
#             WHERE eo.eventId = :eventId
#             """
#             result = await conn.execute(text(fetch_query), {"eventId": eventId})
#             event_organizers = result.fetchall()

#             if not event_organizers:
#                 raise HTTPException(
#                     status_code=404, detail="No Event Organizers found for this event"
#                 )

#             # Mengubah hasil query menjadi list of dictionaries
#             organizers_list = [
#                 {
#                     "username": organizer.username,
#                     "name": organizer.name,
#                     "email": organizer.email,  # Properti phone ditambahkan
#                     "isAdmin": organizer.isAdmin,
#                 }
#                 for organizer in event_organizers
#             ]

#             # Mengembalikan response sukses
#             return {
#                 "status": "SUCCESS",
#                 "message": f"{len(organizers_list)} Event Organizer(s) fetched successfully",
#                 "data": organizers_list,
#             }

#     except HTTPException as e:
#         response.status_code = e.status_code
#         return {"success": False, "error": e.detail}
#     except Exception as e:
#         print(f"Error fetching event organizers for eventId {
#               eventId}: {e}")  # Logging error
#         response.status_code = 500
#         return {"success": False, "error": "An internal server error occurred"}


# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)
