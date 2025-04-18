#!/usr/bin/env python

from typing import Dict, List, Optional, Any, Union, Tuple
import json
import sys
import time  # 导入time模块用于记录会话最后访问时间
import asyncio  # 导入asyncio用于心跳功能
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.sse import EventSourceResponse
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


# 会话管理器类，处理多个连接的状态
class ThinkingSessionManager:
    MAX_SESSIONS = 1000  # 最大会话数量限制
    
    def __init__(self):
        self.sessions: Dict[int, SequentialThinkingServer] = {}  # 使用整数作为字典键
        self.last_access: Dict[int, float] = {}  # 记录每个会话的最后访问时间
        self.next_id = 1  # 自增ID计数器
    
    def _cleanup_oldest_session(self) -> None:
        """清理最老的会话（最长时间未访问的）"""
        if not self.sessions:
            return
            
        # 按访问时间排序，找出最老的会话
        oldest_session_id = min(self.last_access.items(), key=lambda x: x[1])[0]
        self.remove_session(oldest_session_id)
        print(f"会话数量达到上限，已清理最老会话 ID: {oldest_session_id}", file=sys.stderr)
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> Tuple[int, SequentialThinkingServer]:
        """获取现有会话或创建新会话，返回会话ID和服务器实例"""
        current_time = time.time()
        
        # 尝试使用现有会话
        if session_id:
            try:
                # 尝试将输入的session_id转换为整数
                int_id = int(session_id)
                if int_id in self.sessions:
                    # 更新最后访问时间
                    self.last_access[int_id] = current_time
                    return int_id, self.sessions[int_id]
            except (ValueError, TypeError):
                # 如果转换失败，忽略输入的session_id
                pass
        
        # 检查是否达到最大会话限制
        if len(self.sessions) >= self.MAX_SESSIONS:
            self._cleanup_oldest_session()
        
        # 生成新的自增ID
        new_id = self.next_id
        self.next_id += 1
        self.sessions[new_id] = SequentialThinkingServer()
        self.last_access[new_id] = current_time
        return new_id, self.sessions[new_id]
    
    def remove_session(self, session_id: int) -> None:
        """移除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            # 同时删除访问时间记录
            if session_id in self.last_access:
                del self.last_access[session_id]
    
    def update_access_time(self, session_id: int) -> None:
        """更新会话的访问时间"""
        if session_id in self.sessions:
            self.last_access[session_id] = time.time()


# 创建会话管理器实例
thinking_manager = ThinkingSessionManager()


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
- session_id: Identifier for the current session

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
    sessionId: int,  # 会话ID参数，整数类型
    isRevision: Optional[bool] = None,
    revisesThought: Optional[int] = None,
    branchFromThought: Optional[int] = None,
    branchId: Optional[str] = None,
    needsMoreThoughts: Optional[bool] = None
) -> Dict[str, Any]:
    """
    A detailed tool for dynamic and reflective problem-solving through thoughts.
    """
    # 获取会话对应的服务器实例并更新访问时间
    session_id, session_server = thinking_manager.get_or_create_session(str(sessionId))
    thinking_manager.update_access_time(session_id)
    
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
    
    return session_server.process_thought(input_data)


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        """Handle SSE connection."""
        # 从请求中获取会话ID，如果没有则创建新会话
        session_id = request.query_params.get('session_id')
        int_session_id, _ = thinking_manager.get_or_create_session(session_id)
        
        # 创建初始化选项
        initialization_options = mcp_server.create_initialization_options()
        # 保存初始化选项到服务器实例
        mcp_server.initialization_options = initialization_options
        
        # 将会话ID放入初始化选项的默认参数中（不能直接赋值给InitializationOptions对象）
        # InitializationOptions 不支持直接赋值，使用其内部结构或方法
        if hasattr(initialization_options, 'default_parameters'):
            initialization_options.default_parameters['sessionId'] = int_session_id
        elif hasattr(initialization_options, 'set_parameter'):
            initialization_options.set_parameter('sessionId', int_session_id)
        elif hasattr(initialization_options, 'parameters'):
            initialization_options.parameters['sessionId'] = int_session_id
        else:
            print(f"警告: 无法设置会话ID到初始化选项中，连接可能无法使用正确的会话", file=sys.stderr)
        
        # 输出会话ID信息，方便用户查看
        print(f"连接到会话 ID: {int_session_id}", file=sys.stderr)
        
        # 创建一个心跳任务，保持连接活跃
        async def send_heartbeat(write_stream):
            """定期发送心跳消息给客户端以保持连接"""
            try:
                while True:
                    await asyncio.sleep(15)  # 每15秒发送一次心跳
                    print(f"发送心跳到客户端 (会话 ID: {int_session_id})", file=sys.stderr)
                    
                    try:
                        # MCP协议心跳消息 - JSON-RPC 2.0格式
                        heartbeat_message = {
                            "jsonrpc": "2.0",
                            "method": "$/ping",
                            "id": f"heartbeat-{int(time.time())}"
                        }
                        
                        # 将心跳消息转换为SSE事件格式
                        sse_event = {
                            "event": "message",
                            "data": json.dumps(heartbeat_message)
                        }
                        
                        # 检查write_stream支持的方法并使用合适的发送方式
                        if hasattr(write_stream, 'send'):
                            await write_stream.send(sse_event)
                        elif hasattr(write_stream, 'send_json'):
                            await write_stream.send_json(sse_event)
                        elif hasattr(write_stream, 'put'):
                            await write_stream.put(sse_event)
                        else:
                            # 如果上述方法都不可用，尝试直接作为SSE格式字符串发送
                            event_str = f"event: message\ndata: {json.dumps(heartbeat_message)}\n\n"
                            if hasattr(write_stream, 'send_text'):
                                await write_stream.send_text(event_str)
                            else:
                                print(f"无法找到合适的方法发送心跳", file=sys.stderr)
                        
                    except Exception as e:
                        print(f"心跳发送错误: {str(e)}", file=sys.stderr)
                    
            except asyncio.CancelledError:
                # 任务被取消时正常退出
                pass
            except Exception as e:
                print(f"心跳任务错误: {str(e)}", file=sys.stderr)
                print(f"心跳Writer类型: {type(write_stream)}", file=sys.stderr)
                print(f"心跳Writer可用方法: {dir(write_stream)}", file=sys.stderr)
        
        try:
            async with sse.connect_sse(
                    request.scope,
                    request.receive,
                    request._send,  # noqa: SLF001
            ) as (read_stream, write_stream):
                # 添加调试信息，了解write_stream的类型和方法
                print(f"SSE连接建立，write_stream类型: {type(write_stream)}", file=sys.stderr)
                print(f"write_stream可用方法: {dir(write_stream)}", file=sys.stderr)
                
                # 启动心跳任务
                heartbeat_task = asyncio.create_task(send_heartbeat(write_stream))
                
                try:
                    # 运行主处理逻辑
                    await mcp_server.run(
                        read_stream,
                        write_stream,
                        initialization_options,
                    )
                finally:
                    # 确保心跳任务被取消
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
        finally:
            # 连接关闭时不清理会话，而是依靠最大会话限制机制
            print(f"客户端连接关闭 (会话 ID: {int_session_id})", file=sys.stderr)
            pass

    # 创建带有自定义响应头的SSE端点
    async def sse_endpoint(request: Request):
        response = EventSourceResponse(
            generate_events(request),
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Nginx特定设置
            }
        )
        return response
    
    # 定义生成SSE事件的异步生成器
    async def generate_events(request: Request):
        # 这个函数实际不会执行到，因为我们使用自定义的connect_sse
        # 但是需要它来创建EventSourceResponse
        await handle_sse(request)
        yield {}  # 不会执行到这里

    # 使用定制的路由
    routes = [
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]
    
    # 使用定制的中间件设置响应头
    middleware = []
    
    return Starlette(
        debug=debug,
        routes=routes,
        middleware=middleware
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
