import asyncio
from google.adk.workflow import Workflow, node
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.events.request_input import RequestInput
from google.adk.runners import Runner
from google.genai import types

@node
async def test_node(ctx: Context, node_input):
    print(f'test_node started with node_input: {node_input}')
    print(f'ctx.resume_inputs: {ctx.resume_inputs}')
    if ctx.resume_inputs:
        print("Got resume inputs!")
        yield Event(output='Done')
        return
    print('Yielding RequestInput')
    yield RequestInput(name='test_input')
    yield Event(output='Waiting', route='self')

workflow = Workflow(
    name='test',
    edges=[
        ('START', test_node),
        (test_node, {'self': test_node})
    ]
)

async def main():
    runner = Runner(agent=workflow)
    print('--- RUN 1 ---')
    async for e in runner.run_async():
        pass
    print('\n--- RUN 2 (RESUME) ---')
    resume_msg = types.Content(role='user', parts=[types.Part.from_text('{"test_input": "yes"}')])
    async for e in runner.run_async(new_message=resume_msg):
        pass
        
if __name__ == '__main__':
    asyncio.run(main())
