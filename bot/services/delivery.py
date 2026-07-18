"""
Delivery Service - Edits DayZ XML files via Nitrado API.
NEVER forces a server restart. CE cycle handles all spawns naturally.
"""
import aiohttp
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional
import os
import yaml

with open("config/settings.yaml") as f:
    CONFIG = yaml.safe_load(f)

DELIVERY_ZONES = CONFIG["delivery"]["delivery_zones"]
CE_WAIT = CONFIG["delivery"]["ce_cycle_wait_seconds"]
ITEM_LIFETIME = CONFIG["delivery"]["item_lifetime_seconds"]
VEHICLE_LIFETIME = CONFIG["delivery"]["vehicle_lifetime_seconds"]

NITRADO_BASE = "https://api.nitrado.net"

class NitradoAPI:
    def __init__(self, token: str, server_id: str):
        self.token = token
        self.server_id = server_id
        self.headers = {"Authorization": f"Bearer {token}"}
        self.file_base = f"{NITRADO_BASE}/services/{server_id}/gameservers/file_server"

    def _resolve_path(self, path_template: str) -> str:
        return path_template.replace("{server_id}", self.server_id)

    async def download_file(self, path_template: str) -> str:
        path = self._resolve_path(path_template)
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(f"{self.file_base}/download", params={"file": path}) as resp:
                resp.raise_for_status()
                data = await resp.json()
                # Nitrado returns a temp download URL
                dl_url = data["data"]["token"]["url"]
            async with session.get(dl_url) as file_resp:
                return await file_resp.text()

    async def upload_file(self, path_template: str, content: str):
        path = self._resolve_path(path_template)
        async with aiohttp.ClientSession(headers=self.headers) as session:
            form = aiohttp.FormData()
            form.add_field("path", os.path.dirname(path))
            form.add_field("file", content, filename=os.path.basename(path), content_type="text/xml")
            async with session.post(f"{self.file_base}/upload", data=form) as resp:
                resp.raise_for_status()

class DeliveryService:
    def __init__(self, nitrado_token: str, server_id: str):
        self.api = NitradoAPI(nitrado_token, server_id)
        self._revert_tasks = []  # Track scheduled reverts

    # ========================
    # ITEM DELIVERY (types.xml)
    # ========================

    async def queue_item_delivery(self, item_class: str, quantity: int = 1,
                                   delivery_zone: str = "NWAF") -> dict:
        """
        Bumps nominal/min in types.xml and sets restock=0.
        CE engine picks this up on its next natural cycle.
        Server is NEVER restarted.
        """
        try:
            types_path = CONFIG["delivery"]["types_xml_path"]
            xml_str = await self.api.download_file(types_path)
            tree = ET.fromstring(xml_str)

            original_nominal = None
            found = False

            for type_elem in tree.findall("type"):
                if type_elem.get("name") == item_class:
                    found = True
                    nom_el = type_elem.find("nominal")
                    min_el = type_elem.find("min")
                    restock_el = type_elem.find("restock")
                    lifetime_el = type_elem.find("lifetime")

                    original_nominal = int(nom_el.text) if nom_el is not None else 0

                    if nom_el is not None:
                        nom_el.text = str(original_nominal + quantity)
                    if min_el is not None:
                        min_el.text = str(original_nominal + quantity)
                    if restock_el is not None:
                        restock_el.text = "0"  # spawn on next CE cycle
                    if lifetime_el is not None:
                        lifetime_el.text = str(ITEM_LIFETIME)
                    break

            if not found:
                return {"success": False, "message": f"Item class '{item_class}' not found in types.xml"}

            updated_xml = ET.tostring(tree, encoding="unicode", xml_declaration=True)
            await self.api.upload_file(types_path, updated_xml)

            # Schedule revert after pickup window — no restart ever
            asyncio.create_task(
                self._revert_item(item_class, original_nominal, ITEM_LIFETIME)
            )

            return {
                "success": True,
                "item_class": item_class,
                "delivery_zone": delivery_zone,
                "ce_wait_seconds": CE_WAIT,
                "pickup_window_seconds": ITEM_LIFETIME
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _revert_item(self, item_class: str, original_nominal: int, delay: int):
        """After pickup window, revert nominal/min back. No restart needed."""
        await asyncio.sleep(delay)
        try:
            types_path = CONFIG["delivery"]["types_xml_path"]
            xml_str = await self.api.download_file(types_path)
            tree = ET.fromstring(xml_str)
            for type_elem in tree.findall("type"):
                if type_elem.get("name") == item_class:
                    nom_el = type_elem.find("nominal")
                    min_el = type_elem.find("min")
                    restock_el = type_elem.find("restock")
                    if nom_el is not None:
                        nom_el.text = str(original_nominal)
                    if min_el is not None:
                        min_el.text = str(max(0, original_nominal - 1))
                    if restock_el is not None:
                        restock_el.text = "1800"  # restore default restock
                    break
            await self.api.upload_file(types_path, ET.tostring(tree, encoding="unicode", xml_declaration=True))
        except Exception:
            pass  # Revert failure is non-critical

    # ===========================
    # VEHICLE DELIVERY (events.xml)
    # ===========================

    async def queue_vehicle_delivery(self, vehicle_class: str,
                                      delivery_zone: str = "NWAF",
                                      fully_kitted: bool = True) -> dict:
        """
        Injects a one-time vehicle spawn event into events.xml.
        Uses coordinates from the chosen delivery zone.
        CE processes on next natural cycle. NO restart.
        """
        try:
            if delivery_zone not in DELIVERY_ZONES:
                return {"success": False, "message": f"Unknown delivery zone: {delivery_zone}"}

            coords = DELIVERY_ZONES[delivery_zone]
            events_path = CONFIG["delivery"]["events_xml_path"]
            xml_str = await self.api.download_file(events_path)
            root = ET.fromstring(xml_str)

            # Build event element
            event_name = f"VehicleDelivery_{vehicle_class}_{int(datetime.now().timestamp())}"
            event = ET.SubElement(root, "event")
            event.set("name", event_name)

            ET.SubElement(event, "nominal").text = "1"
            ET.SubElement(event, "min").text = "1"
            ET.SubElement(event, "max").text = "1"
            ET.SubElement(event, "lifetime").text = str(VEHICLE_LIFETIME)
            ET.SubElement(event, "restock").text = "0"  # spawn next CE cycle
            ET.SubElement(event, "saferadius").text = "500"
            ET.SubElement(event, "distanceradius").text = "500"
            ET.SubElement(event, "cleanupradius").text = "200"

            children = ET.SubElement(event, "children")
            child = ET.SubElement(children, "child")
            child.set("lootmax", "0")
            child.set("lootmin", "0")
            child.set("max", "1")
            child.set("min", "1")
            child.set("type", vehicle_class)

            # Set spawn position
            pos = ET.SubElement(event, "position")
            pos.set("x", str(coords["x"]))
            pos.set("z", str(coords["z"]))

            updated_xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
            await self.api.upload_file(events_path, updated_xml)

            if fully_kitted:
                await self._apply_vehicle_attachments(vehicle_class)

            # Schedule cleanup of this event entry
            asyncio.create_task(
                self._cleanup_vehicle_event(event_name, VEHICLE_LIFETIME)
            )

            return {
                "success": True,
                "vehicle_class": vehicle_class,
                "delivery_zone": delivery_zone,
                "coords": coords,
                "ce_wait_seconds": CE_WAIT,
                "pickup_window_seconds": VEHICLE_LIFETIME
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _apply_vehicle_attachments(self, vehicle_class: str):
        """Patch cfgspawnabletypes.xml to give vehicle full parts/attachments."""
        try:
            path = CONFIG["delivery"]["cfgspawnabletypes_path"]
            xml_str = await self.api.download_file(path)
            root = ET.fromstring(xml_str)
            # Check if entry already exists
            for vtype in root.findall("type"):
                if vtype.get("name") == vehicle_class:
                    return  # Already has attachments defined
            # Add fully kitted entry
            vtype = ET.SubElement(root, "type")
            vtype.set("name", vehicle_class)
            attachments = ET.SubElement(vtype, "attachments")
            attachments.set("chance", "1.00")
            # Generic full-kit attachment slots — customize per vehicle as needed
            for slot in ["CarBattery", "SparkPlug", "CarRadiator",
                          "CarWheel", "CarWheel", "CarWheel", "CarWheel",
                          "GasolineCanister"]:
                item = ET.SubElement(attachments, "item")
                item.set("name", slot)
                item.set("chance", "1.00")
            updated = ET.tostring(root, encoding="unicode", xml_declaration=True)
            await self.api.upload_file(path, updated)
        except Exception:
            pass

    async def _cleanup_vehicle_event(self, event_name: str, delay: int):
        """Remove the one-time event entry after delivery window expires."""
        await asyncio.sleep(delay)
        try:
            events_path = CONFIG["delivery"]["events_xml_path"]
            xml_str = await self.api.download_file(events_path)
            root = ET.fromstring(xml_str)
            for event in root.findall("event"):
                if event.get("name") == event_name:
                    root.remove(event)
                    break
            await self.api.upload_file(events_path, ET.tostring(root, encoding="unicode", xml_declaration=True))
        except Exception:
            pass
