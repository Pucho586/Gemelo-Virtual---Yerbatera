import aiosqlite
import datetime

DB_FILE = "frigorifico.db"

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        # Tabla para guardar el historial de temperaturas
        await db.execute("""
            CREATE TABLE IF NOT EXISTS temperatura_historia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                camara_nombre TEXT,
                temp_actual REAL,
                temp_objetivo REAL,
                compresor TEXT,
                puerta TEXT
            )
        """)

        # Tabla para gestionar los lotes de carne (Tropas)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tropas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_tropa TEXT UNIQUE,
                fecha_ingreso TEXT,
                peso_kg REAL,
                camara_actual TEXT
            )
        """)
        await db.commit()

async def save_estado(estados: list):
    """Guarda una instantánea (snapshot) de todas las cámaras."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        for estado in estados:
            await db.execute("""
                INSERT INTO temperatura_historia (timestamp, camara_nombre, temp_actual, temp_objetivo, compresor, puerta)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (now, estado["nombre"], estado["temp_actual"], estado["temp_objetivo"], estado["compresor"], estado["puerta"]))
        await db.commit()

async def get_historial(limite: int = 50):
    """Obtiene el historial reciente."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM temperatura_historia ORDER BY id DESC LIMIT ?", (limite,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def crear_tropa(numero: str, peso_kg: float, camara_inicial: str):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT INTO tropas (numero_tropa, fecha_ingreso, peso_kg, camara_actual)
            VALUES (?, ?, ?, ?)
        """, (numero, now, peso_kg, camara_inicial))
        await db.commit()

async def get_tropas():
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tropas ORDER BY id DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
