from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv
import uvicorn
import os
import json
import asyncio

# 导入工具和提示词配置
from tools import get_tools, get_tool_by_name, execute_tool
from prompts import get_planner_prompt, get_executor_prompt, get_verify_prompt

# 加载 .env 文件中的环境变量
load_dotenv()

app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 OpenAI 客户端
api_key = os.getenv("DEEPSEEK_API_KEY")
client = None

if api_key:
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
else:
    print("警告: 未找到 DEEPSEEK_API_KEY，请在 backend/.env 中配置")

class Message(BaseModel):
    message: str

async def event_generator(user_message: str):
    """流式生成事件，实时推送执行进度"""
    
    if not client:
        yield f"data: {json.dumps({'type': 'error', 'content': '未配置API Key'}, ensure_ascii=False)}\n\n"
        return
    
    try:
        # === 阶段1: 规划中 ===
        yield f"data: {json.dumps({'type': 'status', 'content': '规划中...'}, ensure_ascii=False)}\n\n"
        
        # 调用 Planner 智能体
        planner_prompt = get_planner_prompt()
        
        planner_response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": planner_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7
        )
        
        planner_output = planner_response.choices[0].message.content
        
        # 解析规划结果
        try:
            if "```json" in planner_output:
                json_start = planner_output.find("```json") + 7
                json_end = planner_output.find("```", json_start)
                planner_output = planner_output[json_start:json_end].strip()
            elif "```" in planner_output:
                json_start = planner_output.find("```") + 3
                json_end = planner_output.find("```", json_start)
                planner_output = planner_output[json_start:json_end].strip()
                
            plan = json.loads(planner_output)
        except json.JSONDecodeError as e:
            plan = {
                "analysis": "解析失败",
                "subtasks": [{"task_id": 1, "description": "直接回答", "type": "answer"}]
            }
        
        # === 阶段2: 发送TODO清单 ===
        subtasks = plan.get('subtasks', [])
        todos = [{"id": task["task_id"], "description": task["description"], "completed": False} 
                 for task in subtasks]
        
        yield f"data: {json.dumps({'type': 'plan', 'todos': todos, 'analysis': plan.get('analysis', '')}, ensure_ascii=False)}\n\n"
        
        # === 阶段3: Executor 执行子任务 ===
        task_results = {}
        
        for task in subtasks:
            task_id = task['task_id']
            task_type = task.get('type')
            task_desc = task.get('description')
            
            if task_type == 'search':
                # 调用搜索工具
                tool_name = task.get('tool', 'web_search')
                parameters = task.get('parameters', {})
                
                # 执行工具
                result = await execute_tool(tool_name, parameters)
                
                # 格式化搜索结果供后续使用
                if result.get('success'):
                    formatted_result = f"搜索「{parameters.get('query', '')}」的结果:\n\n"
                    for i, r in enumerate(result.get('results', [])[:5]):
                        formatted_result += f"{i+1}. {r.get('title', '')}\n"
                        formatted_result += f"   {r.get('content', '')[:300]}\n"
                        formatted_result += f"   来源: {r.get('url', '')}\n\n"
                    task_results[task_id] = formatted_result
                else:
                    task_results[task_id] = f"搜索失败: {result.get('error', '未知错误')}"
                
            elif task_type == 'answer':
                # answer 类型任务先跳过，等所有 search 完成后统一生成答案
                pass
            
            # 标记任务完成
            yield f"data: {json.dumps({'type': 'task_complete', 'task_id': task_id}, ensure_ascii=False)}\n\n"
        
        # === 阶段4: Executor 汇总生成答案 ===
        # 构建汇总上下文（包含所有 Executor 执行结果）
        summary_context = f"用户问题: {user_message}\n\n"
        summary_context += "=== Executor 执行结果 ===\n\n"
        
        for task_id, result in task_results.items():
            summary_context += f"【任务 {task_id} 结果】\n{result}\n"
        
        summary_context += "\n请根据以上搜索结果，综合分析并回答用户的问题。回答要全面、准确、有条理。"
        
        # 打印汇总模型的输入
        print(f"\n{'='*60}")
        print("【Executor 汇总 - 模型输入】")
        print(f"{'='*60}")
        print(summary_context)
        print(f"{'='*60}\n")
        
        # 调用模型生成汇总答案
        summary_response = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "user", "content": summary_context}]
        )
        
        executor_answer = summary_response.choices[0].message.content
        
        # === 阶段5: Verify 智能体校验和优化 ===
        yield f"data: {json.dumps({'type': 'status', 'content': '校验优化中...'}, ensure_ascii=False)}\n\n"
        
        verify_prompt = get_verify_prompt()
        verify_context = f"用户问题: {user_message}\n\nExecutor 生成的回答:\n{executor_answer}"
        
        verify_response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": verify_prompt},
                {"role": "user", "content": verify_context}
            ],
            temperature=0.3
        )
        
        verified_answer = verify_response.choices[0].message.content
        
        # 打印 Verify 输出
        print(f"\n{'='*60}")
        print("【Verify 智能体输出】")
        print(f"{'='*60}")
        print(verified_answer)
        print(f"{'='*60}\n")
        
        # === 阶段6: 返回最终答案 ===
        yield f"data: {json.dumps({'type': 'final_answer', 'content': verified_answer}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

@app.post("/api/chat")
async def chat(msg: Message):
    """流式响应接口"""
    return StreamingResponse(
        event_generator(msg.message),
        media_type="text/event-stream"
    )

# 挂载前端静态文件
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
