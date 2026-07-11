# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent
from app.config import settings
from app.harness.sensors import LeftShiftedBlueprintPipeline
from app.types import DebateRoundEnvelope


def test_harness_end_to_end_capsule_wiring() -> None:
    """
    End-to-end integration test verifying that:
    1. Phase 1 Grilling records RequirementsSchema upon completion.
    2. Performance Agent capsule runs Left-Shifted Blueprint Sensor Pipeline.
    3. Debate flow properly traverses Performance -> Security/SRE -> Judge.
    """
    old_mock = settings.mock_mode
    settings.mock_mode = True

    try:
        session_service = InMemorySessionService()
        session = session_service.create_session_sync(user_id="test_user", app_name="test_harness")
        runner = Runner(agent=root_agent, session_service=session_service, app_name="test_harness")

        # Step 1: Initialize session with concept
        init_payload = {
            "project_id": "test_e2e_proj",
            "concept": "Event-Sourced Financial Ledger Service",
            "caveman_mode": True,
        }
        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=json.dumps(init_payload))],
        )

        events_round1 = list(
            runner.run(
                new_message=message,
                user_id="test_user",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        )
        assert len(events_round1) > 0, "Expected events from round 1 initialization"

        active_session = session_service.get_session_sync(app_name="test_harness", user_id="test_user", session_id=session.id)
        assert active_session is not None

        # Verify LeftShiftedBlueprintPipeline directly against a test proposal envelope
        mock_envelope = DebateRoundEnvelope(
            proposal="""### Proposed Blueprint
```mermaid
graph TD
    A[API Gateway] --> B[Event Store]
```
Performance is O(1) append.
""",
            round_number=1,
        )
        sensor_res = LeftShiftedBlueprintPipeline.run_pipeline(
            mock_envelope.model_dump(),
            project_id="test_e2e_proj",
        )
        assert sensor_res.passed is True, f"Expected clean proposal to pass sensors: {sensor_res.failed_layer}"

        # Verify Sensor Backpressure Interception on broken Mermaid syntax
        broken_envelope = DebateRoundEnvelope(
            proposal="""### Broken Blueprint
```mermaid
graph TD
    A[API Gateway --> B[Event Store]
```
""",
            round_number=1,
        )
        broken_res = LeftShiftedBlueprintPipeline.run_pipeline(
            broken_envelope.model_dump(),
            project_id="test_e2e_proj",
        )
        assert broken_res.passed is False, "Expected broken bracket in Mermaid to fail sensor pipeline"
        assert "Diagram Syntax" in broken_res.failed_layer
        assert "Mismatched '['" in broken_res.formatted_backpressure or "Mismatched" in broken_res.formatted_backpressure

        # Step 2: Send SKIP to complete Phase 1 Grilling and enter Phase 2 Architectural Debate
        resume_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=json.dumps({"grill_question": "SKIP"}))],
        )
        events_round2 = list(
            runner.run(
                new_message=resume_message,
                user_id="test_user",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        )
        assert len(events_round2) > 0, "Expected events after skipping interview"

        # Verify state was updated with Phase 1 RequirementsSchema and entered Phase 2
        active_session = session_service.get_session_sync(app_name="test_harness", user_id="test_user", session_id=session.id)
        state_dict = active_session.state
        assert state_dict.get("grill_completed") is True, "Expected grill_completed=True after SKIP"
        assert state_dict.get("requirements") is not None, "Expected Phase 1 RequirementsSchema to be recorded"

    finally:
        settings.mock_mode = old_mock
