# Copyright 2021 Universität Tübingen, DKFZ and EMBL
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

"""A test dummy just to make the CI pass."""

import time

import pytest
from ghga_connector.cli import config
from ghga_connector.core.api_calls import get_file_metadata, get_upload_info
from ghga_event_schemas import pydantic_ as event_schemas
from hexkit.providers.akafka.testutils import (
    check_recorded_events,
    EventRecorder,
    ExpectedEvent,
)

from src.commons import BASE_DIR, CONFIG
from src.run_upload_path import delegate_paths
from src.run_download_path import download_file


@pytest.mark.asyncio
async def test_full_path():
    """Test up- and download path"""
    unencrypted_id, encrypted_id, checksum = await delegate_paths()
    upload_id = await check_upload_path(
        unencrypted_id=unencrypted_id, encrypted_id=encrypted_id
    )
    await check_download_path(
        encrypted_id=encrypted_id, upload_id=upload_id, checksum=checksum
    )


async def check_upload_path(*, unencrypted_id: str, encrypted_id: str):
    """Check correct state for upload path"""
    await check_upload_status(file_id=unencrypted_id, expected_status="rejected")
    # <= 180 did not work in actions, so let's currently keep it this way
    time.sleep(240)
    upload_id = await check_upload_status(
        file_id=encrypted_id, expected_status="accepted"
    )
    return upload_id


async def check_upload_status(*, file_id: str, expected_status: str):
    """Assert upload attempt state matches expected state"""
    metadata = get_file_metadata(api_url=config.upload_api, file_id=file_id)
    upload_id = metadata["latest_upload_id"]
    upload_attempt = get_upload_info(api_url=config.upload_api, upload_id=upload_id)
    assert upload_attempt["status"] == expected_status
    return upload_id


async def check_download_path(*, encrypted_id: str, upload_id: str, checksum: str):
    """Check correct state for download path"""
    event_recorder = EventRecorder(
        kafka_servers=CONFIG.kafka_servers, topic="file_downloads"
    )
    async with event_recorder:
        download_file(file_id=encrypted_id, output_dir=BASE_DIR / "example_data")

    payload = event_schemas.FileDownloadServed(
        file_id=encrypted_id, decrypted_sha256=checksum, context="unkown"
    ).json()
    type_ = "download_served"
    key = encrypted_id
    expected_event = ExpectedEvent(payload=payload, type_=type_, key=key)

    check_recorded_events(
        recorded_events=event_recorder.recorded_events, expected_events=[expected_event]
    )