#!/usr/bin/env python3
"""fugaku_mcp.py に stdio で接続し、ツール一覧取得→cluster_status を呼ぶ動作確認。

使い方（venv内・環境変数を設定した状態で）:
  python test_client.py
"""
import asyncio, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fugaku_mcp.py")
    params = StdioServerParameters(
        command=sys.executable,            # 同じvenvのpython
        args=[server],                     # 絶対パス（どのcwdからでも起動可）
        env=os.environ.copy(),             # FUGAKU_* を引き継ぐ
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("== 公開ツール ==")
            for t in tools.tools:
                print(f"  - {t.name}")
            print("\n== cluster_status 呼び出し ==")
            res = await session.call_tool("cluster_status", {})
            for c in res.content:
                print("  ", getattr(c, "text", c))


if __name__ == "__main__":
    asyncio.run(main())
