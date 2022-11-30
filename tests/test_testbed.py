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

import pytest  # type: ignore

from tests.fixtures.local_fixtures import local_s3_fixture  # noqa: F401
from tests.fixtures.local_fixtures import populated_bucket_fixture  # noqa: F401
from tests.fixtures.local_fixtures import publish_and_record_fixture  # noqa: F401
from tests.fixtures.local_fixtures import RecordedEventFixture


@pytest.mark.asyncio
async def test_outbound_payload(
    publish_and_record_fixture: RecordedEventFixture,  # noqa: F811
):
    """Test response event receival"""
    payload = publish_and_record_fixture.payload
    checkable_fields = publish_and_record_fixture.checkable_fields

    assert "upload_date" in payload.keys()
    assert payload["file_id"] == checkable_fields.file_id
    assert payload["reason"] == "The crypt4GH envelope is either malformed or missing."
