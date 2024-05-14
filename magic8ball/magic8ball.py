import discord
import random
import requests
import logging
from discord.ext import commands
from redbot.core import commands, app_commands

# Create logger
mylogger = logging.getLogger('magic8ball')
mylogger.setLevel(logging.DEBUG)  # Set the logging level to DEBUG


class My8ball(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="magic8ball")
    @commands.cooldown(1, 60, commands.BucketType.user)  # Add cooldown to avoid spamming
    @app_commands.describe(message_link="Request a Magic 8-Ball response")
    async def magic_8ball(self, ctx: commands.Context, *, question: str):
        try:
            # Log command invocation details
            author_name = f"{ctx.author.name}#{ctx.author.discriminator}" if ctx.author else "Unknown"
            guild_name = ctx.guild.name if ctx.guild else "Direct Message"
            channel_name = ctx.channel.name if isinstance(ctx.channel, discord.TextChannel) else "Direct Message"

            mylogger.info(f"Magic 8-Ball invoked by {author_name} in {guild_name}/{channel_name} (ID: {ctx.guild.id if ctx.guild else 'N/A'}/{ctx.channel.id if ctx.guild else 'N/A'})")

            # Delete the invoking message after sending the response (only if not in a DM channel)
            if ctx.channel.type != discord.ChannelType.private:
                await ctx.message.delete()

            # Define Magic 8-Ball responses
            responses = [
                "It is certain.",
                "It is decidedly so.",
                "Without a doubt.",
                "Yes - definitely.",
                "You may rely on it.",
                "As I see it, yes.",
                "Most likely.",
                "Outlook good.",
                "Yes.",
                "Signs point to yes.",
                "Reply hazy, try again.",
                "Ask again later.",
                "Better not tell you now.",
                "Cannot predict now.",
                "Concentrate and ask again.",
                "Don't count on it.",
                "My reply is no.",
                "My sources say no.",
                "Outlook not so good.",
                "Very doubtful."
            ]

            # Choose a random response from the list
            response = random.choice(responses)

            # Send the response with an embedded image
            embed = discord.Embed(title="Magic 8-Ball", description=f"**Question:** {question}\n**Answer:** {response}")
            embed.set_image(url="https://hotemoji.com/images/emoji/f/1o0t25h14ef84f.png")
            await ctx.send(embed=embed)

        except Exception as e:
            mylogger.error(f"An error occurred: {e}")
            await ctx.send("An unexpected error occurred. Please check the logs.")
