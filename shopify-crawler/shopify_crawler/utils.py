import re
import concurrent
import asyncio
from datetime import datetime
import pytz


import aiohttp
from google.cloud import firestore


class FirestoreBatchClient:
    DEFAULT_BATCH_SIZE = 10

    def __init__(self, *, max_batch_size: int = None):
        self.db = firestore.Client()
        self.batch_client = self.db.batch()
        self._count = 0
        self.max_batch_size = max_batch_size or self.DEFAULT_BATCH_SIZE
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)

    async def set(self, collection: str, id: str, value: dict):
        event_loop = asyncio.get_event_loop()
        return await event_loop.run_in_executor(
            self.executor, self._set, collection, id, value
        )

    async def exists(self, collection: str, id: str) -> bool:
        event_loop = asyncio.get_event_loop()
        snapshot = await event_loop.run_in_executor(
            self.executor, self._get, collection, id
        )
        return snapshot.exists

    def _get(self, collection: str, id: str):
        cref = self.db.collection(collection).document(id)
        return cref.get()

    def _set(self, collection: str, id: str, value: dict):
        print("Adding a new document", id)
        cref = self.db.collection(collection).document(id)
        self.batch_client.set(cref, value)
        self._count += 1
        if self._count % self.max_batch_size == 0:
            self.batch_client.commit()
            print(f"Added {self.max_batch_size} documents")


class AirtableException(Exception):
    pass


class AirtableClient:
    BASE_URL = "https://api.airtable.com/v0/apppHLxW7K18N7S3c/app-list"

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = aiohttp.ClientSession()

    @property
    def headers(self):
        return {"Authorization": "Bearer {}".format(self.api_key)}

    async def add_row(self, row):
        resp = await self.session.post(
            self.BASE_URL, json={"fields": row}, headers=self.headers
        )
        if resp.status >= 400:
            resp_json = await resp.json()
            error = resp_json["error"]["message"]
            raise AirtableException(error)


def slugify(name: str) -> str:
    slug = re.sub(r"\W", "-", name.lower())
    slug = re.sub(r"-+", "-", slug)
    return slug.strip()


def utcnow() -> datetime:
    return datetime.utcnow().replace(microsecond=0, tzinfo=pytz.utc)