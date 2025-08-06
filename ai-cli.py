import requests
import json
import time
import argparse
import sys
import re
import readline  # 用于改进命令行输入体验
import os
import atexit
import subprocess
import uuid
import logging

# 历史记录文件路径
HISTORY_FILE = os.path.expanduser("~/.ai_cli_history")

# ===== Environment & History Setup =====

def load_env_file(env_path):
    """加载.env文件中的环境变量"""
    if not os.path.exists(env_path):
        return False
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key, value = key.strip(), value.strip()
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = value
        return True
    except Exception as e:
        logging.warning(f"加载环境变量文件 {env_path} 时出错: {e}")
        return False

def load_config_from_env():
    """按照优先级顺序加载.env配置文件"""
    if load_env_file(os.path.join(os.getcwd(), '.env')):
        logging.info(f"从当前目录加载 .env 文件")
        return
    if load_env_file(os.path.expanduser("~/.env")):
        logging.info(f"从用户主目录加载 .env 文件")


def setup_readline():
    """设置readline以支持历史记录和上下键导航"""
    if os.path.exists(HISTORY_FILE):
        readline.read_history_file(HISTORY_FILE)
    readline.set_history_length(1000)
    atexit.register(readline.write_history_file, HISTORY_FILE)

def get_input_with_history(prompt):
    """获取用户输入，支持历史记录导航"""
    try:
        user_input = input(prompt).strip()
        if user_input:
            readline.add_history(user_input)
        return user_input
    except (KeyboardInterrupt, EOFError):
        print("\n感谢使用，再见！")
        logging.info("用户通过 Ctrl+C 或 Ctrl+D 退出")
        sys.exit(0)
    except Exception as e:
        logging.error(f"获取输入时发生错误: {e}")
        print(f"输入错误: {e}")
        return ""

# ===== Tool Definitions =====

def tool_read_file(path):
    """读取本地文件内容。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return {'ok': True, 'content': f.read()}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def tool_write_file(path, content):
    """写入内容到本地文件。"""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def tool_exec_cmd(cmd):
    """执行shell命令。"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, check=False)
        return {'ok': True, 'stdout': result.stdout, 'stderr': result.stderr, 'returncode': result.returncode}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def tool_list_dir(path="."):
    """列出指定目录下所有文件。"""
    try:
        return {'ok': True, 'files': os.listdir(path)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def tool_search_files(path=".", pattern=None):
    """递归查找目录及子目录下的文件。"""
    matches = []
    for root, _, files in os.walk(path):
        for name in files:
            if not pattern or pattern in name:
                matches.append(os.path.join(root, name))
    return {'ok': True, 'files': matches}

def tool_search_content(path, keyword):
    """递归查找目录及子目录下包含特定字符串的文件及行。"""
    matches = []
    for root, _, files in os.walk(path):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        if keyword in line:
                            matches.append({'file': file_path, 'line': i, 'content': line.strip()})
            except Exception:
                continue
    return {'ok': True, 'matches': matches}

# ===== Tool Schemas, Parsers, and Dispatcher =====

TOOLS_FUNCTIONS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "exec_cmd": tool_exec_cmd,
    "list_dir": tool_list_dir,
    "search_files": tool_search_files,
    "search_content": tool_search_content,
}

TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "read_file", "description": "读取本地文件内容。", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "要读取的文件路径"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "写入内容到本地文件。", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "要写入的文件路径"}, "content": {"type": "string", "description": "要写入的内容"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "exec_cmd", "description": "执行shell命令。", "parameters": {"type": "object", "properties": {"cmd": {"type": "string", "description": "要执行的shell命令"}}, "required": ["cmd"]}}},
    {"type": "function", "function": {"name": "list_dir", "description": "列出指定目录下所有文件。", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "要列出的目录路径，默认为当前目录"}},"required": []}}},
    {"type": "function", "function": {"name": "search_files", "description": "递归查找文件。", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "起始目录"}, "pattern": {"type": "string", "description": "文件名包含的字符串，可选"}}, "required": []}}},
    {"type": "function", "function": {"name": "search_content", "description": "递归查找包含特定字符串的文件。", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "起始目录"}, "keyword": {"type": "string", "description": "要搜索的字符串"}}, "required": ["keyword"]}}},
]

def parse_textual_tool_call(text):
    """Parses the model's custom textual format for tool calls."""
    func_pattern = re.compile(r"<function=([\w_]+)>(.*?)</function>", re.DOTALL)
    param_pattern = re.compile(r"<parameter=([\w_]+)>(.*?)</parameter>", re.DOTALL)
    
    tool_calls = []
    functions = func_pattern.finditer(text)
    for func_match in functions:
        func_name = func_match.group(1)
        func_body = func_match.group(2)
        
        arguments = {}
        params = param_pattern.finditer(func_body)
        for param_match in params:
            arguments[param_match.group(1)] = param_match.group(2).strip()
            
        if func_name:
            tool_calls.append({
                "id": f"call_{uuid.uuid4()}",
                "type": "function",
                "function": {"name": func_name, "arguments": json.dumps(arguments)}
            })
            
    return tool_calls or None

def dispatch_tool_call(tool_call):
    """Executes a tool call and returns the result."""
    func_name = tool_call['function']['name']
    try:
        args_str = tool_call['function']['arguments']
        args = json.loads(args_str)
        func = TOOLS_FUNCTIONS.get(func_name)
        if not func:
            result = {"ok": False, "error": f"Unknown tool: {func_name}"}
        else:
            logging.info(f"正在执行工具: {func_name}，参数: {args}")
            print(f"正在执行工具: {func_name}，参数: {args}")
            result = func(**args)
            logging.info(f"工具 {func_name} 执行结果: {json.dumps(result, ensure_ascii=False)}")
    except Exception as e:
        result = {"ok": False, "error": f"Error executing tool {func_name}: {str(e)}"}
        logging.error(f"执行工具 {func_name} 时出错: {e}")
    
    return {
        "tool_call_id": tool_call['id'],
        "role": "tool",
        "name": func_name,
        "content": json.dumps(result, ensure_ascii=False)
    }

# ===== Core Conversation Loop =====

def run_conversation_step(messages, base_url, model, api_key):
    """
    Runs a single step of the conversation: sends messages, handles response.
    Returns the assistant's final text response.
    """
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    cleaned_base_url = base_url.rstrip('/')
    if cleaned_base_url.endswith('/v1'):
        req_url = f"{cleaned_base_url}/chat/completions"
    else:
        req_url = f"{cleaned_base_url}/v1/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    if messages and messages[-1].get("role") == "user":
        payload["tools"] = TOOLS_SCHEMA
        payload["tool_choice"] = "auto"

    try:
        logging.info(f"发送请求到: {req_url}")
        logging.debug(f"请求 Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        response = requests.post(req_url, headers=headers, json=payload, stream=True, timeout=60)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"请求失败: {e}")
        print(f"\n请求失败: {e}")
        if messages and messages[-1]["role"] == "user":
            messages.pop()
        return None

    print("\nAI: ", end='', flush=True)
    final_content = ""
    assistant_response = {"role": "assistant", "content": None, "tool_calls": []}
    
    streamed_tool_calls = []
    for line in response.iter_lines():
        if not line: continue
        decoded_line = line.decode('utf-8')
        if not decoded_line.startswith('data:'): continue
        data_content = decoded_line[6:].strip()
        if data_content == '[DONE]': break

        try:
            chunk = json.loads(data_content)
            logging.debug(f"接收到数据块: {data_content}") # DETAILED LOGGING
            delta = chunk['choices'][0].get('delta', {})

            if delta.get('content'):
                text_content = delta['content']
                print(text_content, end='', flush=True)
                final_content += text_content
            
            if delta.get('tool_calls'):
                if not streamed_tool_calls:
                    logging.info("接收工具调用请求...")
                    print("接收工具调用请求...")
                streamed_tool_calls.extend(delta['tool_calls'])

        except (json.JSONDecodeError, IndexError) as e:
            logging.warning(f"解析流式数据块时出错: {e} - 数据: '{data_content}'")
            continue

    print() 
    logging.info(f"AI流式响应接收完毕。组合内容: '{final_content}'")

    if final_content and not streamed_tool_calls:
        parsed_calls = parse_textual_tool_call(final_content)
        if parsed_calls:
            logging.info("检测到文本格式的工具调用，正在执行...")
            print("检测到文本格式的工具调用，正在执行...")
            assistant_response['tool_calls'] = parsed_calls
            final_content = ""

    if final_content:
        assistant_response['content'] = final_content
    
    if streamed_tool_calls:
        final_tool_calls = {}
        for chunk in streamed_tool_calls:
            index = chunk.get("index")
            if index is None: continue
            if index not in final_tool_calls:
                final_tool_calls[index] = {"id": None, "type": "function", "function": {"name": None, "arguments": ""}}
            if chunk.get("id"):
                final_tool_calls[index]["id"] = chunk["id"]
            if chunk.get("function", {}).get("name"):
                final_tool_calls[index]["function"]["name"] = chunk["function"]["name"]
            if chunk.get("function", {}).get("arguments"):
                final_tool_calls[index]["function"]["arguments"] += chunk["function"]["arguments"]
        assistant_response["tool_calls"] = list(final_tool_calls.values())
        logging.info(f"解析后的工具调用: {json.dumps(assistant_response['tool_calls'], ensure_ascii=False, indent=2)}")

    if assistant_response.get('content') is not None or assistant_response.get('tool_calls'):
        messages.append(assistant_response)
    
    if assistant_response.get("tool_calls"):
        tool_results = [dispatch_tool_call(tc) for tc in assistant_response["tool_calls"]]
        messages.extend(tool_results)
        return run_conversation_step(messages, base_url, model, api_key)

    return final_content

def main():
    # --- Setup Logging ---
    logging.basicConfig(
        level=logging.DEBUG, # Changed to DEBUG for detailed output
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='ai-cli.log',
        filemode='a',
        encoding='utf-8'
    )

    load_config_from_env()
    setup_readline()

    parser = argparse.ArgumentParser(description='OpenAI兼容API流式客户端 (支持工具调用)')
    parser.add_argument('--base_url', default=os.environ.get('AI_CLI_BASE_URL') or os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com'), help='API基础URL')
    parser.add_argument('--model', default=os.environ.get('AI_CLI_MODEL') or os.environ.get('OPENAI_MODEL', 'gpt-4o'), help='模型名称')
    parser.add_argument('--api_key', default=os.environ.get('AI_CLI_API_KEY') or os.environ.get('OPENAI_API_KEY', ''), help='API密钥')
    args = parser.parse_args()

    if not args.api_key:
        print("错误: API密钥未设置。请通过 --api_key 参数或 AI_CLI_API_KEY/OPENAI_API_KEY 环境变量提供。")
        sys.exit(1)

    logging.info("AI CLI 启动")
    print("=" * 50)
    print(f"OpenAI兼容API流式客户端 (模型: {args.model})")
    print("输入 /quit, /exit 或 /bye 退出程序")
    print("日志文件位于: ai-cli.log")
    print("=" * 50)

    messages = []
    while True:
        user_input = get_input_with_history("\n您: ")
        if not user_input:
            continue
        if user_input.lower() in ['/quit', '/exit', '/bye']:
            print("感谢使用，再见！")
            logging.info("用户退出")
            break

        messages.append({"role": "user", "content": user_input})
        logging.info(f"用户输入: {user_input}")
        run_conversation_step(messages, args.base_url, args.model, args.api_key)

if __name__ == "__main__":
    main()
