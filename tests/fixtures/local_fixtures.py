# Copyright 2022 Universität Tübingen, DKFZ and EMBL
# for the German Human Genome-Phenome Archive (GHGA)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime

import pytest_asyncio  # type: ignore
import requests  # type: ignore
from ghga_event_schemas import pydantic_ as event_schemas  # type: ignore
from ghga_service_chassis_lib.utils import big_temp_file  # type: ignore
from hexkit.custom_types import JsonObject  # type: ignore
from hexkit.providers.akafka import KafkaEventPublisher  # type: ignore
from hexkit.providers.akafka.testutils import EventRecorder  # type: ignore
from hexkit.providers.s3 import S3Config, S3ObjectStorage  # type: ignore

from tests.fixtures.config import CONFIG

PART_SIZE = 8 * 1024**2


@dataclass
class CheckablePayloadFields:
    """Fields from recorded event that hold values that can an should be checked"""

    file_id: str
    part_size: int
    content_checksum: str


@dataclass
class RecordedEventFixture:
    """Payload sent and fields that can be checked for equality"""

    payload: JsonObject
    checkable_fields: CheckablePayloadFields


@pytest_asyncio.fixture
async def local_s3_fixture() -> S3ObjectStorage:
    """Clean bucket and object"""
    config = S3Config(
        s3_endpoint_url=CONFIG.s3_endpoint_url,
        s3_access_key_id=CONFIG.s3_access_key_id,
        s3_secret_access_key=CONFIG.s3_access_key_id,
    )
    storage = S3ObjectStorage(config=config)
    if not await storage.does_bucket_exist(bucket_id=CONFIG.inbox_bucket):
        await storage.create_bucket(bucket_id=CONFIG.inbox_bucket)
    if await storage.does_object_exist(
        bucket_id=CONFIG.inbox_bucket, object_id=CONFIG.object_id
    ):
        await storage.delete_object(
            bucket_id=CONFIG.inbox_bucket, object_id=CONFIG.object_id
        )
    yield storage


@pytest_asyncio.fixture
async def populated_bucket_fixture(
    local_s3_fixture: S3ObjectStorage,
) -> event_schemas.FileUploadReceived:
    """Generate test file and prepare event"""
    file_size = 20 * 1024**2

    num_parts = math.ceil(file_size / PART_SIZE)
    with big_temp_file(size=file_size) as random_data:

        checksum = hashlib.sha256(random_data.read()).hexdigest()
        # rewind file
        random_data.seek(0)

        upload_id = await local_s3_fixture.init_multipart_upload(
            bucket_id=CONFIG.inbox_bucket, object_id=CONFIG.object_id
        )
        try:
            for part_number in range(1, num_parts + 1):

                part = random_data.read(PART_SIZE)
                upload_url = await local_s3_fixture.get_part_upload_url(
                    upload_id=upload_id,
                    bucket_id=CONFIG.inbox_bucket,
                    object_id=CONFIG.object_id,
                    part_number=part_number,
                )
                response = requests.put(url=upload_url, data=part, timeout=2)
                assert response.status_code == 200

            await local_s3_fixture.complete_multipart_upload(
                upload_id=upload_id,
                bucket_id=CONFIG.inbox_bucket,
                object_id=CONFIG.object_id,
            )

        except (Exception, KeyboardInterrupt):
            await local_s3_fixture.abort_multipart_upload(
                upload_id=upload_id,
                bucket_id=CONFIG.inbox_bucket,
                object_id=CONFIG.object_id,
            )

        event = event_schemas.FileUploadReceived(
            file_id=CONFIG.object_id,
            submitter_public_key=CONFIG.submitter_pubkey,
            upload_date=datetime.utcnow().isoformat(),
            decrypted_size=file_size,
            expected_decrypted_sha256=checksum,
        )
        yield event


@pytest_asyncio.fixture
async def publish_and_record_fixture(
    populated_bucket_fixture: event_schemas.FileUploadReceived,
):
    """Publish incoming event, record outgoing response event"""

    async with EventRecorder(
        kafka_servers=CONFIG.kafka_servers, topic="file_interrogation"
    ) as event_recorder:
        async with KafkaEventPublisher.construct(config=CONFIG) as publisher:
            type_ = "file_upload_received"
            key = CONFIG.object_id
            topic = "file_uploads"
            await publisher.publish(
                payload=populated_bucket_fixture.dict(),
                type_=type_,
                key=key,
                topic=topic,
            )

    assert len(event_recorder.recorded_events) == 1

    return RecordedEventFixture(
        payload=event_recorder.recorded_events[0].payload,
        checkable_fields=CheckablePayloadFields(
            file_id=CONFIG.object_id,
            part_size=PART_SIZE,
            content_checksum=populated_bucket_fixture.dict()[
                "expected_decrypted_sha256"
            ],
        ),
    )
