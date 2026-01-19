import discord
from discord.ext import commands
import os
import json
import random
import asyncio
from datetime import datetime
import aiohttp
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

# Configuration
CONFIG = {
    'prefix': '!',
    'xp_min': 15,
    'xp_max': 25,
    'xp_cooldown': 60,
    'xp_per_level': 100,
    'level_up_multiplier': 10,
    'data_file': 'data.json'
}

# Simple JSON Database
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

# Initialize
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=CONFIG['prefix'], intents=intents)
db = SimpleDB(CONFIG['data_file'])

# Events
@bot.event
async def on_ready():
    logger.info(f'✅ Logged in as {bot.user}')
    logger.info(f'📊 Connected to {len(bot.guilds)} guilds')
    await bot.change_presence(activity=discord.Game(name=f"{CONFIG['prefix']}help"))
    logger.info('🚀 All systems operational!')

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    # XP System
    user_data = db.get_user(str(message.guild.id), str(message.author.id))
    now = datetime.now().timestamp()
    
    if now - user_data['last_message'] >= CONFIG['xp_cooldown']:
        user_data['last_message'] = now
        xp_gain = random.randint(CONFIG['xp_min'], CONFIG['xp_max'])
        user_data['xp'] += xp_gain
        xp_needed = user_data['level'] * CONFIG['xp_per_level']
        
        if user_data['xp'] >= xp_needed:
            user_data['level'] += 1
            user_data['xp'] = 0
            
            coin_reward = user_data['level'] * CONFIG['level_up_multiplier']
            user_data['coins'] += coin_reward
            
            messages = [
                f'🎉 GG {message.author.mention}! You leveled up to **Level {user_data["level"]}**!',
                f'⭐ Congrats {message.author.mention}! You\'re now **Level {user_data["level"]}**!',
                f'🚀 Level up! {message.author.mention} reached **Level {user_data["level"]}**!'
            ]
            
            await message.channel.send(
                f'{random.choice(messages)} You earned **{coin_reward:,} coins**! 💰'
            )
        
        db.set_user(str(message.guild.id), str(message.author.id), user_data)
    
    await bot.process_commands(message)

# Commands
@bot.command(name='bothelp')
async def help_command(ctx):
    embed = discord.Embed(
        title='🤖 Bot Commands',
        color=0x5865F2
    )
    embed.add_field(
        name='📊 Leveling',
        value='`!rank [@user]` - View rank\n`!leaderboard` - Top 10 users',
        inline=False
    )
    embed.add_field(
        name='💰 Economy',
        value='`!balance [@user]` - Check balance\n`!daily` - Daily reward\n`!work` - Work for coins',
        inline=False
    )
    embed.add_field(
        name='🎮 Fun',
        value='`!8ball <question>` - Magic 8ball\n`!roll [sides]` - Roll dice\n`!flip` - Flip coin\n`!cat` - Random cat\n`!dog` - Random dog',
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! Latency: `{latency}ms`')

@bot.command(name='rank')
async def rank(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_data = db.get_user(str(ctx.guild.id), str(target.id))
    xp_needed = user_data['level'] * CONFIG['xp_per_level']
    
    all_users = db.get_all_guild_users(str(ctx.guild.id))
    rank = next((i + 1 for i, u in enumerate(all_users) if u['user_id'] == str(target.id)), 'Unranked')
    
    progress = int((user_data['xp'] / xp_needed) * 20) if xp_needed > 0 else 0
    bar = '█' * progress + '░' * (20 - progress)
    
    embed = discord.Embed(color=0x4D96FF)
    embed.set_author(name=f"{target.display_name}'s Profile", icon_url=target.display_avatar.url)
    embed.description = f"""
**RANK** • #{rank} / {len(all_users)}
**LEVEL** • {user_data['level']}
**XP** • {user_data['xp']:,} / {xp_needed:,}

`{bar}`

**💰 BALANCE** • {user_data['coins']:,} coins
    """
    await ctx.send(embed=embed)

@bot.command(name='leaderboard', aliases=['lb'])
async def leaderboard(ctx):
    all_users = db.get_all_guild_users(str(ctx.guild.id))[:10]
    
    description = []
    for i, u in enumerate(all_users):
        medal = '🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'**{i+1}.**'
        description.append(
            f'{medal} <@{u["user_id"]}>\n'
            f'└ Level {u["data"]["level"]} ({u["data"]["xp"]:,} XP) • {u["data"]["coins"]:,} coins'
        )
    
    embed = discord.Embed(
        title='🏆 Server Leaderboard',
        description='\n'.join(description) if description else 'No users yet!',
        color=0x9B59B6
    )
    await ctx.send(embed=embed)

@bot.command(name='balance', aliases=['bal'])
async def balance(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_data = db.get_user(str(ctx.guild.id), str(target.id))
    
    embed = discord.Embed(
        title='💰 Balance',
        description=f'{target.mention} has **{user_data["coins"]:,}** coins!',
        color=0xFFD700
    )
    await ctx.send(embed=embed)

@bot.command(name='daily')
async def daily(ctx):
    user_data = db.get_user(str(ctx.guild.id), str(ctx.author.id))
    now = datetime.now().timestamp()
    
    if now - user_data['last_daily'] < 86400:
        time_left = 86400 - (now - user_data['last_daily'])
        hours = int(time_left / 3600)
        await ctx.send(f'⏳ You already claimed your daily! Come back in {hours} hours.')
        return
    
    reward = 100
    user_data['coins'] += reward
    user_data['last_daily'] = now
    db.set_user(str(ctx.guild.id), str(ctx.author.id), user_data)
    
    await ctx.send(f'✅ You claimed your daily reward of **{reward:,}** coins!\n💰 New balance: **{user_data["coins"]:,}** coins')

@bot.command(name='work')
async def work(ctx):
    user_data = db.get_user(str(ctx.guild.id), str(ctx.author.id))
    now = datetime.now().timestamp()
    
    if now - user_data['last_work'] < 3600:
        time_left = 3600 - (now - user_data['last_work'])
        minutes = int(time_left / 60)
        await ctx.send(f'⏳ You need to rest! Come back in {minutes} minutes.')
        return
    
    earnings = random.randint(10, 50)
    user_data['coins'] += earnings
    user_data['last_work'] = now
    db.set_user(str(ctx.guild.id), str(ctx.author.id), user_data)
    
    jobs = [
        'You worked as a programmer and earned',
        'You delivered pizza and earned',
        'You streamed on Twitch and earned'
    ]
    
    await ctx.send(f'💼 {random.choice(jobs)} **{earnings:,}** coins!\n💰 New balance: **{user_data["coins"]:,}** coins')

@bot.command(name='8ball')
async def eightball(ctx, *, question):
    responses = [
        'Yes, definitely!', 'No way!', 'Maybe...', 'Ask again later',
        'Absolutely!', 'I doubt it', 'Signs point to yes', 'Very doubtful'
    ]
    await ctx.send(f'🔮 {random.choice(responses)}')

@bot.command(name='roll')
async def roll(ctx, sides: int = 6):
    if sides < 2 or sides > 100:
        await ctx.send('❌ Dice must have between 2 and 100 sides!')
        return
    result = random.randint(1, sides)
    await ctx.send(f'🎲 You rolled a **{result}** (1-{sides})')

@bot.command(name='flip')
async def flip(ctx):
    result = random.choice(['Heads', 'Tails'])
    await ctx.send(f'🪙 The coin landed on **{result}**!')

@bot.command(name='cat')
async def cat(ctx):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://api.thecatapi.com/v1/images/search') as resp:
                data = await resp.json()
                embed = discord.Embed(title='🐱 Random Kitty!', color=0xFF69B4)
                embed.set_image(url=data[0]['url'])
                await ctx.send(embed=embed)
        except:
            await ctx.send('Failed to fetch cat 😿')

@bot.command(name='dog')
async def dog(ctx):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://api.thedogapi.com/v1/images/search') as resp:
                data = await resp.json()
                embed = discord.Embed(title='🐶 Random Doggy!', color=0xFF69B4)
                embed.set_image(url=data[0]['url'])
                await ctx.send(embed=embed)
        except:
            await ctx.send('Failed to fetch dog 😥')

# Run bot
if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error('❌ DISCORD_TOKEN not set!')
        exit(1)
    
    logger.info('🚀 Starting bot...')
    bot.run(token)