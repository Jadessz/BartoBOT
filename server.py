import os
import threading
import logging
import asyncio
from aiohttp import web
from bot import run_bot

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord_bot_server')

# Create a simple web server for health checks
async def health_check(request):
    """Health check endpoint for Render.com and Uptime Robot."""
    return web.Response(text="Bot is running!", status=200)

async def setup_web_server():
    """Set up a simple web server for health checks."""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    # Get port from environment variable (for Render.com)
    port = int(os.getenv('PORT', 8080))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Web server started on port {port}")
    
    # Keep the server running without blocking request processing
    try:
        while True:
            await asyncio.sleep(60)  # Check every minute instead of every hour
    except asyncio.CancelledError:
        logger.info("Web server is shutting down")
        await runner.cleanup()
        raise

def run_bot_thread():
    """Run the Discord bot in a separate thread."""
    try:
        # Call run_bot with default parameters (web_server_mode=False)
        run_bot()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        logger.info("Web server will continue running even if bot fails to start")

def main():
    """Main function to run both the bot and web server."""
    # Start the bot in a separate thread
    bot_thread = threading.Thread(target=run_bot_thread)
    bot_thread.daemon = True  # Make thread daemon so it exits when main thread exits
    bot_thread.start()
    
    # Start the web server in the main thread
    asyncio.run(setup_web_server())

if __name__ == "__main__":
    main()