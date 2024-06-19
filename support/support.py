import discord
import logging
from redbot.core import commands, app_commands
from discord.utils import get

ALLOWED_ROLE_IDS = [1198381095553617922, 1252252269790105721]

# Create logger
mylogger = logging.getLogger('test_support')
mylogger.setLevel(logging.DEBUG)  # Set the logging level to DEBUG


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
                # Fetch the message from the message link or ID
                message_id = int(message_link.split('/')[-1]) if '/' in message_link else int(message_link)
                message_link = await ctx.channel.fetch_message(message_id)
            elif ctx.message.reference:
                # Use the replied message if no link or ID is provided
                message_id = ctx.message.reference.message_id
                message_link = await ctx.channel.fetch_message(message_id)
            else:
                await ctx.send("Please provide a valid message link, ID, or reply to a message.")
                return

            # Check if the linked message is associated with a guild
            if not message_link.guild:
                return await ctx.send("The specified message is not associated with a guild. Aborting...")

            # Attempt to fetch the member corresponding to the author of the linked message
            message_author = message_link.author
            if not isinstance(message_author, discord.Member):
                # The author is not a guild member (likely a bot or user outside the guild)
                return await ctx.send("The author of the linked message is not a member of the guild. Aborting...")

            # Log command invocation details
            author_name = f"{ctx.author.name}#{ctx.author.discriminator}" if ctx.author else "Unknown"
            guild_name = ctx.guild.name if ctx.guild else "Direct Message"
            channel_name = ctx.channel.name if isinstance(ctx.channel, discord.TextChannel) else "Direct Message"
        
            mylogger.info(f"Support invoked by {author_name} in {guild_name}/{channel_name} (ID: {ctx.guild.id if ctx.guild else 'N/A'}/{ctx.channel.id if ctx.guild else 'N/A'})")
            
            # Log the invoker and their roles for troubleshooting
            invoker_display_name = ctx.author.display_name
            invoker_username = ctx.author.name
            mylogger.info(f"Invoker: {invoker_display_name} ({invoker_username}), Roles: {ctx.author.roles}")
            mylogger.info(f"message_link.author: {message_link.author}")
            mylogger.info(f"self.bot.user: {self.bot.user}")

            # Check if the author has the "Support" role or any other allowed roles
            invoker_has_allowed_role = any(role.id in ALLOWED_ROLE_IDS for role in ctx.author.roles)

            # Log the result of the role check for troubleshooting
            mylogger.info(f"Has allowed role: {invoker_has_allowed_role}")

            if invoker_has_allowed_role or message_link.author == ctx.author:
                # Allow the command since the invoker has an allowed role or is the author of the linked message
                pass
            else:
                await ctx.send("You don't have permission to use this command or the specified message is not yours.")
                return

            if isinstance(message_link.author, discord.Member) and message_link.guild:
                # Retrieve the display name (nickname) of the message author within the guild
                author_display_name = message_link.author.display_name
                
                # Send an acknowledgment message
                await ctx.send("Processing your request...")

                # Determine the appropriate forum channel ID based on bot user ID
                forum_channel_id = None
                if self.bot_uid == 1250781032756674641:     # Sparky
                    forum_channel_id = 1252251752397537291  # #test-elf-support
                elif self.bot_uid == 1252847131476230194:     # Sparky Jr
                    forum_channel_id = 1252251752397537291  # #test-elf-support
                elif self.bot_uid == 1250431337156837428:   # Spanky
                    forum_channel_id = 1245513340176961606  # #elf-support

                # Get the forum channel
                forum_channel = self.bot.get_channel(forum_channel_id)
                if not forum_channel:
                    return await ctx.send(f'Could not find a channel with ID {forum_channel_id}.')

                # Construct subject and description with author's display name (nickname)
                subject = f"{author_display_name} ({message_link.author.name}) needs elf-ssistance. Invoked by {invoker_display_name}"
                description = f"{message_link.author.mention}, please continue the conversation here.\n\n**Content:** {message_link.content}\n\n**Attachments:**(if any)"

                # Create a thread in the forum channel with content
                thread = await forum_channel.create_thread(name=subject, content=description, applied_tags=["open"], auto_archive_duration=10080)
                
                if message_link.attachments:
                    for attachment in message_link.attachments:
                        await thread.send(file=await attachment.to_file())

                # Notify the original message author and provide the link to the new thread
                await message_link.author.send(f"A new support thread has been created for your message: {thread.jump_url}")

                # Delete the original message and leave a trace
                await message_link.delete()
                trace_message = await ctx.send(f"A message by {author_display_name} ({message_link.author.name}) was moved to {thread.jump_url} by {invoker_display_name}")
            else:
                await ctx.send("The specified message is not associated with a guild member. Aborting...")

        except Exception as e:
            mylogger.exception('An error occurred during message processing:', exc_info=e)
            await ctx.send("An error occurred while processing your request.")
