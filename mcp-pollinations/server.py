import asyncio
import urllib.parse
import urllib.request
import os
import re
from datetime import datetime
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

OUTPUT_DIR = Path.home() / "Pictures" / "pollinations"

app = Server("pollinations-image-gen")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_image",
            description="Generate an image using Pollinations.ai. Returns the saved image path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Text description of the image to generate",
                    },
                    "width": {
                        "type": "integer",
                        "description": "Image width in pixels (default: 1024)",
                        "default": 1024,
                    },
                    "height": {
                        "type": "integer",
                        "description": "Image height in pixels (default: 1024)",
                        "default": 1024,
                    },
                    "model": {
                        "type": "string",
                        "description": "Model to use: flux (default), flux-realism, turbo",
                        "default": "flux",
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducibility (optional)",
                    },
                },
                "required": ["prompt"],
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name != "generate_image":
        raise ValueError(f"Unknown tool: {name}")

    prompt = arguments["prompt"]
    width = arguments.get("width", 1024)
    height = arguments.get("height", 1024)
    model = arguments.get("model", "flux")
    seed = arguments.get("seed")

    encoded_prompt = urllib.parse.quote(prompt)
    params = f"?width={width}&height={height}&model={model}&nologo=true"
    if seed is not None:
        params += f"&seed={seed}"

    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}{params}"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\s-]", "", prompt[:40]).strip().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = OUTPUT_DIR / f"{timestamp}_{safe_name}.jpg"

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: urllib.request.urlretrieve(url, filename))

    with open(filename, "rb") as f:
        image_data = f.read()

    import base64
    image_b64 = base64.standard_b64encode(image_data).decode()

    return [
        TextContent(type="text", text=f"Image saved to: {filename}\nPrompt: {prompt}\nModel: {model} | {width}x{height}"),
        ImageContent(type="image", data=image_b64, mimeType="image/jpeg"),
    ]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
