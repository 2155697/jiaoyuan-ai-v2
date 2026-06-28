"""
教员AI顾问 API - 服务器启动脚本

提供简单的方式来启动FastAPI服务器，支持命令行参数和环境变量。

用法:
    # 默认启动（端口8000）
    python start_server.py

    # 指定端口
    python start_server.py --port 8080

    # 开发模式（自动重载）
    python start_server.py --reload

    # 指定模型
    MODEL_NAME=qwen3:32b python start_server.py

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# 将项目根目录加入路径
_project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_dir not in sys.path:
    sys.path.insert(0, _project_dir)

import uvicorn

logger = logging.getLogger("jiaoyuan.api")


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="教员AI顾问 API 服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
环境变量:
  OLLAMA_HOST    Ollama服务地址（默认 http://localhost:11434）
  MODEL_NAME     模型名称（默认 qwen3:8b）
  LOG_LEVEL      日志级别（默认 INFO）
  CORS_ORIGINS   允许的CORS来源（逗号分隔）
        """,
    )

    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("API_HOST", "0.0.0.0"),
        help="绑定地址（默认 0.0.0.0）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("API_PORT", "8000")),
        help="监听端口（默认 8000）",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.environ.get("API_RELOAD", "false").lower() == "true",
        help="开发模式：代码变更自动重载",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("API_WORKERS", "1")),
        help="工作进程数（生产环境建议 > 1，默认 1）",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.environ.get("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（默认 INFO）",
    )

    return parser.parse_args()


def main() -> None:
    """主函数"""
    args = parse_args()

    # 设置日志
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("教员AI顾问 API 服务器")
    logger.info("=" * 60)
    logger.info("Host:       %s", args.host)
    logger.info("Port:       %d", args.port)
    logger.info("Workers:    %d", args.workers)
    logger.info("Reload:     %s", args.reload)
    logger.info("Log Level:  %s", args.log_level)
    logger.info("Model:      %s", os.environ.get("MODEL_NAME", "qwen3:8b"))
    logger.info("Ollama:     %s", os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    logger.info("=" * 60)

    # uvicorn配置
    uvicorn_config = {
        "app": "api.main:app",
        "host": args.host,
        "port": args.port,
        "reload": args.reload,
        "log_level": "warning",
        "access_log": False,
    }

    # 生产环境多进程模式（不能与reload同时使用）
    if args.workers > 1 and not args.reload:
        uvicorn_config["workers"] = args.workers
        logger.info("生产模式：使用 %d 个工作进程", args.workers)
    elif args.reload:
        logger.info("开发模式：启用自动重载")

    try:
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        logger.info("\n服务器已停止")
        sys.exit(0)
    except Exception as e:
        logger.error("服务器启动失败: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
