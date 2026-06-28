#!/bin/bash
# 教员AI顾问 - 前端启动脚本

cd ~/jiaoyuan-ai-v2/frontend

echo "=========================================="
echo "  教员AI顾问 - 启动前端"
echo "=========================================="

# 设置npm国内镜像（加速下载）
npm config set registry https://registry.npmmirror.com

echo "[1/2] 安装前端依赖（首次需要，约1-2分钟）..."
npm install

echo "[2/2] 启动前端开发服务器..."
echo "=========================================="
echo "  启动成功后，浏览器打开:"
echo "  http://localhost:5173"
echo "=========================================="
npm run dev
