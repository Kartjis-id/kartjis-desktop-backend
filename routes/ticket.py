# from typing import Optional
# from fastapi import HTTPException, Request, Response
# from sqlalchemy.ext.asyncio import create_async_engine
# import jwt
# import hashlib
# import hashlib
# import pytz
# import random
# import uuid
# from fastapi import APIRouter, Query, Response, HTTPException, Request
# from pydantic import BaseModel
# from sqlalchemy import text
# from config.db import online_engine, online_engine2
# from datetime import datetime, timedelta
# import uvicorn
# import bcrypt
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from fastapi import Security, Depends

# security = HTTPBearer()
# SECRET_KEY = "a_very_secret_key_1234567890!@#$%^&*()"
# ALGORITHM = "HS256"


# ticket = APIRouter()


# @ticket.get("/")
# async def root():
#     return {"message": "CORS sudah aktif!"}

# # LOGIN


# class LoginData(BaseModel):
#     username: str
#     password: str

# # Fungsi untuk membuat token JWT


# def create_token(user_data: dict):
#     expiration = datetime.utcnow() + timedelta(days=7)
#     payload = {**user_data, "exp": expiration}
#     return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# # Fungsi untuk mengambil user dari token


# async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
#     try:
#         token = credentials.credentials
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload
#     except jwt.ExpiredSignatureError:
#         raise HTTPException(status_code=401, detail="Token expired")
#     except jwt.InvalidTokenError:
#         raise HTTPException(status_code=401, detail="Invalid token")

# # Endpoint login yang menghasilkan token


# @ticket.post('/api/users/login')
# async def login(login_data: LoginData, response: Response):
#     try:
#         if (login_data.username == 'kakimenapak'):
#             return await loginOld(login_data, response)

#         async with online_engine.begin() as conn:
#             fetch_query = f"""
#             select u.id, u.username, u.roles='EVENT_ORGANIZER' as "isAdmin", eo.event_id "eventId", u."name", u.email, u.password  from users u
#             join event_organizers eo on eo.username  = u.username 
#             WHERE u.username = :username
#             """
#             result = await conn.execute(text(fetch_query), {"username": login_data.username})
#             user = result.fetchone()

#             if not user:
#                 raise HTTPException(status_code=404, detail="User not found")

#             hashed_password = user.password
#             if hashed_password.startswith("{bcrypt}"):
#                 hashed_password = hashed_password.replace("{bcrypt}", "", 1)

#             if not bcrypt.checkpw(login_data.password.encode('utf-8'), hashed_password.encode('utf-8')):
#                 raise HTTPException(
#                     status_code=401, detail="Invalid credentials")

#             # Buat token JWT yang menyimpan eventId
#             token = create_token({
#                 "username": user.username,
#                 "eventId": user.eventId
#             })

#             return {
#                 "status": "SUCCESS",
#                 "message": "Login successful",
#                 "data": {
#                     "userId": user.id,
#                     "username": user.username,
#                     "isAdmin": user.isAdmin == 1,
#                     "eventId": user.eventId,
#                     "name": user.name,
#                     "email": user.email,
#                     "token": token
#                 }
#             }
#     except HTTPException as e:
#         response.status_code = e.status_code
#         return {"success": False, "error": e.detail}
#     except Exception as e:
#         print(e)
#         response.status_code = 500
#         return {"success": False, "error": "An internal server error occurred"}


# # GEt ORDERS
# @ticket.get('/api/events/orders')
# async def read_orders(
#     response: Response,
#     search: str = Query(default=None, description="Search by name or email"),
#     user: dict = Depends(get_current_user)  # Ambil user dari token
# ):

#     if (user["username"] == "kakimenapak"):
#         return await read_orders_old(response=response, search=search, user=user)

#     try:
#         event_id = user["eventId"]  # Ambil eventId dari token
#         async with online_engine.begin() as conn:
#             base_query = f"""
#             SELECT 
#                 o.id AS "id",
#                 t.id AS "orderId",
#                 tv.id AS "tvId",
#                 o.order_status_id,
#                 tc.name AS "ticketName",
#                 tc.price AS "ticketPrice",
#                 t2.created_at AS "orderCreatedAt",
#                 u.address, 
#                 tv.hash AS "hash",
#                 u2.name AS "verifiedByName",
#                 CASE
#                     WHEN tv.scanned_at IS NULL THEN FALSE
#                     WHEN tv.un_scanned_at IS NOT NULL AND tv.un_scanned_at > tv.scanned_at THEN FALSE
#                     ELSE TRUE
#                 END AS "isVerified",
#                 tv.scanned_at AS "verifiedAt",
#                 tv.un_scanned_at AS "unverifiedAt",
#                 tv.scanned_by AS "verifiedBy",
#                 tv.un_scanned_by AS "unverifiedBy",
#                 -- Subquery untuk mendapatkan ticketNum
#                 ROW_NUMBER() OVER (PARTITION BY t.order_id ORDER BY t.id) AS "ticketNum",
#                 -- Subquery untuk mendapatkan ticketCount
#                 COUNT(*) OVER (PARTITION BY t.order_id) AS "ticketCount",
#                 t.customer_email AS "email",
#                 t.customer_name AS "name",
#                 t.customer_gender AS "gender",
#                 t.customer_phone_number AS "phoneNumber",
#                 tc.id AS "ticketId"
#             FROM orders o
#             JOIN tickets t ON t.order_id = o.id
#             JOIN transactions t2 ON t2.order_id = o.id  
#             LEFT JOIN ticket_verification tv ON tv.ticket_code = t.code 
#             LEFT JOIN users u2 ON u2.id = tv.scanned_by
#             LEFT JOIN ticket_categories tc ON tc.id = t.ticket_category_id
#             LEFT JOIN users u ON u.email = o.customer_id 
#             LEFT JOIN ticket_custom_fields tcf ON tcf.ticket_id = t.id
#             WHERE t.event_id = :event_id
#             AND o.order_status_id = 1
#             """

#             params = {'event_id': event_id}
#             if search:
#                 base_query += " AND (LOWER(t.customer_name) LIKE LOWER(:search) OR LOWER(t.customer_email) LIKE LOWER(:search))"
#                 params['search'] = f"%{search}%"

#             base_query += " ORDER BY t.customer_name"

#             result_proxy = await conn.execute(text(base_query), params)
#             data = result_proxy.fetchall()

#             formatted_data = []
#             for row in data:
#                 row_dict = dict(row)
#                 formatted_row = {
#                     "address": "-",
#                     "name": row_dict["name"],
#                     "birthDate": "",
#                     "email": row_dict["email"],
#                     "gender": row_dict["gender"],
#                     "id": row_dict["id"],
#                     "commiteeName": "",
#                     "orderId": row_dict["orderId"],
#                     "phoneNumber": row_dict["phoneNumber"],
#                     "socialMedia": '',
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
#                     "ticketCount": row_dict.get("ticketCount", 0),
#                     "ticketNum": row_dict.get("ticketNum", 0),
#                     "verifiedBy": {
#                         "id": row_dict.get("verifiedById"),
#                         "name": row_dict.get("verifiedByName"),
#                     },
#                     "isHide": False
#                 }

#                 formatted_data.append(formatted_row)

#         return {
#             "status": "SUCCESS",
#             "data": formatted_data
#         }

#     except Exception as e:
#         print(e)
#         response.status_code = 500
#         return {"success": False, "error": str(e)}


# @ticket.get('/api/events/ticket-type-summary')
# async def ticket_type_summary(
#     response: Response,
#     user: dict = Depends(get_current_user)
# ):

#     if (user["username"] == "kakimenapak"):
#         return await ticket_type_summary_old(response=response, user=user)

#     try:
#         event_id = user["eventId"]
#         async with online_engine.begin() as conn:

#             summary_query = """
#                 SELECT
#                     tc.name AS ticket_type_name,
#                     COALESCE(COUNT(od.id), 0) AS total_sold,
#                     COALESCE(SUM(CASE WHEN od.customer_gender = 'MALE' THEN 1 ELSE 0 END), 0) AS male_count,
#                     COALESCE(SUM(CASE WHEN od.customer_gender = 'FEMALE' THEN 1 ELSE 0 END), 0) AS female_count,
#                     tc.price AS ticket_price,
#                     tc.stock AS stock,
#                     e.admin_fee AS admin_fee,
#                     COALESCE(tc.price * COUNT(od.id), 0) AS total_price,
#                     COALESCE((tc.price * COUNT(od.id)) + (COUNT(od.id) * e.admin_fee), 0) AS revenue_after_admin_fee,
#                     COALESCE(SUM(CASE WHEN tv.scanned_at IS NOT NULL THEN 1 ELSE 0 END), 0) AS verified_count,
#                     COALESCE(SUM(CASE WHEN tv.scanned_at IS NULL THEN 1 ELSE 0 END), 0) AS unverified_count
#                 FROM ticket_categories AS tc
#                 LEFT JOIN tickets AS od ON od.ticket_category_id = tc.id
#                 LEFT JOIN orders AS o ON od.order_id = o.id
#                 LEFT JOIN ticket_verification tv ON tv.ticket_code = od.code 
#                 LEFT JOIN events e ON e.id = od.event_id 
#                 WHERE od.event_id = :event_id AND order_status_id = 1
#                 GROUP BY tc.id, tc.name, tc.price, tc.stock, e.admin_fee
#                 ORDER BY tc.name
#                 """

#             params = {'event_id': event_id}
#             result_proxy = await conn.execute(text(summary_query), params)
#             data = result_proxy.fetchall()

#             ticket_counts = [
#                 {
#                     "ticketTypeName": row["ticket_type_name"] or "",
#                     "totalSold": row["total_sold"] or 0,
#                     "maleCount": row["male_count"] or 0,
#                     "femaleCount": row["female_count"] or 0,
#                     "ticketPrice": row["ticket_price"] or 0,
#                     "totalPrice": row["total_price"] or 0,
#                     "adminFee": row["admin_fee"] or 0,
#                     "stock": row["stock"] or 0,
#                     "revenueAfterAdminFee": row["revenue_after_admin_fee"] or 0,
#                     "verifiedCount": row["verified_count"] or 0,
#                     "unverifiedCount": row["unverified_count"] or 0,
#                 }
#                 for row in data
#             ]

#             # Gunakan ticket_counts agar semua value sudah pasti ada dan tidak None
#             total_tickets = sum(row["totalSold"] for row in ticket_counts)
#             total_verified = sum(row["verifiedCount"] for row in ticket_counts)
#             total_unverified = sum(row["unverifiedCount"]
#                                    for row in ticket_counts)

#             ticket_summary = {
#                 "total": total_tickets,
#                 "verifiedCount": total_verified,
#                 "unverifiedCount": total_unverified
#             }

#             return {
#                 "status": "SUCCESS",
#                 "data": {
#                     "ticketSummary": ticket_summary,
#                     "ticketCounts": ticket_counts
#                 }
#             }

#     except Exception as e:
#         print("❌ Error:", e)
#         response.status_code = 500
#         return {
#             "status": "ERROR",
#             "error": str(e)
#         }


# # GET EVENTs
# @ticket.get("/api/events")
# async def get_event_details2(response: Response, user: dict = Depends(get_current_user)):
#     if (user["username"] == "kakimenapak"):
#         print("old")
#         return await get_event_details_old(response=response, user=user)
#     event_id = user["eventId"]
#     try:
#         async with online_engine.connect() as conn:
#             event_query = f"""
#             select e.id as "eventId", e."name" as "eventName", tc.id as "ticketId", tc."name" as "ticketName", tc.price as "ticketPrice"
#             from events e
#             left join ticket_categories tc on tc.event_id = e.id
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
#                 "banner": '',
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


# @ticket.delete('/api/orders/{id}')
# async def delete_order(id: str, response: Response):
#     try:
#         async with online_engine.begin() as conn:
#             # Delete query
#             delete_query = f"DELETE FROM orders WHERE id = :id"
#             result = await conn.execute(text(delete_query), {'id': id})

#             # Check if any row was deleted
#             if result.rowcount == 0:
#                 raise HTTPException(status_code=404, detail="Order not found")

#         return {"status": "SUCCESS", "data": f"Order with ID {id} deleted successfully"}

#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {"status": "ERROR", "error": str(e)}


# # GET EO
# @ticket.get('/api/event-organizers')
# async def get_event_organizers(response: Response, user: dict = Depends(get_current_user)):
#     if (user["username"] == "kakimenapak"):
#         return await get_event_organizers_old(response=response, user=user)

#     try:
#         eventId = user["eventId"]
#         async with online_engine.begin() as conn:
#             # Query untuk mendapatkan semua event organizers berdasarkan eventId
#             fetch_query = f"""
#             SELECT
#                 eo.id as id,
#                 eo.username as username,
#                 eo.name as name,
#                 eo.email as email,
#                 eo.roles as roles,
#                 COUNT(tv.id) AS "totalVerification"
#             FROM users eo
#             left JOIN ticket_verification as tv
#                 ON tv.scanned_by = eo.id
#             left join event_organizers eo2 on eo2.username  = eo.username 
#             WHERE eo2.event_id = :eventId
#             GROUP BY eo.id, eo.username, eo.name, eo.email, eo.roles
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
#                     "id": organizer.id,
#                     "username": organizer.username,
#                     "name": organizer.name,
#                     "email": organizer.email,  # Properti phone ditambahkan
#                     "isAdmin": organizer.roles == 'EVENT_ORGANIZER',
#                     "totalVerification": organizer.totalVerification,
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
#         response.status_code = 500
#         return {"success": False, "error": "An internal server error occurred"}


# # ADD TICKET
# class TicketBase(BaseModel):
#     name: str
#     price: float
#     stock: int
#     eventId: str


# @ticket.post('/api/tickets')
# async def create_ticket(ticket_data: TicketBase, response: Response, user: dict = Depends(get_current_user)):
#     try:
#         eventId = user["eventId"]
#         async with online_engine.begin() as conn:
#             insert_query = f"""
#             INSERT INTO {db1}.tickets (name, price, stock, adminFee, eventId, id, updatedAt)
#             VALUES (:name, :price, :stock, :adminFee, :eventId, :id, :updatedAt)
#             """
#             params = {
#                 "name": ticket_data.name,
#                 "price": ticket_data.price,
#                 "stock": ticket_data.stock,
#                 "adminFee": 10000,
#                 "eventId": eventId,
#                 "id": uuid.uuid4(),
#                 "updatedAt": datetime.now(),
#             }

#             await conn.execute(text(insert_query), params)

#         return {"status": "SUCCESS", "message": "Ticket created successfully"}
#     except Exception as e:
#         print(e)
#         response.status_code = 500  # Internal Server Error
#         return {"success": False, "error": str(e)}

# # UODATE TICKEt


# @ticket.put('/api/tickets/{ticket_id}')
# async def update_ticket(ticket_id: str, ticket_data: TicketBase, response: Response):
#     try:
#         async with online_engine.begin() as conn:
#             update_query = f"""
#             UPDATE {db1}.tickets
#             SET name = :name, price = :price, stock = :stock
#             WHERE id = :ticket_id
#             """
#             params = {
#                 "name": ticket_data.name,
#                 "price": ticket_data.price,
#                 "stock": ticket_data.stock,
#                 "ticket_id": ticket_id,
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

# # VERIFY


# @ticket.put('/api/events/orders/{hash}')
# async def update_verification(hash: str,  request: Request, response: Response, user: dict = Depends(get_current_user)):
#     if (user["username"] == "kakimenapak"):
#         return await update_verification_old(hash)

#     try:
#         # Ambil data dari body request
#         event_id = user["eventId"]
#         body = await request.json()
#         is_verify = body.get('isVerify')  # Mengambil nilai isVerify dari body
#         verified_by = body.get('verifiedBy')  # ID user yang memverifikasi

#         # Validasi body request
#         if is_verify is None or not isinstance(is_verify, bool):
#             response.status_code = 400  # Bad Request

#             return {
#                 "success": False,
#                 "status": 'Failed',
#                 "code": '',
#                 "data": {
#                     "code": "KARTJIS.44",
#                     "detail": "'isVerify' harus berupa boolean."
#                 },
#             }

#         if not verified_by:
#             response.status_code = 400  # Bad Request

#             return {
#                 "success": False,
#                 "status": 'Failed',
#                 "code": '',
#                 "data": {
#                     "code": "KARTJIS.44",
#                     "detail": "'verifiedBy' tidak boleh kosong."
#                 },
#             }

#         # Set zona waktu lokal (misalnya waktu Makassar)
#         local_tz = pytz.timezone("Asia/Makassar")
#         aware_datetime = datetime.now(local_tz)

#         # Convert to naive datetime, tapi dalam zona waktu Asia/Makassar
#         current_datetime = aware_datetime.replace(tzinfo=None)

#         async with online_engine.begin() as conn:
#             # Query untuk memeriksa status tiket
#             check_query = f"""
#                 SELECT 
#                     o.id AS "id",
#                     t.id AS "orderId",
#                     tv.id AS "tvId",
#                     o.order_status_id,
#                     tc.name AS "ticketName",
#                     tc.price AS "ticketPrice",
#                     t2.created_at AS "orderCreatedAt",
#                     u.address, 
#                     tv.hash AS "hash",
#                     u2.name as "verifiedByName",
#                     tv.scanned_at IS NOT NULL AS "isVerified",
#                     tv.scanned_at AS "verifiedAt",
#                     tv.un_scanned_at AS "unverifiedAt",
#                     tv.scanned_by AS "verifiedBy",
#                     tv.un_scanned_by AS "unverifiedBy",
#                     ROW_NUMBER() OVER (PARTITION BY t.order_id ORDER BY t.id) AS "ticketNum",
#                     COALESCE(COUNT(*) OVER (PARTITION BY t.order_id), 0) AS "ticketCount",
#                     t.customer_email AS "email",
#                     t.customer_name AS "name",
#                     t.customer_gender AS "gender",
#                     t.customer_phone_number AS "phoneNumber",
#                     tc.id AS "ticketId"
#                 FROM orders o
#                 JOIN tickets t ON t.order_id = o.id
#                 JOIN transactions t2 ON t2.order_id = o.id  
#                 LEFT JOIN ticket_verification tv ON tv.ticket_code = t.code 
#                 LEFT JOIN users u2 on u2.id = tv.scanned_by
#                 LEFT JOIN ticket_categories tc ON tc.id = t.ticket_category_id
#                 LEFT JOIN users u ON u.email = o.customer_id 
#                 LEFT JOIN ticket_custom_fields tcf ON tcf.ticket_id = t.id
#                                 WHERE (tv.hash = :hash || tv.ticket_code = :hash) and t.event_id = :event_id and order_status_id = 1
#                 ;
#             """

#             check_result = await conn.execute(text(check_query), {"hash": hash.lower(), "event_id": event_id})
#             row_dict = check_result.fetchone()

#             if not row_dict:
#                 response.status_code = 200  # Not Found
#                 return {
#                     "success": False,
#                     "status": 'Failed',
#                     "code": '',
#                     "data": {
#                         "code": "KARTJIS.40",
#                         "detail": "Kartjis tidak ditemukan."
#                     },
#                 }

#             # Ambil status verifikasi saat ini
#             formatted_row = {
#                 "address": "",
#                 "name": row_dict["name"],
#                 "birthDate": "",
#                 "email": row_dict["email"],
#                 "gender": row_dict["gender"],
#                 "id": row_dict["id"],
#                 "commiteeName": "",
#                 "orderId": row_dict["orderId"],
#                 "phoneNumber": row_dict["phoneNumber"],
#                 "socialMedia": '',
#                 "ticketId": row_dict["ticketId"],
#                 "verifiedAt": row_dict["verifiedAt"],
#                 "ticket": {
#                     "id": row_dict["ticketId"],
#                     "name": row_dict["ticketName"],
#                     "eventId": event_id,
#                     "price": row_dict["ticketPrice"]
#                 },
#                 "eventId": event_id,
#                 "orderCreatedAt": row_dict["orderCreatedAt"],
#                 "isScanned": bool(row_dict["isVerified"]),
#                 "hash": row_dict["hash"],
#                 "ticketCount": row_dict["ticketCount"],
#                 "ticketNum": row_dict["ticketNum"],
#                 "verifiedBy": {
#                     "id": row_dict["verifiedBy"],
#                     "name": row_dict["verifiedByName"],
#                 },
#                 "isHide": False
#             }

#             if is_verify and bool(row_dict["isVerified"]):
#                 response.status_code = 200  # Bad Request
#                 return {
#                     "success": False,
#                     "status": 'Failed',
#                     "code": '',
#                     "data": {
#                         "code": "KARTJIS.41",
#                         "detail": "Kartjis sudah diverifikasi.",
#                         "orderDetail": formatted_row,
#                     }
#                 }

#             # Update status verifikasi
#             query_update = f"""
#                 UPDATE ticket_verification AS tv
#                 SET
#                     scanned_at = :scanned_at,
#                     scanned_by = :scanned_by,
#                     un_scanned_at = :un_scanned_at,
#                     un_scanned_by = :un_scanned_by
#                 FROM tickets t
#                 JOIN orders o ON o.id = t.order_id
#                 WHERE tv.ticket_code = t.code
#                 AND tv.hash = :hash or tv.ticket_code = :hash
#                 AND t.event_id = :event_id;
#             """

#             await conn.execute(text(query_update), {
#                 "scanned_at": current_datetime if is_verify else None,
#                 "un_scanned_at": None if is_verify else current_datetime,
#                 "scanned_by": verified_by if is_verify else None,
#                 "un_scanned_by": None if is_verify else verified_by,
#                 "hash": hash.lower(),
#                 "event_id": event_id,
#             })

#             query_user = f"""
#                     select u.name from users u where id = :id"""
#             check_user = await conn.execute(text(query_user), {"id": verified_by})
#             row_dict2 = check_user.fetchone()

#             # Response sukses

#             formatted_row['isScanned'] = True if is_verify else False
#             formatted_row['verifiedAt'] = current_datetime
#             formatted_row['verifiedBy'] = {
#                 "id": verified_by,
#                 "name": row_dict2["name"],
#             } if is_verify else {
#                 "id": verified_by,
#                 "name": row_dict2["name"],
#             }

#         return {
#             "success": True,
#             "status": 'SUCCEss',
#             "code": '',
#             "data": {
#                 "code": 'KARTJIS.21' if is_verify else "KARTJIS.20",
#                 "detail": "Berhasil memverifikasi Kartjis." if is_verify else "Berhasil membatalkan verifikasi Kartjis.",
#                 "orderDetail": formatted_row,
#             },
#         }

#     except HTTPException as http_error:
#         # Tangani HTTPException
#         raise http_error
#     except Exception as e:
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "status": 'Failed',
#             "code": '',
#                     "data": {
#                         "code": "KARTJIS.50",
#                         "detail": "Terjadi kesalahan internal server."
#                     }
#         },


# # Add OTS
# @ticket.post('/api/events/offline-transactions')
# async def ots2(request: dict, response: Response,  user: dict = Depends(get_current_user)):
#     tickets = request.get("data", [])
#     event_id = user['eventId']
#     ordal = request.get('ordal', False)

#     async with online_engine.begin() as conn:
#         try:
#             if len(tickets) <= 0:
#                 return
#             order_id = str(uuid.uuid4())
#             current_time = datetime(
#                 year=2025, month=1, day=19) if ordal else datetime.now()
#             customer_id = str(uuid.uuid4())
#             ticket1 = tickets[0]

#             await conn.execute(
#                 text(f"""INSERT INTO {db1}.customers (`id`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `createdAt`, `updatedAt`) VALUES (:id, :name, :email, :birthDate, :phoneNumber, :gender, :createdAt, :updatedAt)"""),
#                 {
#                     "id": customer_id,
#                     "name": ticket1["customer_name"],
#                     "email": ticket1["customer_email"],
#                     "birthDate": ticket1["customer_birthdate"],
#                     "phoneNumber": ticket1["customer_phone"],
#                     "gender": ticket1["customer_gender"],
#                     "createdAt": current_time,
#                     "updatedAt": current_time,
#                     "address": '',
#                 },
#             )

#             # Insert into `orders`
#             await conn.execute(
#                 text(f"""
#                     INSERT INTO {db1}.orders (`id`, `status`, `createdAt`, `updatedAt`, `customerId`, `eventId`)
#                     VALUES (:id, 'SUCCESS', :createdAt, :updatedAt, :customerId, :eventId)
#                 """),
#                 {
#                     "id": order_id,
#                     "createdAt": current_time,
#                     "updatedAt": current_time,
#                     "eventId": event_id,
#                     "customerId": customer_id
#                 },
#             )

#             # Insert into `customers`

#             for ticket in tickets:
#                 ticket_id = ticket["ticket_id"],
#                 order_detail_id = str(uuid.uuid4())
#                 verification_id = str(uuid.uuid4())

#                 result = await conn.execute(
#                     text(
#                         f"SELECT id FROM {db1}.tickets WHERE `id` = :id and `eventId` = :eventId"
#                     ),
#                     {"id": ticket_id, "eventId": event_id},
#                 )
#                 existing_ticket = result.fetchone()

#                 if existing_ticket:
#                     ticket_id = existing_ticket[0]
#                 else:
#                     await conn.execute(
#                         text(f"""
#                             INSERT INTO {db1}.tickets (`id`, `name`, `price`, `eventId`, `stock`, `createdAt`, `updatedAt`, `adminFee`)
#                             VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, 0)
#                         """),
#                         {
#                             "id": ticket_id,
#                             "name": 'OTS',
#                             "price": 0,
#                             "eventId": event_id,
#                             "stock": 100,
#                             "createdAt": current_time,
#                             "updatedAt": current_time,
#                         },
#                     )

#                 # Insert into `orderdetails`
#                 await conn.execute(
#                     text(f"""
#                         INSERT INTO {db1}.orderDetails (`id`, `ticketId`, `quantity`, `orderId`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `address`, `socialMedia`, `location`, `commiteeName`)
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
#                         "location": '666' if ordal else None,
#                         "commiteeName": None,
#                     },
#                 )

#                 # Generate MD5 hash for ticket verification
#                 random_number = random.randint(1000, 9999)
#                 combined_string = f"{ticket['customer_email']}{
#                     order_detail_id}{current_time}{random_number}"
#                 hash_value = hashlib.md5(combined_string.encode()).hexdigest()

#                 await conn.execute(
#                     text(f"""
#                         INSERT INTO {db1}.TicketVerification (`id`, `hash`, `isScanned`, `createdAt`, `updatedAt`, `orderDetailId`)
#                         VALUES (:id, :hash, :isScanned, :createdAt, :updatedAt, :orderDetailId)
#                     """),
#                     {
#                         "id": verification_id,
#                         "hash": hash_value,
#                         "isScanned": 0 if ordal else 1,
#                         "createdAt": current_time,
#                         "updatedAt": current_time,
#                         "orderDetailId": order_detail_id,
#                     },
#                 )

#             return {
#                 "success": True,
#                 "data": "Tickets successfully created.",
#             }

#         except Exception as e:
#             print(e)
#             response.status_code = 500  # Internal Server Error
#             return {
#                 "success": False,
#                 "error": str(e),
#             }

# # Bom verification


# @ticket.get('/api/events/orders2')
# async def read_orders2(
#     response: Response,
#     search: Optional[str] = Query(None, description="Search by name or email"),
#     ticket_type: Optional[str] = Query(
#         None, description="Filter by ticket type"),
#     verified: Optional[bool] = Query(
#         None, description="Filter by verification status (true/false)"),
#     page: int = Query(1, ge=1, description="Page number"),
#     page_size: int = Query(
#         50, ge=1, le=100, description="Number of results per page"),
#     user: dict = Depends(get_current_user),
# ):

#     if (user["username"] == "kakimenapak"):
#         return await read_orders2(
#             response=response,
#             search=search,
#             ticket_type=ticket_type,
#             verified=verified,
#             page=page,
#             page_size=page_size,
#             user=user
#         )
#     try:
#         event_id = user["eventId"]
#         offset = (page - 1) * page_size

#         async with online_engine.begin() as conn:
#             base_query = text(f"""
# SELECT 
#                 o.id AS "id",
#                 t.id AS "orderId",
#                 tv.id AS "tvId",
#                 o.order_status_id,
#                 tc.name AS "ticketName",
#                 tc.price AS "ticketPrice",
#                 t2.created_at AS "orderCreatedAt",
#                 u.address, 
#                 tv.hash AS "hash",
#                 u2.name AS "verifiedByName",
#                 CASE
#                     WHEN tv.scanned_at IS NULL THEN FALSE
#                     WHEN tv.un_scanned_at IS NOT NULL AND tv.un_scanned_at > tv.scanned_at THEN FALSE
#                     ELSE TRUE
#                 END AS "isVerified",
#                 tv.scanned_at AS "verifiedAt",
#                 tv.un_scanned_at AS "unverifiedAt",
#                 tv.scanned_by AS "verifiedById",
#                 tv.un_scanned_by AS "unverifiedBy",
#                 -- Subquery untuk mendapatkan ticketNum
#                 ROW_NUMBER() OVER (PARTITION BY t.order_id ORDER BY t.id) AS "ticketNum",
#                 -- Subquery untuk mendapatkan ticketCount
#                 COUNT(*) OVER (PARTITION BY t.order_id) AS "ticketCount",
#                 t.customer_email AS "email",
#                 t.customer_name AS "name",
#                 t.customer_gender AS "gender",
#                 t.customer_phone_number AS "phoneNumber",
#                 tc.id AS "ticketId"
#             FROM orders o
#             JOIN tickets t ON t.order_id = o.id
#             JOIN transactions t2 ON t2.order_id = o.id  
#             LEFT JOIN ticket_verification tv ON tv.ticket_code = t.code 
#             LEFT JOIN users u2 ON u2.id = tv.scanned_by
#             LEFT JOIN ticket_categories tc ON tc.id = t.ticket_category_id
#             LEFT JOIN users u ON u.email = o.customer_id 
#             LEFT JOIN ticket_custom_fields tcf ON tcf.ticket_id = t.id
#             WHERE t.event_id = :event_id
#             AND o.order_status_id = 1

#             """)

#             count_query = text(f"""
#             SELECT COUNT(*)
#             FROM orders o
#             right JOIN tickets t ON t.order_id = o.id
#             JOIN ticket_categories tc ON tc.id = t.ticket_category_id
#             JOIN ticket_verification tv ON tv.ticket_code = t.code
#             WHERE t.event_id = :event_id
#             AND o.order_status_id = 1
#             """)

#             params = {'event_id': event_id}

#             if search:
#                 base_query = text(str(
#                     base_query) + " AND (LOWER(t.customer_name) LIKE LOWER(:search) OR LOWER(t.customer_email) LIKE LOWER(:search))")
#                 count_query = text(str(
#                     count_query) + " AND (LOWER(t.customer_name) LIKE LOWER(:search) OR LOWER(t.customer_email) LIKE LOWER(:search))")
#                 params['search'] = f"%{search}%"

#             if ticket_type:
#                 base_query = text(str(base_query) +
#                                   " AND tc.name = :ticket_type")
#                 count_query = text(str(count_query) +
#                                    " AND tc.name = :ticket_type")
#                 params['ticket_type'] = ticket_type

#             if verified is not None:
#                 base_query = text(str(
#                     base_query) + (" AND tv.scanned_at is not null" if verified else " AND tv.scanned_at is null"))
#                 count_query = text(str(
#                     count_query) + (" AND tv.scanned_at is not null" if verified else " AND tv.scanned_at is null"))

#                 params['verified'] = 1 if verified else 0

#             if verified is False:
#                 order_by_clause = " ORDER BY t.customer_name"
#             elif verified is True:
#                 order_by_clause = " ORDER BY tv.scanned_at IS NULL DESC"
#             else:
#                 order_by_clause = " ORDER BY t2.created_at DESC"

#             base_query = text(str(base_query) + order_by_clause +
#                               " LIMIT :page_size OFFSET :offset")
#             params.update({'page_size': page_size, 'offset': offset})

#             # Execute queries
#             result_proxy = await conn.execute(base_query, params)
#             data = result_proxy.mappings().all()

#             count_result = await conn.execute(count_query, params)
#             total_records = count_result.scalar()

#             total_pages = (total_records + page_size - 1) // page_size

#             formatted_data = [
#                 {
#                     "address": row["address"],
#                     "name": row["name"],
#                     "birthDate": '',
#                     "email": row["email"],
#                     "gender": row["gender"],
#                     "id": row["id"],
#                     "orderId": row["orderId"],
#                     "phoneNumber": row["phoneNumber"],
#                     "socialMedia": '',
#                     "ticketId": row["ticketId"],
#                     "verifiedAt": row["verifiedAt"],
#                     "ticket": {
#                         "id": row["ticketId"],
#                         "name": row["ticketName"],
#                         "eventId": event_id,
#                         "price": row["ticketPrice"]
#                     },
#                     "eventId": event_id,
#                     "orderCreatedAt": row["orderCreatedAt"],
#                     "isScanned": bool(row["isVerified"]),
#                     "hash": row["hash"],
#                     "ticketCount": row["ticketCount"],
#                     "ticketNum": row["ticketNum"],
#                     "verifiedBy": {
#                         "id": row["verifiedById"],
#                         "name": row["verifiedByName"],
#                     },
#                     "isHide": False
#                 } for row in data
#             ]

#         return {
#             "status": "SUCCESS",
#             "message": "okay",
#             "data": {
#                 "tickets": formatted_data,
#                 "pagination": {
#                     "totalRecords": total_records,
#                     "totalPages": total_pages,
#                     "currentPage": page,
#                     "pageSize": page_size
#                 },
#             }
#         }
#     except Exception as e:
#         print(e)
#         response.status_code = 500
#         return {"success": False, "error": str(e)}


# db1 = 'kartjis_old_db'
# db2 = 'event_commitee_kartjis'

# # LOGIN


# class LoginData(BaseModel):
#     username: str
#     password: str

# # Fungsi untuk membuat token JWT


# def create_token(user_data: dict):
#     expiration = datetime.utcnow() + timedelta(days=7)
#     payload = {**user_data, "exp": expiration}
#     return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# # Fungsi untuk mengambil user dari token


# async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
#     try:
#         token = credentials.credentials
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload
#     except jwt.ExpiredSignatureError:
#         raise HTTPException(status_code=401, detail="Token expired")
#     except jwt.InvalidTokenError:
#         raise HTTPException(status_code=401, detail="Invalid token")

# # Endpoint login yang menghasilkan token


# async def loginOld(login_data: LoginData, response: Response):
#     try:

#         async with online_engine2.begin() as conn:
#             fetch_query = f"""
#             SELECT id, username, password, isAdmin, eventId, name, email
#             FROM {db2}.users WHERE username = :username
#             """

#             result = await conn.execute(text(fetch_query), {"username": login_data.username})

#             user = result.fetchone()
#             print(user)

#             if not user:
#                 raise HTTPException(status_code=404, detail="User not found")

#             if not bcrypt.checkpw(login_data.password.encode('utf-8'), user.password.encode('utf-8')):
#                 raise HTTPException(
#                     status_code=401, detail="Invalid credentials")

#             # Buat token JWT yang menyimpan eventId
#             token = create_token({
#                 "username": user.username,
#                 "eventId": user.eventId
#             })

#             return {
#                 "status": "SUCCESS",
#                 "message": "Login successful",
#                 "data": {
#                     "userId": user.id,
#                     "username": user.username,
#                     "isAdmin": user.isAdmin == 1,
#                     "eventId": user.eventId,
#                     "name": user.name,
#                     "email": user.email,
#                     "token": token
#                 }
#             }
#     except HTTPException as e:
#         response.status_code = e.status_code
#         return {"success": False, "error": e.detail}
#     except Exception as e:
#         print(e)
#         response.status_code = 500
#         return {"success": False, "error": "An internal server error occurred"}


# # # GEt ORDERS
# # @ticket.get('/api/events/orders')
# async def read_orders_old(
#     response: Response,
#     search: str = Query(default=None, description="Search by name or email"),
#     user: dict = Depends(get_current_user)  # Ambil user dari token
# ):
#     try:
#         event_id = user["eventId"]  # Ambil eventId dari token

#         async with online_engine2.begin() as conn:
#             base_query = f"""
#             SELECT od.address as address, od.birthDate as birthDate,
#             od.email AS email, od.gender as gender, od.id as id,
#             od.location as location, od.NAME AS name, o.id as orderId, od.phoneNumber as phoneNumber,
#             od.socialMedia as socialMedia,
#             t.id as ticketId, t.name as ticketName, t.price as ticketPrice,
#             o.createdAt as orderCreatedAt,
#             tv.hash AS hash, tv.isScanned AS isVerified, tv.id as tvId, tv.updatedAt as verifiedAt,
#             ROW_NUMBER() OVER (PARTITION BY od.orderId ORDER BY od.NAME) AS ticketNum, tv.verifiedBy,
#             COUNT(*) OVER (PARTITION BY od.orderId) AS ticketCount,
#             u.id AS verifiedById, u.name AS verifiedByName
#             FROM {db1}.TicketVerification AS tv
#             INNER JOIN {db1}.orderDetails AS od ON tv.orderDetailId=od.id
#             INNER JOIN {db1}.tickets AS t ON od.ticketId=t.id
#             INNER JOIN {db1}.orders o ON od.orderId = o.id
#             LEFT JOIN {db2}.users u ON tv.verifiedBy = u.id
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
#                     "commiteeName": "",
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
#                     "ticketNum": row_dict["ticketNum"],
#                     "verifiedBy": {
#                         "id": row_dict.get("verifiedById"),
#                         "name": row_dict.get("verifiedByName"),
#                     },
#                     "isHide": row_dict.get("location") == '666'
#                 }

#                 formatted_data.append(formatted_row)

#         return {
#             "status": "SUCCESS",
#             "data": formatted_data
#         }

#     except Exception as e:
#         response.status_code = 500
#         return {"success": False, "error": str(e)}


# async def ticket_type_summary_old(
#     response: Response,
#     user: dict = Depends(get_current_user)  # Ambil user dari token
# ):
#     try:
#         event_id = user["eventId"]
#         async with online_engine2.begin() as conn:

#             summary_query = f"""
#             SELECT
#                 t.name AS ticketTypeName,
#                 COALESCE(COUNT(od.id), 0) AS totalSold,
#                 COALESCE(SUM(CASE WHEN od.gender = 'Male' THEN 1 ELSE 0 END), 0) AS maleCount,
#                 COALESCE(SUM(CASE WHEN od.gender = 'Female' THEN 1 ELSE 0 END), 0) AS femaleCount,
#                 t.price AS ticketPrice,
#                 t.stock AS stock,
#                 t.adminFee AS adminFee,
#                 COALESCE(t.price * COUNT(od.id), 0) AS totalPrice,
#                 COALESCE((t.price * COUNT(od.id)) + (COUNT(od.id) * t.adminFee), 0) AS revenueAfterAdminFee,
#                 COALESCE(SUM(CASE WHEN tv.isScanned = 1 THEN 1 ELSE 0 END), 0) AS verifiedCount,
#                 COALESCE(SUM(CASE WHEN tv.isScanned = 0 THEN 1 ELSE 0 END), 0) AS unverifiedCount
#             FROM {db1}.tickets AS t
#             LEFT JOIN {db1}.orderDetails AS od ON od.ticketId = t.id
#             LEFT JOIN {db1}.orders AS o ON od.orderId = o.id AND o.status = 'SUCCESS'
#             LEFT JOIN {db1}.TicketVerification tv ON tv.orderDetailId = od.id
#             WHERE t.eventId = :event_id 
#                 AND o.status = 'SUCCESS'
#                 AND od.location <> '666'
#             GROUP BY t.id
#             ORDER BY t.name;
#             """

#             params = {'event_id': event_id}
#             result_proxy = await conn.execute(text(summary_query), params)
#             data = result_proxy.fetchall()

#             ticket_counts = [
#                 {
#                     "ticketTypeName": row["ticketTypeName"],
#                     "totalSold": row["totalSold"],
#                     "maleCount": row["maleCount"],
#                     "femaleCount": row["femaleCount"],
#                     "ticketPrice": row["ticketPrice"],
#                     "totalPrice": row["totalPrice"],
#                     "adminFee": row["adminFee"],
#                     "stock": row["stock"],
#                     "revenueAfterAdminFee": row["revenueAfterAdminFee"],
#                     "verifiedCount": row["verifiedCount"],
#                     "unverifiedCount": row["unverifiedCount"],
#                 }
#                 for row in data
#             ]

#             # Hitung summary keseluruhan
#             total_tickets = sum(row["totalSold"] for row in data)
#             total_verified = sum(row["verifiedCount"] for row in data)
#             total_unverified = sum(row["unverifiedCount"] for row in data)

#             ticket_summary = {
#                 "total": total_tickets,
#                 "verifiedCount": total_verified,
#                 "unverifiedCount": total_unverified
#             }

#             return {
#                 "status": "SUCCESS",
#                 "data": {
#                     "ticketSummary": ticket_summary,
#                     "ticketCounts": ticket_counts
#                 }
#             }

#     except Exception as e:
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "error": str(e),
#         }


# # @ticket.delete('/api/orders/{id}')
# # async def delete_order(id: str, response: Response):
# #     try:
# #         async with online_engine2.begin() as conn:
# #             # Delete query
# #             delete_query = f"DELETE FROM {db1}.orders WHERE id = :id"
# #             result = await conn.execute(text(delete_query), {'id': id})

# #             # Check if any row was deleted
# #             if result.rowcount == 0:
# #                 raise HTTPException(status_code=404, detail="Order not found")

# #         return {"status": "SUCCESS", "data": f"Order with ID {id} deleted successfully"}

# #     except HTTPException as e:
# #         raise e
# #     except Exception as e:
# #         print(e)
# #         response.status_code = 500  # Internal Server Error
# #         return {"status": "ERROR", "error": str(e)}


# async def get_event_details_old(response: Response, user: dict = Depends(get_current_user)):
#     event_id = user["eventId"]
#     try:
#         async with online_engine2.connect() as conn:
#             event_query = f"""
#             SELECT e.id as eventId, e.name as eventName,
#                    t.id as ticketId, t.name as ticketName, t.price as ticketPrice
#             FROM {db1}.events e
#             LEFT JOIN {db1}.tickets t ON e.id = t.eventId
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


# # # GET EO
# async def get_event_organizers_old(response: Response, user: dict = Depends(get_current_user)):
#     try:
#         eventId = user["eventId"]
#         async with online_engine2.begin() as conn:
#             # Query untuk mendapatkan semua event organizers berdasarkan eventId
#             fetch_query = f"""
#             SELECT
#                 eo.id as id,
#                 eo.username as username,
#                 eo.name as name,
#                 eo.email as email,
#                 eo.isAdmin as isAdmin,
#                 COUNT(tv.id) AS totalVerification
#             FROM {db2}.users eo
#             left JOIN {db1}.TicketVerification tv
#                 ON tv.verifiedBy = eo.id
#             WHERE eo.eventId = :eventId
#             GROUP BY eo.username, eo.name, eo.email, eo.isAdmin
#         """

#             result = await conn.execute(text(fetch_query), {"eventId": eventId})
#             event_organizers = result.fetchall()

#             if not event_organizers:
#                 raise HTTPException(
#                     status_code=404, detail="No Event Organizers found for this event"
#                 )

#             # Mengubah hasil query menjadi list of dictionaries
#             organizers_list = [
#                 {
#                     "id": organizer.id,
#                     "username": organizer.username,
#                     "name": organizer.name,
#                     "email": organizer.email,  # Properti phone ditambahkan
#                     "isAdmin": organizer.isAdmin == 1,
#                     "totalVerification": organizer.totalVerification,
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
#         response.status_code = 500
#         return {"success": False, "error": "An internal server error occurred"}


# # # ADD TICKET
# # class TicketBase(BaseModel):
# #     name: str
# #     price: float
# #     stock: int
# #     eventId: str


# # @ticket.post('/api/tickets')
# # async def create_ticket(ticket_data: TicketBase, response: Response, user: dict = Depends(get_current_user)):
# #     try:
# #         eventId = user["eventId"]
# #         async with online_engine2.begin() as conn:
# #             insert_query = f"""
# #             INSERT INTO {db1}.tickets (name, price, stock, adminFee, eventId, id, updatedAt)
# #             VALUES (:name, :price, :stock, :adminFee, :eventId, :id, :updatedAt)
# #             """
# #             params = {
# #                 "name": ticket_data.name,
# #                 "price": ticket_data.price,
# #                 "stock": ticket_data.stock,
# #                 "adminFee": 10000,
# #                 "eventId": eventId,
# #                 "id": uuid.uuid4(),
# #                 "updatedAt": datetime.now(),
# #             }

# #             await conn.execute(text(insert_query), params)

# #         return {"status": "SUCCESS", "message": "Ticket created successfully"}
# #     except Exception as e:
# #         print(e)
# #         response.status_code = 500  # Internal Server Error
# #         return {"success": False, "error": str(e)}

# # # UODATE TICKEt


# # @ticket.put('/api/tickets/{ticket_id}')
# # async def update_ticket(ticket_id: str, ticket_data: TicketBase, response: Response):
# #     try:
# #         async with online_engine2.begin() as conn:
# #             update_query = f"""
# #             UPDATE {db1}.tickets
# #             SET name = :name, price = :price, stock = :stock
# #             WHERE id = :ticket_id
# #             """
# #             params = {
# #                 "name": ticket_data.name,
# #                 "price": ticket_data.price,
# #                 "stock": ticket_data.stock,
# #                 "ticket_id": ticket_id,
# #             }

# #             result = await conn.execute(text(update_query), params)

# #             if result.rowcount == 0:
# #                 response.status_code = 404  # Not Found
# #                 return {"success": False, "message": "Ticket not found"}

# #         return {"status": "SUCCESS", "message": "Ticket updated successfully"}
# #     except Exception as e:
# #         print(e)
# #         response.status_code = 500  # Internal Server Error
# #         return {"success": False, "error": str(e)}

# # # VERIFY


# # @ticket.put('/api/events/orders/{hash}')
# async def update_verification_old(hash: str,  request: Request, response: Response, user: dict = Depends(get_current_user)):
#     try:
#         # Ambil data dari body request
#         event_id = user["eventId"]
#         body = await request.json()
#         is_verify = body.get('isVerify')  # Mengambil nilai isVerify dari body
#         verified_by = body.get('verifiedBy')  # ID user yang memverifikasi

#         # Validasi body request
#         if is_verify is None or not isinstance(is_verify, bool):
#             response.status_code = 400  # Bad Request

#             return {
#                 "success": False,
#                 "status": 'Failed',
#                 "code": '',
#                 "data": {
#                     "code": "KARTJIS.44",
#                     "detail": "'isVerify' harus berupa boolean."
#                 },
#             }

#         if not verified_by:
#             response.status_code = 400  # Bad Request

#             return {
#                 "success": False,
#                 "status": 'Failed',
#                 "code": '',
#                 "data": {
#                     "code": "KARTJIS.44",
#                     "detail": "'verifiedBy' tidak boleh kosong."
#                 },
#             }

#         # Set zona waktu lokal (misalnya waktu Makassar)
#         local_tz = pytz.timezone("Asia/Makassar")
#         current_datetime = datetime.now(local_tz)

#         async with online_engine2.begin() as conn:
#             # Query untuk memeriksa status tiket
#             check_query = f"""
#                 SELECT od.address as address, od.birthDate as birthDate,
#                 od.email AS email, od.gender as gender, od.id as id,
#                 od.location as location, od.NAME AS name, o.id as orderId, od.phoneNumber as phoneNumber,
#                 od.socialMedia as socialMedia,
#                 t.id as ticketId, t.name as ticketName, t.price as ticketPrice,
#                 o.createdAt as orderCreatedAt,
#                 tv.hash AS hash, tv.isScanned AS isVerified, tv.id as tvId, tv.updatedAt as verifiedAt,
#                 ROW_NUMBER() OVER (PARTITION BY od.orderId ORDER BY od.NAME) AS ticketNum, tv.verifiedBy,
#                 COUNT(*) OVER (PARTITION BY od.orderId) AS ticketCount,
#                 u.id AS verifiedById, u.name AS verifiedByName
#                 FROM {db1}.TicketVerification AS tv
#                 INNER JOIN {db1}.orderDetails AS od ON tv.orderDetailId=od.id
#                 INNER JOIN {db1}.tickets AS t ON od.ticketId=t.id
#                 INNER JOIN {db1}.orders o ON od.orderId = o.id
#                 LEFT JOIN {db2}.users u ON tv.verifiedBy = u.id
#                 WHERE (tv.hash = :hash OR LOWER(t.id) = :hash) AND t.eventId = :event_id AND o.status = 'SUCCESS'
#             """

#             check_result = await conn.execute(text(check_query), {"hash": hash.lower(), "event_id": event_id})
#             row_dict = check_result.fetchone()

#             if not row_dict:
#                 response.status_code = 200  # Not Found
#                 return {
#                     "success": False,
#                     "status": 'Failed',
#                     "code": '',
#                     "data": {
#                         "code": "KARTJIS.40",
#                         "detail": "Kartjis tidak ditemukan."
#                     },
#                 }

#             # Ambil status verifikasi saat ini
#             formatted_row = {
#                 "address": row_dict["address"],
#                 "name": row_dict["name"],
#                 "birthDate": row_dict["birthDate"],
#                 "email": row_dict["email"],
#                 "gender": row_dict["gender"],
#                 "id": row_dict["id"],
#                 "commiteeName": "",
#                 "orderId": row_dict["orderId"],
#                 "phoneNumber": row_dict["phoneNumber"],
#                 "socialMedia": row_dict["socialMedia"],
#                 "ticketId": row_dict["ticketId"],
#                 "verifiedAt": row_dict["verifiedAt"],
#                 "ticket": {
#                     "id": row_dict["ticketId"],
#                     "name": row_dict["ticketName"],
#                     "eventId": event_id,
#                     "price": row_dict["ticketPrice"]
#                 },
#                 "eventId": event_id,
#                 "orderCreatedAt": row_dict["orderCreatedAt"],
#                 "isScanned": bool(row_dict["isVerified"]),
#                 "hash": row_dict["hash"],
#                 "ticketCount": row_dict["ticketCount"],
#                 "ticketNum": row_dict["ticketNum"],
#                 "verifiedBy": {
#                     "id": row_dict["verifiedById"],
#                     "name": row_dict["verifiedByName"],
#                 },
#                 "isHide": row_dict["location"] == '666'
#             }

#             if is_verify and bool(row_dict["isVerified"]):
#                 response.status_code = 200  # Bad Request
#                 return {
#                     "success": False,
#                     "status": 'Failed',
#                     "code": '',
#                     "data": {
#                         "code": "KARTJIS.41",
#                         "detail": "Kartjis sudah diverifikasi.",
#                         "orderDetail": formatted_row, }
#                 }

#             # Update status verifikasi
#             query_update = f"""
#                 UPDATE {db1}.TicketVerification AS tv
#                 INNER JOIN {db1}.orderDetails AS od ON tv.orderDetailId = od.id
#                 INNER JOIN {db1}.tickets AS t ON od.ticketId = t.id
#                 SET
#                     tv.isScanned = :is_verify,
#                     tv.updatedAt = :current_datetime,
#                     tv.verifiedBy = :verified_by
#                 WHERE (tv.hash = :hash OR LOWER(t.id) = :hash)  AND t.eventId = :event_id
#             """

#             await conn.execute(text(query_update), {
#                 "is_verify": 1 if is_verify else 0,
#                 "current_datetime": current_datetime,
#                 "verified_by": verified_by,
#                 "hash": hash.lower(),
#                 "event_id": event_id,
#                 "orderDetail": formatted_row,
#             })

#         # Response sukses

#         return {
#             "success": True,
#             "status": 'SUCCEss',
#             "code": '',
#             "data": {
#                 "code": 'KARTJIS.21' if is_verify else "KARTJIS.20",
#                 "detail": "Berhasil memverifikasi Kartjis." if is_verify else "Berhasil membatalkan verifikasi Kartjis."
#             },
#         }

#     except HTTPException as http_error:
#         # Tangani HTTPException
#         raise http_error
#     except Exception as e:
#         response.status_code = 500  # Internal Server Error
#         return {
#             "success": False,
#             "status": 'Failed',
#             "code": '',
#                     "data": {
#                         "code": "KARTJIS.50",
#                         "detail": "Terjadi kesalahan internal server."
#                     }
#         },


# # # Add OTS
# # @ticket.post('/api/events/offline-transactions')
# # async def ots2(request: dict, response: Response,  user: dict = Depends(get_current_user)):
# #     tickets = request.get("data", [])
# #     event_id = user['eventId']
# #     ordal = request.get('ordal', False)

# #     async with online_engine2.begin() as conn:
# #         try:
# #             if len(tickets) <= 0:
# #                 return
# #             order_id = str(uuid.uuid4())
# #             current_time = datetime.now()
# #             customer_id = str(uuid.uuid4())
# #             ticket1 = tickets[0]

# #             await conn.execute(
# #                 text(f"""
# #                     INSERT INTO {db1}.customers (`id`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `createdAt`, `updatedAt`)
# #                     VALUES (:id, :name, :email, :birthDate, :phoneNumber, :gender, :createdAt, :updatedAt)
# #                 """),
# #                 {
# #                     "id": customer_id,
# #                     "name": ticket1["customer_name"],
# #                     "email": ticket1["customer_email"],
# #                     "birthDate": ticket1["customer_birthdate"],
# #                     "phoneNumber": ticket1["customer_phone"],
# #                     "gender": ticket1["customer_gender"],
# #                     "createdAt": current_time,
# #                     "updatedAt": current_time,
# #                     "address": '',
# #                 },
# #             )

# #             # Insert into `orders`
# #             await conn.execute(
# #                 text(f"""
# #                     INSERT INTO {db1}.orders (`id`, `status`, `createdAt`, `updatedAt`, `customerId`, `eventId`)
# #                     VALUES (:id, 'SUCCESS', :createdAt, :updatedAt, :customerId, :eventId)
# #                 """),
# #                 {
# #                     "id": order_id,
# #                     "createdAt": current_time,
# #                     "updatedAt": current_time,
# #                     "eventId": event_id,
# #                     "customerId": customer_id
# #                 },
# #             )

# #             # Insert into `customers`

# #             for ticket in tickets:
# #                 ticket_id = ticket["ticket_id"],
# #                 order_detail_id = str(uuid.uuid4())
# #                 verification_id = str(uuid.uuid4())

# #                 result = await conn.execute(
# #                     text(
# #                         f"SELECT id FROM {
# #                             db1}.tickets WHERE `id` = :id and `eventId` = :eventId"
# #                     ),
# #                     {"id": ticket_id, "eventId": event_id},
# #                 )
# #                 existing_ticket = result.fetchone()

# #                 if existing_ticket:
# #                     ticket_id = existing_ticket[0]
# #                 else:
# #                     await conn.execute(
# #                         text(f"""
# #                             INSERT INTO {db1}.tickets (`id`, `name`, `price`, `eventId`, `stock`, `createdAt`, `updatedAt`, `adminFee`)
# #                             VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, 0)
# #                         """),
# #                         {
# #                             "id": ticket_id,
# #                             "name": 'OTS',
# #                             "price": 0,
# #                             "eventId": event_id,
# #                             "stock": 100,
# #                             "createdAt": current_time,
# #                             "updatedAt": current_time,
# #                         },
# #                     )

# #                 # Insert into `orderdetails`
# #                 await conn.execute(
# #                     text(f"""
# #                         INSERT INTO {db1}.orderDetails (`id`, `ticketId`, `quantity`, `orderId`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `address`, `socialMedia`, `location`, `commiteeName`)
# #                         VALUES (:id, :ticketId, 1, :orderId, :name, :email, :birthDate, :phoneNumber, :gender, :address, :socialMedia, :location, :commiteeName)
# #                     """),
# #                     {
# #                         "id": order_detail_id,
# #                         "ticketId": ticket_id,
# #                         "orderId": order_id,
# #                         "name": ticket["customer_name"],
# #                         "email": ticket["customer_email"],
# #                         "birthDate": ticket["customer_birthdate"],
# #                         "phoneNumber": ticket["customer_phone"],
# #                         "gender": ticket["customer_gender"],
# #                         "address": ticket["address"],
# #                         "socialMedia": ticket["social_media"],
# #                         "location": '666' if ordal else None,
# #                         "commiteeName": None,
# #                     },
# #                 )

# #                 # Generate MD5 hash for ticket verification
# #                 random_number = random.randint(1000, 9999)
# #                 combined_string = f"{ticket['customer_email']}{
# #                     order_detail_id}{current_time}{random_number}"
# #                 hash_value = hashlib.md5(combined_string.encode()).hexdigest()

# #                 await conn.execute(
# #                     text(f"""
# #                         INSERT INTO {db1}.TicketVerification (`id`, `hash`, `isScanned`, `createdAt`, `updatedAt`, `orderDetailId`)
# #                         VALUES (:id, :hash, :isScanned, :createdAt, :updatedAt, :orderDetailId)
# #                     """),
# #                     {
# #                         "id": verification_id,
# #                         "hash": hash_value,
# #                         "isScanned": 0 if ordal else 1,
# #                         "createdAt": current_time,
# #                         "updatedAt": current_time,
# #                         "orderDetailId": order_detail_id,
# #                     },
# #                 )

# #             return {
# #                 "success": True,
# #                 "data": "Tickets successfully created.",
# #             }

# #         except Exception as e:
# #             print(e)
# #             response.status_code = 500  # Internal Server Error
# #             return {
# #                 "success": False,
# #                 "error": str(e),
# #             }

# # # Bom verification


# # @ticket.put('/api/events/{event_id}/tickets/verifications')
# # async def bulk_update_ticket_verifications(event_id: str, request: Request, response: Response):
# #     try:
# #         # Mengambil data dari body request
# #         body = await request.json()
# #         updates = body.get('data', [])  # List of updates

# #         if not isinstance(updates, list) or not updates:
# #             response.status_code = 400
# #             return {"success": False, "message": "Invalid request body. 'verifications' must be a non-empty list."}

# #         async with online_engine2.begin() as conn:
# #             # Prepare update query
# #             for verification in updates:
# #                 hash_value = verification.get("hash")
# #                 is_verify = verification.get("isVerify")
# #                 verified_by_id = verification.get("verifiedById")

# #                 if not hash_value or is_verify is None:
# #                     continue  # Skip invalid entries

# #                 # Set timezone to local
# #                 local_tz = pytz.timezone("Asia/Makassar")
# #                 current_datetime = datetime.now(local_tz)

# #                 # Update query
# #                 update_query = f"""
# #                 UPDATE {db1}.TicketVerification AS tv
# #                 INNER JOIN {db1}.orderDetails AS od ON tv.orderDetailId = od.id
# #                 INNER JOIN {db1}.tickets AS t ON od.ticketId = t.id
# #                 SET
# #                     tv.isScanned = :is_verify,
# #                     tv.updatedAt = :updated_at,
# #                     tv.verifiedBy = :verified_by_id
# #                 WHERE
# #                     tv.hash = :hash_value
# #                     AND t.eventId = :event_id
# #                 """

# #                 # Execute update
# #                 await conn.execute(text(update_query), {
# #                     "is_verify": 1 if is_verify else 0,
# #                     "updated_at": current_datetime,
# #                     "verified_by_id": verified_by_id,
# #                     "hash_value": hash_value,
# #                     "event_id": event_id,
# #                 })

# #         # Return response
# #         return {
# #             "success": True,
# #             "message": "Bulk ticket verifications updated successfully."
# #         }

# #     except Exception as e:
# #         print(e)
# #         response.status_code = 500  # Internal Server Error
# #         return {
# #             "success": False,
# #             "message": "An error occurred while processing the request.",
# #             "error": str(e),
# #         }

# #     # Sync OTS


# # @ticket.put('/api/events/{event_id}/sync-offline-transactions')
# # async def sync_ots(request: dict, event_id: str, response: Response):
# #     tickets = request.get("data", [])  # Mengambil array tiket dari key 'data'
# #     async with online_engine2.begin() as conn:
# #         try:
# #             for ticket in tickets:
# #                 # Diberikan di request body
# #                 ticket_id = ticket.get("ticket_id")
# #                 customer_id = uuid.uuid4()  # Fallback jika tidak ada
# #                 order_id = ticket.get("order_id")  # Diberikan di request body
# #                 # Diberikan di request body
# #                 order_detail_id = ticket.get("order_detail_id")
# #                 hash_value = ticket.get("hash")  # Diberikan di request body
# #                 current_time = datetime.now()

# #                 # Cek tiket yang ada di database
# #                 result = await conn.execute(
# #                     text(
# #                         f"SELECT id FROM {
# #                             db1}.tickets WHERE `id` = :id and `eventId` = :eventId"
# #                     ),
# #                     {"id": ticket_id, "eventId": event_id},
# #                 )
# #                 existing_ticket = result.fetchone()

# #                 if existing_ticket:
# #                     ticket_id = existing_ticket[0]
# #                 else:
# #                     return {
# #                         "success": False,
# #                         "error": str('ticket id required'),
# #                     }
# #                 # else:
# #                 #     await conn.execute(
# #                 #         text(f"""
# #                 #             INSERT INTO {db1}.tickets (`id`, `name`, `price`, `eventId`, `stock`, `createdAt`, `updatedAt`, `adminFee`)
# #                 #             VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, 0)
# #                 #         """),
# #                 #         {
# #                 #             "id": ticket_id,
# #                 #             "name": 'OTS',
# #                 #             "price": 0,
# #                 #             "eventId": event_id,
# #                 #             "stock": 100,
# #                 #             "createdAt": current_time,
# #                 #             "updatedAt": current_time,
# #                 #         },
# #                 #     )

# #                 # Insert ke tabel `customers`
# #                 await conn.execute(
# #                     text(f"""
# #                         INSERT INTO {db1}.customers (`id`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `createdAt`, `updatedAt`)
# #                         VALUES (:id, :name, :email, :birthDate, :phoneNumber, :gender, :createdAt, :updatedAt)
# #                     """),
# #                     {
# #                         "id": customer_id,
# #                         "name": ticket["customer_name"],
# #                         "email": ticket["customer_email"],
# #                         "birthDate": ticket["customer_birthdate"],
# #                         "phoneNumber": ticket["customer_phone"],
# #                         "gender": ticket["customer_gender"],
# #                         "createdAt": current_time,
# #                         "updatedAt": current_time,
# #                     },
# #                 )

# #                 # Insert ke tabel `orders`
# #                 await conn.execute(
# #                     text(f"""
# #                         INSERT INTO {db1}.orders (`id`, `status`, `createdAt`, `updatedAt`, `customerId`, `eventId`)
# #                         VALUES (:id, 'SUCCESS', :createdAt, :updatedAt, :customerId, :eventId)
# #                     """),
# #                     {
# #                         "id": order_id,
# #                         "createdAt": current_time,
# #                         "updatedAt": current_time,
# #                         "customerId": customer_id,
# #                         "eventId": event_id,
# #                     },
# #                 )

# #                 # Insert ke tabel `orderdetails`
# #                 await conn.execute(
# #                     text(f"""
# #                         INSERT INTO {db1}.orderDetails (`id`, `ticketId`, `quantity`, `orderId`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `address`, `socialMedia`, `location`, `commiteeName`)
# #                         VALUES (:id, :ticketId, 1, :orderId, :name, :email, :birthDate, :phoneNumber, :gender, :address, :socialMedia, :location, :commiteeName)
# #                     """),
# #                     {
# #                         "id": order_detail_id,
# #                         "ticketId": ticket_id,
# #                         "orderId": order_id,
# #                         "name": ticket["customer_name"],
# #                         "email": ticket["customer_email"],
# #                         "birthDate": ticket["customer_birthdate"],
# #                         "phoneNumber": ticket["customer_phone"],
# #                         "gender": ticket["customer_gender"],
# #                         "address": ticket["address"],
# #                         "socialMedia": ticket["social_media"],
# #                         "location": None,
# #                         "commiteeName": None,
# #                     },
# #                 )

# #                 # Insert ke tabel `ticketverification`
# #                 await conn.execute(
# #                     text(f"""
# #                         INSERT INTO {db1}.TicketVerification (`id`, `hash`, `isScanned`, `createdAt`, `updatedAt`, `orderDetailId`)
# #                         VALUES (:id, :hash, 1, :createdAt, :updatedAt, :orderDetailId)
# #                     """),
# #                     {
# #                         "id": str(uuid.uuid4()),
# #                         "hash": hash_value,
# #                         "createdAt": current_time,
# #                         "updatedAt": current_time,
# #                         "orderDetailId": order_detail_id,
# #                     },
# #                 )

# #             return {
# #                 "success": True,
# #                 "message": "Tickets successfully synced.",
# #             }

# #         except Exception as e:
# #             print(e)
# #             response.status_code = 500  # Internal Server Error
# #             return {
# #                 "success": False,
# #                 "error": str(e),
# #             }


# async def read_orders2(
#     response: Response,
#     search: Optional[str] = Query(None, description="Search by name or email"),
#     ticket_type: Optional[str] = Query(
#         None, description="Filter by ticket type"),
#     verified: Optional[bool] = Query(
#         None, description="Filter by verification status (true/false)"),
#     page: int = Query(1, ge=1, description="Page number"),
#     page_size: int = Query(
#         50, ge=1, le=100, description="Number of results per page"),
#     user: dict = Depends(get_current_user),
# ):
#     try:
#         event_id = user["eventId"]
#         offset = (page - 1) * page_size

#         async with online_engine2.begin() as conn:
#             base_query = text(f"""
#             SELECT od.address, od.birthDate, od.email, od.gender, od.id, od.location, od.NAME AS name,
#                    o.id as orderId, od.phoneNumber, od.socialMedia, t.id as ticketId, t.name as ticketName, t.price as ticketPrice,
#                    o.createdAt as orderCreatedAt, tv.hash, tv.isScanned AS isVerified, tv.id as tvId, tv.updatedAt as verifiedAt,
#                    tv.verifiedBy, u.id AS verifiedById, u.name AS verifiedByName,
#                    ROW_NUMBER() OVER (PARTITION BY od.orderId ORDER BY od.NAME) AS ticketNum,
#                    COUNT(*) OVER (PARTITION BY od.orderId) AS ticketCount
#             FROM {db1}.TicketVerification AS tv
#             INNER JOIN {db1}.orderDetails AS od ON tv.orderDetailId = od.id
#             INNER JOIN {db1}.tickets AS t ON od.ticketId = t.id
#             INNER JOIN {db1}.orders o ON od.orderId = o.id
#             LEFT JOIN {db2}.users u ON tv.verifiedBy = u.id
#             WHERE t.eventId = :event_id 
#                   AND o.status = 'SUCCESS'
#                   AND od.location <> '666'
#             """)

#             count_query = text(f"""
#             SELECT COUNT(*)
#             FROM {db1}.orders o
#             INNER JOIN {db1}.orderDetails od ON o.id = od.orderId
#             INNER JOIN {db1}.tickets t ON od.ticketId = t.id
#             INNER JOIN {db1}.TicketVerification AS tv ON tv.orderDetailId = od.id
#             WHERE t.eventId = :event_id 
#                   AND o.status = 'SUCCESS'
#                   AND od.location <> '666'
#             """)

#             params = {'event_id': event_id}

#             if search:
#                 base_query = text(str(
#                     base_query) + " AND (LOWER(od.name) LIKE LOWER(:search) OR LOWER(od.email) LIKE LOWER(:search))")
#                 count_query = text(str(
#                     count_query) + " AND (LOWER(od.name) LIKE LOWER(:search) OR LOWER(od.email) LIKE LOWER(:search))")
#                 params['search'] = f"%{search}%"

#             if ticket_type:
#                 base_query = text(str(base_query) +
#                                   " AND t.name = :ticket_type")
#                 count_query = text(str(count_query) +
#                                    " AND t.name = :ticket_type")
#                 params['ticket_type'] = ticket_type

#             if verified is not None:
#                 base_query = text(str(base_query) +
#                                   " AND tv.isScanned = :verified")
#                 count_query = text(str(count_query) +
#                                    " AND tv.isScanned = :verified")
#                 params['verified'] = 1 if verified else 0

#             base_query = text(
#                 str(base_query) + " ORDER BY od.NAME LIMIT :page_size OFFSET :offset")
#             params.update({'page_size': page_size, 'offset': offset})

#             # Execute queries
#             result_proxy = await conn.execute(base_query, params)
#             data = result_proxy.mappings().all()

#             count_result = await conn.execute(count_query, params)
#             total_records = count_result.scalar()

#             total_pages = (total_records + page_size - 1) // page_size

#             formatted_data = [
#                 {
#                     "address": row["address"],
#                     "name": row["name"],
#                     "birthDate": row["birthDate"],
#                     "email": row["email"],
#                     "gender": row["gender"],
#                     "id": row["id"],
#                     "orderId": row["orderId"],
#                     "phoneNumber": row["phoneNumber"],
#                     "socialMedia": row["socialMedia"],
#                     "ticketId": row["ticketId"],
#                     "verifiedAt": row["verifiedAt"],
#                     "ticket": {
#                         "id": row["ticketId"],
#                         "name": row["ticketName"],
#                         "eventId": event_id,
#                         "price": row["ticketPrice"]
#                     },
#                     "eventId": event_id,
#                     "orderCreatedAt": row["orderCreatedAt"],
#                     "isScanned": bool(row["isVerified"]),
#                     "hash": row["hash"],
#                     "ticketCount": row["ticketCount"],
#                     "ticketNum": row["ticketNum"],
#                     "verifiedBy": {
#                         "id": row["verifiedById"],
#                         "name": row["verifiedByName"],
#                     },
#                     "isHide": row["location"] == '666'
#                 } for row in data
#             ]

#         return {
#             "status": "SUCCESS",
#             "message": "okay",
#             "data": {
#                 "tickets": formatted_data,
#                 "pagination": {
#                     "totalRecords": total_records,
#                     "totalPages": total_pages,
#                     "currentPage": page,
#                     "pageSize": page_size
#                 },
#             }
#         }
#     except Exception as e:
#         response.status_code = 500
#         return {"success": False, "error": str(e)}


# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)
