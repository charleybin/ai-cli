import requests
import json
import time
import argparse
import sys
import re
import readline  # 用于改进命令行输入体验
import os
import atexit

# 历史记录文件路径
HISTORY_FILE = os.path.expanduser("~/.ai_cli_history")

def load_env_file(env_path):
    """加载.env文件中的环境变量"""
    if not os.path.exists(env_path):
        return False
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释行
                if not line or line.startswith('#'):
                    continue
                
                # 解析 KEY=VALUE 格式
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 移除引号
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    # 设置环境变量（如果尚未设置）
                    if key and key not in os.environ:
                        os.environ[key] = value
        
        print(f"已加载环境变量文件: {env_path}")
        return True
    except Exception as e:
        print(f"警告: 加载环境变量文件 {env_path} 时出错: {e}")
        return False

def load_config_from_env():
    """按照优先级顺序加载.env配置文件"""
    # 1. 优先读取当前目录中的.env
    current_dir_env = os.path.join(os.getcwd(), '.env')
    if load_env_file(current_dir_env):
        return
    
    # 2. 如果当前目录中没有，则读取用户目录下的.env
    user_dir_env = os.path.expanduser("~/.env")
    load_env_file(user_dir_env)

def setup_readline():
    """设置readline以支持历史记录和上下键导航"""
    try:
        # 设置历史记录文件
        if os.path.exists(HISTORY_FILE):
            readline.read_history_file(HISTORY_FILE)
        
        # 设置历史记录长度
        readline.set_history_length(1000)
        
        # 设置readline配置
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set editing-mode emacs")
        
        # 注册退出时保存历史记录
        atexit.register(readline.write_history_file, HISTORY_FILE)
        
        return True
    except ImportError:
        print("警告: readline模块不可用，历史记录功能将被禁用")
        return False
    except Exception as e:
        print(f"警告: 设置readline时出错: {e}")
        return False

def safe_input(prompt):
    """安全获取用户输入，智能处理中文删除边界"""
    while True:
        try:
            # 尝试使用标准输入
            user_input = input(prompt).strip()
            return user_input
        except UnicodeDecodeError as e:
            # 捕获编码错误，提取错误位置
            error_pos = e.start
            print(f"\n检测到编码问题，位置: {error_pos}")
            
            # 尝试修复输入
            raw_data = sys.stdin.buffer.read()
            
            # 尝试UTF-8解码（优先）
            try:
                decoded = raw_data.decode('utf-8').strip()
                print(f"成功使用UTF-8解码: {decoded}")
                return decoded
            except:
                pass
            
            # 尝试GBK解码（常见中文编码）
            try:
                decoded = raw_data.decode('gbk').strip()
                print(f"成功使用GBK解码: {decoded}")
                return decoded
            except:
                pass
            
            # 智能修复：删除无效字节范围
            print("尝试智能修复无效字节...")
            # 创建有效字节范围（0x00-0x7F 和 0xC0-0xFF 的中文起始字节）
            valid_bytes = bytes(range(0, 128)) + bytes(range(194, 256))
            
            # 过滤无效字节
            cleaned_bytes = bytes(b for b in raw_data if b in valid_bytes)
            
            try:
                # 尝试UTF-8解码修复后的字节
                decoded = cleaned_bytes.decode('utf-8').strip()
                print(f"修复后输入: {decoded}")
                return decoded
            except:
                # 最终回退：删除问题位置附近的字符
                if len(raw_data) > error_pos:
                    # 删除错误位置附近的字节（前后各2字节）
                    start = max(0, error_pos - 2)
                    end = min(len(raw_data), error_pos + 3)
                    fixed_bytes = raw_data[:start] + raw_data[end:]
                    
                    try:
                        decoded = fixed_bytes.decode('utf-8').strip()
                        print(f"删除无效字节后输入: {decoded}")
                        return decoded
                    except:
                        pass
            
            # 所有尝试失败，返回空输入
            print("无法修复输入，请重新输入")
            return ""

def get_input_with_history(prompt):
    """获取用户输入，支持历史记录导航"""
    try:
        user_input = input(prompt).strip()
        # 如果输入不为空，添加到历史记录
        if user_input:
            readline.add_history(user_input)
        return user_input
    except KeyboardInterrupt:
        print("\n检测到Ctrl+C，退出程序")
        sys.exit(0)
    except EOFError:
        print("\n检测到EOF，退出程序")
        sys.exit(0)
    except Exception as e:
        print(f"输入错误: {e}")
        return ""

def main():
    # 加载环境变量配置
    load_config_from_env()

    # 设置readline和历史记录
    readline_available = setup_readline()
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='OpenAI兼容API流式客户端')
    parser.add_argument('--base_url', 
                        default=os.environ.get('AI_CLI_BASE_URL') or 
                                os.environ.get('OPENAI_BASE_URL', 'http://localhost:7867'),
                        help='API基础URL，默认为http://localhost:7867，可通过AI_CLI_BASE_URL或OPENAI_BASE_URL环境变量设置')
    parser.add_argument('--model', 
                        default=os.environ.get('AI_CLI_MODEL') or 
                                os.environ.get('OPENAI_MODEL', 'Qwen3'),
                        help='模型名称，默认为Qwen3，可通过AI_CLI_MODEL或OPENAI_MODEL环境变量设置')
    parser.add_argument('--api_key', 
                        default=os.environ.get('AI_CLI_API_KEY') or 
                                os.environ.get('OPENAI_API_KEY', ''),
                        help='API密钥，默认为空，可通过AI_CLI_API_KEY或OPENAI_API_KEY环境变量设置')
    args = parser.parse_args()
    
    # 显示系统编码信息
    print("=" * 50)
    print(f"OpenAI兼容API流式客户端 (模型: {args.model})")
    print("输入 /quit, /exit 或 /bye 退出程序")
    if readline_available:
        print("支持上下键浏览历史记录，Tab键自动补全")
    print("=" * 50)
    
    # 主循环
    while True:
        # 获取用户输入（使用支持历史记录的输入函数）
        try:
            user_input = get_input_with_history("\n您: ")
        except KeyboardInterrupt:
            print("\n检测到Ctrl+C，退出程序")
            break
        except Exception as e:
            print(f"输入错误: {e}")
            continue
        
        # 检查退出命令
        if user_input.lower() in ['/quit', '/exit', '/bye']:
            print("感谢使用，再见！")
            break
        
        # 处理空输入
        if not user_input:
            continue
            
        # 发送请求并处理响应
        process_query(user_input, args.base_url, args.model, args.api_key)

def process_query(user_input, base_url, model, api_key):
    """处理用户查询并显示流式响应"""
    # 初始化统计变量
    total_tokens = 0
    start_time = None
    first_token_received = False
    
    try:
        # 准备请求头
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        suffix = "/v1/chat/completions"

        # 增强URL拼接的容错性
        # 如果base_url已经包含完整的路径，则直接使用
        if base_url.endswith("/v1/chat/completions"):
            req_url = base_url
        # 如果base_url包含/v1但不包含完整路径，则只添加/chat/completions部分
        elif base_url.endswith("/v1"):
            req_url = f"{base_url}/chat/completions"
        # 如果base_url既不包含/v1也不包含完整路径，则添加完整suffix
        else:
            req_url = f"{base_url}{suffix}"
        
        # 发送流式请求
        response = requests.post(
            req_url,
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": user_input}],
                "stream": True
            },
            stream=True,
            timeout=30
        )
        
        # 检查响应状态
        if response.status_code != 200:
            print(f"请求失败: HTTP {response.status_code} - {response.text}")
            return
        
        print("\nAI: ", end='', flush=True)
        # 逐行处理响应
        for line in response.iter_lines():
            # 过滤空行
            if line:
                decoded_line = line.decode('utf-8')
                
                # 处理SSE格式的数据行
                if decoded_line.startswith('data:'):
                    data_content = decoded_line[5:].strip()
                    
                    # 处理流结束标记
                    if data_content == '[DONE]':
                        break
                    
                    # 记录第一个token的到达时间
                    if not first_token_received:
                        start_time = time.time()
                        first_token_received = True
                    
                    try:
                        # 解析JSON数据
                        json_data = json.loads(data_content)
                        
                        # 提取并处理内容
                        if 'choices' in json_data and json_data['choices']:
                            choice = json_data['choices'][0]
                            if 'delta' in choice and 'content' in choice['delta']:
                                content = choice['delta']['content']
                                # 流式输出内容
                                print(content, end='', flush=True)
                                
                                # 累加token计数（使用字符长度作为近似）
                                token_count = len(content)
                                total_tokens += token_count
                    except json.JSONDecodeError:
                        print(f"\n[警告] JSON解析失败的行: {data_content}")
    
    except requests.exceptions.RequestException as e:
        print(f"\n请求发生错误: {e}")
        return
    
    # 性能统计和输出
    if first_token_received:
        end_time = time.time()
        duration = end_time - start_time
        
        # 输出最终结果和统计信息
        print("\n\n--- 性能统计 ---")
        print(f"总处理时间: {duration:.4f} 秒")
        print(f"总Token数: {total_tokens}")
        
        if duration > 0:
            tps = total_tokens / duration
            print(f"Token处理速度: {tps:.2f} TPS (Tokens Per Second)")
        else:
            print("处理时间过短，无法计算TPS")
    else:
        print("\n未接收到有效数据流")

if __name__ == "__main__":
    main()
