import discord
from redbot.core import commands
import re
import logging

# Set up logging
mylogger = logging.getLogger('MoveMessage')
mylogger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
mylogger.addHandler(handler)

# List of allowed role IDs
ALLOWED_ROLE_IDS = [1198381095553617922, 1252252269790105721]

class MoveMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_allowed(self, ctx):
        return any(role.id in ALLOWED_ROLE_IDS for role in ctx.author.roles)

    def extract_message_id(self, input_str):
        url_match = re.match(r'https:\/\/discord\.com\/channels\/\d+\/\d+\/(\d+)', input_str)
        if url_match:
            return int(url_match.group(1))
        elif re.match(r'^\d+$', input_str):
            return int(input_str)
        else:
            return None

    def extract_channel_or_thread_id(self, input_str):
        url_match = re.match(r'https:\/\/discord\.com\/channels\/\d+\/\d+\/(\d+)', input_str)
        if url_match:
            return int(url_match.group(1))
        else:
            mention_match = re.match(r'<#(\d+)>', input_str)
            if mention_match:
                return int(mention_match.group(1))
            elif re.match(r'^\d+$', input_str):
                return int(input_str)
            else:
                return None

    async def fetch_target_channel(self, ctx, target_channel_or_url):
        channel_or_thread_id = self.extract_channel_or_thread_id(target_channel_or_url)
        mylogger.debug(f"Extracted channel or thread ID: {channel_or_thread_id}")
        if channel_or_thread_id:
            target_channel = self.bot.get_channel(channel_or_thread_id)
            if target_channel is None:
                try:
                    target_channel = await ctx.guild.fetch_channel(channel_or_thread_id)
                except discord.NotFound:
                    mylogger.debug(f"Channel or thread with ID {channel_or_thread_id} not found.")
                    target_channel = None
            mylogger.debug(f"Fetched channel or thread: {target_channel}")
            return target_channel
        else:
            mylogger.debug(f"Invalid target channel or thread URL: {target_channel_or_url}")
            return None

    @commands.command(name="move")
    async def move_message(self, ctx, input_str: str, target_channel_or_url: str):
        if not await self.is_allowed(ctx):
            return await ctx.send("You do not have the required role to use this command.")

        message_id = self.extract_message_id(input_str)

        if message_id is None:
            mylogger.debug("Invalid input for message ID or URL.")
            return await ctx.send("Invalid input. Please provide a valid message ID or URL.")

        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            mylogger.debug(f"Message with ID {message_id} not found.")
            return await ctx.send("Message not found.")
        except discord.Forbidden:
            mylogger.debug(f"Forbidden access to message with ID {message_id}.")
            return await ctx.send("I do not have permission to access this message.")
        except discord.HTTPException as e:
            mylogger.debug(f"HTTP exception while fetching message with ID {message_id}: {e}")
            return await ctx.send(f"An error occurred while fetching the message: {e}")

        target_channel = await self.fetch_target_channel(ctx, target_channel_or_url)

        if target_channel is None:
            return await ctx.send(f"Invalid target channel. Please provide a valid channel mention or URL.")

        await self.move_and_notify(ctx, message, target_channel)

    @commands.command(name="movemany")
    async def move_many_messages(self, ctx, input_str: str, target_channel_or_url: str):
        if not await self.is_allowed(ctx):
            return await ctx.send("You do not have the required role to use this command.")

        message_ids = self.extract_message_ids(input_str)

        if not message_ids:
            mylogger.debug("Invalid input for message IDs or URLs.")
            return await ctx.send("Invalid input. Please provide valid message IDs or URLs.")

        messages_to_move = []
        for message_id in message_ids:
            try:
                message = await ctx.channel.fetch_message(message_id)
                messages_to_move.append(message)
            except discord.NotFound:
                await ctx.send(f"Message with ID {message_id} not found.")
                mylogger.debug(f"Message with ID {message_id} not found.")
            except discord.Forbidden:
                await ctx.send(f"I do not have permission to access message with ID {message_id}.")
                mylogger.debug(f"Forbidden access to message with ID {message_id}.")
            except discord.HTTPException as e:
                await ctx.send(f"An error occurred while fetching the message with ID {message_id}: {e}")
                mylogger.debug(f"HTTP exception while fetching message with ID {message_id}: {e}")

        target_channel = await self.fetch_target_channel(ctx, target_channel_or_url)

        if target_channel is None:
            return await ctx.send(f"Invalid target channel. Please provide a valid channel mention or URL.")

        for message in messages_to_move:
            await self.move_and_notify(ctx, message, target_channel)

    def extract_message_ids(self, input_str):
        message_ids = []
        urls = re.findall(r'https:\/\/discord\.com\/channels\/\d+\/\d+\/(\d+)', input_str)
        ids = input_str.split(",")
        for id_str in ids:
            id_str = id_str.strip()
            if re.match(r'^\d+$', id_str):
                message_ids.append(int(id_str))
        message_ids.extend([int(url) for url in urls])
        return list(set(message_ids))  # Remove duplicates

    @commands.command(name="movefromuser")
    async def move_messages_from_user(self, ctx, user: discord.Member, num_messages: int, target_channel_or_url: str):
        if not await self.is_allowed(ctx):
            return await ctx.send("You do not have the required role to use this command.")

        def check(msg):
            return msg.author == user

        messages_to_move = []
        async for message in ctx.channel.history(limit=200):
            if check(message):
                messages_to_move.append(message)
            if len(messages_to_move) >= num_messages:
                break

        if not messages_to_move:
            mylogger.debug(f"No messages found from user {user.display_name}.")
            return await ctx.send("No messages found from the specified user.")
        elif len(messages_to_move) < num_messages:
            mylogger.debug(f"Only found {len(messages_to_move)} messages from user {user.display_name}.")
            await ctx.send(f"Only found {len(messages_to_move)} messages from {user.display_name}.")

        target_channel = await self.fetch_target_channel(ctx, target_channel_or_url)

        if target_channel is None:
            return await ctx.send(f"Invalid target channel or thread: {target_channel_or_url}")

        for message in messages_to_move:
            await self.move_and_notify(ctx, message, target_channel)

    async def move_and_notify(self, ctx, message, target_channel):
        embed = discord.Embed(description=message.content, color=message.author.color)
        avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
        embed.set_author(name=message.author.display_name, icon_url=avatar_url)
        embed.timestamp = message.created_at
        embed.add_field(name="Original Message", value=f"[Jump to message]({message.jump_url})")

        # Include images if present
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)

        try:
            moved_message = await target_channel.send(embed=embed)
            mylogger.debug(f"Message moved to {target_channel.mention}")
        except discord.HTTPException as e:
            mylogger.debug(f"An error occurred while moving the message: {e}")
            return await ctx.send(f"An error occurred while moving the message: {e}")

        note_embed = discord.Embed(
            description=f"Your message has been moved to {target_channel.mention} for reference:\n\n[Original Message]({moved_message.jump_url})",
            color=discord.Color.red()
        )
        note_embed.set_author(name=message.author.display_name, icon_url=avatar_url)

        try:
            await ctx.send(content=message.author.mention, embed=note_embed)
        except discord.HTTPException as e:
            mylogger.debug(f"An error occurred while notifying the user: {e}")
            await ctx.send(f"An error occurred while notifying the user: {e}")

async def setup(bot):
    await bot.add_cog(MoveMessage(bot))
