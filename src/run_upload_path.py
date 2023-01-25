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
"""This is... UPLOAD!!!"""

import asyncio
import hashlib
import os
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from ghga_connector.cli import upload
from ghga_event_schemas import pydantic_ as event_schemas
from ghga_service_chassis_lib.utils import big_temp_file
from hexkit.config import config_from_yaml
from hexkit.providers.akafka import KafkaConfig, KafkaEventPublisher
from hexkit.providers.mongodb import MongoDbConfig, MongoDbDaoFactory
from hexkit.providers.s3 import S3Config, S3ObjectStorage
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent.parent

FILE_NAME = os.urandom(16).hex()


@config_from_yaml(prefix="tb")
class Config(S3Config, KafkaConfig):
    """
    Custom Config class for the test app.
    Defaults set for not running inside devcontainer.
    """

    db_connection_str: str
    file_metadata_event_topic: str
    file_metadata_event_type: str
    inbox_bucket: str
    submitter_pubkey: str
    vault_host: str
    vault_port: int
    vault_token: str


CONFIG = Config()


class DBConfig:
    """TODO: Could be an enum"""

    dcs_config = MongoDbConfig(
        db_connection_str=CONFIG.db_connection_str, db_name="dcs"
    )
    ifrs_config = MongoDbConfig(
        db_connection_str=CONFIG.db_connection_str, db_name="ifrs"
    )
    irs_config = MongoDbConfig(
        db_connection_str=CONFIG.db_connection_str, db_name="irs"
    )
    ucs_config = MongoDbConfig(
        db_connection_str=CONFIG.db_connection_str, db_name="ucs"
    )


class UploadRejectedQuery(BaseModel):
    """Query model for file upload rejection"""

    id_: str
    file_id: str
    status: str


class UCSMetadataQuery(BaseModel):
    """Query model for IFRS validation"""

    file_id: str
    file_name: str


async def upload_and_verify():
    """TODO"""
    file_id = await run_upload()
    await check_state(file_id=file_id)


async def run_upload():
    """main"""
    file_id = os.urandom(16).hex()
    file_size = 20 * 1024**2
    file_data, file_size, checksum = generate_file(file_size=file_size)
    await populate_metadata(
        file_id=file_id, decrypted_size=file_size, decrypted_sha256=checksum
    )
    # need path for connector
    with NamedTemporaryFile() as tmp_file:
        tmp_file.write(file_data)
        tmp_file.seek(0)
        upload_file(file_id=file_id, file_path=tmp_file.name)
    return file_id


def generate_file(file_size: int):
    """Generate encrypted test file"""

    with big_temp_file(size=file_size) as random_data:
        random_data.seek(0)
        data = random_data.read()
        size = len(data)
        checksum = hashlib.sha256(data).hexdigest()
        return data, size, checksum


async def populate_metadata(file_id: str, decrypted_size: int, decrypted_sha256: str):
    """Populate metadedata submission schema and send event for UCS"""
    metadata_files = [
        event_schemas.MetadataSubmissionFiles(
            file_id=file_id,
            file_name=FILE_NAME,
            decrypted_size=decrypted_size,
            decrypted_sha256=decrypted_sha256,
        ),
    ]
    metadata_upserted = event_schemas.MetadataSubmissionUpserted(
        associated_files=metadata_files
    )

    async with KafkaEventPublisher.construct(config=CONFIG) as publisher:
        type_ = CONFIG.file_metadata_event_type
        key = file_id
        topic = CONFIG.file_metadata_event_topic
        await publisher.publish(
            payload=metadata_upserted.dict(),
            type_=type_,
            key=key,
            topic=topic,
        )
    time.sleep(15)


def upload_file(file_id: str, file_path: str):
    """Run file upload using the ghga-connector"""
    upload(
        file_id=file_id,
        file_path=file_path,
        pubkey_path=BASE_DIR / "example_data" / "key.pub",
    )


async def check_state(file_id: str):
    """TODO"""
    await check_s3(file_id=file_id)
    internal_id = await check_metadata()
    await check_rejected(internal_id=internal_id)
    # await check_ifrs()
    await check_dcs_db()
    await check_secret()


async def check_s3(file_id: str):
    """TODO"""
    storage = S3ObjectStorage(config=CONFIG)
    object_exists = await storage.does_object_exist(
        bucket_id=CONFIG.inbox_bucket, object_id=file_id
    )
    if not object_exists:
        raise ValueError("Object missing in inbox")


async def check_metadata():
    """TODO"""
    dao_factory = MongoDbDaoFactory(config=DBConfig.ucs_config)
    metadata_dao = await dao_factory.get_dao(
        name="file_metadata", dto_model=UCSMetadataQuery, id_field="file_id"
    )

    result = await metadata_dao.find_one(mapping={"file_name": FILE_NAME})

    # assert result
    internal_id = result.file_id

    return internal_id


async def check_rejected(internal_id: str):
    """TODO"""
    time.sleep(20)
    dao_factory = MongoDbDaoFactory(config=DBConfig.ucs_config)
    upload_attempt_dao = await dao_factory.get_dao(
        name="upload_attempts", dto_model=UploadRejectedQuery, id_field="id_"
    )
    result = await upload_attempt_dao.find_one(mapping={"file_id": internal_id})

    print(result)
    # assert result
    # assert result.status == "rejected"


async def check_dcs_db():
    """TODO"""


async def check_secret():
    """TODO"""


if __name__ == "__main__":
    asyncio.run(upload_and_verify())
