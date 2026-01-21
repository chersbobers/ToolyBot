import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import json
import random
import asyncio
from datetime import datetime
import aiohttp
import logging
from aiohttp import web
import feedparser

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

# Configuration
CONFIG = {
    'xp_min': 15,
    'xp_max': 25,
    'xp_cooldown': 60,
    'xp_per_level': 100,
    'level_up_multiplier': 10,
    'data_file': 'data.json',
    'video_check_interval': 300  # 5 minutes
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

# Bot setup
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix='/', intents=intents)
        self.db = SimpleDB(CONFIG['data_file'])
    
    async def setup_hook(self):
        # Start YouTube checker
        self.check_youtube.start()
        # Sync slash commands
        await self.tree.sync()
        logger.info('✅ Slash commands synced!')
    
    @tasks.loop(seconds=CONFIG['video_check_interval'])
    async def check_youtube(self):
        """Check for new YouTube videos"""
        youtube_channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
        
        if not youtube_channel_id:
            return
        
        try:
            feed_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={youtube_channel_id}'
            
            # Parse feed
            feed = await asyncio.to_thread(feedparser.parse, feed_url)
            
            if not feed.entries:
                return
            
            latest = feed.entries[0]
            video_id = latest.yt_videoid if hasattr(latest, 'yt_videoid') else latest.id.split(':')[-1]
            
            # Check each guild for notifications
            for guild in self.guilds:
                guild_id = str(guild.id)
                
                # Get guild settings
                if 'youtube' not in self.db.data:
                    self.db.data['youtube'] = {}
                
                if guild_id not in self.db.data['youtube']:
                    self.db.data['youtube'][guild_id] = {
                        'enabled': True,
                        'channel_id': None,
                        'last_video_id': None
                    }
                
                guild_settings = self.db.data['youtube'][guild_id]
                
                # Skip if disabled or no channel set
                if not guild_settings['enabled'] or not guild_settings['channel_id']:
                    continue
                
                # Check if this is a new video
                if video_id != guild_settings['last_video_id'] and guild_settings['last_video_id']:
                    channel = self.get_channel(int(guild_settings['channel_id']))
                    
                    if channel:
                        embed = discord.Embed(
                            title='🎬 New YouTube Video!',
                            description=f'**{latest.title}**',
                            url=latest.link,
                            color=0xFF0000,
                            timestamp=datetime.utcnow()
                        )
                        
                        # Add thumbnail if available
                        if hasattr(latest, 'media_thumbnail') and latest.media_thumbnail:
                            embed.set_thumbnail(url=latest.media_thumbnail[0]['url'])
                        
                        embed.add_field(name='Channel', value=latest.author, inline=True)
                        
                        # Parse published date
                        if hasattr(latest, 'published'):
                            embed.add_field(name='Published', value=latest.published, inline=True)
                        
                        await channel.send('📺 New video alert! @everyone', embed=embed)
                        logger.info(f'📺 Sent notification for: {latest.title}')
                
                # Update last video ID
                guild_settings['last_video_id'] = video_id
                self.db.save()
        
        except Exception as e:
            logger.error(f'❌ Error checking YouTube: {e}')
    
    @check_youtube.before_loop
    async def before_check_youtube(self):
        await self.wait_until_ready()

bot = MyBot()

# Simple HTTP server for Render health checks
async def health_check(request):
    return web.Response(text="Bot is running! ✅")

async def start_web_server():
    """Start a simple web server for Render health checks"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f'🌐 Health check server running on port {port}')

# Events
@bot.event
async def on_ready():
    # Start web server for Render
    asyncio.create_task(start_web_server())
    
    logger.info(f'✅ Logged in as {bot.user}')
    logger.info(f'📊 Connected to {len(bot.guilds)} guilds')
    await bot.change_presence(activity=discord.Game(name="/help"))
    logger.info('🚀 All systems operational!')

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    # XP System
    user_data = bot.db.get_user(str(message.guild.id), str(message.author.id))
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
        
        bot.db.set_user(str(message.guild.id), str(message.author.id), user_data)
    
    await bot.process_commands(message)

# Slash Commands
@bot.tree.command(name='help', description='Show all available commands')
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title='🤖 Bot Commands',
        description='Here are all the slash commands you can use!',
        color=0x5865F2
    )
    embed.add_field(
        name='📊 Leveling',
        value='`/rank` - View your rank\n`/leaderboard` - Top 10 users',
        inline=False
    )
    embed.add_field(
        name='💰 Economy',
        value='`/balance` - Check balance\n`/daily` - Daily reward\n`/work` - Work for coins',
        inline=False
    )
    embed.add_field(
        name='🎮 Fun',
        value='`/8ball` - Magic 8ball\n`/roll` - Roll dice\n`/flip` - Flip coin\n`/cat` - Random cat\n`/dog` - Random dog',
        inline=False
    )
    embed.add_field(
        name='ℹ️ Info',
        value='`/ping` - Check bot latency\n`/serverinfo` - Server information',
        inline=False
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='ping', description='Check bot latency')
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f'🏓 Pong! Latency: `{latency}ms`')

@bot.tree.command(name='rank', description='View your rank and level')
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    user_data = bot.db.get_user(str(interaction.guild.id), str(target.id))
    xp_needed = user_data['level'] * CONFIG['xp_per_level']
    
    all_users = bot.db.get_all_guild_users(str(interaction.guild.id))
    rank = next((i + 1 for i, u in enumerate(all_users) if u['user_id'] == str(target.id)), 'Unranked')
    
    progress = int((user_data['xp'] / xp_needed) * 20) if xp_needed > 0 else 0
    bar = '█' * progress + '░' * (20 - progress)
    
    color = 0xFF6B6B if user_data['level'] >= 50 else 0xFFD93D if user_data['level'] >= 30 else 0x6BCB77 if user_data['level'] >= 15 else 0x4D96FF
    
    embed = discord.Embed(color=color)
    embed.set_author(name=f"{target.display_name}'s Profile", icon_url=target.display_avatar.url)
    embed.description = f"""
**RANK** • #{rank} / {len(all_users)}
**LEVEL** • {user_data['level']}
**XP** • {user_data['xp']:,} / {xp_needed:,}

`{bar}`

**💰 BALANCE** • {user_data['coins']:,} coins
    """
    embed.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='leaderboard', description='View the server leaderboard')
async def leaderboard(interaction: discord.Interaction):
    all_users = bot.db.get_all_guild_users(str(interaction.guild.id))[:10]
    
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
        color=0x9B59B6,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text='Top 10 users by level and XP')
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='balance', description='Check your coin balance')
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    user_data = bot.db.get_user(str(interaction.guild.id), str(target.id))
    
    embed = discord.Embed(
        title='💰 Balance',
        description=f'{target.mention} has **{user_data["coins"]:,}** coins in wallet and **{user_data["bank"]:,}** in bank!\n**Total:** {user_data["coins"] + user_data["bank"]:,} coins',
        color=0xFFD700
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='daily', description='Claim your daily reward')
async def daily(interaction: discord.Interaction):
    user_data = bot.db.get_user(str(interaction.guild.id), str(interaction.user.id))
    now = datetime.now().timestamp()
    
    if now - user_data['last_daily'] < 86400:
        time_left = 86400 - (now - user_data['last_daily'])
        hours = int(time_left / 3600)
        await interaction.response.send_message(f'⏳ You already claimed your daily! Come back in {hours} hours.', ephemeral=True)
        return
    
    reward = 100
    user_data['coins'] += reward
    user_data['last_daily'] = now
    bot.db.set_user(str(interaction.guild.id), str(interaction.user.id), user_data)
    
    await interaction.response.send_message(f'✅ You claimed your daily reward of **{reward:,}** coins!\n💰 New balance: **{user_data["coins"]:,}** coins')

@bot.tree.command(name='work', description='Work to earn coins')
async def work(interaction: discord.Interaction):
    user_data = bot.db.get_user(str(interaction.guild.id), str(interaction.user.id))
    now = datetime.now().timestamp()
    
    if now - user_data['last_work'] < 3600:
        time_left = 3600 - (now - user_data['last_work'])
        minutes = int(time_left / 60)
        await interaction.response.send_message(f'⏳ You need to rest! Come back in {minutes} minutes.', ephemeral=True)
        return
    
    earnings = random.randint(10, 50)
    user_data['coins'] += earnings
    user_data['last_work'] = now
    bot.db.set_user(str(interaction.guild.id), str(interaction.user.id), user_data)
    
    jobs = [
        'You worked as a programmer and earned',
        'You delivered pizza and earned',
        'You streamed on Twitch and earned',
        'You mowed lawns and earned',
        'You washed cars and earned',
        'You tutored students and earned'
    ]
    
    await interaction.response.send_message(f'💼 {random.choice(jobs)} **{earnings:,}** coins!\n💰 New balance: **{user_data["coins"]:,}** coins')

@bot.tree.command(name='8ball', description='Ask the magic 8ball a question')
async def eightball(interaction: discord.Interaction, question: str):
    responses = [
        'Yes, definitely!', 'It is certain.', 'Without a doubt.', 'You may rely on it.',
        'As I see it, yes.', 'Most likely.', 'Outlook good.', 'Signs point to yes.',
        'Reply hazy, try again.', 'Ask again later.', 'Better not tell you now.',
        'Cannot predict now.', "Don't count on it.", 'My reply is no.', 'Very doubtful.'
    ]
    await interaction.response.send_message(f'🔮 **{question}**\n{random.choice(responses)}')

@bot.tree.command(name='roll', description='Roll a dice')
async def roll(interaction: discord.Interaction, sides: int = 6):
    if sides < 2 or sides > 100:
        await interaction.response.send_message('❌ Dice must have between 2 and 100 sides!', ephemeral=True)
        return
    result = random.randint(1, sides)
    await interaction.response.send_message(f'🎲 You rolled a **{result}** (1-{sides})')

@bot.tree.command(name='flip', description='Flip a coin')
async def flip(interaction: discord.Interaction):
    result = random.choice(['Heads', 'Tails'])
    await interaction.response.send_message(f'🪙 The coin landed on **{result}**!')

@bot.tree.command(name='cat', description='Get a random cat picture')
async def cat(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://api.thecatapi.com/v1/images/search') as resp:
                data = await resp.json()
                embed = discord.Embed(title='🐱 Random Kitty!', color=0xFF69B4)
                embed.set_image(url=data[0]['url'])
                embed.set_footer(text=f'Requested by {interaction.user.name}')
                await interaction.followup.send(embed=embed)
        except:
            await interaction.followup.send('Failed to fetch a cat picture 😿')

@bot.tree.command(name='dog', description='Get a random dog picture')
async def dog(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://api.thedogapi.com/v1/images/search') as resp:
                data = await resp.json()
                embed = discord.Embed(title='🐶 Random Doggy!', color=0xFF69B4)
                embed.set_image(url=data[0]['url'])
                embed.set_footer(text=f'Requested by {interaction.user.name}')
                await interaction.followup.send(embed=embed)
        except:
            await interaction.followup.send('Failed to fetch a dog picture 😥')

@bot.tree.command(name='serverinfo', description='Display server information')
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    
    embed = discord.Embed(
        title=f'📊 {guild.name}',
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(name='👑 Owner', value=guild.owner.mention, inline=True)
    embed.add_field(name='👥 Members', value=guild.member_count, inline=True)
    embed.add_field(name='📅 Created', value=guild.created_at.strftime('%Y-%m-%d'), inline=True)
    embed.add_field(name='💬 Channels', value=len(guild.channels), inline=True)
    embed.add_field(name='😀 Emojis', value=len(guild.emojis), inline=True)
    embed.add_field(name='🎭 Roles', value=len(guild.roles), inline=True)
    
    await interaction.response.send_message(embed=embed)

# Reaction Roles
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    
    # Get reaction role data
    guild_id = str(payload.guild_id)
    message_id = str(payload.message_id)
    
    if 'reaction_roles' not in bot.db.data:
        bot.db.data['reaction_roles'] = {}
    
    if guild_id not in bot.db.data['reaction_roles']:
        return
    
    if message_id not in bot.db.data['reaction_roles'][guild_id]:
        return
    
    emoji_str = str(payload.emoji)
    role_id = bot.db.data['reaction_roles'][guild_id][message_id].get(emoji_str)
    
    if not role_id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    role = guild.get_role(int(role_id))
    if not role:
        return
    
    member = guild.get_member(payload.user_id)
    if not member:
        return
    
    try:
        await member.add_roles(role)
        logger.info(f'✅ Added role {role.name} to {member.name}')
    except Exception as e:
        logger.error(f'❌ Error adding role: {e}')

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id:
        return
    
    guild_id = str(payload.guild_id)
    message_id = str(payload.message_id)
    
    if 'reaction_roles' not in bot.db.data:
        return
    
    if guild_id not in bot.db.data.get('reaction_roles', {}):
        return
    
    if message_id not in bot.db.data['reaction_roles'][guild_id]:
        return
    
    emoji_str = str(payload.emoji)
    role_id = bot.db.data['reaction_roles'][guild_id][message_id].get(emoji_str)
    
    if not role_id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    role = guild.get_role(int(role_id))
    if not role:
        return
    
    member = guild.get_member(payload.user_id)
    if not member:
        return
    
    try:
        await member.remove_roles(role)
        logger.info(f'➖ Removed role {role.name} from {member.name}')
    except Exception as e:
        logger.error(f'❌ Error removing role: {e}')

@bot.tree.command(name='reactionrole', description='[ADMIN] Create a reaction role')
@app_commands.describe(
    message_id='Message ID to add reactions to',
    emoji='Emoji to use (e.g., 🎮)',
    role='Role to assign'
)
@app_commands.default_permissions(administrator=True)
async def reactionrole(interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
    try:
        message = await interaction.channel.fetch_message(int(message_id))
    except discord.NotFound:
        await interaction.response.send_message('❌ Message not found in this channel!', ephemeral=True)
        return
    except ValueError:
        await interaction.response.send_message('❌ Invalid message ID!', ephemeral=True)
        return
    
    try:
        await message.add_reaction(emoji)
    except discord.HTTPException:
        await interaction.response.send_message('❌ Invalid emoji or unable to add reaction!', ephemeral=True)
        return
    
    # Save reaction role
    guild_id = str(interaction.guild.id)
    
    if 'reaction_roles' not in bot.db.data:
        bot.db.data['reaction_roles'] = {}
    
    if guild_id not in bot.db.data['reaction_roles']:
        bot.db.data['reaction_roles'][guild_id] = {}
    
    if message_id not in bot.db.data['reaction_roles'][guild_id]:
        bot.db.data['reaction_roles'][guild_id][message_id] = {}
    
    bot.db.data['reaction_roles'][guild_id][message_id][emoji] = str(role.id)
    bot.db.save()
    
    embed = discord.Embed(
        title='✅ Reaction Role Created',
        description=f'React with {emoji} on the message to get {role.mention}',
        color=0x00FF00
    )
    embed.add_field(name='Message ID', value=message_id, inline=True)
    embed.add_field(name='Emoji', value=emoji, inline=True)
    embed.add_field(name='Role', value=role.mention, inline=True)
    
    await interaction.response.send_message(embed=embed)
    logger.info(f'✅ Created reaction role: {emoji} -> {role.name}')

@bot.tree.command(name='removereactionrole', description='[ADMIN] Remove a reaction role')
@app_commands.describe(
    message_id='Message ID',
    emoji='Emoji to remove (leave empty to remove all)'
)
@app_commands.default_permissions(administrator=True)
async def removereactionrole(interaction: discord.Interaction, message_id: str, emoji: str = None):
    guild_id = str(interaction.guild.id)
    
    if 'reaction_roles' not in bot.db.data:
        bot.db.data['reaction_roles'] = {}
    
    if guild_id not in bot.db.data['reaction_roles'] or message_id not in bot.db.data['reaction_roles'].get(guild_id, {}):
        await interaction.response.send_message('❌ No reaction roles found for that message!', ephemeral=True)
        return
    
    if emoji:
        if emoji not in bot.db.data['reaction_roles'][guild_id][message_id]:
            await interaction.response.send_message('❌ That emoji is not set up for reaction roles!', ephemeral=True)
            return
        
        del bot.db.data['reaction_roles'][guild_id][message_id][emoji]
        bot.db.save()
        await interaction.response.send_message(f'✅ Removed reaction role for {emoji}')
    else:
        del bot.db.data['reaction_roles'][guild_id][message_id]
        bot.db.save()
        await interaction.response.send_message(f'✅ Removed all reaction roles from message {message_id}')

@bot.tree.command(name='listreactionroles', description='List all reaction roles')
async def listreactionroles(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    if 'reaction_roles' not in bot.db.data:
        bot.db.data['reaction_roles'] = {}
    
    guild_reactions = bot.db.data['reaction_roles'].get(guild_id, {})
    
    if not guild_reactions:
        await interaction.response.send_message('No reaction roles configured yet!')
        return
    
    embed = discord.Embed(
        title='🎭 Reaction Roles',
        color=0x9B59B6
    )
    
    for msg_id, reactions in guild_reactions.items():
        roles_text = []
        for emoji, role_id in reactions.items():
            role = interaction.guild.get_role(int(role_id))
            role_name = role.mention if role else f'Role ID: {role_id}'
            roles_text.append(f'{emoji} → {role_name}')
        
        embed.add_field(
            name=f'Message ID: {msg_id}',
            value='\n'.join(roles_text) if roles_text else 'No reactions',
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='createreactionpanel', description='[ADMIN] Create a reaction role panel')
@app_commands.describe(
    title='Panel title',
    description='Panel description'
)
@app_commands.default_permissions(administrator=True)
async def createreactionpanel(interaction: discord.Interaction, title: str, description: str):
    embed = discord.Embed(
        title=f'🎭 {title}',
        description=description,
        color=0x9B59B6
    )
    embed.set_footer(text='React below to get your roles!')
    
    message = await interaction.channel.send(embed=embed)
    
    await interaction.response.send_message(
        f'✅ Panel created! Message ID: `{message.id}`\n'
        f'Use `/reactionrole {message.id} <emoji> <role>` to add roles to it.',
        ephemeral=True
    )

# YouTube Notifications Commands
@bot.tree.command(name='setupyoutube', description='[ADMIN] Set up YouTube notifications in this channel')
@app_commands.default_permissions(administrator=True)
async def setupyoutube(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    if 'youtube' not in bot.db.data:
        bot.db.data['youtube'] = {}
    
    if guild_id not in bot.db.data['youtube']:
        bot.db.data['youtube'][guild_id] = {
            'enabled': True,
            'channel_id': None,
            'last_video_id': None
        }
    
    bot.db.data['youtube'][guild_id]['channel_id'] = str(interaction.channel.id)
    bot.db.data['youtube'][guild_id]['enabled'] = True
    bot.db.save()
    
    youtube_channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    
    if not youtube_channel_id:
        await interaction.response.send_message(
            '⚠️ YouTube notifications set up in this channel, but `YOUTUBE_CHANNEL_ID` environment variable is not set!\n'
            'Ask the bot owner to set it on Render.',
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title='✅ YouTube Notifications Enabled',
        description=f'New video notifications will be posted in {interaction.channel.mention}',
        color=0xFF0000
    )
    embed.add_field(name='Check Interval', value='Every 5 minutes', inline=True)
    embed.add_field(name='Status', value='🟢 Active', inline=True)
    
    await interaction.response.send_message(embed=embed)
    logger.info(f'✅ YouTube notifications enabled in {interaction.guild.name} → #{interaction.channel.name}')

@bot.tree.command(name='toggleyoutube', description='[ADMIN] Toggle YouTube notifications on/off')
@app_commands.default_permissions(administrator=True)
async def toggleyoutube(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    if 'youtube' not in bot.db.data:
        bot.db.data['youtube'] = {}
    
    if guild_id not in bot.db.data['youtube']:
        bot.db.data['youtube'][guild_id] = {
            'enabled': False,
            'channel_id': None,
            'last_video_id': None
        }
    
    # Toggle
    bot.db.data['youtube'][guild_id]['enabled'] = not bot.db.data['youtube'][guild_id].get('enabled', False)
    bot.db.save()
    
    status = 'enabled ✅' if bot.db.data['youtube'][guild_id]['enabled'] else 'disabled ❌'
    color = 0x00FF00 if bot.db.data['youtube'][guild_id]['enabled'] else 0x808080
    
    embed = discord.Embed(
        title='🔔 YouTube Notifications',
        description=f'YouTube notifications are now **{status}**',
        color=color,
        timestamp=datetime.utcnow()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='youtubestatus', description='Check YouTube notification status')
async def youtubestatus(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    if 'youtube' not in bot.db.data:
        bot.db.data['youtube'] = {}
    
    settings = bot.db.data['youtube'].get(guild_id, {
        'enabled': False,
        'channel_id': None,
        'last_video_id': None
    })
    
    youtube_channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    
    embed = discord.Embed(
        title='📺 YouTube Notification Status',
        color=0xFF0000
    )
    
    status = '🟢 Enabled' if settings.get('enabled') else '🔴 Disabled'
    embed.add_field(name='Status', value=status, inline=True)
    
    if settings.get('channel_id'):
        channel = interaction.guild.get_channel(int(settings['channel_id']))
        channel_name = channel.mention if channel else 'Channel not found'
        embed.add_field(name='Notification Channel', value=channel_name, inline=True)
    else:
        embed.add_field(name='Notification Channel', value='Not set', inline=True)
    
    if youtube_channel_id:
        embed.add_field(name='YouTube Channel ID', value=f'`{youtube_channel_id}`', inline=False)
    else:
        embed.add_field(name='⚠️ Warning', value='`YOUTUBE_CHANNEL_ID` not set in environment variables', inline=False)
    
    if settings.get('last_video_id'):
        embed.add_field(name='Last Video ID', value=f'`{settings["last_video_id"]}`', inline=False)
    
    embed.set_footer(text='Use /setupyoutube to configure')
    
    await interaction.response.send_message(embed=embed)

# Run bot
if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error('❌ DISCORD_TOKEN not set!')
        exit(1)
    
    logger.info('🚀 Starting bot...')
    bot.run(token)