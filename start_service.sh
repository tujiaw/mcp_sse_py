#!/bin/bash

# 服务启动脚本，支持指定服务名和端口号

# 显示使用方法
function show_usage() {
    echo "用法: $0 <服务名> <端口号>"
    echo "示例: $0 gaode_weather 8000"
    exit 1
}

# 检查参数数量
if [ $# -ne 2 ]; then
    show_usage
fi

SERVICE_NAME=$1
PORT=$2

# 检查服务名是否存在
if [ ! -d "src/$SERVICE_NAME" ]; then
    echo "错误: 服务目录 'src/$SERVICE_NAME' 不存在"
    exit 1
fi

# 检查端口号是否为数字
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "错误: 端口号必须是一个数字"
    exit 1
fi

# 检查虚拟环境是否存在
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "错误: 虚拟环境目录 '$VENV_DIR' 不存在"
    exit 1
fi

# 设置虚拟环境中Python解释器的路径
if [ -f "$VENV_DIR/bin/python" ]; then
    PYTHON_PATH="$VENV_DIR/bin/python"
elif [ -f "$VENV_DIR/Scripts/python.exe" ]; then
    PYTHON_PATH="$VENV_DIR/Scripts/python.exe"
else
    echo "错误: 无法找到虚拟环境中的Python解释器"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 设置日志文件名
LOG_FILE="logs/${SERVICE_NAME}_${PORT}.log"

echo "正在启动服务: $SERVICE_NAME 在端口: $PORT"
echo "使用虚拟环境: $PYTHON_PATH"
echo "日志将保存在: $LOG_FILE"

# 使用nohup启动服务
cd $(dirname "$0")

# 检查是否存在main.py文件
if [ -f "src/$SERVICE_NAME/main.py" ]; then
    echo "找到入口文件: src/$SERVICE_NAME/main.py"
    nohup "$PYTHON_PATH" "src/$SERVICE_NAME/main.py" --port=$PORT > "$LOG_FILE" 2>&1 &
elif [ -f "src/$SERVICE_NAME/__main__.py" ]; then
    echo "找到入口文件: src/$SERVICE_NAME/__main__.py"
    nohup "$PYTHON_PATH" -m "src.$SERVICE_NAME" --port=$PORT > "$LOG_FILE" 2>&1 &
else
    echo "警告: 未找到明确的入口文件，尝试执行作为脚本执行"
    nohup "$PYTHON_PATH" -c "import sys; sys.path.insert(0, '.'); from src.$SERVICE_NAME import main; main.main(port=$PORT)" > "$LOG_FILE" 2>&1 &
fi

# 获取进程ID
PID=$!

if [ $? -eq 0 ]; then
    echo "服务已成功启动，进程ID: $PID"
    echo $PID > "logs/${SERVICE_NAME}_${PORT}.pid"
else
    echo "服务启动失败，请查看日志文件获取详细信息"
    exit 1
fi 