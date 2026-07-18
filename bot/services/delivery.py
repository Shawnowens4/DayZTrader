"""
Delivery Service
Edits DayZ CE XML files via Nitrado API.
NEVER restarts the server - CE cycle handles spawning.
"""

import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import json
import os

log = logging.getLogger('DeliveryService')

# Pre-configured safe delivery zones
DELIVERY_ZONES: Dict[str, Dict] = {
    'NWAF':         {'x': 4500.0, 'z': 10200.0, 'label': 'Northwest Airfield'},
    'Balota':       {'x': 4800.0, 'z': 2400.0,  'label': 'Balota Airstrip'},
    'Berezino':     {'x': 13600.0,'z': 6100.0,  'label': 'Berezino'},
    'Elektro':      {'x': 11800.0,'z': 2300.0,  'label': 'Elektrozavodsk'},
    'Cherno':       {'x': 9100.0, 'z': 2300.0,  'label': 'Chernogorsk'},
    'Vybor':        {'x': 4200.0, 'z': 9300.0,  'label': 'Vybor'},
    'Zelenogorsk':  {'x': 2500.0, 'z': 5800.0,  'label': 'Zelenogorsk'},
    'Stary_Sobor':  {'x': 6000.0, 'z': 9000.0,  'label': 'Stary Sobor'},
}


@dataclass
class DeliveryJob:
    purchase_id: int
    item_class: str
    item_display: str
    is_vehicle: bool
    delivery_zone: str
    quantity: int = 1
    fully_kitted: bool = True
    attachments: List[Dict] = field(default_factory=list)
    container_items: List[Dict] = field(default_factory=list)
    discord_id: int = 0
    status: str = 'pending'
    created_at: datetime = field(default_factory=datetime.now)


class NitradoAPI:
    """Nitrado file server API wrapper"""

    def __init__(self, token: str, server_id: str):
        self.token = token
        self.server_id = server_id
        self.base = 'https://api.nitrado.net'
        self.mission = f'/games/{server_id}/ftp/dayzxb_missions/dayzOffline.chernarusplus'

    @property
    def headers(self):
        return {'Authorization': f'Bearer {self.token}'}

    async def download_file(self, relative_path: str) -> str:
        url = f'{self.base}/services/{self.server_id}/gameservers/file_server/download'
        params = {'file': f'{self.mission}/{relative_path}'}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=self.headers, params=params) as r:
                r.raise_for_status()
                data = await r.json()
                # Nitrado returns a token URL for actual file
                file_url = data['data']['token']['url']
            async with s.get(file_url) as fr:
                return await fr.text()

    async def upload_file(self, relative_path: str, content: str):
        url = f'{self.base}/services/{self.server_id}/gameservers/file_server/upload'
        params = {'path': f'{self.mission}/', 'file': relative_path.split('/')[-1]}
        form = aiohttp.FormData()
        form.add_field('file', content, filename=relative_path.split('/')[-1],
                       content_type='application/xml')
        async with aiohttp.ClientSession() as s:
            async with s.post(url, headers=self.headers, params=params, data=form) as r:
                r.raise_for_status()
                log.info(f'Uploaded {relative_path} to Nitrado')


class DeliveryService:
    """
    Handles all CE XML edits for item/vehicle delivery.
    Uses an async queue to serialize all file edits.
    NEVER calls server restart.
    CE cycle (~1-5 min) handles actual spawning.
    """

    TYPES_PATH = 'db/types.xml'
    EVENTS_PATH = 'db/events.xml'
    SPAWNABLE_PATH = 'db/cfgspawnabletypes.xml'

    def __init__(self, nitrado: NitradoAPI, db, bot=None):
        self.nitrado = nitrado
        self.db = db
        self.bot = bot
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._lock = asyncio.Lock()
        self._running = False

    async def start(self):
        """Start the delivery queue processor"""
        self._running = True
        asyncio.create_task(self._process_loop())
        log.info('Delivery queue started')

    async def queue_delivery(self, job: DeliveryJob):
        """Add a delivery job to the queue"""
        await self._queue.put(job)
        log.info(f'Queued delivery: {job.item_class} for {job.discord_id}')

    async def _process_loop(self):
        """Process deliveries one at a time - prevents XML race conditions"""
        while self._running:
            job = await self._queue.get()
            async with self._lock:
                try:
                    if job.is_vehicle:
                        await self._deliver_vehicle(job)
                    else:
                        await self._deliver_item(job)
                    await asyncio.sleep(3)  # Brief pause between file edits
                except Exception as e:
                    log.error(f'Delivery failed for {job.item_class}: {e}')
                    await self._handle_failed_delivery(job, str(e))
                finally:
                    self._queue.task_done()

    # ==================== ITEM DELIVERY ====================

    async def _deliver_item(self, job: DeliveryJob):
        """Edit types.xml to trigger CE spawn - no restart"""
        log.info(f'Delivering item: {job.item_class} to {job.delivery_zone}')

        xml_text = await self.nitrado.download_file(self.TYPES_PATH)
        tree = ET.fromstring(xml_text)

        original_nominal = None
        original_min = None
        found = False

        for type_elem in tree.findall('type'):
            if type_elem.get('name') == job.item_class:
                found = True
                nominal_el = type_elem.find('nominal')
                min_el = type_elem.find('min')
                restock_el = type_elem.find('restock')
                lifetime_el = type_elem.find('lifetime')

                original_nominal = int(nominal_el.text) if nominal_el is not None else 0
                original_min = int(min_el.text) if min_el is not None else 0

                # Bump nominal and min to force CE to spawn
                if nominal_el is not None:
                    nominal_el.text = str(original_nominal + job.quantity)
                if min_el is not None:
                    min_el.text = str(original_min + job.quantity)
                if restock_el is not None:
                    restock_el.text = '0'  # spawn on next CE cycle
                if lifetime_el is not None:
                    lifetime_el.text = '7200'  # 2hr pickup window
                break

        if not found:
            log.warning(f'Item {job.item_class} not found in types.xml')
            await self._handle_failed_delivery(job, 'Item not found in types.xml')
            return

        updated_xml = ET.tostring(tree, encoding='unicode')
        await self.nitrado.upload_file(self.TYPES_PATH, updated_xml)

        # Update delivery queue DB record
        await self.db.execute(
            "UPDATE delivery_queue SET status='written', original_nominal=?, original_min=?, "
            "revert_at=?, updated_at=CURRENT_TIMESTAMP WHERE purchase_id=?",
            (original_nominal, original_min,
             datetime.now() + timedelta(seconds=7200),
             job.purchase_id)
        )
        await self.db.commit()

        # Notify player - CE will spawn within ~1-5 minutes
        await self._notify_player(job, spawning=True)

        # Schedule revert after pickup window
        asyncio.create_task(
            self._revert_item(job, original_nominal, original_min, delay=7200)
        )

    # ==================== VEHICLE DELIVERY ====================

    async def _deliver_vehicle(self, job: DeliveryJob):
        """Inject vehicle event into events.xml - no restart"""
        log.info(f'Delivering vehicle: {job.item_class} to {job.delivery_zone}')

        zone = DELIVERY_ZONES.get(job.delivery_zone)
        if not zone:
            await self._handle_failed_delivery(job, f'Unknown zone: {job.delivery_zone}')
            return

        # Step 1: Inject event into events.xml
        events_xml = await self.nitrado.download_file(self.EVENTS_PATH)
        events_tree = ET.fromstring(events_xml)

        event_name = f'VehicleDelivery_{job.item_class}_{job.purchase_id}'
        new_event = ET.SubElement(events_tree, 'event')
        new_event.set('name', event_name)

        ET.SubElement(new_event, 'nominal').text = '1'
        ET.SubElement(new_event, 'min').text = '1'
        ET.SubElement(new_event, 'max').text = '1'
        ET.SubElement(new_event, 'lifetime').text = '14400'  # 4hr
        ET.SubElement(new_event, 'restock').text = '0'
        ET.SubElement(new_event, 'saferadius').text = '10'
        ET.SubElement(new_event, 'distanceradius').text = '20'
        ET.SubElement(new_event, 'cleanupradius').text = '200'
        ET.SubElement(new_event, 'secondary').text = 'StaticHeliCrash'
        ET.SubElement(new_event, 'flags').set('deletable', '0')
        ET.SubElement(new_event, 'flags').set('init_random', '0')
        ET.SubElement(new_event, 'flags').set('remove_damaged', '1')

        pos_elem = ET.SubElement(new_event, 'pos')
        pos_elem.set('x', str(zone['x']))
        pos_elem.set('a', '0')
        pos_elem.set('z', str(zone['z']))

        child_elem = ET.SubElement(new_event, 'child')
        child_elem.set('lootmax', '0')
        child_elem.set('lootmin', '0')
        child_elem.set('max', '1')
        child_elem.set('min', '1')
        child_elem.set('type', job.item_class)

        updated_events = ET.tostring(events_tree, encoding='unicode')
        await self.nitrado.upload_file(self.EVENTS_PATH, updated_events)

        # Step 2: Apply full kit attachments if requested
        if job.fully_kitted and job.attachments:
            await self._apply_vehicle_attachments(job)

        # Update DB
        await self.db.execute(
            "UPDATE delivery_queue SET status='written', revert_at=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE purchase_id=?",
            (datetime.now() + timedelta(seconds=14400), job.purchase_id)
        )
        await self.db.commit()

        await self._notify_player(job, spawning=True)

        # Schedule event cleanup after pickup window
        asyncio.create_task(
            self._cleanup_vehicle_event(event_name, job, delay=14400)
        )

    # ==================== REVERT / CLEANUP ====================

    async def _revert_item(self, job: DeliveryJob, orig_nominal: int,
                           orig_min: int, delay: int):
        """Restore types.xml after pickup window - no restart"""
        await asyncio.sleep(delay)
        try:
            xml_text = await self.nitrado.download_file(self.TYPES_PATH)
            tree = ET.fromstring(xml_text)
            for type_elem in tree.findall('type'):
                if type_elem.get('name') == job.item_class:
                    nominal_el = type_elem.find('nominal')
                    min_el = type_elem.find('min')
                    if nominal_el is not None:
                        nominal_el.text = str(orig_nominal)
                    if min_el is not None:
                        min_el.text = str(orig_min)
                    break
            await self.nitrado.upload_file(self.TYPES_PATH, ET.tostring(tree, encoding='unicode'))
            await self.db.execute(
                "UPDATE delivery_queue SET status='reverted' WHERE purchase_id=?",
                (job.purchase_id,)
            )
            await self.db.commit()
            log.info(f'Reverted types.xml for {job.item_class}')
        except Exception as e:
            log.error(f'Revert failed for {job.item_class}: {e}')

    async def _cleanup_vehicle_event(self, event_name: str, job: DeliveryJob, delay: int):
        """Remove vehicle event from events.xml after pickup window"""
        await asyncio.sleep(delay)
        try:
            events_xml = await self.nitrado.download_file(self.EVENTS_PATH)
            tree = ET.fromstring(events_xml)
            for event in tree.findall('event'):
                if event.get('name') == event_name:
                    tree.remove(event)
                    break
            await self.nitrado.upload_file(self.EVENTS_PATH, ET.tostring(tree, encoding='unicode'))
            await self.db.execute(
                "UPDATE delivery_queue SET status='reverted' WHERE purchase_id=?",
                (job.purchase_id,)
            )
            await self.db.commit()
            log.info(f'Cleaned up vehicle event: {event_name}')
        except Exception as e:
            log.error(f'Vehicle event cleanup failed: {e}')

    async def _apply_vehicle_attachments(self, job: DeliveryJob):
        """Patch cfgspawnabletypes.xml with full kit attachments"""
        xml_text = await self.nitrado.download_file(self.SPAWNABLE_PATH)
        tree = ET.fromstring(xml_text)
        # Add or update vehicle entry with attachments
        # (builder tool populates job.attachments from the vehicle builder UI)
        existing = None
        for vtype in tree.findall('type'):
            if vtype.get('name') == job.item_class:
                existing = vtype
                break
        if existing is None:
            existing = ET.SubElement(tree, 'type')
            existing.set('name', job.item_class)
        # Clear old attachments
        for old in existing.findall('attachments'):
            existing.remove(old)
        # Add new
        for attachment_group in job.attachments:
            att_el = ET.SubElement(existing, 'attachments')
            att_el.set('chance', str(attachment_group.get('chance', 1.0)))
            for item in attachment_group.get('items', []):
                item_el = ET.SubElement(att_el, 'item')
                item_el.set('name', item['class'])
                item_el.set('chance', str(item.get('chance', 1.0)))
        await self.nitrado.upload_file(self.SPAWNABLE_PATH, ET.tostring(tree, encoding='unicode'))

    # ==================== NOTIFICATIONS ====================

    async def _notify_player(self, job: DeliveryJob, spawning: bool = False):
        if not self.bot:
            return
        try:
            user = await self.bot.fetch_user(job.discord_id)
            if spawning:
                zone = DELIVERY_ZONES.get(job.delivery_zone, {})
                embed = discord.Embed(
                    title='📦 Delivery In Progress',
                    description=f'Your **{job.item_display}** is being prepared!',
                    color=0x00ff88
                )
                embed.add_field(name='📍 Delivery Zone', value=zone.get('label', job.delivery_zone))
                embed.add_field(name='⏱ ETA', value='~1-5 minutes (next CE cycle)')
                embed.add_field(
                    name='⏰ Pickup Window',
                    value='2 hours (items) / 4 hours (vehicles)',
                    inline=False
                )
                embed.set_footer(text='Server is NOT restarting — CE cycle handles delivery automatically')
                await user.send(embed=embed)
        except Exception as e:
            log.warning(f'Could not DM player {job.discord_id}: {e}')

    async def _handle_failed_delivery(self, job: DeliveryJob, error: str):
        log.error(f'Delivery failed: {job.item_class} / {error}')
        await self.db.execute(
            "UPDATE delivery_queue SET status='failed' WHERE purchase_id=?",
            (job.purchase_id,)
        )
        await self.db.commit()
