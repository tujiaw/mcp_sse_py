from typing import Dict, Optional, Union
import re
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
from pydantic import BaseModel
import argparse

# 创建MCP服务
mcp = FastMCP("clean_html")

# 定义要保留的HTML标签
ALLOWED_TAGS = [
    'div', 'p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'table', 'tr', 'td', 'th', 'thead', 'tbody',
    'a', 'img', 'button', 'input', 'select', 'option', 'form',
    'label', 'section', 'article', 'header', 'footer', 'nav',
    'main', 'aside', 'details', 'summary', 'figure', 'figcaption'
]

# 要移除的属性（保留id、class、href、src等有用属性）
REMOVE_ATTRS = [
    'style', 'onclick', 'onmouseover', 'onmouseout', 'onload',
    'onerror', 'onkeyup', 'onkeydown', 'onchange', 'data-reactid'
]


@mcp.tool()
async def clean_html(html_content: str, keep_structure: bool = True) -> Dict:
    """
    清洗HTML内容，移除head、CSS和JavaScript，只保留有用的标签

    Args:
        html_content: 要清洗的HTML内容
        keep_structure: 是否保留文档结构（如果为False，则只提取文本内容）
    """
    try:
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 移除head标签
        if soup.head:
            soup.head.decompose()
        
        # 移除script标签
        for script in soup.find_all('script'):
            script.decompose()
        
        # 移除style标签
        for style in soup.find_all('style'):
            style.decompose()
        
        # 移除注释
        for comment in soup.find_all(text=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()
            
        # 移除链接的样式表
        for link in soup.find_all('link', rel='stylesheet'):
            link.decompose()
            
        if not keep_structure:
            # 只保留文本内容
            return {
                "cleaned_html": None,
                "text_content": soup.get_text(separator=' ', strip=True),
                "status": "success"
            }
        
        # 递归清理标签和属性
        def clean_tag(tag):
            # 如果标签不在允许列表中，替换为其内容
            if tag.name and tag.name.lower() not in ALLOWED_TAGS:
                tag.replace_with_children()
                return
                
            # 移除不需要的属性
            for attr in list(tag.attrs.keys()):
                if attr.lower() in REMOVE_ATTRS or attr.startswith('on'):
                    del tag[attr]
            
            # 递归处理子标签
            for child in list(tag.children):
                if hasattr(child, 'name') and child.name:
                    clean_tag(child)
        
        # 从body开始清理
        if soup.body:
            clean_tag(soup.body)
            cleaned_html = str(soup.body)
        else:
            # 如果没有body标签，从整个文档清理
            for tag in list(soup.children):
                if hasattr(tag, 'name') and tag.name:
                    clean_tag(tag)
            cleaned_html = str(soup)
            
        # 移除多余的空白字符
        cleaned_html = re.sub(r'\s{2,}', ' ', cleaned_html)
        
        return {
            "cleaned_html": cleaned_html,
            "text_content": soup.get_text(separator=' ', strip=True),
            "status": "success"
        }
    except Exception as e:
        return {
            "cleaned_html": None,
            "text_content": None,
            "status": "error",
            "error": str(e)
        }


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """创建Starlette应用，使用SSE提供MCP服务"""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        """处理SSE连接"""
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
    
    parser = argparse.ArgumentParser(description='运行HTML清洗工具服务')
    parser.add_argument('--host', default='0.0.0.0', help='绑定的主机地址')
    parser.add_argument('--port', type=int, default=8081, help='监听的端口')
    args = parser.parse_args()

    # 绑定SSE请求处理到MCP服务器
    starlette_app = create_starlette_app(mcp_server, debug=True)

    print(f"HTML清洗服务已启动，访问 http://{args.host}:{args.port}/sse")
    uvicorn.run(starlette_app, host=args.host, port=args.port)
