"""
Delivery Service - CE cycle-based item/vehicle spawning via Nitrado API
NEVER restarts the server. Edits XML files and lets CE do the work.
Fixed:
  - delivery_queue INSERT columns match schema (discord_id, not buyer_discord_id)
  - UPDATE no longer references xml_file_edited (not in schema)
  - Returns dict with success/message for DeliveryQueue compatibility
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

DELIVERY_ZONES = {
    'NWAF':     {'x': 4541.0, 'z': 11254.0, 'y': 0, 'description': 'Northwest Airfield'},
    'Berezino': {'x': 11822.0, 'z': 9234.0,  'y': 0, 'description': 'Berezino'},
    'Elektro':  {'x': 10440.0, 'z': 2500.0,  'y': 0, 'description': 'Elektrozavodsk'},
    'Cherno':   {'x': 7200.0,  'z': 2400.0,  'y': 0, 'description': 'Chernogorsk'},
    'Balota':   {'x': 6091.0,  'z': 2400.0,  'y': 0, 'description': 'Balota Airstrip'},
    'NEAF':     {'x': 13412.0, 'z': 13100.0, 'y': 0, 'description': 'Northeast Airfield'},
    'Tisy':     {'x': 1050.0,  'z': 13210.0, 'y': 0, 'description': 'Tisy Military'},
    'Vybor':    {'x': 3700.0,  'z': 9200.0,  'y': 0, 'description': 'Vybor'},
}


class NitradoAPI:
    def __init__(self):
        self.token = os.getenv('NITRADO_TOKEN')
        self.server_id = os.getenv('NITRADO_SERVER_ID')
        self.base = 'https://api.nitrado.net'
        self.file_base = f'{self.base}/services/{self.server_id}/gameservers/file_server'

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


class DeliveryService:
    def __init__(self):
        self.nitrado = NitradoAPI()
        self.db_path = DB_PATH

    async def queue_item_delivery(
        self, item_class: str, quantity: int,
        delivery_zone: str, buyer_id: int = 0,
        purchase_ref: str = None
    ) -> dict:
        """Queue an item for CE-cycle delivery. Returns {success, job_id}."""
        revert_at = datetime.now() + timedelta(seconds=7200)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'INSERT INTO delivery_queue '
                '(job_type, item_class, item_display, quantity, delivery_zone, discord_id, revert_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                ('item', item_class, item_class, quantity,
                 delivery_zone, buyer_id, revert_at.isoformat())
            )
            job_id = cursor.lastrowid
            await db.commit()
        # Kick off the actual XML edit
        asyncio.create_task(
            self._deliver_item({
                'job_id': job_id,
                'job_type': 'item',
                'item_class': item_class,
                'quantity': quantity,
                'delivery_zone': delivery_zone,
            })
        )
        return {'success': True, 'job_id': job_id}

    async def queue_vehicle_delivery(
        self, vehicle_class: str, delivery_zone: str,
        fully_kitted: bool = True, buyer_id: int = 0,
        purchase_ref: str = None
    ) -> dict:
        """Queue a vehicle for CE-cycle delivery. Returns {success, job_id}."""
        revert_at = datetime.now() + timedelta(seconds=14400)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'INSERT INTO delivery_queue '
                '(job_type, item_class, item_display, quantity, delivery_zone, discord_id, is_vehicle, fully_kitted, revert_at) '
                'VALUES (?, ?, ?, 1, ?, ?, 1, ?, ?)',
                ('vehicle', vehicle_class, vehicle_class,
                 delivery_zone, buyer_id, int(fully_kitted), revert_at.isoformat())
            )
            job_id = cursor.lastrowid
            await db.commit()
        asyncio.create_task(
            self._deliver_vehicle({
                'job_id': job_id,
                'job_type': 'vehicle',
                'item_class': vehicle_class,
                'quantity': 1,
                'delivery_zone': delivery_zone,
                'fully_kitted': fully_kitted,
            })
        )
        return {'success': True, 'job_id': job_id}

    async def _deliver_item(self, job: dict):
        sid = os.getenv('NITRADO_SERVER_ID')
        path = (
            f'/games/{sid}/noftp/dayzxbox/config/dayzStandalone'
            '/mpmissions/dayzOffline.chernarusplus/db/types.xml'
        )
        try:
            xml_str = await self.nitrado.download_file(path)
            tree = ET.fromstring(xml_str)
            found = False
            for type_elem in tree.findall('type'):
                if type_elem.get('name') == job['item_class']:
                    nominal_elem = type_elem.find('nominal')
                    min_elem = type_elem.find('min')
                    restock_elem = type_elem.find('restock')
                    lifetime_elem = type_elem.find('lifetime')
                    original = int(nominal_elem.text) if nominal_elem is not None else 0
                    new_val = original + job['quantity']
                    if nominal_elem is not None: nominal_elem.text = str(new_val)
                    if min_elem is not None: min_elem.text = str(new_val)
                    if restock_elem is not None: restock_elem.text = '0'
                    if lifetime_elem is not None: lifetime_elem.text = '7200'
                    found = True
                    break
            if not found:
                raise ValueError(f'Item class {job["item_class"]} not found in types.xml')
            await self.nitrado.upload_file(path, ET.tostring(tree, encoding='unicode'))
            await self._mark_complete(job['job_id'])
        except Exception as e:
            await self._mark_failed(job['job_id'], str(e))
            raise

    async def _deliver_vehicle(self, job: dict):
        sid = os.getenv('NITRADO_SERVER_ID')
        path = (
            f'/games/{sid}/noftp/dayzxbox/config/dayzStandalone'
            '/mpmissions/dayzOffline.chernarusplus/events.xml'
        )
        zone = DELIVERY_ZONES.get(job['delivery_zone'], DELIVERY_ZONES['NWAF'])
        try:
            xml_str = await self.nitrado.download_file(path)
            tree = ET.fromstring(xml_str)
            event_name = f'VehiclePurchase_{job["job_id"]}'
            event = ET.SubElement(tree, 'event', name=event_name)
            ET.SubElement(event, 'nominal').text = '1'
            ET.SubElement(event, 'min').text = '1'
            ET.SubElement(event, 'max').text = '1'
            ET.SubElement(event, 'lifetime').text = '14400'
            ET.SubElement(event, 'restock').text = '0'
            ET.SubElement(event, 'saferadius').text = '5'
            ET.SubElement(event, 'distanceradius').text = '5'
            ET.SubElement(event, 'cleanupradius').text = '10'
            ET.SubElement(event, 'child', lootmax='0', lootmin='0',
                          max='1', min='1', type=job['item_class'])
            pos = ET.SubElement(event, 'pos')
            pos.set('x', str(zone['x']))
            pos.set('z', str(zone['z']))
            pos.set('a', '0')
            await self.nitrado.upload_file(path, ET.tostring(tree, encoding='unicode'))
            await self._mark_complete(job['job_id'])
        except Exception as e:
            await self._mark_failed(job['job_id'], str(e))
            raise

    async def _mark_complete(self, job_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE delivery_queue SET status = 'complete', processed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), job_id)
            )
            await db.commit()

    async def _mark_failed(self, job_id, error: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE delivery_queue SET status = 'failed', processed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), job_id)
            )
            await db.commit()
