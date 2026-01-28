import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import logging
import feedparser

logger = logging.getLogger('bot')

class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_youtube.start()
    
    def cog_unload(self):
        self.check_youtube.cancel()
    
    @tasks.loop(seconds=300)
    async def check_youtube(self):
        if 'youtube' not in self.bot.db.data:
            return
        
        for guild_id, settings in self.bot.db.data['youtube'].items():
            if not settings.get('enabled') or not settings.get('channel_id') or not settings.get('youtube_channel_id'):
                continue
            
            try:
                feed_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={settings["youtube_channel_id"]}'
                feed = await asyncio.to_thread(feedparser.parse, feed_url)
                
                if not feed.entries:
                    continue
                
                latest = feed.entries[0]
                video_id = latest.yt_videoid if hasattr(latest, 'yt_videoid') else latest.id.split(':')[-1]
                
                if video_id != settings.get('last_video_id') and settings.get('last_video_id'):
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue
                    
                    channel = guild.get_channel(int(settings['channel_id']))
                    if not channel:
                        continue
                    
                    embed = discord.Embed(
                        title='New YouTube Video!',
                        description=f'**{latest.title}**',
                        url=latest.link,
                        color=0xFF0000,
                        timestamp=datetime.utcnow()
                    )
                    
                    if hasattr(latest, 'media_thumbnail') and latest.media_thumbnail:
                        embed.set_thumbnail(url=latest.media_thumbnail[0]['url'])
                    
                    embed.add_field(name='Channel', value=latest.author, inline=True)
                    
                    if hasattr(latest, 'published'):
                        embed.add_field(name='Published', value=latest.published, inline=True)
                    
                    await channel.send('New video alert! @everyone', embed=embed)
                    logger.info(f'Sent notification for: {latest.title}')
                
                settings['last_video_id'] = video_id
                self.bot.db.save()
            
            except Exception as e:
                logger.error(f'Error checking YouTube: {e}')
    
    @check_youtube.before_loop
    async def before_check_youtube(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command(name='ping', description='Check bot latency')
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f'Pong! Latency: `{latency}ms`')
    
    @app_commands.command(name='serverinfo', description='Display server information')
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        embed = discord.Embed(
            title=f'{guild.name}',
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name='Owner', value=guild.owner.mention, inline=True)
        embed.add_field(name='Members', value=guild.member_count, inline=True)
        embed.add_field(name='Created', value=guild.created_at.strftime('%Y-%m-%d'), inline=True)
        embed.add_field(name='Channels', value=len(guild.channels), inline=True)
        embed.add_field(name='Emojis', value=len(guild.emojis), inline=True)
        embed.add_field(name='Roles', value=len(guild.roles), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='userinfo', description='Display user information')
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        
        embed = discord.Embed(
            title=f'{target.name}',
            color=target.color if target.color != discord.Color.default() else 0x5865F2,
            timestamp=datetime.utcnow()
        )
        
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(name='ID', value=target.id, inline=True)
        embed.add_field(name='Nickname', value=target.nick or 'None', inline=True)
        embed.add_field(name='Bot', value='Yes' if target.bot else 'No', inline=True)
        embed.add_field(name='Joined Server', value=target.joined_at.strftime('%Y-%m-%d %H:%M') if target.joined_at else 'Unknown', inline=True)
        embed.add_field(name='Account Created', value=target.created_at.strftime('%Y-%m-%d %H:%M'), inline=True)
        
        roles = [role.mention for role in target.roles if role.name != '@everyone']
        embed.add_field(name=f'Roles ({len(roles)})', value=' '.join(roles) if roles else 'None', inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='kick', description='[MOD] Kick a member from the server')
    @app_commands.describe(member='Member to kick', reason='Reason for kick')
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = 'No reason provided'):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message('You cannot kick this member!', ephemeral=True)
            return
        
        if member == interaction.guild.owner:
            await interaction.response.send_message('You cannot kick the server owner!', ephemeral=True)
            return
        
        try:
            await member.kick(reason=f'{reason} | Kicked by {interaction.user}')
            
            embed = discord.Embed(
                title='Member Kicked',
                description=f'{member.mention} has been kicked from the server',
                color=0xFF9500,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Moderator', value=interaction.user.mention, inline=True)
            embed.add_field(name='Reason', value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            logger.info(f'{member} kicked by {interaction.user} - Reason: {reason}')
        except discord.Forbidden:
            await interaction.response.send_message('I do not have permission to kick this member!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'An error occurred: {e}', ephemeral=True)
    
    @app_commands.command(name='ban', description='[MOD] Ban a member from the server')
    @app_commands.describe(member='Member to ban', reason='Reason for ban', delete_days='Days of messages to delete (0-7)')
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = 'No reason provided', delete_days: int = 0):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message('You cannot ban this member!', ephemeral=True)
            return
        
        if member == interaction.guild.owner:
            await interaction.response.send_message('You cannot ban the server owner!', ephemeral=True)
            return
        
        if delete_days < 0 or delete_days > 7:
            await interaction.response.send_message('Delete days must be between 0 and 7!', ephemeral=True)
            return
        
        try:
            await member.ban(reason=f'{reason} | Banned by {interaction.user}', delete_message_days=delete_days)
            
            embed = discord.Embed(
                title='Member Banned',
                description=f'{member.mention} has been banned from the server',
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Moderator', value=interaction.user.mention, inline=True)
            embed.add_field(name='Reason', value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            logger.info(f'{member} banned by {interaction.user} - Reason: {reason}')
        except discord.Forbidden:
            await interaction.response.send_message('I do not have permission to ban this member!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'An error occurred: {e}', ephemeral=True)
    
    @app_commands.command(name='unban', description='[MOD] Unban a user from the server')
    @app_commands.describe(user_id='User ID to unban', reason='Reason for unban')
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = 'No reason provided'):
        try:
            user = await self.bot.fetch_user(int(user_id))
        except:
            await interaction.response.send_message('Invalid user ID!', ephemeral=True)
            return
        
        try:
            await interaction.guild.unban(user, reason=f'{reason} | Unbanned by {interaction.user}')
            
            embed = discord.Embed(
                title='User Unbanned',
                description=f'{user.mention} has been unbanned from the server',
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Moderator', value=interaction.user.mention, inline=True)
            embed.add_field(name='Reason', value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            logger.info(f'{user} unbanned by {interaction.user} - Reason: {reason}')
        except discord.NotFound:
            await interaction.response.send_message('This user is not banned!', ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message('I do not have permission to unban users!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'An error occurred: {e}', ephemeral=True)
    
    @app_commands.command(name='timeout', description='[MOD] Timeout a member')
    @app_commands.describe(member='Member to timeout', duration='Duration in minutes', reason='Reason for timeout')
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = 'No reason provided'):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message('You cannot timeout this member!', ephemeral=True)
            return
        
        if member == interaction.guild.owner:
            await interaction.response.send_message('You cannot timeout the server owner!', ephemeral=True)
            return
        
        if duration < 1 or duration > 40320:
            await interaction.response.send_message('Duration must be between 1 minute and 28 days!', ephemeral=True)
            return
        
        try:
            timeout_until = datetime.utcnow() + timedelta(minutes=duration)
            await member.timeout(timeout_until, reason=f'{reason} | Timed out by {interaction.user}')
            
            embed = discord.Embed(
                title='Member Timed Out',
                description=f'{member.mention} has been timed out',
                color=0xFFA500,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Moderator', value=interaction.user.mention, inline=True)
            embed.add_field(name='Duration', value=f'{duration} minutes', inline=True)
            embed.add_field(name='Reason', value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            logger.info(f'{member} timed out by {interaction.user} for {duration}m - Reason: {reason}')
        except discord.Forbidden:
            await interaction.response.send_message('I do not have permission to timeout this member!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'An error occurred: {e}', ephemeral=True)
    
    @app_commands.command(name='warn', description='[MOD] Warn a member')
    @app_commands.describe(member='Member to warn', reason='Reason for warning')
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)
        
        if 'warnings' not in self.bot.db.data:
            self.bot.db.data['warnings'] = {}
        
        if guild_id not in self.bot.db.data['warnings']:
            self.bot.db.data['warnings'][guild_id] = {}
        
        if user_id not in self.bot.db.data['warnings'][guild_id]:
            self.bot.db.data['warnings'][guild_id][user_id] = []
        
        warning = {
            'reason': reason,
            'moderator': str(interaction.user.id),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.bot.db.data['warnings'][guild_id][user_id].append(warning)
        self.bot.db.save()
        
        warning_count = len(self.bot.db.data['warnings'][guild_id][user_id])
        
        embed = discord.Embed(
            title='Member Warned',
            description=f'{member.mention} has been warned',
            color=0xFFFF00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='Moderator', value=interaction.user.mention, inline=True)
        embed.add_field(name='Total Warnings', value=warning_count, inline=True)
        embed.add_field(name='Reason', value=reason, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
        try:
            await member.send(f'You have been warned in **{interaction.guild.name}**\n**Reason:** {reason}\n**Total Warnings:** {warning_count}')
        except:
            pass
        
        logger.info(f'{member} warned by {interaction.user} - Reason: {reason}')
    
    @app_commands.command(name='warnings', description='View warnings for a member')
    @app_commands.describe(member='Member to check warnings for')
    async def warnings(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        guild_id = str(interaction.guild.id)
        user_id = str(target.id)
        
        if 'warnings' not in self.bot.db.data:
            self.bot.db.data['warnings'] = {}
        
        user_warnings = self.bot.db.data['warnings'].get(guild_id, {}).get(user_id, [])
        
        if not user_warnings:
            await interaction.response.send_message(f'{target.mention} has no warnings!', ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f'Warnings for {target.display_name}',
            color=0xFFFF00,
            timestamp=datetime.utcnow()
        )
        
        for i, warning in enumerate(user_warnings[-10:], 1):
            moderator = interaction.guild.get_member(int(warning['moderator']))
            mod_name = moderator.mention if moderator else f"<@{warning['moderator']}>"
            timestamp = datetime.fromisoformat(warning['timestamp']).strftime('%Y-%m-%d %H:%M')
            
            embed.add_field(
                name=f'Warning #{i}',
                value=f'**Moderator:** {mod_name}\n**Reason:** {warning["reason"]}\n**Date:** {timestamp}',
                inline=False
            )
        
        embed.set_footer(text=f'Total warnings: {len(user_warnings)} | Showing last 10')
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='clearwarnings', description='[MOD] Clear warnings for a member')
    @app_commands.describe(member='Member to clear warnings for')
    @app_commands.default_permissions(moderate_members=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)
        
        if 'warnings' not in self.bot.db.data:
            self.bot.db.data['warnings'] = {}
        
        if guild_id not in self.bot.db.data['warnings'] or user_id not in self.bot.db.data['warnings'][guild_id]:
            await interaction.response.send_message(f'{member.mention} has no warnings to clear!', ephemeral=True)
            return
        
        warning_count = len(self.bot.db.data['warnings'][guild_id][user_id])
        self.bot.db.data['warnings'][guild_id][user_id] = []
        self.bot.db.save()
        
        embed = discord.Embed(
            title='Warnings Cleared',
            description=f'Cleared {warning_count} warning(s) for {member.mention}',
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='Moderator', value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        logger.info(f'Cleared {warning_count} warnings for {member} by {interaction.user}')
    
    @app_commands.command(name='purge', description='[MOD] Delete multiple messages')
    @app_commands.describe(amount='Number of messages to delete (1-100)', member='Only delete messages from this member (optional)')
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int, member: discord.Member = None):
        if amount < 1 or amount > 100:
            await interaction.response.send_message('Amount must be between 1 and 100!', ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            if member:
                deleted = await interaction.channel.purge(limit=amount, check=lambda m: m.author == member)
            else:
                deleted = await interaction.channel.purge(limit=amount)
            
            await interaction.followup.send(f'Deleted {len(deleted)} message(s)!', ephemeral=True)
            logger.info(f'{interaction.user} purged {len(deleted)} messages in #{interaction.channel.name}')
        except discord.Forbidden:
            await interaction.followup.send('I do not have permission to delete messages!', ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f'An error occurred: {e}', ephemeral=True)
    
    @app_commands.command(name='lock', description='[MOD] Lock a channel')
    @app_commands.describe(channel='Channel to lock (defaults to current channel)')
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        
        try:
            await target_channel.set_permissions(interaction.guild.default_role, send_messages=False)
            
            embed = discord.Embed(
                title='Channel Locked',
                description=f'{target_channel.mention} has been locked',
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Moderator', value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            logger.info(f'{target_channel.name} locked by {interaction.user}')
        except discord.Forbidden:
            await interaction.response.send_message('I do not have permission to lock this channel!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'An error occurred: {e}', ephemeral=True)
    
    @app_commands.command(name='unlock', description='[MOD] Unlock a channel')
    @app_commands.describe(channel='Channel to unlock (defaults to current channel)')
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        
        try:
            await target_channel.set_permissions(interaction.guild.default_role, send_messages=None)
            
            embed = discord.Embed(
                title='Channel Unlocked',
                description=f'{target_channel.mention} has been unlocked',
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Moderator', value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            logger.info(f'{target_channel.name} unlocked by {interaction.user}')
        except discord.Forbidden:
            await interaction.response.send_message('I do not have permission to unlock this channel!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'An error occurred: {e}', ephemeral=True)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        
        guild_id = str(payload.guild_id)
        message_id = str(payload.message_id)
        
        if 'reaction_roles' not in self.bot.db.data:
            self.bot.db.data['reaction_roles'] = {}
        
        if guild_id not in self.bot.db.data['reaction_roles']:
            return
        
        if message_id not in self.bot.db.data['reaction_roles'][guild_id]:
            return
        
        emoji_str = str(payload.emoji)
        role_id = self.bot.db.data['reaction_roles'][guild_id][message_id].get(emoji_str)
        
        if not role_id:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
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
            logger.info(f'Added role {role.name} to {member.name}')
        except Exception as e:
            logger.error(f'Error adding role: {e}')
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        
        guild_id = str(payload.guild_id)
        message_id = str(payload.message_id)
        
        if 'reaction_roles' not in self.bot.db.data:
            return
        
        if guild_id not in self.bot.db.data.get('reaction_roles', {}):
            return
        
        if message_id not in self.bot.db.data['reaction_roles'][guild_id]:
            return
        
        emoji_str = str(payload.emoji)
        role_id = self.bot.db.data['reaction_roles'][guild_id][message_id].get(emoji_str)
        
        if not role_id:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
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
            logger.info(f'Removed role {role.name} from {member.name}')
        except Exception as e:
            logger.error(f'Error removing role: {e}')
    
    @app_commands.command(name='reactionrole', description='[ADMIN] Create a reaction role')
    @app_commands.describe(message_id='Message ID to add reactions to', emoji='Emoji to use (e.g., 🎮)', role='Role to assign')
    @app_commands.default_permissions(administrator=True)
    async def reactionrole(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        try:
            message = await interaction.channel.fetch_message(int(message_id))
        except discord.NotFound:
            await interaction.response.send_message('Message not found in this channel!', ephemeral=True)
            return
        except ValueError:
            await interaction.response.send_message('Invalid message ID!', ephemeral=True)
            return
        
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await interaction.response.send_message('Invalid emoji or unable to add reaction!', ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        
        if 'reaction_roles' not in self.bot.db.data:
            self.bot.db.data['reaction_roles'] = {}
        
        if guild_id not in self.bot.db.data['reaction_roles']:
            self.bot.db.data['reaction_roles'][guild_id] = {}
        
        if message_id not in self.bot.db.data['reaction_roles'][guild_id]:
            self.bot.db.data['reaction_roles'][guild_id][message_id] = {}
        
        self.bot.db.data['reaction_roles'][guild_id][message_id][emoji] = str(role.id)
        self.bot.db.save()
        
        embed = discord.Embed(
            title='Reaction Role Created',
            description=f'React with {emoji} on the message to get {role.mention}',
            color=0x00FF00
        )
        embed.add_field(name='Message ID', value=message_id, inline=True)
        embed.add_field(name='Emoji', value=emoji, inline=True)
        embed.add_field(name='Role', value=role.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        logger.info(f'Created reaction role: {emoji} -> {role.name}')
    
    @app_commands.command(name='removereactionrole', description='[ADMIN] Remove a reaction role')
    @app_commands.describe(message_id='Message ID', emoji='Emoji to remove (leave empty to remove all)')
    @app_commands.default_permissions(administrator=True)
    async def removereactionrole(self, interaction: discord.Interaction, message_id: str, emoji: str = None):
        guild_id = str(interaction.guild.id)
        
        if 'reaction_roles' not in self.bot.db.data:
            self.bot.db.data['reaction_roles'] = {}
        
        if guild_id not in self.bot.db.data['reaction_roles'] or message_id not in self.bot.db.data['reaction_roles'].get(guild_id, {}):
            await interaction.response.send_message('No reaction roles found for that message!', ephemeral=True)
            return
        
        if emoji:
            if emoji not in self.bot.db.data['reaction_roles'][guild_id][message_id]:
                await interaction.response.send_message('That emoji is not set up for reaction roles!', ephemeral=True)
                return
            
            del self.bot.db.data['reaction_roles'][guild_id][message_id][emoji]
            self.bot.db.save()
            await interaction.response.send_message(f'Removed reaction role for {emoji}')
        else:
            del self.bot.db.data['reaction_roles'][guild_id][message_id]
            self.bot.db.save()
            await interaction.response.send_message(f'Removed all reaction roles from message {message_id}')
    
    @app_commands.command(name='listreactionroles', description='List all reaction roles')
    async def listreactionroles(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if 'reaction_roles' not in self.bot.db.data:
            self.bot.db.data['reaction_roles'] = {}
        
        guild_reactions = self.bot.db.data['reaction_roles'].get(guild_id, {})
        
        if not guild_reactions:
            await interaction.response.send_message('No reaction roles configured yet!')
            return
        
        embed = discord.Embed(
            title='Reaction Roles',
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
    
    @app_commands.command(name='createreactionpanel', description='[ADMIN] Create a reaction role panel')
    @app_commands.describe(title='Panel title', description='Panel description')
    @app_commands.default_permissions(administrator=True)
    async def createreactionpanel(self, interaction: discord.Interaction, title: str, description: str):
        embed = discord.Embed(
            title=f'{title}',
            description=description,
            color=0x9B59B6
        )
        embed.set_footer(text='React below to get your roles!')
        
        message = await interaction.channel.send(embed=embed)
        
        await interaction.response.send_message(
            f'Panel created! Message ID: `{message.id}`\n'
            f'Use `/reactionrole {message.id} <emoji> <role>` to add roles to it.',
            ephemeral=True
        )
    
    @app_commands.command(name='setupyoutube', description='[ADMIN] Set up YouTube notifications')
    @app_commands.describe(youtube_channel_id='YouTube Channel ID (from channel URL)', notification_channel='Discord channel for notifications (defaults to current channel)')
    @app_commands.default_permissions(administrator=True)
    async def setupyoutube(self, interaction: discord.Interaction, youtube_channel_id: str, notification_channel: discord.TextChannel = None):
        guild_id = str(interaction.guild.id)
        channel = notification_channel or interaction.channel
        
        if 'youtube' not in self.bot.db.data:
            self.bot.db.data['youtube'] = {}
        
        self.bot.db.data['youtube'][guild_id] = {
            'enabled': True,
            'channel_id': str(channel.id),
            'youtube_channel_id': youtube_channel_id.strip(),
            'last_video_id': None
        }
        self.bot.db.save()
        
        embed = discord.Embed(
            title='YouTube Notifications Configured',
            description=f'New video notifications will be posted in {channel.mention}',
            color=0xFF0000
        )
        embed.add_field(name='YouTube Channel ID', value=f'`{youtube_channel_id}`', inline=False)
        embed.add_field(name='Check Interval', value='Every 5 minutes', inline=True)
        embed.add_field(name='Status', value='Active', inline=True)
        
        await interaction.response.send_message(embed=embed)
        logger.info(f'YouTube notifications enabled in {interaction.guild.name} → #{channel.name}')
    
    @app_commands.command(name='toggleyoutube', description='[ADMIN] Toggle YouTube notifications on/off')
    @app_commands.default_permissions(administrator=True)
    async def toggleyoutube(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if 'youtube' not in self.bot.db.data:
            self.bot.db.data['youtube'] = {}
        
        if guild_id not in self.bot.db.data['youtube']:
            self.bot.db.data['youtube'][guild_id] = {
                'enabled': False,
                'channel_id': None,
                'last_video_id': None
            }
        
        self.bot.db.data['youtube'][guild_id]['enabled'] = not self.bot.db.data['youtube'][guild_id].get('enabled', False)
        self.bot.db.save()
        
        status = 'enabled' if self.bot.db.data['youtube'][guild_id]['enabled'] else 'disabled'
        color = 0x00FF00 if self.bot.db.data['youtube'][guild_id]['enabled'] else 0x808080
        
        embed = discord.Embed(
            title='YouTube Notifications',
            description=f'YouTube notifications are now **{status}**',
            color=color,
            timestamp=datetime.utcnow()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='youtubestatus', description='Check YouTube notification status')
    async def youtubestatus(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if 'youtube' not in self.bot.db.data:
            self.bot.db.data['youtube'] = {}
        
        settings = self.bot.db.data['youtube'].get(guild_id, {
            'enabled': False,
            'channel_id': None,
            'last_video_id': None
        })
        
        embed = discord.Embed(
            title='YouTube Notification Status',
            color=0xFF0000
        )
        
        status = 'Enabled' if settings.get('enabled') else 'Disabled'
        embed.add_field(name='Status', value=status, inline=True)
        
        if settings.get('channel_id'):
            channel = interaction.guild.get_channel(int(settings['channel_id']))
            channel_name = channel.mention if channel else 'Channel not found'
            embed.add_field(name='Notification Channel', value=channel_name, inline=True)
        else:
            embed.add_field(name='Notification Channel', value='Not set', inline=True)
        
        if settings.get('youtube_channel_id'):
            embed.add_field(name='YouTube Channel ID', value=f'`{settings["youtube_channel_id"]}`', inline=False)
        else:
            embed.add_field(name='Warning', value='YouTube Channel ID not set', inline=False)
        
        if settings.get('last_video_id'):
            embed.add_field(name='Last Video ID', value=f'`{settings["last_video_id"]}`', inline=False)
        
        embed.set_footer(text='Use /setupyoutube to configure')
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='testlastvideo', description='[ADMIN] Manually announce the latest YouTube video')
    @app_commands.default_permissions(administrator=True)
    async def testlastvideo(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if 'youtube' not in self.bot.db.data:
            self.bot.db.data['youtube'] = {}
        
        settings = self.bot.db.data['youtube'].get(guild_id, {})
        
        if not settings.get('youtube_channel_id'):
            await interaction.response.send_message('YouTube Channel ID not configured! Use `/setupyoutube` first.', ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            feed_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={settings["youtube_channel_id"]}'
            feed = await asyncio.to_thread(feedparser.parse, feed_url)
            
            if not feed.entries:
                await interaction.followup.send('No videos found for this channel!')
                return
            
            latest = feed.entries[0]
            video_id = latest.yt_videoid if hasattr(latest, 'yt_videoid') else latest.id.split(':')[-1]
            
            embed = discord.Embed(
                title='Latest YouTube Video (Test)',
                description=f'**{latest.title}**',
                url=latest.link,
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            
            if hasattr(latest, 'media_thumbnail') and latest.media_thumbnail:
                embed.set_thumbnail(url=latest.media_thumbnail[0]['url'])
            
            embed.add_field(name='Channel', value=latest.author, inline=True)
            
            if hasattr(latest, 'published'):
                embed.add_field(name='Published', value=latest.published, inline=True)
            
            embed.set_footer(text='This is a test notification')
            
            await interaction.followup.send(embed=embed)
            logger.info(f'Test notification sent for: {latest.title}')
        
        except Exception as e:
            await interaction.followup.send(f'Error fetching video: {e}')
            logger.error(f'Error in testlastvideo: {e}')

async def setup(bot):
    await bot.add_cog(System(bot))