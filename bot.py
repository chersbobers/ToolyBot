import discord
from discord.ext import commands
import os
import json
import logging
import tomllib
from aiohttp import web
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

def load_config():
    base_path = os.path.dirname(__file__)
    config_path = os.path.join(base_path, "config.toml")
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        logger.error("config.toml missing.")
        exit(1)

CONFIG = load_config()

class SimpleDB:
    def __init__(self, filename):
        self.filename = filename
        self.data = self.load()
    
    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except:
                return {'users': {}, 'guilds': {}}
        return {'users': {}, 'guilds': {}}
    
    def save(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_user(self, guild_id, user_id):
        key = f"{guild_id}_{user_id}"
        if key not in self.data['users']:
            self.data['users'][key] = {
                'coins': 0, 'bank': 0, 'level': 1, 'xp': 0,
                'last_message': 0, 'last_daily': 0, 'last_work': 0
            }
        return self.data['users'][key]
    
    def set_user(self, guild_id, user_id, data):
        key = f"{guild_id}_{user_id}"
        self.data['users'][key] = data
        self.save()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix='/', intents=intents)
        self.db = SimpleDB(CONFIG['bot']['data_file'])
        self.config = CONFIG
    
    async def setup_hook(self):
        for extension in self.config['bot']['enabled_cogs']:
            try:
                await self.load_extension(extension)
                logger.info(f'Loaded: {extension}')
            except Exception as e:
                logger.error(f'Error {extension}: {e}')
        
        await self.tree.sync()

bot = MyBot()

async def health_check(request):
    return web.Response(text="Bot is running!")

async def redirect_handler(request):
    code = request.match_info.get('code', '')
    if os.path.exists(CONFIG['bot']['data_file']):
        try:
            with open(CONFIG['bot']['data_file'], 'r') as f:
                data = json.load(f)
            for guild_id, guild_data in data.get('guilds', {}).items():
                if 'urls' in guild_data and code in guild_data['urls']:
                    return web.Response(status=301, headers={'Location': guild_data['urls'][code]})
        except Exception as e:
            logger.error(f'Error: {e}')
    return web.Response(text='Not Found', status=404)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_get('/{code}', redirect_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@bot.event
async def on_ready():
    asyncio.create_task(start_web_server())
    logger.info(f'Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Game(name="Commands"))

if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error('DISCORD_TOKEN not set')
        exit(1)
    bot.run(token)