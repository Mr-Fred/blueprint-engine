import pytest
from app.harness.tools import stream_agent_with_tools, get_harness_tools


class MockChunk:
    def __init__(self, text=None, function_call=None):
        self.text = text
        if function_call:
            class MockFC:
                name = function_call[0]
                args = function_call[1]
            class MockPart:
                function_call = MockFC()
            class MockContent:
                parts = [MockPart()]
            class MockCandidate:
                content = MockContent()
            self.candidates = [MockCandidate()]
        else:
            self.candidates = []


class MockAsyncGenerator:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        self.iter = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration


class MockModels:
    def __init__(self):
        self.turn = 0

    async def generate_content_stream(self, model, contents, config):
        self.turn += 1
        if self.turn == 1:
            # First turn: returns a function call
            return MockAsyncGenerator([
                MockChunk(function_call=("add_verified_fact", {"project_id": "proj_stream_test", "statement": "Must use Redis", "verifier": "Tester"}))
            ])
        else:
            # Second turn: returns markdown text after tool output
            return MockAsyncGenerator([
                MockChunk(text="### Proposed Architecture\nWe will use Redis.")
            ])


class MockClient:
    def __init__(self):
        class Aio:
            pass
        self.aio = Aio()
        self.aio.models = MockModels()


@pytest.mark.asyncio
async def test_stream_agent_with_tools_executes_tool_and_yields_text():
    client = MockClient()
    tools = get_harness_tools()

    texts = []
    async for t in stream_agent_with_tools(
        client=client,
        model_id="gemini-test",
        prompt="Propose caching layer",
        tools=tools,
    ):
        texts.append(t)

    full_output = "".join(texts)
    assert "### Proposed Architecture" in full_output
    assert client.aio.models.turn == 2
