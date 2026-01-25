import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='balance', description='Check your coin balance')
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        user_data = self.bot.db.get_user(str(interaction.guild.id), str(target.id))
        
        embed = discord.Embed(
            title='💰 Balance',
            description=f'{target.mention} has **{user_data["coins"]:,}** coins in wallet and **{user_data["bank"]:,}** in bank!\n**Total:** {user_data["coins"] + user_data["bank"]:,} coins',
            color=0xFFD700
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='daily', description='Claim your daily reward')
    async def daily(self, interaction: discord.Interaction):
        user_data = self.bot.db.get_user(str(interaction.guild.id), str(interaction.user.id))
        now = datetime.now().timestamp()
        
        if now - user_data['last_daily'] < 86400:
            time_left = 86400 - (now - user_data['last_daily'])
            hours = int(time_left / 3600)
            await interaction.response.send_message(f'⏳ You already claimed your daily! Come back in {hours} hours.', ephemeral=True)
            return
        
        reward = 100
        user_data['coins'] += reward
        user_data['last_daily'] = now
        self.bot.db.set_user(str(interaction.guild.id), str(interaction.user.id), user_data)
        
        await interaction.response.send_message(f'✅ You claimed your daily reward of **{reward:,}** coins!\n💰 New balance: **{user_data["coins"]:,}** coins')
    
    @app_commands.command(name='work', description='Work to earn coins')
    async def work(self, interaction: discord.Interaction):
        user_data = self.bot.db.get_user(str(interaction.guild.id), str(interaction.user.id))
        now = datetime.now().timestamp()
        
        if now - user_data['last_work'] < 3600:
            time_left = 3600 - (now - user_data['last_work'])
            minutes = int(time_left / 60)
            await interaction.response.send_message(f'⏳ You need to rest! Come back in {minutes} minutes.', ephemeral=True)
            return
        
        earnings = random.randint(10, 50)
        user_data['coins'] += earnings
        user_data['last_work'] = now
        self.bot.db.set_user(str(interaction.guild.id), str(interaction.user.id), user_data)
        
        jobs = [
            'You worked as a programmer and earned',
            'You delivered pizza and earned',
            'You streamed on Twitch and earned',
            'You mowed lawns and earned',
            'You washed cars and earned',
            'You tutored students and earned'
        ]
        
        await interaction.response.send_message(f'💼 {random.choice(jobs)} **{earnings:,}** coins!\n💰 New balance: **{user_data["coins"]:,}** coins')

async def setup(bot):
    await bot.add_cog(Economy(bot))