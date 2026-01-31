import discord
from discord.ext import commands
import os
import json
import logging
from aiohttp import web
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

CONFIG = {
    'xp_min': 15,
    'xp_max': 25,
    'xp_cooldown': 60,
    'xp_per_level': 100,
    'level_up_multiplier': 10,
    'data_file': 'data.json',
    'video_check_interval': 300
}

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
                'coins': 0,
                'bank': 0,
                'level': 1,
                'xp': 0,
                'last_message': 0,
                'last_daily': 0,
                'last_work': 0
            }
        return self.data['users'][key]
    
    def set_user(self, guild_id, user_id, data):
        key = f"{guild_id}_{user_id}"
        self.data['users'][key] = data
        self.save()
    
    def get_all_guild_users(self, guild_id):
        users = []
        for key, data in self.data['users'].items():
            if key.startswith(f"{guild_id}_"):
                user_id = key.split('_')[1]
                users.append({'user_id': user_id, 'data': data})
        users.sort(key=lambda x: (x['data']['level'], x['data']['xp']), reverse=True)
        return users

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix='/', intents=intents)
        self.db = SimpleDB(CONFIG['data_file'])
        self.config = CONFIG
    
    async def setup_hook(self):
        await self.load_extension('cogs.leveling')
        await self.load_extension('cogs.system')
        await self.load_extension('cogs.economy')
        await self.load_extension('cogs.fun')
        await self.load_extension('cogs.utility')
        
        await self.tree.sync()
        logger.info('All cogs loaded and commands synced!')

bot = MyBot()

async def health_check(request):
    return web.Response(text="Bot is running!")

async def redirect_handler(request):
    code = request.match_info.get('code', '')
    
    if os.path.exists(CONFIG['data_file']):
        try:
            with open(CONFIG['data_file'], 'r') as f:
                data = json.load(f)
            
            for guild_id, guild_data in data.get('guilds', {}).items():
                if 'urls' in guild_data and code in guild_data['urls']:
                    return web.Response(
                        status=301,
                        headers={'Location': guild_data['urls'][code]}
                    )
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
    logger.info(f'Web server running on port {port}')

@bot.event
async def on_ready():
    asyncio.create_task(start_web_server())
    
    logger.info(f'Logged in as {bot.user}')
    logger.info(f'Connected to {len(bot.guilds)} guilds')
    await bot.change_presence(activity=discord.Game(name="/help"))
    logger.info('All systems operational!')

@bot.tree.command(name='help', description='Show all available commands')
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title='Bot Commands',
        description='Here are all the slash commands you can use!',
        color=0x5865F2
    )
    embed.add_field(
        name='Leveling & Economy',
        value='`/rank` - View your rank\n`/leaderboard` - Top 10 users\n`/balance` - Check balance\n`/daily` - Daily reward\n`/work` - Work for coins',
        inline=False
    )
    embed.add_field(
        name='Fun',
        value='`/8ball` - Magic 8ball\n`/roll` - Roll dice\n`/flip` - Flip coin\n`/cat` - Random cat\n`/dog` - Random dog',
        inline=False
    )
    embed.add_field(
        name='System & Moderation',
        value='`/kick` - Kick member\n`/ban` - Ban member\n`/unban` - Unban user\n`/timeout` - Timeout member\n`/warn` - Warn member\n`/warnings` - View warnings\n`/clearwarnings` - Clear warnings\n`/purge` - Delete messages\n`/lock` - Lock channel\n`/unlock` - Unlock channel',
        inline=False
    )
    embed.add_field(
        name='Reaction Roles & YouTube',
        value='`/reactionrole` - Create reaction role\n`/removereactionrole` - Remove reaction role\n`/listreactionroles` - List reaction roles\n`/createreactionpanel` - Create panel\n`/setupyoutube` - Setup YouTube\n`/toggleyoutube` - Toggle YouTube\n`/youtubestatus` - YouTube status\n`/testlastvideo` - Test video',
        inline=False
    )
    embed.add_field(
        name='Utility',
        value='`/shorten` - Shorten a URL',
        inline=False
    )
    embed.add_field(
        name='Info',
        value='`/ping` - Bot latency\n`/serverinfo` - Server info\n`/userinfo` - User info',
        inline=False
    )
    await interaction.response.send_message(embed=embed)

if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error('DISCORD_TOKEN not set!')
        exit(1)
    
    logger.info("everythings working")
    logger.info('hello from chersbobers and booly co :3')
    bot.run(token)