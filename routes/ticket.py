from fastapi import HTTPException, Request, Response
import jwt
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
from fastapi.middleware.cors import CORSMiddleware
import bcrypt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security, Depends

security = HTTPBearer()
SECRET_KEY = "a_very_secret_key_1234567890!@#$%^&*()"
ALGORITHM = "HS256"


app = FastAPI()

# Konfigurasi CORS (Hanya bisa di FastAPI, bukan APIRouter)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Bisa diganti dengan daftar domain yang diizinkan
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

ticket = APIRouter()


@ticket.get("/")
async def root():
    return {"message": "CORS sudah aktif!"}

# Daftarkan router ke aplikasi FastAPI
app.include_router(ticket, prefix="/api/events/orders")


db1 = 'kartjis_old_db'
db2 = 'event_commitee_kartjis'

# LOGIN


class LoginData(BaseModel):
    username: str
    password: str

# Fungsi untuk membuat token JWT


def create_token(user_data: dict):
    expiration = datetime.utcnow() + timedelta(days=7)
    payload = {**user_data, "exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# Fungsi untuk mengambil user dari token


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Endpoint login yang menghasilkan token


@ticket.post('/api/users/login')
async def login(login_data: LoginData, response: Response):
    try:
        async with online_engine.begin() as conn:
            fetch_query = f"""
            SELECT id, username, password, isAdmin, eventId, name, email
            FROM {db2}.users WHERE username = :username
            """
            result = await conn.execute(text(fetch_query), {"username": login_data.username})
            user = result.fetchone()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            if not bcrypt.checkpw(login_data.password.encode('utf-8'), user.password.encode('utf-8')):
                raise HTTPException(
                    status_code=401, detail="Invalid credentials")

            # Buat token JWT yang menyimpan eventId
            token = create_token({
                "username": user.username,
                "eventId": user.eventId
            })

            return {
                "status": "SUCCESS",
                "message": "Login successful",
                "data": {
                    "userId": user.id,
                    "username": user.username,
                    "isAdmin": user.isAdmin == 1,
                    "eventId": user.eventId,
                    "name": user.name,
                    "email": user.email,
                    "token": token
                }
            }
    except HTTPException as e:
        response.status_code = e.status_code
        return {"success": False, "error": e.detail}
    except Exception as e:
        print(e)
        response.status_code = 500
        return {"success": False, "error": "An internal server error occurred"}


# GEt ORDERS
@ticket.get('/api/events/orders')
async def read_orders(
    response: Response,
    search: str = Query(default=None, description="Search by name or email"),
    user: dict = Depends(get_current_user)  # Ambil user dari token
):
    try:
        event_id = user["eventId"]  # Ambil eventId dari token

        async with online_engine.begin() as conn:
            base_query = f"""
            SELECT od.address as address, od.birthDate as birthDate,
            od.email AS email, od.gender as gender, od.id as id,
            od.location as location, od.NAME AS name, o.id as orderId, od.phoneNumber as phoneNumber,
            od.socialMedia as socialMedia,
            t.id as ticketId, t.name as ticketName, t.price as ticketPrice,
            o.createdAt as orderCreatedAt,
            tv.hash AS hash, tv.isScanned AS isVerified, tv.id as tvId, tv.updatedAt as verifiedAt,
            ROW_NUMBER() OVER (PARTITION BY od.orderId ORDER BY od.NAME) AS ticketNum, tv.verifiedBy,
            COUNT(*) OVER (PARTITION BY od.orderId) AS ticketCount,
            u.id AS verifiedById, u.name AS verifiedByName
            FROM {db1}.TicketVerification AS tv
            INNER JOIN {db1}.orderDetails AS od ON tv.orderDetailId=od.id
            INNER JOIN {db1}.tickets AS t ON od.ticketId=t.id
            INNER JOIN {db1}.orders o ON od.orderId = o.id
            LEFT JOIN {db2}.users u ON tv.verifiedBy = u.id
            WHERE t.eventId = :event_id and o.status = "SUCCESS"
            """

            params = {'event_id': event_id}
            if search:
                base_query += " AND (LOWER(od.name) LIKE LOWER(:search) OR LOWER(od.email) LIKE LOWER(:search))"
                params['search'] = f"%{search}%"

            base_query += " ORDER BY od.NAME"

            result_proxy = await conn.execute(text(base_query), params)
            data = result_proxy.fetchall()

            formatted_data = []
            for row in data:
                row_dict = dict(row)
                formatted_row = {
                    "address": row_dict["address"],
                    "name": row_dict["name"],
                    "birthDate": row_dict["birthDate"],
                    "email": row_dict["email"],
                    "gender": row_dict["gender"],
                    "id": row_dict["id"],
                    "commiteeName": "",
                    "orderId": row_dict["orderId"],
                    "phoneNumber": row_dict["phoneNumber"],
                    "socialMedia": row_dict["socialMedia"],
                    "ticketId": row_dict["ticketId"],
                    "verifiedAt": row_dict["verifiedAt"],
                    "ticket": {
                        "id": row_dict["ticketId"],
                        "name": row_dict["ticketName"],
                        "eventId": event_id,
                        "price": row_dict["ticketPrice"]
                    },
                    "eventId": event_id,
                    "orderCreatedAt": row_dict["orderCreatedAt"],
                    "isScanned": bool(row_dict["isVerified"]),
                    "hash": row_dict["hash"],
                    "ticketCount": row_dict["ticketCount"],
                    "ticketNum": row_dict["ticketNum"],
                    "verifiedBy": {
                        "id": row_dict.get("verifiedById"),
                        "name": row_dict.get("verifiedByName"),
                    },
                    "isHide": row_dict.get("location") == '666'
                }

                formatted_data.append(formatted_row)

        return {
            "status": "SUCCESS",
            "data": formatted_data
        }

    except Exception as e:
        print(e)
        response.status_code = 500
        return {"success": False, "error": str(e)}


@ticket.get('/api/events/ticket-type-summary')
async def ticket_type_summary(
    response: Response,
    user: dict = Depends(get_current_user)  # Ambil user dari token
):
    try:
        eventId = user["eventId"]
        async with online_engine.begin() as conn:

            summary_query = f"""
            SELECT
                t.name AS ticketTypeName,
                COALESCE(COUNT(od.id), 0) AS totalSold,
                COALESCE(SUM(CASE WHEN od.gender = 'Male' THEN 1 ELSE 0 END), 0) AS maleCount,
                COALESCE(SUM(CASE WHEN od.gender = 'Female' THEN 1 ELSE 0 END), 0) AS femaleCount,
                t.price AS ticketPrice,
                t.stock AS stock,
                t.adminFee AS adminFee,
                COALESCE(t.price * COUNT(od.id), 0) AS totalPrice,
                COALESCE((t.price * COUNT(od.id)) + (COUNT(od.id) * t.adminFee), 0) AS revenueAfterAdminFee
            FROM {db1}.tickets AS t
            LEFT JOIN {db1}.orderDetails AS od ON od.ticketId = t.id
            LEFT JOIN {db1}.orders AS o ON od.orderId = o.id AND o.status = 'SUCCESS'
            WHERE t.eventId = :event_id
            GROUP BY t.id
            ORDER BY t.name;
            """

            params = {'event_id': eventId}
            result_proxy = await conn.execute(text(summary_query), params)

            data = result_proxy.fetchall()

            summary_data = [
                {
                    "ticketTypeName": row["ticketTypeName"],
                    "totalSold": row["totalSold"],
                    "maleCount": row["maleCount"],
                    "femaleCount": row["femaleCount"],
                    "ticketPrice": row["ticketPrice"],
                    "totalPrice": row["totalPrice"],
                    "adminFee": row["adminFee"],
                    "stock": row["stock"],
                    "revenueAfterAdminFee": row["revenueAfterAdminFee"]
                }
                for row in data
            ]

        return {
            "status": "SUCCESS",
            "data": summary_data
        }

    except Exception as e:
        print(e)
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "error": str(e),
        }


@ticket.delete('/api/orders/{id}')
async def delete_order(id: str, response: Response):
    try:
        async with online_engine.begin() as conn:
            # Delete query
            delete_query = f"DELETE FROM {db1}.orders WHERE id = :id"
            result = await conn.execute(text(delete_query), {'id': id})

            # Check if any row was deleted
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Order not found")

        return {"status": "SUCCESS", "data": f"Order with ID {id} deleted successfully"}

    except HTTPException as e:
        raise e
    except Exception as e:
        print(e)
        response.status_code = 500  # Internal Server Error
        return {"status": "ERROR", "error": str(e)}


# GET EVENTs
@ticket.get("/api/events")
async def get_event_details2(response: Response, user: dict = Depends(get_current_user)):
    event_id = user["eventId"]
    try:
        async with online_engine.connect() as conn:
            event_query = f"""
            SELECT e.id as eventId, e.name as eventName,
                   t.id as ticketId, t.name as ticketName, t.price as ticketPrice
            FROM {db1}.events e
            LEFT JOIN {db1}.tickets t ON e.id = t.eventId
            WHERE e.id = :event_id
            """

            result = await conn.execute(text(event_query), {"event_id": event_id})
            rows = result.fetchall()

            if not rows:
                response.status_code = 404
                return {"status": "NOT_FOUND", "message": "Event not found"}

            # Extract event details
            event_data = {
                "id": rows[0]["eventId"],
                "banner": '',  # Placeholder for banner, update if necessary
                "name": rows[0]["eventName"],
                "tickets": [
                    {
                        "id": row["ticketId"],
                        "name": row["ticketName"],
                        "eventId": event_id,
                        "price": row["ticketPrice"]
                    } for row in rows if row["ticketId"]
                ]
            }

        return {
            "status": "SUCCESS",
            "data": event_data
        }

    except Exception as e:
        print(e)
        response.status_code = 500  # Internal Server Error
        return {
            "status": "ERROR",
            "message": str(e)}


# GET EO
@ticket.get('/api/event-organizers')
async def get_event_organizers(response: Response, user: dict = Depends(get_current_user)):
    try:
        eventId = user["eventId"]
        async with online_engine.begin() as conn:
            # Query untuk mendapatkan semua event organizers berdasarkan eventId
            fetch_query = f"""
            SELECT
                eo.id as id,
                eo.username as username,
                eo.name as name,
                eo.email as email,
                eo.isAdmin as isAdmin,
                COUNT(tv.id) AS totalVerification
            FROM {db2}.users eo
            left JOIN {db1}.TicketVerification tv
                ON tv.verifiedBy = eo.id
            WHERE eo.eventId = :eventId
            GROUP BY eo.username, eo.name, eo.email, eo.isAdmin
        """

            result = await conn.execute(text(fetch_query), {"eventId": eventId})
            event_organizers = result.fetchall()

            if not event_organizers:
                raise HTTPException(
                    status_code=404, detail="No Event Organizers found for this event"
                )

            # Mengubah hasil query menjadi list of dictionaries
            organizers_list = [
                {
                    "id": organizer.id,
                    "username": organizer.username,
                    "name": organizer.name,
                    "email": organizer.email,  # Properti phone ditambahkan
                    "isAdmin": organizer.isAdmin == 1,
                    "totalVerification": organizer.totalVerification,
                }
                for organizer in event_organizers
            ]

            # Mengembalikan response sukses
            return {
                "status": "SUCCESS",
                "message": f"{len(organizers_list)} Event Organizer(s) fetched successfully",
                "data": organizers_list,
            }

    except HTTPException as e:
        response.status_code = e.status_code
        return {"success": False, "error": e.detail}
    except Exception as e:
        print(f"Error fetching event organizers for eventId {
              eventId}: {e}")  # Logging error
        response.status_code = 500
        return {"success": False, "error": "An internal server error occurred"}


# ADD TICKET
class TicketBase(BaseModel):
    name: str
    price: float
    stock: int
    eventId: str


@ticket.post('/api/tickets')
async def create_ticket(ticket_data: TicketBase, response: Response, user: dict = Depends(get_current_user)):
    try:
        eventId = user["eventId"]
        async with online_engine.begin() as conn:
            insert_query = f"""
            INSERT INTO {db1}.tickets (name, price, stock, adminFee, eventId, id, updatedAt)
            VALUES (:name, :price, :stock, :adminFee, :eventId, :id, :updatedAt)
            """
            params = {
                "name": ticket_data.name,
                "price": ticket_data.price,
                "stock": ticket_data.stock,
                "adminFee": 10000,
                "eventId": eventId,
                "id": uuid.uuid4(),
                "updatedAt": datetime.now(),
            }

            await conn.execute(text(insert_query), params)

        return {"status": "SUCCESS", "message": "Ticket created successfully"}
    except Exception as e:
        print(e)
        response.status_code = 500  # Internal Server Error
        return {"success": False, "error": str(e)}

# UODATE TICKEt


@ticket.put('/api/tickets/{ticket_id}')
async def update_ticket(ticket_id: str, ticket_data: TicketBase, response: Response):
    try:
        async with online_engine.begin() as conn:
            update_query = f"""
            UPDATE {db1}.tickets
            SET name = :name, price = :price, stock = :stock
            WHERE id = :ticket_id
            """
            params = {
                "name": ticket_data.name,
                "price": ticket_data.price,
                "stock": ticket_data.stock,
                "ticket_id": ticket_id,
            }

            result = await conn.execute(text(update_query), params)

            if result.rowcount == 0:
                response.status_code = 404  # Not Found
                return {"success": False, "message": "Ticket not found"}

        return {"status": "SUCCESS", "message": "Ticket updated successfully"}
    except Exception as e:
        print(e)
        response.status_code = 500  # Internal Server Error
        return {"success": False, "error": str(e)}

# VERIFY


@ticket.put('/api/events/orders/{hash}')
async def update_verification(hash: str,  request: Request, response: Response, user: dict = Depends(get_current_user)):
    try:
        # Ambil data dari body request
        event_id = user["eventId"]
        body = await request.json()
        is_verify = body.get('isVerify')  # Mengambil nilai isVerify dari body
        verified_by = body.get('verifiedBy')  # ID user yang memverifikasi

        # Validasi body request
        if is_verify is None or not isinstance(is_verify, bool):
            response.status_code = 400  # Bad Request

            return {
                "success": False,
                "status": 'Failed',
                "code": '',
                "data": {
                    "code": "KARTJIS.44",
                    "detail": "'isVerify' harus berupa boolean."
                },
            }

        if not verified_by:
            response.status_code = 400  # Bad Request

            return {
                "success": False,
                "status": 'Failed',
                "code": '',
                "data": {
                    "code": "KARTJIS.44",
                    "detail": "'verifiedBy' tidak boleh kosong."
                },
            }

        # Set zona waktu lokal (misalnya waktu Makassar)
        local_tz = pytz.timezone("Asia/Makassar")
        current_datetime = datetime.now(local_tz)

        async with online_engine.begin() as conn:
            # Query untuk memeriksa status tiket
            check_query = f"""
                SELECT tv.isScanned, tv.hash
                FROM {db1}.TicketVerification AS tv
                INNER JOIN {db1}.orderDetails AS od ON tv.orderDetailId = od.id
                INNER JOIN {db1}.tickets AS t ON od.ticketId = t.id
                INNER JOIN {db1}.orders o ON od.orderId = o.id
                WHERE tv.hash = :hash AND t.eventId = :event_id AND o.status = 'SUCCESS'
            """

            check_result = await conn.execute(text(check_query), {"hash": hash, "event_id": event_id})
            row = check_result.fetchone()

            if not row:
                response.status_code = 200  # Not Found
                return {
                    "success": False,
                    "status": 'Failed',
                    "code": '',
                    "data": {
                        "code": "KARTJIS.40",
                        "detail": "Kartjis tidak ditemukan."
                    },
                }

            # Ambil status verifikasi saat ini
            verification_status = row[0]  # Nilai isScanned

            # Cek kondisi untuk isVerify
            if is_verify and verification_status:
                response.status_code = 200  # Bad Request
                return {
                    "success": False,
                    "status": 'Failed',
                    "code": '',
                    "data": {
                        "code": "KARTJIS.41",
                        "detail": "Kartjis sudah diverifikasi."
                    }
                }

            # Update status verifikasi
            query_update = f"""
                UPDATE {db1}.TicketVerification AS tv
                INNER JOIN {db1}.orderDetails AS od ON tv.orderDetailId = od.id
                INNER JOIN {db1}.tickets AS t ON od.ticketId = t.id
                SET
                    tv.isScanned = :is_verify,
                    tv.updatedAt = :current_datetime,
                    tv.verifiedBy = :verified_by
                WHERE tv.hash = :hash AND t.eventId = :event_id
            """

            await conn.execute(text(query_update), {
                "is_verify": 1 if is_verify else 0,
                "current_datetime": current_datetime,
                "verified_by": verified_by,
                "hash": hash,
                "event_id": event_id,
            })

        # Response sukses

        return {
            "success": True,
            "status": 'SUCCEss',
            "code": '',
            "data": {
                "code": 'KARTJIS.21' if is_verify else "KARTJIS.20",
                "detail": "Berhasil memverifikasi Kartjis." if is_verify else "Berhasil membatalkan verifikasi Kartjis."
            },
        }

    except HTTPException as http_error:
        # Tangani HTTPException
        raise http_error
    except Exception as e:
        print(f"Error: {e}")
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "status": 'Failed',
            "code": '',
                    "data": {
                        "code": "KARTJIS.50",
                        "detail": "Terjadi kesalahan internal server."
                    }
        },


# Add OTS
@ticket.post('/api/events/offline-transactions')
async def ots2(request: dict, response: Response,  user: dict = Depends(get_current_user)):
    tickets = request.get("data", [])
    event_id = user['eventId']
    ordal = request.get('ordal', False)

    async with online_engine.begin() as conn:
        try:
            for ticket in tickets:
                ticket_id = ticket["ticket_id"],
                customer_id = str(uuid.uuid4())
                order_id = str(uuid.uuid4())
                order_detail_id = str(uuid.uuid4())
                verification_id = str(uuid.uuid4())
                current_time = datetime.now()

                result = await conn.execute(
                    text(
                        f"SELECT id FROM {
                            db1}.tickets WHERE `id` = :id and `eventId` = :eventId"
                    ),
                    {"id": ticket_id, "eventId": event_id},
                )
                existing_ticket = result.fetchone()

                if existing_ticket:
                    ticket_id = existing_ticket[0]
                else:
                    await conn.execute(
                        text(f"""
                            INSERT INTO {db1}.tickets (`id`, `name`, `price`, `eventId`, `stock`, `createdAt`, `updatedAt`, `adminFee`)
                            VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, 0)
                        """),
                        {
                            "id": ticket_id,
                            "name": 'OTS',
                            "price": 0,
                            "eventId": event_id,
                            "stock": 100,
                            "createdAt": current_time,
                            "updatedAt": current_time,
                        },
                    )

                # Insert into `customers`
                await conn.execute(
                    text(f"""
                        INSERT INTO {db1}.customers (`id`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `createdAt`, `updatedAt`)
                        VALUES (:id, :name, :email, :birthDate, :phoneNumber, :gender, :createdAt, :updatedAt)
                    """),
                    {
                        "id": customer_id,
                        "name": ticket["customer_name"],
                        "email": ticket["customer_email"],
                        "birthDate": ticket["customer_birthdate"],
                        "phoneNumber": ticket["customer_phone"],
                        "gender": ticket["customer_gender"],
                        "createdAt": current_time,
                        "updatedAt": current_time,
                        "address": '',
                    },
                )

                # Insert into `orders`
                await conn.execute(
                    text(f"""
                        INSERT INTO {db1}.orders (`id`, `status`, `createdAt`, `updatedAt`, `customerId`, `eventId`)
                        VALUES (:id, 'SUCCESS', :createdAt, :updatedAt, :customerId, :eventId)
                    """),
                    {
                        "id": order_id,
                        "createdAt": current_time,
                        "updatedAt": current_time,
                        "customerId": customer_id,
                        "eventId": event_id,
                    },
                )

                # Insert into `orderdetails`
                await conn.execute(
                    text(f"""
                        INSERT INTO {db1}.orderDetails (`id`, `ticketId`, `quantity`, `orderId`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `address`, `socialMedia`, `location`, `commiteeName`)
                        VALUES (:id, :ticketId, 1, :orderId, :name, :email, :birthDate, :phoneNumber, :gender, :address, :socialMedia, :location, :commiteeName)
                    """),
                    {
                        "id": order_detail_id,
                        "ticketId": ticket_id,
                        "orderId": order_id,
                        "name": ticket["customer_name"],
                        "email": ticket["customer_email"],
                        "birthDate": ticket["customer_birthdate"],
                        "phoneNumber": ticket["customer_phone"],
                        "gender": ticket["customer_gender"],
                        "address": ticket["address"],
                        "socialMedia": ticket["social_media"],
                        "location": '666' if ordal else None,
                        "commiteeName": None,
                    },
                )

                # Generate MD5 hash for ticket verification
                random_number = random.randint(1000, 9999)
                combined_string = f"{ticket['customer_email']}{
                    order_detail_id}{current_time}{random_number}"
                hash_value = hashlib.md5(combined_string.encode()).hexdigest()

                await conn.execute(
                    text(f"""
                        INSERT INTO {db1}.TicketVerification (`id`, `hash`, `isScanned`, `createdAt`, `updatedAt`, `orderDetailId`)
                        VALUES (:id, :hash, :isScanned, :createdAt, :updatedAt, :orderDetailId)
                    """),
                    {
                        "id": verification_id,
                        "hash": hash_value,
                        "isScanned": 0 if ordal else 1,
                        "createdAt": current_time,
                        "updatedAt": current_time,
                        "orderDetailId": order_detail_id,
                    },
                )

            return {
                "success": True,
                "data": "Tickets successfully created.",
            }

        except Exception as e:
            print(e)
            response.status_code = 500  # Internal Server Error
            return {
                "success": False,
                "error": str(e),
            }

# Bom verification


@ticket.put('/api/events/{event_id}/tickets/verifications')
async def bulk_update_ticket_verifications(event_id: str, request: Request, response: Response):
    try:
        # Mengambil data dari body request
        body = await request.json()
        updates = body.get('data', [])  # List of updates

        if not isinstance(updates, list) or not updates:
            response.status_code = 400
            return {"success": False, "message": "Invalid request body. 'verifications' must be a non-empty list."}

        async with online_engine.begin() as conn:
            # Prepare update query
            for verification in updates:
                hash_value = verification.get("hash")
                is_verify = verification.get("isVerify")
                verified_by_id = verification.get("verifiedById")

                if not hash_value or is_verify is None:
                    continue  # Skip invalid entries

                # Set timezone to local
                local_tz = pytz.timezone("Asia/Makassar")
                current_datetime = datetime.now(local_tz)

                # Update query
                update_query = f"""
                UPDATE {db1}.TicketVerification AS tv
                INNER JOIN {db1}.orderDetails AS od ON tv.orderDetailId = od.id
                INNER JOIN {db1}.tickets AS t ON od.ticketId = t.id
                SET
                    tv.isScanned = :is_verify,
                    tv.updatedAt = :updated_at,
                    tv.verifiedBy = :verified_by_id
                WHERE
                    tv.hash = :hash_value
                    AND t.eventId = :event_id
                """

                # Execute update
                await conn.execute(text(update_query), {
                    "is_verify": 1 if is_verify else 0,
                    "updated_at": current_datetime,
                    "verified_by_id": verified_by_id,
                    "hash_value": hash_value,
                    "event_id": event_id,
                })

        # Return response
        return {
            "success": True,
            "message": "Bulk ticket verifications updated successfully."
        }

    except Exception as e:
        print(e)
        response.status_code = 500  # Internal Server Error
        return {
            "success": False,
            "message": "An error occurred while processing the request.",
            "error": str(e),
        }

    # Sync OTS


@ticket.put('/api/events/{event_id}/sync-offline-transactions')
async def sync_ots(request: dict, event_id: str, response: Response):
    tickets = request.get("data", [])  # Mengambil array tiket dari key 'data'
    async with online_engine.begin() as conn:
        try:
            for ticket in tickets:
                # Diberikan di request body
                ticket_id = ticket.get("ticket_id")
                customer_id = uuid.uuid4()  # Fallback jika tidak ada
                order_id = ticket.get("order_id")  # Diberikan di request body
                # Diberikan di request body
                order_detail_id = ticket.get("order_detail_id")
                hash_value = ticket.get("hash")  # Diberikan di request body
                current_time = datetime.now()

                # Cek tiket yang ada di database
                result = await conn.execute(
                    text(
                        f"SELECT id FROM {
                            db1}.tickets WHERE `id` = :id and `eventId` = :eventId"
                    ),
                    {"id": ticket_id, "eventId": event_id},
                )
                existing_ticket = result.fetchone()

                if existing_ticket:
                    ticket_id = existing_ticket[0]
                else:
                    return {
                        "success": False,
                        "error": str('ticket id required'),
                    }
                # else:
                #     await conn.execute(
                #         text(f"""
                #             INSERT INTO {db1}.tickets (`id`, `name`, `price`, `eventId`, `stock`, `createdAt`, `updatedAt`, `adminFee`)
                #             VALUES (:id, :name, :price, :eventId, :stock, :createdAt, :updatedAt, 0)
                #         """),
                #         {
                #             "id": ticket_id,
                #             "name": 'OTS',
                #             "price": 0,
                #             "eventId": event_id,
                #             "stock": 100,
                #             "createdAt": current_time,
                #             "updatedAt": current_time,
                #         },
                #     )

                # Insert ke tabel `customers`
                await conn.execute(
                    text(f"""
                        INSERT INTO {db1}.customers (`id`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `createdAt`, `updatedAt`)
                        VALUES (:id, :name, :email, :birthDate, :phoneNumber, :gender, :createdAt, :updatedAt)
                    """),
                    {
                        "id": customer_id,
                        "name": ticket["customer_name"],
                        "email": ticket["customer_email"],
                        "birthDate": ticket["customer_birthdate"],
                        "phoneNumber": ticket["customer_phone"],
                        "gender": ticket["customer_gender"],
                        "createdAt": current_time,
                        "updatedAt": current_time,
                    },
                )

                # Insert ke tabel `orders`
                await conn.execute(
                    text(f"""
                        INSERT INTO {db1}.orders (`id`, `status`, `createdAt`, `updatedAt`, `customerId`, `eventId`)
                        VALUES (:id, 'SUCCESS', :createdAt, :updatedAt, :customerId, :eventId)
                    """),
                    {
                        "id": order_id,
                        "createdAt": current_time,
                        "updatedAt": current_time,
                        "customerId": customer_id,
                        "eventId": event_id,
                    },
                )

                # Insert ke tabel `orderdetails`
                await conn.execute(
                    text(f"""
                        INSERT INTO {db1}.orderDetails (`id`, `ticketId`, `quantity`, `orderId`, `name`, `email`, `birthDate`, `phoneNumber`, `gender`, `address`, `socialMedia`, `location`, `commiteeName`)
                        VALUES (:id, :ticketId, 1, :orderId, :name, :email, :birthDate, :phoneNumber, :gender, :address, :socialMedia, :location, :commiteeName)
                    """),
                    {
                        "id": order_detail_id,
                        "ticketId": ticket_id,
                        "orderId": order_id,
                        "name": ticket["customer_name"],
                        "email": ticket["customer_email"],
                        "birthDate": ticket["customer_birthdate"],
                        "phoneNumber": ticket["customer_phone"],
                        "gender": ticket["customer_gender"],
                        "address": ticket["address"],
                        "socialMedia": ticket["social_media"],
                        "location": None,
                        "commiteeName": None,
                    },
                )

                # Insert ke tabel `ticketverification`
                await conn.execute(
                    text(f"""
                        INSERT INTO {db1}.TicketVerification (`id`, `hash`, `isScanned`, `createdAt`, `updatedAt`, `orderDetailId`)
                        VALUES (:id, :hash, 1, :createdAt, :updatedAt, :orderDetailId)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "hash": hash_value,
                        "createdAt": current_time,
                        "updatedAt": current_time,
                        "orderDetailId": order_detail_id,
                    },
                )

            return {
                "success": True,
                "message": "Tickets successfully synced.",
            }

        except Exception as e:
            print(e)
            response.status_code = 500  # Internal Server Error
            return {
                "success": False,
                "error": str(e),
            }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)
