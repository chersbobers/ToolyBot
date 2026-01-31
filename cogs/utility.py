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
    @app_commands.describe(
        url='The URL you want to shorten',
        code='Custom short code (optional)'
    )
    async def shorten_url(self, interaction: discord.Interaction, url: str, code: str = None):
        if not self.is_valid_url(url):
            await interaction.response.send_message(
                'Please provide a valid URL',
                ephemeral=True
            )
            return
        
        guild_data = self.get_guild_data(interaction.guild_id)
        
        for existing_code, stored_url in guild_data['urls'].items():
            if stored_url == url:
                shortened = f"https://{self.domain}/{existing_code}"
                embed = discord.Embed(title='URL Already Shortened', color=0x5865F2)
                embed.add_field(name='Original', value=url[:100] + ('...' if len(url) > 100 else ''), inline=False)
                embed.add_field(name='Shortened', value=shortened, inline=False)
                await interaction.response.send_message(embed=embed)
                return
        
        if code:
            if code in guild_data['urls']:
                await interaction.response.send_message(
                    'This short code is already taken',
                    ephemeral=True
                )
                return
        else:
            code = self.generate_short_code()
            while code in guild_data['urls']:
                code = self.generate_short_code()
        
        guild_data['urls'][code] = url
        self.bot.db.save()
        
        shortened = f"https://{self.domain}/{code}"
        
        embed = discord.Embed(title='URL Shortened', color=0x5865F2)
        embed.add_field(name='Original', value=url[:100] + ('...' if len(url) > 100 else ''), inline=False)
        embed.add_field(name='Shortened', value=shortened, inline=False)
        embed.add_field(name='Code', value=code, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='expand', description='Get the original URL from a short code')
    @app_commands.describe(code='The short code to expand')
    async def expand_url(self, interaction: discord.Interaction, code: str):
        guild_data = self.get_guild_data(interaction.guild_id)
        
        if code in guild_data['urls']:
            original_url = guild_data['urls'][code]
            embed = discord.Embed(title='URL Expanded', color=0x5865F2)
            embed.add_field(name='Code', value=code, inline=False)
            embed.add_field(name='Original URL', value=original_url, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message('Short code not found', ephemeral=True)
    
    @app_commands.command(name='listshort', description='List all shortened URLs')
    async def list_short(self, interaction: discord.Interaction):
        guild_data = self.get_guild_data(interaction.guild_id)
        
        if not guild_data['urls']:
            await interaction.response.send_message('No shortened URLs found', ephemeral=True)
            return
        
        embed = discord.Embed(title='Shortened URLs', color=0x5865F2)
        
        count = 0
        for code, url in guild_data['urls'].items():
            if count >= 25:
                break
            shortened = f"https://{self.domain}/{code}"
            embed.add_field(
                name=code,
                value=f"{url[:50]}{'...' if len(url) > 50 else ''}\n{shortened}",
                inline=False
            )
            count += 1
        
        if len(guild_data['urls']) > 25:
            embed.set_footer(text=f'Showing 25 of {len(guild_data["urls"])} URLs')
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='deleteshort', description='Delete a shortened URL')
    @app_commands.describe(code='The short code to delete')
    async def delete_short(self, interaction: discord.Interaction, code: str):
        guild_data = self.get_guild_data(interaction.guild_id)
        
        if code in guild_data['urls']:
            url = guild_data['urls'][code]
            del guild_data['urls'][code]
            self.bot.db.save()
            
            embed = discord.Embed(title='URL Deleted', color=0x5865F2)
            embed.add_field(name='Code', value=code, inline=False)
            embed.add_field(name='Original URL', value=url, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message('Short code not found', ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utility(bot))