import discord
from discord.ext import commands
from discord import app_commands
import re
import random
import string

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.domain = "u.chers.moe"
    
    def is_valid_url(self, url):
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    def generate_short_code(self, length=6):
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def get_guild_data(self, guild_id):
        if 'guilds' not in self.bot.db.data:
            self.bot.db.data['guilds'] = {}
        if str(guild_id) not in self.bot.db.data['guilds']:
            self.bot.db.data['guilds'][str(guild_id)] = {'urls': {}}
        if 'urls' not in self.bot.db.data['guilds'][str(guild_id)]:
            self.bot.db.data['guilds'][str(guild_id)]['urls'] = {}
        return self.bot.db.data['guilds'][str(guild_id)]
    
    @app_commands.command(name='shorten', description='Shorten a long URL')
    @app_commands.describe(url='The URL you want to shorten')
    async def shorten_url(self, interaction: discord.Interaction, url: str):
        if not self.is_valid_url(url):
            await interaction.response.send_message(
                'Please provide a valid URL',
                ephemeral=True
            )
            return
        
        guild_data = self.get_guild_data(interaction.guild_id)
        
        for code, stored_url in guild_data['urls'].items():
            if stored_url == url:
                shortened = f"https://{self.domain}/{code}"
                embed = discord.Embed(title='URL Shortened', color=0x5865F2)
                embed.add_field(name='Original', value=url[:100] + ('...' if len(url) > 100 else ''), inline=False)
                embed.add_field(name='Shortened', value=shortened, inline=False)
                await interaction.response.send_message(embed=embed)
                return
        
        code = self.generate_short_code()
        while code in guild_data['urls']:
            code = self.generate_short_code()
        
        guild_data['urls'][code] = url
        self.bot.db.save()
        
        shortened = f"https://{self.domain}/{code}"
        
        embed = discord.Embed(title='URL Shortened', color=0x5865F2)
        embed.add_field(name='Original', value=url[:100] + ('...' if len(url) > 100 else ''), inline=False)
        embed.add_field(name='Shortened', value=shortened, inline=False)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))