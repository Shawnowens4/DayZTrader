"""
Delivery Queue - Serializes all XML file edits to prevent race conditions.
Fixed:
  - DeliveryJob uses job_type (not item_type) to match delivery.py and trader.py
  - process_loop calls correct delivery service methods
  - queue_size property exposed for admin panel
"""
import asyncio
from dataclasses import dataclass
from typing import Optional, Callable
from datetime import datetime


@dataclass
class DeliveryJob:
    job_id: str
    job_type: str           # 'item' or 'vehicle'  (was item_type — fixed)
    item_class: str
    delivery_zone: str
    quantity: int = 1
    fully_kitted: bool = False
    buyer_id: int = 0
    purchase_id: Optional[int] = None
    discord_id: Optional[int] = None
    callback: Optional[Callable] = None
    queued_at: datetime = None
    retries: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.queued_at is None:
            self.queued_at = datetime.now()


class DeliveryQueue:
    def __init__(self, delivery_service):
        self.delivery = delivery_service
        self._queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._running = False

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    async def add(self, job: DeliveryJob):
        await self._queue.put(job)
        print(f'[DeliveryQueue] Job queued: {job.job_id} ({job.item_class})')

    async def process_loop(self):
        """Runs forever. Processes one delivery at a time. Never restarts server."""
        self._running = True
        while True:
            job = await self._queue.get()
            async with self._lock:
                try:
                    print(f'[DeliveryQueue] Processing: {job.job_id}')
                    if job.job_type == 'vehicle':
                        result = await self.delivery.queue_vehicle_delivery(
                            job.item_class, job.delivery_zone, job.fully_kitted, job.buyer_id
                        )
                    else:
                        result = await self.delivery.queue_item_delivery(
                            job.item_class, job.quantity, job.delivery_zone, job.buyer_id
                        )

                    if result['success']:
                        print(f'[DeliveryQueue] Success: {job.job_id}')
                        if job.callback:
                            await job.callback(job, result)
                    else:
                        raise Exception(result.get('message', 'Unknown delivery error'))

                except Exception as e:
                    job.retries += 1
                    print(f'[DeliveryQueue] Failed ({job.retries}/{job.max_retries}): {e}')
                    if job.retries < job.max_retries:
                        await asyncio.sleep(30)
                        await self._queue.put(job)
                    else:
                        print(f'[DeliveryQueue] Job {job.job_id} permanently failed.')
                        if job.callback:
                            await job.callback(job, {'success': False, 'message': str(e)})
                finally:
                    self._queue.task_done()
                    await asyncio.sleep(3)
