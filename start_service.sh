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

# 创建日志目录
mkdir -p logs

# 设置日志文件名
LOG_FILE="logs/${SERVICE_NAME}_${PORT}.log"

echo "正在启动服务: $SERVICE_NAME 在端口: $PORT"
echo "日志将保存在: $LOG_FILE"

# 使用nohup启动服务
cd $(dirname "$0")
nohup python -m src.$SERVICE_NAME --port=$PORT > "$LOG_FILE" 2>&1 &

# 获取进程ID
PID=$!

if [ $? -eq 0 ]; then
    echo "服务已成功启动，进程ID: $PID"
    echo $PID > "logs/${SERVICE_NAME}_${PORT}.pid"
else
    echo "服务启动失败，请查看日志文件获取详细信息"
    exit 1
fi 