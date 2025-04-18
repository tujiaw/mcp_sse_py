#!/usr/bin/env python

from typing import Dict, List, Optional, Any, Union
import json
import sys
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn

# 初始化FastMCP
mcp = FastMCP("sequential-thinking-server", version="0.2.0")

class ThoughtData:
    def __init__(
        self,
        thought: str,
        thought_number: int,
        total_thoughts: int,
        next_thought_needed: bool,
        is_revision: Optional[bool] = None,
        revises_thought: Optional[int] = None,
        branch_from_thought: Optional[int] = None,
        branch_id: Optional[str] = None,
        needs_more_thoughts: Optional[bool] = None
    ):
        self.thought = thought
        self.thought_number = thought_number
        self.total_thoughts = total_thoughts
        self.next_thought_needed = next_thought_needed
        self.is_revision = is_revision
        self.revises_thought = revises_thought
        self.branch_from_thought = branch_from_thought
        self.branch_id = branch_id
        self.needs_more_thoughts = needs_more_thoughts

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThoughtData':
        return cls(
            thought=data.get('thought', ''),
            thought_number=data.get('thoughtNumber', 0),
            total_thoughts=data.get('totalThoughts', 0),
            next_thought_needed=data.get('nextThoughtNeeded', False),
            is_revision=data.get('isRevision'),
            revises_thought=data.get('revisesThought'),
            branch_from_thought=data.get('branchFromThought'),
            branch_id=data.get('branchId'),
            needs_more_thoughts=data.get('needsMoreThoughts')
        )


class SequentialThinkingServer:
    def __init__(self):
        self.thought_history: List[ThoughtData] = []
        self.branches: Dict[str, List[ThoughtData]] = {}

    def validate_thought_data(self, input_data: Dict[str, Any]) -> ThoughtData:
        if not input_data.get('thought') or not isinstance(input_data.get('thought'), str):
            raise ValueError('Invalid thought: must be a string')
            
        if not input_data.get('thoughtNumber') or not isinstance(input_data.get('thoughtNumber'), int):
            raise ValueError('Invalid thoughtNumber: must be a number')
            
        if not input_data.get('totalThoughts') or not isinstance(input_data.get('totalThoughts'), int):
            raise ValueError('Invalid totalThoughts: must be a number')
            
        if not isinstance(input_data.get('nextThoughtNeeded'), bool):
            raise ValueError('Invalid nextThoughtNeeded: must be a boolean')

        return ThoughtData.from_dict(input_data)

    def format_thought(self, thought_data: ThoughtData) -> str:
        prefix = ''
        context = ''

        if thought_data.is_revision:
            prefix = '🔄 Revision'
            context = f" (revising thought {thought_data.revises_thought})"
        elif thought_data.branch_from_thought:
            prefix = '🌿 Branch'
            context = f" (from thought {thought_data.branch_from_thought}, ID: {thought_data.branch_id})"
        else:
            prefix = '💭 Thought'
            context = ''

        header = f"{prefix} {thought_data.thought_number}/{thought_data.total_thoughts}{context}"
        border = "─" * (max(len(header), len(thought_data.thought)) + 4)

        return f"""
┌{border}┐
│ {header} │
├{border}┤
│ {thought_data.thought.ljust(len(border) - 2)} │
└{border}┘"""

    def process_thought(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            validated_input = self.validate_thought_data(input_data)

            if validated_input.thought_number > validated_input.total_thoughts:
                validated_input.total_thoughts = validated_input.thought_number

            self.thought_history.append(validated_input)

            if validated_input.branch_from_thought and validated_input.branch_id:
                if validated_input.branch_id not in self.branches:
                    self.branches[validated_input.branch_id] = []
                self.branches[validated_input.branch_id].append(validated_input)

            formatted_thought = self.format_thought(validated_input)
            print(formatted_thought, file=sys.stderr)

            return {
                "thoughtNumber": validated_input.thought_number,
                "totalThoughts": validated_input.total_thoughts,
                "nextThoughtNeeded": validated_input.next_thought_needed,
                "branches": list(self.branches.keys()),
                "thoughtHistoryLength": len(self.thought_history)
            }
        except Exception as error:
            raise ValueError(str(error))


# 创建单例
thinking_server = SequentialThinkingServer()


@mcp.tool(
    description="""A detailed tool for dynamic and reflective problem-solving through thoughts.
This tool helps analyze problems through a flexible thinking process that can adapt and evolve.
Each thought can build on, question, or revise previous insights as understanding deepens.

When to use this tool:
- Breaking down complex problems into steps
- Planning and design with room for revision
- Analysis that might need course correction
- Problems where the full scope might not be clear initially
- Problems that require a multi-step solution
- Tasks that need to maintain context over multiple steps
- Situations where irrelevant information needs to be filtered out

Key features:
- You can adjust total_thoughts up or down as you progress
- You can question or revise previous thoughts
- You can add more thoughts even after reaching what seemed like the end
- You can express uncertainty and explore alternative approaches
- Not every thought needs to build linearly - you can branch or backtrack
- Generates a solution hypothesis
- Verifies the hypothesis based on the Chain of Thought steps
- Repeats the process until satisfied
- Provides a correct answer

Parameters explained:
- thought: Your current thinking step, which can include:
* Regular analytical steps
* Revisions of previous thoughts
* Questions about previous decisions
* Realizations about needing more analysis
* Changes in approach
* Hypothesis generation
* Hypothesis verification
- next_thought_needed: True if you need more thinking, even if at what seemed like the end
- thought_number: Current number in sequence (can go beyond initial total if needed)
- total_thoughts: Current estimate of thoughts needed (can be adjusted up/down)
- is_revision: A boolean indicating if this thought revises previous thinking
- revises_thought: If is_revision is true, which thought number is being reconsidered
- branch_from_thought: If branching, which thought number is the branching point
- branch_id: Identifier for the current branch (if any)
- needs_more_thoughts: If reaching end but realizing more thoughts needed

You should:
1. Start with an initial estimate of needed thoughts, but be ready to adjust
2. Feel free to question or revise previous thoughts
3. Don't hesitate to add more thoughts if needed, even at the "end"
4. Express uncertainty when present
5. Mark thoughts that revise previous thinking or branch into new paths
6. Ignore information that is irrelevant to the current step
7. Generate a solution hypothesis when appropriate
8. Verify the hypothesis based on the Chain of Thought steps
9. Repeat the process until satisfied with the solution
10. Provide a single, ideally correct answer as the final output
11. Only set next_thought_needed to false when truly done and a satisfactory answer is reached"""
)
async def sequentialthinking(
    thought: str,
    thoughtNumber: int,
    totalThoughts: int,
    nextThoughtNeeded: bool,
    isRevision: Optional[bool] = None,
    revisesThought: Optional[int] = None,
    branchFromThought: Optional[int] = None,
    branchId: Optional[str] = None,
    needsMoreThoughts: Optional[bool] = None
) -> Dict[str, Any]:
    """
    A detailed tool for dynamic and reflective problem-solving through thoughts.
    """
    input_data = {
        "thought": thought,
        "thoughtNumber": thoughtNumber,
        "totalThoughts": totalThoughts,
        "nextThoughtNeeded": nextThoughtNeeded,
        "isRevision": isRevision,
        "revisesThought": revisesThought,
        "branchFromThought": branchFromThought,
        "branchId": branchId,
        "needsMoreThoughts": needsMoreThoughts
    }
    
    return thinking_server.process_thought(input_data)


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        """Handle SSE connection."""
        # 创建初始化选项
        initialization_options = mcp_server.create_initialization_options()
        # 保存初始化选项到服务器实例
        mcp_server.initialization_options = initialization_options
        
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                initialization_options,
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


if __name__ == "__main__":
    mcp_server = mcp._mcp_server  # noqa: WPS437

    import argparse
    
    parser = argparse.ArgumentParser(description='Run Sequential Thinking SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8002, help='Port to listen on')
    args = parser.parse_args()

    print("Sequential Thinking MCP Server running on SSE", file=sys.stderr)
    
    # Bind SSE request handling to MCP server
    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)
