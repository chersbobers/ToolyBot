import discord
from discord import app_commands
from discord.ext import commands
import random
import aiohttp

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='8ball', description='Ask the magic 8ball a question')
    async def eightball(self, interaction: discord.Interaction, question: str):
        responses = [
            'Yes, definitely!', 'It is certain.', 'Without a doubt.', 'You may rely on it.',
            'As I see it, yes.', 'Most likely.', 'Outlook good.', 'Signs point to yes.',
            'Reply hazy, try again.', 'Ask again later.', 'Better not tell you now.',
            'Cannot predict now.', "Don't count on it.", 'My reply is no.', 'Very doubtful.'
        ]
        await interaction.response.send_message(f'🔮 **{question}**\n{random.choice(responses)}')
    
    @app_commands.command(name='roll', description='Roll a dice')
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        if sides < 2 or sides > 100:
            await interaction.response.send_message('❌ Dice must have between 2 and 100 sides!', ephemeral=True)
            return
        result = random.randint(1, sides)
        await interaction.response.send_message(f'🎲 You rolled a **{result}** (1-{sides})')
    
    @app_commands.command(name='flip', description='Flip a coin')
    async def flip(self, interaction: discord.Interaction):
        result = random.choice(['Heads', 'Tails'])
        await interaction.response.send_message(f'🪙 The coin landed on **{result}**!')
    
    @app_commands.command(name='cat', description='Get a random cat picture')
    async def cat(self, interaction: discord.Interaction):
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
    
    @app_commands.command(name='dog', description='Get a random dog picture')
    async def dog(self, interaction: discord.Interaction):
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

async def setup(bot):
    await bot.add_cog(Fun(bot))