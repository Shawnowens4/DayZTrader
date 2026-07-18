"""
Delivery Queue - Serializes all XML file edits to prevent race conditions.
Multiple simultaneous purchases are processed one at a time.
NEVER restarts the server.
"""

import asyncio
import sqlite3
from datetime import datetime
from bot.services.delivery import DeliveryJob

class DeliveryQueue:
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._delivery_service = None  # Set after bot init

    def set_delivery_service(self, svc):
        self._delivery_service = svc

    async def add(self, job: DeliveryJob):
        await self._queue.put(job)

    async def process_loop(self):
        """
        Runs forever as a background task.
        Processes one delivery job at a time — no overlapping XML edits.
        """
        while True:
            job: DeliveryJob = await self._queue.get()
            async with self._lock:
                try:
                    if self._delivery_service:
                        if job.job_type == 'item':
                            await self._delivery_service.deliver_item(job)
                        elif job.job_type == 'vehicle':
                            await self._delivery_service.deliver_vehicle(job)
                    # Brief pause between sequential file edits
                    await asyncio.sleep(3)
                except Exception as e:
                    print(f'[DELIVERY QUEUE] Error processing job {job.job_id}: {e}')
                finally:
                    self._queue.task_done()

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()
