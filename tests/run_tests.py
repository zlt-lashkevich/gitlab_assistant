import asyncio
import pytest

async def main():
    pytest.main([
        "--cov=src",
        "--cov-report=term-missing",
        "tests/"
    ])

if __name__ == "__main__":
    asyncio.run(main())
