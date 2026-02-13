"""CLI entry point: python -m dash"""

import asyncio

from dash.agents import dash

if __name__ == "__main__":
    asyncio.run(dash.acli_app(stream=True))
