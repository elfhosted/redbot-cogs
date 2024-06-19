import discord
import logging
from redbot.core import commands, app_commands
from discord.utils import get

ALLOWED_ROLE_IDS = [1198381095553617922, 1252252269790105721]

mylogger = logging.getLogger('test_support')
mylogger.setLevel(logging.DEBUG)

class RedBotCogSupport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_name = bot.user.name
        self.bot_uid = bot.user.id

    @commands.hybrid_command(name="support")
    @app_commands.describe(message_link="The discord message link or ID you want to create a new elf-support forum post.")
    async def support(self, ctx, message_link: str = None):
        try:
            if message_link:
                message_id = int(message_link.split('/')[-1]) if '/' in message_link else int(message_link)
                message_link = await ctx.channel.fetch_message(message_id)
            elif ctx.message.reference:
                message_id = ctx.message.reference.message_id
                message_link = await ctx.channel.fetch_message(message_id)
            else:
                await ctx.send("Please provide a valid message link, ID, or reply to a message.")
                return

            if not message_link.guild:
                return await ctx.send("The specified message is not associated with a guild. Aborting...")

            message_author = message_link.author
            if not isinstance(message_author, discord.Member):
                return await ctx.send("The author of the linked message is not a member of the guild. Aborting...")

            author_name = f"{ctx.author.name}#{ctx.author.discriminator}" if ctx.author else "Unknown"
            guild_name = ctx.guild.name if ctx.guild else "Direct Message"
            channel_name = ctx.channel.name if isinstance(ctx.channel, discord.TextChannel) else "Direct Message"
        
            mylogger.info(f"Support invoked by {author_name} in {guild_name}/{channel_name} (ID: {ctx.guild.id if ctx.guild else 'N/A'}/{ctx.channel.id if ctx.guild else 'N/A'})")
            invoker_display_name = ctx.author.display_name
            invoker_username = ctx.author.name
            mylogger.info(f"Invoker: {invoker_display_name} ({invoker_username}), Roles: {ctx.author.roles}")
            mylogger.info(f"message_link.author: {message_link.author}")
            mylogger.info(f"self.bot.user: {self.bot.user}")

            invoker_has_allowed_role = any(role.id in ALLOWED_ROLE_IDS for role in ctx.author.roles)
            mylogger.info(f"Has allowed role: {invoker_has_allowed_role}")

            if not (invoker_has_allowed_role or message_link.author == ctx.author):
                await ctx.send("You don't have permission to use this command or the specified message is not yours.")
                return

            if isinstance(message_link.author, discord.Member) and message_link.guild:
                author_display_name = message_link.author.display_name
                await ctx.send("Processing your request...")

                forum_channel_id = None
                if self.bot_uid == 1250781032756674641:
                    forum_channel_id = 1252251752397537291
                elif self.bot_uid == 1252847131476230194:
                    forum_channel_id = 1252251752397537291
                elif self.bot_uid == 1250431337156837428:
                    forum_channel_id = 1245513340176961606

                forum_channel = self.bot.get_channel(forum_channel_id)
                if not forum_channel:
                    return await ctx.send(f'Could not find a channel with ID {forum_channel_id}.')

                subject = f"{author_display_name} ({message_link.author.name}) needs elf-ssistance. Invoked by {invoker_display_name}"
                description = f"{message_link.author.mention}, please continue the conversation here.\n\n**Content:** {message_link.content}\n\n**Attachments:**(if any)"

                tag = discord.utils.get(forum_channel.available_tags, name="open")

                thread = await forum_channel.create_thread(name=subject, content=description, applied_tags=[tag], auto_archive_duration=10080)

                if message_link.attachments:
                    for attachment in message_link.attachments:
                        await thread.send(file=await attachment.to_file())

                first_message = await thread.fetch_message(thread.id)

                await message_link.author.send(f"A new support thread has been created for your message: {first_message.jump_url}")
                await message_link.delete()
                trace_message = await ctx.send(f"A message by {author_display_name} ({message_link.author.name}) was moved to {first_message.jump_url} by {invoker_display_name}")
            else:
                await ctx.send("The specified message is not associated with a guild member. Aborting...")

        except Exception as e:
            mylogger.exception('An error occurred during message processing:', exc_info=e)
            await ctx.send("An error occurred while processing your request.")
