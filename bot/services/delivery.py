"""
Delivery Service - CE cycle-based item/vehicle spawning via Nitrado API
NEVER restarts the server. Edits XML files and lets CE do the work.
"""
import aiohttp
import asyncio
import aiosqlite
import os
import uuid
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'trader.db')

# Delivery zones (Chernarus coordinates)
DELIVERY_ZONES = {
    'NWAF':     {'x': 4541.0, 'z': 11254.0, 'y': 0, 'description': 'Northwest Airfield'},
    'Berezino': {'x': 11822.0, 'z': 9234.0,  'y': 0, 'description': 'Berezino'},
    'Elektro':  {'x': 10440.0, 'z': 2500.0,  'y': 0, 'description': 'Elektrozavodsk'},
    'Cherno':   {'x': 7200.0,  'z': 2400.0,  'y': 0, 'description': 'Chernogorsk'},
    'Balota':   {'x': 6091.0,  'z': 2400.0,  'y': 0, 'description': 'Balota Airstrip'},
    'NEAF':     {'x': 13412.0, 'z': 13100.0, 'y': 0, 'description': 'Northeast Airfield'},
    'Tisy':     {'x': 1050.0,  'z': 13210.0, 'y': 0, 'description': 'Tisy Military'},
}

class NitradoAPI:
    def __init__(self):
        self.token = os.getenv('NITRADO_TOKEN')
        self.server_id = os.getenv('NITRADO_SERVER_ID')
        self.base = 'https://api.nitrado.net'
        self.file_base = f'{self.base}/services/{self.server_id}/gameservers/file_server'
        self.mission_path = '/games/{sid}/noftp/dayzxbox/config/dayzStandalone/mpmissions/dayzOffline.chernarusplus'

    @property
    def headers(self):
        return {'Authorization': f'Bearer {self.token}'}

    async def download_file(self, filepath: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{self.file_base}/download',
                params={'file': filepath},
                headers=self.headers
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                # Nitrado returns a token URL for the actual file
                async with session.get(data['data']['url']) as file_resp:
                    return await file_resp.text()

    async def upload_file(self, filepath: str, content: str) -> bool:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field('path', os.path.dirname(filepath))
            form.add_field('file', content, filename=os.path.basename(filepath),
                           content_type='application/octet-stream')
            async with session.post(
                f'{self.file_base}/upload',
                data=form,
                headers=self.headers
            ) as resp:
                resp.raise_for_status()
                return True


class DeliveryQueue:
    """Serialized queue - prevents simultaneous XML edits"""
    def __init__(self):
        self._queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._running = False

    async def add(self, job: dict):
        await self._queue.put(job)

    async def start(self, delivery_service):
        self._running = True
        while self._running:
            job = await self._queue.get()
            async with self._lock:
                try:
                    await delivery_service.execute_job(job)
                    await asyncio.sleep(3)  # brief pause between file edits
                except Exception as e:
                    print(f'[DeliveryQueue] Job failed: {e}')
                    await delivery_service.mark_job_failed(job, str(e))
                finally:
                    self._queue.task_done()


class DeliveryService:
    def __init__(self):
        self.nitrado = NitradoAPI()
        self.queue = DeliveryQueue()
        self.db_path = DB_PATH

    async def queue_item_delivery(self, item_class: str, quantity: int,
                                   delivery_zone: str, buyer_id: int,
                                   purchase_ref: str = None) -> str:
        """Queue an item for CE-cycle delivery. NO server restart."""
        job_id = str(uuid.uuid4())[:8].upper()
        job = {
            'job_id': job_id,
            'job_type': 'item',
            'item_class': item_class,
            'quantity': quantity,
            'delivery_zone': delivery_zone,
            'buyer_id': buyer_id,
            'purchase_ref': purchase_ref,
        }
        # Log to DB
        revert_at = datetime.now() + timedelta(seconds=7200)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO delivery_queue
                   (job_type, item_class, quantity, delivery_zone, buyer_discord_id, purchase_ref, revert_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ('item', item_class, quantity, delivery_zone, buyer_id,
                 purchase_ref, revert_at.isoformat())
            )
            await db.commit()
        await self.queue.add(job)
        return job_id

    async def queue_vehicle_delivery(self, vehicle_class: str, delivery_zone: str,
                                      buyer_id: int, fully_kitted: bool = True,
                                      purchase_ref: str = None) -> str:
        """Queue a vehicle for CE-cycle delivery. NO server restart."""
        job_id = str(uuid.uuid4())[:8].upper()
        job = {
            'job_id': job_id,
            'job_type': 'vehicle',
            'item_class': vehicle_class,
            'quantity': 1,
            'delivery_zone': delivery_zone,
            'buyer_id': buyer_id,
            'fully_kitted': fully_kitted,
            'purchase_ref': purchase_ref,
        }
        revert_at = datetime.now() + timedelta(seconds=14400)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO delivery_queue
                   (job_type, item_class, quantity, delivery_zone, buyer_discord_id, purchase_ref, revert_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ('vehicle', vehicle_class, 1, delivery_zone, buyer_id,
                 purchase_ref, revert_at.isoformat())
            )
            await db.commit()
        await self.queue.add(job)
        return job_id

    async def execute_job(self, job: dict):
        if job['job_type'] == 'item':
            await self._deliver_item(job)
        elif job['job_type'] == 'vehicle':
            await self._deliver_vehicle(job)

    async def _deliver_item(self, job: dict):
        """Bump nominal+min in types.xml. CE spawns on next cycle. No restart."""
        sid = os.getenv('NITRADO_SERVER_ID')
        path = f'/games/{sid}/noftp/dayzxbox/config/dayzStandalone/mpmissions/dayzOffline.chernarusplus/db/types.xml'

        xml_str = await self.nitrado.download_file(path)
        tree = ET.fromstring(xml_str)

        original_nominal = None
        found = False
        for type_elem in tree.findall('type'):
            if type_elem.get('name') == job['item_class']:
                nominal_elem = type_elem.find('nominal')
                min_elem = type_elem.find('min')
                restock_elem = type_elem.find('restock')
                lifetime_elem = type_elem.find('lifetime')

                original_nominal = int(nominal_elem.text) if nominal_elem is not None else 0
                new_val = original_nominal + job['quantity']

                if nominal_elem is not None: nominal_elem.text = str(new_val)
                if min_elem is not None: min_elem.text = str(new_val)
                if restock_elem is not None: restock_elem.text = '0'      # next CE cycle
                if lifetime_elem is not None: lifetime_elem.text = '7200' # 2hr pickup window
                found = True
                break

        if not found:
            raise ValueError(f'Item class {job["item_class"]} not found in types.xml')

        await self.nitrado.upload_file(path, ET.tostring(tree, encoding='unicode'))

        # Update DB status
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE delivery_queue SET status = 'complete', xml_file_edited = ?, completed_at = ? WHERE job_type = ? AND item_class = ? AND status = 'pending'",
                (path, datetime.now().isoformat(), 'item', job['item_class'])
            )
            await db.commit()

    async def _deliver_vehicle(self, job: dict):
        """Inject vehicle event in events.xml. CE spawns on next cycle. No restart."""
        sid = os.getenv('NITRADO_SERVER_ID')
        path = f'/games/{sid}/noftp/dayzxbox/config/dayzStandalone/mpmissions/dayzOffline.chernarusplus/events.xml'
        zone = DELIVERY_ZONES.get(job['delivery_zone'], DELIVERY_ZONES['NWAF'])

        xml_str = await self.nitrado.download_file(path)
        tree = ET.fromstring(xml_str)

        # Build event element
        event_name = f'VehiclePurchase_{job["job_id"]}'
        event = ET.SubElement(tree, 'event', name=event_name)
        ET.SubElement(event, 'nominal').text = '1'
        ET.SubElement(event, 'min').text = '1'
        ET.SubElement(event, 'max').text = '1'
        ET.SubElement(event, 'lifetime').text = '14400'
        ET.SubElement(event, 'restock').text = '0'   # CE spawns next cycle
        ET.SubElement(event, 'saferadius').text = '5'
        ET.SubElement(event, 'distanceradius').text = '5'
        ET.SubElement(event, 'cleanupradius').text = '10'
        child = ET.SubElement(event, 'child', lootmax='0', lootmin='0',
                               max='1', min='1', type=job['item_class'])
        # Position
        pos = ET.SubElement(event, 'pos')
        pos.set('x', str(zone['x']))
        pos.set('z', str(zone['z']))
        pos.set('a', '0')

        await self.nitrado.upload_file(path, ET.tostring(tree, encoding='unicode'))

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE delivery_queue SET status = 'complete', xml_file_edited = ?, completed_at = ? WHERE job_type = ? AND item_class = ? AND status = 'pending'",
                (path, datetime.now().isoformat(), 'vehicle', job['item_class'])
            )
            await db.commit()

    async def mark_job_failed(self, job: dict, error: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE delivery_queue SET status = 'failed' WHERE item_class = ? AND status = 'pending'",
                (job['item_class'],)
            )
            await db.commit()
