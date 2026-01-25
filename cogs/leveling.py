import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        user_data = self.bot.db.get_user(str(message.guild.id), str(message.author.id))
        now = datetime.now().timestamp()
        
        if now - user_data['last_message'] >= self.bot.config['xp_cooldown']:
            user_data['last_message'] = now
            xp_gain = random.randint(self.bot.config['xp_min'], self.bot.config['xp_max'])
            user_data['xp'] += xp_gain
            xp_needed = user_data['level'] * self.bot.config['xp_per_level']
            
            if user_data['xp'] >= xp_needed:
                user_data['level'] += 1
                user_data['xp'] = 0
                
                coin_reward = user_data['level'] * self.bot.config['level_up_multiplier']
                user_data['coins'] += coin_reward
                
                messages = [
                    f'🎉 GG {message.author.mention}! You leveled up to **Level {user_data["level"]}**!',
                    f'⭐ Congrats {message.author.mention}! You\'re now **Level {user_data["level"]}**!',
                    f'🚀 Level up! {message.author.mention} reached **Level {user_data["level"]}**!'
                ]
                
                await message.channel.send(
                    f'{random.choice(messages)} You earned **{coin_reward:,} coins**! 💰'
                )
            
            self.bot.db.set_user(str(message.guild.id), str(message.author.id), user_data)
    
    @app_commands.command(name='rank', description='View your rank and level')
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        user_data = self.bot.db.get_user(str(interaction.guild.id), str(target.id))
        xp_needed = user_data['level'] * self.bot.config['xp_per_level']
        
        all_users = self.bot.db.get_all_guild_users(str(interaction.guild.id))
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
    
    @app_commands.command(name='leaderboard', description='View the server leaderboard')
    async def leaderboard(self, interaction: discord.Interaction):
        all_users = self.bot.db.get_all_guild_users(str(interaction.guild.id))[:10]
        
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

async def setup(bot):
    await bot.add_cog(Leveling(bot))