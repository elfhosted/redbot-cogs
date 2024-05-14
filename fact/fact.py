import os
import discord
import requests
import logging
import json
import random
from discord.ext import commands
from redbot.core import commands, app_commands

# Create logger
mylogger = logging.getLogger('fact')
mylogger.setLevel(logging.DEBUG)  # Set the logging level to DEBUG


class MyRandom(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sent_facts = set()  # Set to store sent facts
        self.load_sent_facts()

    def load_sent_facts(self):
        cog_directory = os.path.dirname(__file__)
        output_dir = os.path.join(cog_directory, 'sent_facts.json')
        try:
            with open(output_dir, 'r') as file:
                self.sent_facts = set(json.load(file))
        except FileNotFoundError:
            pass  # Ignore if the file doesn't exist

    def save_sent_facts(self):
        # Get the directory path of the current cog
        cog_directory = os.path.dirname(__file__)
        mylogger.info(f"cog_directory: {cog_directory}")
        output_dir = os.path.join(cog_directory, 'sent_facts.json')

        with open(output_dir, 'w') as file:
            json.dump(list(self.sent_facts), file)
        mylogger.info(f"Total facts saved in 'sent_facts.json': {len(self.sent_facts)}")

    @commands.command(name="fact")
    @app_commands.describe(message_link="Request a random fact")
    @commands.cooldown(1, 60, commands.BucketType.user)  # 1 command per 60 seconds per user
    async def fact(self, ctx: commands.Context):
        try:
            if ctx.channel.type == discord.ChannelType.private:
                pass

            if ctx.author:
                author_name = f"{ctx.author.name}#{ctx.author.discriminator}"
            else:
                author_name = "Unknown"

            if ctx.guild:
                guild_name = ctx.guild.name
            else:
                guild_name = "Direct Message"  # For DM channels

            if ctx.channel:
                if isinstance(ctx.channel, discord.TextChannel):
                    channel_name = ctx.channel.name
                else:
                    channel_name = "Direct Message"
            else:
                channel_name = "Unknown Channel"

            mylogger.info(f"Random fact requested by {author_name} in {guild_name}/{channel_name} (ID: {ctx.guild.id if ctx.guild else 'N/A'}/{ctx.channel.id if ctx.channel else 'N/A'})")

            # Delete the invoking message after sending the fact (only if not in a DM channel)
            if ctx.channel.type != discord.ChannelType.private:
                await ctx.message.delete()

            max_attempts = 10  # Maximum number of attempts to fetch a unique fact
            attempts = 0

            # Fetch a new fact until a unique one is found or max attempts reached
            while attempts < max_attempts:
                fact = requests.get("https://uselessfacts.jsph.pl/random.json?language=en").json()["text"]

                if fact not in self.sent_facts:
                    break  # Exit the loop if a unique fact is found

                attempts += 1

            if attempts == max_attempts:
                await ctx.send("Unable to fetch a unique fact. Please try again later.")
                return

            # Store the sent fact in the set
            self.sent_facts.add(fact)
            self.save_sent_facts()

            # Generate a random color for the embedded message
            random_color = discord.Color(random.randint(0, 0xFFFFFF))

            # Send the fact as an embedded message with the bot's avatar as the image
            embed = discord.Embed(title="Random Fact", description=fact, color=random_color)
            embed.set_footer(text=f"Brought to you by uselessfacts.jsph.pl")

            # Check if the 'avatar_url' attribute is available
            if hasattr(self.bot.user, 'avatar_url'):
                bot_avatar_url = self.bot.user.avatar_url
                embed.set_image(url=bot_avatar_url)
            elif hasattr(self.bot.user, 'avatar'):
                # 'avatar' is used in some cases
                bot_avatar_url = self.bot.user.avatar
                embed.set_image(url=bot_avatar_url)

            await ctx.send(embed=embed)

        except requests.RequestException as e:
            mylogger.error(f"Error fetching the random fact: {e}")
            await ctx.send(f"An error occurred while fetching the random fact: {e}")
        except (KeyError, ValueError) as e:
            mylogger.error(f"Error parsing the response: {e}")
            await ctx.send(f"An error occurred while parsing the response: {e}")
