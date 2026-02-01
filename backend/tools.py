"""
工具定义与实现文件
维护所有可供模型调用的工具
使用 DuckDuckGo 搜索，无需 API Key
"""
from duckduckgo_search import DDGS

# 工具定义列表
TOOLS = [
    {
        "name": "web_search",
        "description": "在互联网上搜索最新信息。当需要查找实时数据、新闻、天气、股票价格或任何需要联网才能获取的信息时使用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询词，应该简洁明确地描述需要搜索的内容"
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回的最大搜索结果数量，默认为5",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
]

def get_tools():
    """返回所有可用工具列表"""
    return TOOLS

def get_tool_by_name(name: str):
    """根据工具名称获取工具配置"""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


async def execute_web_search(query: str, max_results: int = 5) -> dict:
    """
    执行网络搜索（使用 DuckDuckGo，无需 API Key）
    
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数
        
    Returns:
        包含搜索结果的字典
    """
    try:
        # 使用 DuckDuckGo 搜索
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        # 格式化结果
        formatted_results = []
        for item in results:
            formatted_results.append({
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "content": item.get("body", "")
            })
        
        return {
            "success": True,
            "query": query,
            "results": formatted_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": []
        }


async def execute_tool(tool_name: str, parameters: dict) -> dict:
    """
    统一的工具执行入口
    
    Args:
        tool_name: 工具名称
        parameters: 工具参数
        
    Returns:
        工具执行结果
    """
    if tool_name == "web_search":
        query = parameters.get("query", "")
        max_results = parameters.get("max_results", 5)
        return await execute_web_search(query, max_results)
    else:
        return {
            "success": False,
            "error": f"未知工具: {tool_name}"
        }
