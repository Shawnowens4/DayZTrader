"""
Delivery Service - Edits Nitrado XML files for CE-based item/vehicle spawns.

CRITICAL RULE: This service NEVER restarts the server.
All spawns are handled by DayZ's Central Economy cleanup cycle
which runs continuously in the background (~1-5 minutes).

Strategy:
  Items:    Bump nominal/min in types.xml + set restock=0
  Vehicles: Inject one-time event in events.xml + cfgspawnabletypes
  Revert:   Scheduled async task resets values after pickup window
"""

import aiohttp
import asyncio
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional
import yaml

with open('config/settings.yaml') as f:
    _cfg = yaml.safe_load(f)

NITRADO_BASE   = 'https://api.nitrado.net'
TYPES_PATH     = _cfg['nitrado']['files']['types_xml']
EVENTS_PATH    = _cfg['nitrado']['files']['events_xml']
SPAWNABLE_PATH = _cfg['nitrado']['files']['cfgspawnabletypes_xml']

DELIVERY_ZONES = _cfg['delivery']['delivery_zones']
ITEM_LIFETIME  = _cfg['delivery']['item_lifetime_seconds']     # 7200s default
VEH_LIFETIME   = _cfg['delivery']['vehicle_lifetime_seconds']  # 14400s default


@dataclass
class DeliveryJob:
    job_id: int
    job_type: str          # 'item' or 'vehicle'
    item_class: str
    quantity: int = 1
    delivery_zone: str = 'NWAF'
    fully_kitted: bool = False
    purchase_id: Optional[int] = None
    listing_id: Optional[str] = None


class NitradoAPI:
    def __init__(self, token: str, server_id: str):
        self.token = token
        self.server_id = server_id
        self.headers = {'Authorization': f'Bearer {token}'}

    async def download_file(self, path: str) -> str:
        url = f'{NITRADO_BASE}/services/{self.server_id}/gameservers/file_server/download'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={'file': path}, headers=self.headers) as r:
                r.raise_for_status()
                data = await r.json()
                # Nitrado returns a download token URL
                dl_url = data['data']['token']['url']
            async with session.get(dl_url) as r2:
                return await r2.text()

    async def upload_file(self, path: str, content: str):
        url = f'{NITRADO_BASE}/services/{self.server_id}/gameservers/file_server/upload'
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field('path', path)
            form.add_field('file', content, filename='upload.xml', content_type='application/xml')
            async with session.post(url, data=form, headers=self.headers) as r:
                r.raise_for_status()

    # NOTE: restart_server() is intentionally NOT implemented.
    # The CE cycle handles all spawns automatically.


class DeliveryService:
    def __init__(self, nitrado_token: str, server_id: str, queue, db_path: str = 'db/dayz_trader.db'):
        self.api = NitradoAPI(nitrado_token, server_id)
        self.queue = queue
        self.db_path = db_path
        self._revert_tasks = {}  # job_id -> asyncio.Task

    def _conn(self):
        return sqlite3.connect(self.db_path)

    # ─────────────────────────────────────────
    # PUBLIC: Queue a delivery (thread-safe)
    # ─────────────────────────────────────────

    async def queue_delivery(self, job: DeliveryJob):
        """Add delivery to queue. Multiple purchases are serialized safely."""
        with self._conn() as conn:
            conn.execute(
                '''INSERT INTO delivery_jobs
                (purchase_id, listing_id, job_type, item_class, quantity, delivery_zone, status)
                VALUES (?, ?, ?, ?, ?, ?, 'queued')''',
                (job.purchase_id, job.listing_id, job.job_type,
                 job.item_class, job.quantity, job.delivery_zone)
            )
            job.job_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        await self.queue.add(job)

    # ─────────────────────────────────────────
    # ITEM DELIVERY via types.xml
    # ─────────────────────────────────────────

    async def deliver_item(self, job: DeliveryJob):
        """
        Bumps nominal/min in types.xml and sets restock=0.
        CE engine spawns item on its next cycle (1-5 min).
        NEVER restarts server.
        """
        self._set_job_status(job.job_id, 'processing')
        try:
            xml_str = await self.api.download_file(TYPES_PATH)
            root = ET.fromstring(xml_str)

            original_nominal = None
            original_min = None

            for type_elem in root.findall('type'):
                if type_elem.get('name') == job.item_class:
                    nom_el = type_elem.find('nominal')
                    min_el = type_elem.find('min')
                    rst_el = type_elem.find('restock')
                    lft_el = type_elem.find('lifetime')

                    original_nominal = int(nom_el.text) if nom_el is not None else 0
                    original_min = int(min_el.text) if min_el is not None else 0

                    # Bump by quantity — CE sees the deficit and fills it
                    if nom_el is not None: nom_el.text = str(original_nominal + job.quantity)
                    if min_el is not None: min_el.text = str(original_min + job.quantity)
                    # restock=0 means spawn on NEXT CE cycle
                    if rst_el is not None: rst_el.text = '0'
                    # Give player a generous pickup window
                    if lft_el is not None: lft_el.text = str(ITEM_LIFETIME)
                    break

            if original_nominal is None:
                self._set_job_status(job.job_id, 'failed', f'Class {job.item_class} not found in types.xml')
                return

            await self.api.upload_file(TYPES_PATH, ET.tostring(root, encoding='unicode', xml_declaration=True))

            # Store originals for revert
            with self._conn() as conn:
                conn.execute(
                    'UPDATE delivery_jobs SET original_nominal=?, original_min=?, revert_at=? WHERE id=?',
                    (original_nominal, original_min,
                     (datetime.now() + timedelta(seconds=ITEM_LIFETIME)).isoformat(),
                     job.job_id)
                )

            self._set_job_status(job.job_id, 'done')

            # Schedule automatic revert after pickup window
            task = asyncio.create_task(
                self._revert_item_after(job, original_nominal, original_min, ITEM_LIFETIME)
            )
            self._revert_tasks[job.job_id] = task

        except Exception as e:
            self._set_job_status(job.job_id, 'failed', str(e))
            raise

    async def _revert_item_after(self, job: DeliveryJob, orig_nominal: int, orig_min: int, delay: int):
        """Wait for pickup window then reset types.xml back to original values."""
        await asyncio.sleep(delay)
        try:
            xml_str = await self.api.download_file(TYPES_PATH)
            root = ET.fromstring(xml_str)
            for type_elem in root.findall('type'):
                if type_elem.get('name') == job.item_class:
                    nom_el = type_elem.find('nominal')
                    min_el = type_elem.find('min')
                    if nom_el is not None: nom_el.text = str(orig_nominal)
                    if min_el is not None: min_el.text = str(orig_min)
                    break
            await self.api.upload_file(TYPES_PATH, ET.tostring(root, encoding='unicode', xml_declaration=True))
            self._set_job_status(job.job_id, 'reverted')
        except Exception:
            pass  # Revert failure is non-critical

    # ─────────────────────────────────────────
    # VEHICLE DELIVERY via events.xml
    # ─────────────────────────────────────────

    async def deliver_vehicle(self, job: DeliveryJob):
        """
        Injects a one-time vehicle spawn event into events.xml.
        CE engine processes events on next cycle.
        Optionally patches cfgspawnabletypes for full kit.
        NEVER restarts server.
        """
        self._set_job_status(job.job_id, 'processing')
        zone = DELIVERY_ZONES.get(job.delivery_zone, DELIVERY_ZONES['NWAF'])

        try:
            events_str = await self.api.download_file(EVENTS_PATH)
            root = ET.fromstring(events_str)

            event_name = f'VehicleDelivery_{job.item_class}_{job.job_id}'

            event = ET.SubElement(root, 'event')
            event.set('name', event_name)

            ET.SubElement(event, 'nominal').text = '1'
            ET.SubElement(event, 'min').text = '1'
            ET.SubElement(event, 'max').text = '1'
            ET.SubElement(event, 'lifetime').text = str(VEH_LIFETIME)
            ET.SubElement(event, 'restock').text = '0'  # Spawn next CE cycle
            ET.SubElement(event, 'saferadius').text = '5'
            ET.SubElement(event, 'distanceradius').text = '20'
            ET.SubElement(event, 'cleanupradius').text = '200'
            ET.SubElement(event, 'flags').set('deletable', '1')

            child = ET.SubElement(event, 'child')
            child.set('lootmax', '0')
            child.set('lootmin', '0')
            child.set('max', '1')
            child.set('min', '1')
            child.set('type', job.item_class)

            # Set spawn position to chosen delivery zone
            pos = ET.SubElement(event, 'position')
            pos.set('x', str(zone['x']))
            pos.set('y', '0')
            pos.set('z', str(zone['z']))

            await self.api.upload_file(EVENTS_PATH, ET.tostring(root, encoding='unicode', xml_declaration=True))

            # Optionally apply full kit attachments
            if job.fully_kitted:
                await self._apply_vehicle_kit(job.item_class)

            self._set_job_status(job.job_id, 'done')

            # Schedule cleanup of the injected event
            asyncio.create_task(
                self._cleanup_vehicle_event_after(job, event_name, VEH_LIFETIME)
            )

        except Exception as e:
            self._set_job_status(job.job_id, 'failed', str(e))
            raise

    async def _cleanup_vehicle_event_after(self, job: DeliveryJob, event_name: str, delay: int):
        """Remove the injected event from events.xml after pickup window."""
        await asyncio.sleep(delay)
        try:
            events_str = await self.api.download_file(EVENTS_PATH)
            root = ET.fromstring(events_str)
            for event in root.findall('event'):
                if event.get('name') == event_name:
                    root.remove(event)
                    break
            await self.api.upload_file(EVENTS_PATH, ET.tostring(root, encoding='unicode', xml_declaration=True))
            self._set_job_status(job.job_id, 'reverted')
        except Exception:
            pass

    async def _apply_vehicle_kit(self, vehicle_class: str):
        """Patch cfgspawnabletypes to include all parts/attachments for the vehicle."""
        spawnable_str = await self.api.download_file(SPAWNABLE_PATH)
        root = ET.fromstring(spawnable_str)
        # Only add if not already present
        existing = [t.get('name') for t in root.findall('type')]
        if vehicle_class not in existing:
            vtype = ET.SubElement(root, 'type')
            vtype.set('name', vehicle_class)
            # Add all standard vehicle parts
            for part in ['CarRadiator','CarBattery','SparkPlug','CarWheel','CarDoor1','CarDoor2','CarDoor3','CarDoor4']:
                att = ET.SubElement(vtype, 'attachments')
                att.set('chance', '1.00')
                item = ET.SubElement(att, 'item')
                item.set('name', part)
                item.set('chance', '1.00')
            await self.api.upload_file(SPAWNABLE_PATH, ET.tostring(root, encoding='unicode', xml_declaration=True))

    # ─────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────

    def _set_job_status(self, job_id: int, status: str, error: str = None):
        with self._conn() as conn:
            conn.execute(
                'UPDATE delivery_jobs SET status=?, error_text=?, completed_at=? WHERE id=?',
                (status, error, datetime.now().isoformat() if status in ('done','failed','reverted') else None, job_id)
            )

    def get_job_status(self, job_id: int) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute('SELECT status FROM delivery_jobs WHERE id=?', (job_id,)).fetchone()
        return row[0] if row else None
