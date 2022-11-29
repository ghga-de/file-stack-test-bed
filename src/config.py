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
"""App config for tests and interaction with the Interrogation Room Service"""

from hexkit.config import config_from_yaml  # type: ignore
from pydantic import BaseSettings, SecretStr  # type: ignore


@config_from_yaml(prefix="tb")
class Config(BaseSettings):
    """CUstom Config class for the test app"""

    s3_endpoint_url: str
    s3_access_key_id: str
    s3_secret_access_key: SecretStr
    inbox_bucket: str
    object_id: str
    submitter_pubkey: str
    service_instance_id: str
    kafka_servers: list[str]
    service_name: str


CONFIG = Config()
