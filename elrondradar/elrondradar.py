import asyncio
import logging
import re
from typing import Optional, Tuple

import aiohttp
import discord
from redbot.core import Config, app_commands, commands


log = logging.getLogger("red.elrondradar")

DEFAULT_ALLOWED_USER_IDS = [396052375409917952]
DEFAULT_ALLOWED_ROLE_IDS = [
    1198381095553617922,
    1252252269790105721,
    1247172016490938472,
]
DEFAULT_TENANT_ROLE_IDS = [1391914584440311840]
DEFAULT_LINK_INSTRUCTIONS_CHANNEL_ID = 1392004498611900476
SUPPORTED_EMOJIS = {"🚨", "🐧", "🏎️", "🏎", "👀", "🛠️", "🛠", "⏳", "⌛", "✅", "📦", "🔁", "🔄"}
DEFAULT_TICKET_CATEGORY_ID = 1281426693906759730
DEFAULT_BACKEND_CHANNEL_ID = 1480735317089587251
USERNAME_RE = re.compile(r"(?:aa-)?[a-z0-9][a-z0-9-]{1,60}", re.IGNORECASE)
USERNAME_STOPWORDS = {"account", "elfhosted", "username", "user", "none", "unknown", "not", "sure", "unsure", "na", "n/a"}


class DiagnosisRequestModal(discord.ui.Modal):
    """Collect staff context before asking Elrond to spend diagnosis tokens."""

    def __init__(self, cog, ticket_channel_id: int, ticket_channel_name: str, ticket_url: str, backend_thread_id: int, source_message_id: int):
        super().__init__(title="Elrond diagnosis")
        self.cog = cog
        self.ticket_channel_id = ticket_channel_id
        self.ticket_channel_name = ticket_channel_name
        self.ticket_url = ticket_url
        self.backend_thread_id = backend_thread_id
        self.source_message_id = source_message_id
        self.context = discord.ui.TextInput(
            label="What should Elrond focus on?",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=800,
            placeholder="Optional. Add symptoms, suspicion, or what has already been checked.",
        )
        self.add_item(self.context)

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id if interaction.guild else await self.cog.config.guild_id()
        data = {
            "action": "diagnosis_requested",
            "guild_id": str(guild_id),
            "channel_id": str(self.ticket_channel_id),
            "channel_name": self.ticket_channel_name,
            "message_id": str(self.source_message_id),
            "message_url": self.ticket_url,
            "message_content": str(self.context.value or "").strip(),
            "backend_thread_id": str(self.backend_thread_id),
            "backend_thread_url": getattr(interaction.channel, "jump_url", ""),
            "staff_discord_id": str(interaction.user.id),
            "staff_display_name": getattr(interaction.user, "display_name", str(interaction.user)),
        }
        status, body = await self.cog._post_to_elrond(data)
        if status is None:
            await interaction.response.send_message("Elrond diagnosis request failed: endpoint or token is not configured.", ephemeral=True)
        elif status >= 300:
            await interaction.response.send_message(f"Elrond diagnosis request failed: HTTP {status} {body[:300]}", ephemeral=True)
        else:
            await interaction.response.send_message("Elrond diagnosis request queued.", ephemeral=True)


class DiagnosisRequestView(discord.ui.View):
    """Button wrapper that opens the diagnosis modal on demand."""

    def __init__(self, cog, ticket_channel_id: int, ticket_channel_name: str, ticket_url: str, backend_thread_id: int, source_message_id: int):
        super().__init__(timeout=None)
        button = discord.ui.Button(
            label="Activate Elrond diagnosis",
            style=discord.ButtonStyle.primary,
            custom_id=f"elrondradar:diagnose:{ticket_channel_id}",
        )

        async def callback(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message("Run this from the ElfHosted guild.", ephemeral=True)
                return
            member = interaction.user if isinstance(interaction.user, discord.Member) else None
            if not await cog._is_allowed_staff(interaction.guild, interaction.user.id, member):
                await interaction.response.send_message("Only authorised staff can activate Elrond diagnosis.", ephemeral=True)
                return
            await interaction.response.send_modal(
                DiagnosisRequestModal(cog, ticket_channel_id, ticket_channel_name, ticket_url, backend_thread_id, source_message_id)
            )

        button.callback = callback
        self.add_item(button)


class ElrondRadar(commands.Cog):
    """Bridge staff reactions to Elrond support radar."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2026051701, force_registration=True)
        self.config.register_global(
            enabled=False,
            endpoint_url="http://openclaw.openclaw:18789/elrond/support-radar/reaction",
            gateway_token="",
            guild_id=396055506072109067,
            allowed_user_ids=DEFAULT_ALLOWED_USER_IDS,
            allowed_role_ids=DEFAULT_ALLOWED_ROLE_IDS,
            tenant_role_ids=DEFAULT_TENANT_ROLE_IDS,
            link_instructions_channel_id=DEFAULT_LINK_INSTRUCTIONS_CHANNEL_ID,
            ticket_category_id=DEFAULT_TICKET_CATEGORY_ID,
            backend_channel_id=DEFAULT_BACKEND_CHANNEL_ID,
            announce_ticket_link=True,
            tracked_ticket_channel_ids=[],
            tracked_ticket_identity_resolved={},
            user_notes={},
        )

    def _reactions_intent_state(self) -> str:
        intents = getattr(self.bot, "intents", None)
        if intents is None:
            return "unknown"
        if hasattr(intents, "reactions"):
            return str(getattr(intents, "reactions"))
        return str(getattr(intents, "guild_reactions", "unknown"))

    def _normalized_emoji(self, emoji) -> str:
        return str(emoji or "").strip().replace("\ufe0f", "")

    def _is_supported_emoji(self, emoji) -> bool:
        text = str(emoji or "").strip()
        return text in SUPPORTED_EMOJIS or self._normalized_emoji(text) in SUPPORTED_EMOJIS

    @commands.group(name="elrondradar")
    @commands.admin_or_permissions(manage_guild=True)
    async def elrondradar(self, ctx):
        """Configure the Elrond support radar bridge."""

    @elrondradar.command(name="enable")
    async def enable(self, ctx):
        """Enable reaction forwarding."""
        await self.config.enabled.set(True)
        await ctx.send("Elrond radar bridge enabled.")

    @elrondradar.command(name="disable")
    async def disable(self, ctx):
        """Disable reaction forwarding."""
        await self.config.enabled.set(False)
        await ctx.send("Elrond radar bridge disabled.")

    @elrondradar.command(name="setendpoint")
    async def setendpoint(self, ctx, endpoint_url: str):
        """Set the Elrond/OpenClaw webhook endpoint URL."""
        await self.config.endpoint_url.set(endpoint_url.strip())
        await ctx.send("Elrond radar endpoint updated.")

    @elrondradar.command(name="settoken")
    async def settoken(self, ctx, gateway_token: str):
        """Set the OpenClaw gateway token used for webhook auth."""
        await self.config.gateway_token.set(gateway_token.strip())
        await ctx.send("Elrond radar gateway token updated.")

    @elrondradar.command(name="status")
    async def status(self, ctx):
        """Show bridge status without revealing the token."""
        cfg = await self.config.all()
        token_state = "set" if cfg.get("gateway_token") else "missing"
        await ctx.send(
            "Elrond radar bridge:\n"
            f"- enabled: {cfg.get('enabled')}\n"
            f"- endpoint: {cfg.get('endpoint_url')}\n"
            f"- guild_id: {cfg.get('guild_id')}\n"
            f"- token: {token_state}\n"
            f"- reactions intent: {self._reactions_intent_state()}\n"
            f"- ticket category: {cfg.get('ticket_category_id')}\n"
            f"- backend channel: {cfg.get('backend_channel_id')}\n"
            f"- announce ticket link: {cfg.get('announce_ticket_link')}\n"
            f"- allowed users: {len(cfg.get('allowed_user_ids') or [])}\n"
            f"- allowed roles: {len(cfg.get('allowed_role_ids') or [])}\n"
            f"- tenant roles: {len(cfg.get('tenant_role_ids') or [])}\n"
            f"- link instructions channel: {cfg.get('link_instructions_channel_id')}"
        )

    @elrondradar.command(name="setticketcategory")
    async def setticketcategory(self, ctx, category_id: int):
        """Set the Discord category ID watched for fresh support tickets."""
        await self.config.ticket_category_id.set(category_id)
        await ctx.send("Elrond radar ticket category updated.")

    @elrondradar.command(name="setbackendchannel")
    async def setbackendchannel(self, ctx, channel_id: int):
        """Set the staff backend channel where intake threads are created."""
        await self.config.backend_channel_id.set(channel_id)
        await ctx.send("Elrond radar backend channel updated.")

    @elrondradar.command(name="settenantrole")
    async def settenantrole(self, ctx, role_id: int):
        """Set the Discord role used to identify tenant members in ticket channels."""
        await self.config.tenant_role_ids.set([role_id])
        await ctx.send("Elrond radar tenant role updated.")

    @elrondradar.command(name="setlinkchannel")
    async def setlinkchannel(self, ctx, channel_id: int):
        """Set the channel users should visit to link their Discord account."""
        await self.config.link_instructions_channel_id.set(channel_id)
        await ctx.send("Elrond radar link instructions channel updated.")

    @elrondradar.command(name="cleartickets")
    async def cleartickets(self, ctx):
        """Clear tracked ticket IDs so category scan/create can retry intake."""
        await self.config.tracked_ticket_channel_ids.set([])
        await self.config.tracked_ticket_identity_resolved.set({})
        await ctx.send("Elrond radar tracked ticket cache cleared.")

    @elrondradar.command(name="scantickets")
    async def scantickets(self, ctx, limit: int = 25, force: bool = False):
        """Scan configured ticket category and create missing backend intake threads."""
        if ctx.guild is None:
            await ctx.send("Run this in the configured guild.")
            return
        if ctx.guild.id != await self.config.guild_id():
            await ctx.send("This server is not the configured Elrond radar guild.")
            return

        category_id = await self.config.ticket_category_id()
        candidates = [
            channel for channel in getattr(ctx.guild, "text_channels", [])
            if getattr(channel, "category_id", None) == category_id
        ]
        candidates = sorted(candidates, key=lambda channel: getattr(channel, "created_at", None) or discord.utils.utcnow(), reverse=True)
        processed = 0
        attempted = 0
        async with ctx.typing():
            for channel in candidates[: max(1, min(limit, 100))]:
                attempted += 1
                if await self._handle_ticket_channel_create(channel, force=force):
                    processed += 1
        await ctx.send(f"Elrond radar ticket scan complete: processed {processed}/{attempted} visible channel(s) in category {category_id}. force={force}")

    @elrondradar.command(name="rerunintake", aliases=["rerunticket"])
    async def rerunintake(self, ctx, channel_id: int):
        """Force a fresh backend intake for one support ticket channel."""
        if ctx.guild is None:
            await ctx.send("Run this in the configured guild.")
            return
        if ctx.guild.id != await self.config.guild_id():
            await ctx.send("This server is not the configured Elrond radar guild.")
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await ctx.guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                await ctx.send(f"Could not fetch ticket channel {channel_id}: {exc}")
                return

        requested_channel = channel
        category_id = await self.config.ticket_category_id()
        if getattr(channel, "category_id", None) != category_id:
            source_channel = await self._source_ticket_channel_from_intake(ctx.guild, channel)
            if source_channel is not None:
                channel = source_channel

        async with ctx.typing():
            try:
                processed = await self._handle_ticket_channel_create(channel, force=True)
            except Exception as exc:
                log.exception("Elrond radar forced intake failed for channel %s", channel_id)
                await ctx.send(f"Elrond radar forced intake failed for {channel_id}: {exc}")
                return

        if processed:
            if requested_channel.id == channel.id:
                await ctx.send(f"Elrond radar forced intake posted for <#{channel.id}>.")
            else:
                await ctx.send(f"Elrond radar forced intake posted for <#{channel.id}> from backend thread <#{requested_channel.id}>.")
        else:
            await ctx.send(f"Elrond radar did not post an intake for <#{channel.id}>. Run inspectticket {channel.id} for details.")

    @elrondradar.command(name="inspectticket")
    async def inspectticket(self, ctx, channel_id: int):
        """Show what Redbot can mechanically extract from a support ticket channel."""
        if ctx.guild is None:
            await ctx.send("Run this in the configured guild.")
            return
        if ctx.guild.id != await self.config.guild_id():
            await ctx.send("This server is not the configured Elrond radar guild.")
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await ctx.guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                await ctx.send(f"Could not fetch ticket channel {channel_id}: {exc}")
                return

        if not hasattr(channel, "history"):
            await ctx.send(f"Channel {channel_id} is not a readable text channel.")
            return

        tenant_member = await self._ticket_tenant_member(channel)
        visible_members = await self._ticket_visible_members(channel)
        unlinked_members = [member for member in visible_members if tenant_member is None or member.id != tenant_member.id]
        first_message = await self._first_useful_channel_message(channel, tenant_member.id if tenant_member is not None else None)
        ticket_username = self._ticket_username(first_message)
        excerpt = self._message_excerpt(first_message, limit=900)
        source_url = first_message.jump_url if first_message is not None else f"https://discord.com/channels/{ctx.guild.id}/{channel.id}"
        category_id = getattr(channel, "category_id", None)
        expected_category = await self.config.ticket_category_id()

        lines = [
            "Elrond radar ticket inspection:",
            f"- channel: #{getattr(channel, 'name', channel.id)} ({channel.id})",
            f"- category: {category_id} ({'ok' if category_id == expected_category else 'expected ' + str(expected_category)})",
            f"- linked discord member: {tenant_member} ({tenant_member.id})" if tenant_member is not None else "- linked discord member: not found",
            f"- modal account username: {ticket_username}" if ticket_username else "- modal account username: not found",
            "- unlinked visible members: " + (", ".join(f"{member} ({member.id})" for member in unlinked_members[:5]) if unlinked_members else "none"),
            f"- first useful message: {first_message.id} by {first_message.author}" if first_message is not None else "- first useful message: not found",
            f"- source: {source_url}",
            "- excerpt: " + (excerpt or "not provided"),
        ]
        await ctx.send("\n".join(lines)[:1900], allowed_mentions=discord.AllowedMentions.none())

    @elrondradar.command(name="test")
    async def test(self, ctx, channel_id: int, message_id: int, emoji: str = "👀"):
        """Send a synthetic radar event for a specific Discord message."""
        if ctx.guild is None:
            await ctx.send("Run this in the configured guild.")
            return
        if ctx.guild.id != await self.config.guild_id():
            await ctx.send("This server is not the configured Elrond radar guild.")
            return
        if not self._is_supported_emoji(emoji):
            await ctx.send(f"Unsupported radar emoji: {emoji}")
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await ctx.guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                await ctx.send(f"Could not fetch channel {channel_id}: {type(exc).__name__}")
                return
        if not hasattr(channel, "fetch_message"):
            await ctx.send(f"Channel {channel_id} cannot fetch messages.")
            return

        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            await ctx.send(f"Could not fetch message {message_id}: {type(exc).__name__}")
            return

        data = self._build_payload(
            action="added",
            guild_id=ctx.guild.id,
            channel_id=channel_id,
            message_id=message_id,
            emoji=emoji,
            staff_id=ctx.author.id,
            staff_display_name=getattr(ctx.author, "display_name", str(ctx.author)),
            message=message,
        )
        status, body = await self._post_to_elrond(data)
        if status is None:
            await ctx.send("Elrond radar test failed: endpoint or token is not configured.")
        elif status >= 300:
            await ctx.send(f"Elrond radar test failed: HTTP {status} {body[:300]}")
        else:
            await ctx.send(f"Elrond radar test accepted: HTTP {status}")

    @elrondradar.command(name="findtest")
    async def findtest(self, ctx, message_id: int, emoji: str = "👀"):
        """Find a message by ID across visible guild channels, then send a synthetic radar event."""
        if ctx.guild is None:
            await ctx.send("Run this in the configured guild.")
            return
        if ctx.guild.id != await self.config.guild_id():
            await ctx.send("This server is not the configured Elrond radar guild.")
            return
        if not self._is_supported_emoji(emoji):
            await ctx.send(f"Unsupported radar emoji: {emoji}")
            return

        async with ctx.typing():
            message = await self._find_message_in_guild(ctx.guild, message_id)
        if message is None:
            await ctx.send(f"Could not find message {message_id} in channels Redbot can read.")
            return

        data = self._build_payload(
            action="added",
            guild_id=ctx.guild.id,
            channel_id=message.channel.id,
            message_id=message_id,
            emoji=emoji,
            staff_id=ctx.author.id,
            staff_display_name=getattr(ctx.author, "display_name", str(ctx.author)),
            message=message,
        )
        status, body = await self._post_to_elrond(data)
        if status is None:
            await ctx.send("Elrond radar findtest failed: endpoint or token is not configured.")
        elif status >= 300:
            await ctx.send(f"Elrond radar findtest failed: HTTP {status} {body[:300]}")
        else:
            await ctx.send(f"Elrond radar findtest accepted: HTTP {status} in <#{message.channel.id}>")

    @commands.command(name="usernote-prefix-add")
    async def usernote_add(self, ctx: commands.Context, target: str, note: str):
        """Add a staff note for a Discord user or ElfHosted username."""
        if await self._block_prefix_usernote_in_ticket(ctx):
            return
        if not await self._ctx_is_allowed_staff(ctx):
            await self._send_private(ctx, "Only authorised staff can manage user notes.")
            return
        if not " ".join(str(note or "").split()):
            await self._send_private(ctx, "Note text is required.")
            return
        key, label = await self._note_key_from_target(ctx.guild, target)
        if not key:
            await self._send_private(ctx, "I couldn't resolve that target. Use a Discord mention/ID or ElfHosted username.")
            return
        saved = await self._add_user_note(key, label, note, ctx.author, ctx.channel)
        await self._send_private(ctx, f"Saved note for {saved['label']}.")

    @commands.command(name="usernote-prefix")
    async def usernote(self, ctx: commands.Context, note: str):
        """Add a staff note for the user inferred from the current ticket/intake context."""
        if await self._block_prefix_usernote_in_ticket(ctx):
            return
        if not await self._ctx_is_allowed_staff(ctx):
            await self._send_private(ctx, "Only authorised staff can manage user notes.")
            return
        if not " ".join(str(note or "").split()):
            await self._send_private(ctx, "Note text is required.")
            return
        key, label = await self._infer_note_target(ctx)
        if not key:
            await self._send_private(ctx, "I couldn't infer a user here. Use /usernote-add with a Discord user, ID, or ElfHosted username.")
            return
        saved = await self._add_user_note(key, label, note, ctx.author, ctx.channel)
        await self._send_private(ctx, f"Saved note for {saved['label']}.")

    @commands.command(name="usernote-prefix-list")
    async def usernote_list(self, ctx: commands.Context, target: Optional[str] = None):
        """List staff notes for a Discord user or ElfHosted username."""
        if await self._block_prefix_usernote_in_ticket(ctx):
            return
        if not await self._ctx_is_allowed_staff(ctx):
            await self._send_private(ctx, "Only authorised staff can view user notes.")
            return
        if target:
            key, label = await self._note_key_from_target(ctx.guild, target)
        else:
            key, label = await self._infer_note_target(ctx)
        if not key:
            await self._send_private(ctx, "I couldn't infer a user here. Provide a Discord user, ID, or ElfHosted username.")
            return
        block = await self._format_user_notes_for_keys([key], heading=f"Notes for {label}")
        await self._send_private(ctx, block or f"No notes for {label}.")

    @commands.command(name="usernote-prefix-delete")
    async def usernote_delete(self, ctx: commands.Context, number: int, target: Optional[str] = None):
        """Delete a staff note by number from /usernote-list."""
        if await self._block_prefix_usernote_in_ticket(ctx):
            return
        if not await self._ctx_is_allowed_staff(ctx):
            await self._send_private(ctx, "Only authorised staff can delete user notes.")
            return
        if target:
            key, label = await self._note_key_from_target(ctx.guild, target)
        else:
            key, label = await self._infer_note_target(ctx)
        if not key:
            await self._send_private(ctx, "I couldn't infer a user here. Provide a Discord user, ID, or ElfHosted username.")
            return
        deleted = await self._delete_user_note_by_number(key, number)
        if deleted is None:
            await self._send_private(ctx, f"No note #{number} for {label}. Run /usernote-list first.")
            return
        await self._send_private(ctx, f"Deleted note #{number} for {label}: {deleted.get('text', '')[:120]}")

    @app_commands.command(name="usernote", description="Add a staff note for the user inferred from this ticket or intake thread.")
    @app_commands.guilds(discord.Object(id=396055506072109067))
    @app_commands.guild_only()
    @app_commands.describe(note="Staff-only note for the user inferred from this ticket or intake thread")
    async def usernote_slash(self, interaction: discord.Interaction, note: str):
        if not await self._interaction_is_allowed_staff(interaction):
            await interaction.response.send_message("Only authorised staff can manage user notes.", ephemeral=True)
            return
        if not " ".join(str(note or "").split()):
            await interaction.response.send_message("Note text is required.", ephemeral=True)
            return
        key, label = await self._infer_note_target_from_channel(interaction.guild, interaction.channel)
        if not key:
            await interaction.response.send_message("I couldn't infer a user here. Use /usernote-add with a Discord user, ID, or ElfHosted username.", ephemeral=True)
            return
        saved = await self._add_user_note(key, label, note, interaction.user, interaction.channel)
        await interaction.response.send_message(f"Saved note for {saved['label']}.", ephemeral=True)

    @app_commands.command(name="usernote-add", description="Add a staff note for a Discord user or ElfHosted username.")
    @app_commands.guilds(discord.Object(id=396055506072109067))
    @app_commands.guild_only()
    @app_commands.describe(target="Discord mention/ID or ElfHosted username", note="Staff-only note to attach to future intakes")
    async def usernote_add_slash(self, interaction: discord.Interaction, target: str, note: str):
        if not await self._interaction_is_allowed_staff(interaction):
            await interaction.response.send_message("Only authorised staff can manage user notes.", ephemeral=True)
            return
        if not " ".join(str(note or "").split()):
            await interaction.response.send_message("Note text is required.", ephemeral=True)
            return
        key, label = await self._note_key_from_target(interaction.guild, target)
        if not key:
            await interaction.response.send_message("I couldn't resolve that target. Use a Discord mention/ID or ElfHosted username.", ephemeral=True)
            return
        saved = await self._add_user_note(key, label, note, interaction.user, interaction.channel)
        await interaction.response.send_message(f"Saved note for {saved['label']}.", ephemeral=True)

    @app_commands.command(name="usernote-list", description="List staff notes for a Discord user or ElfHosted username.")
    @app_commands.guilds(discord.Object(id=396055506072109067))
    @app_commands.guild_only()
    @app_commands.describe(target="Optional Discord mention/ID or ElfHosted username; omit in ticket/intake context")
    async def usernote_list_slash(self, interaction: discord.Interaction, target: Optional[str] = None):
        if not await self._interaction_is_allowed_staff(interaction):
            await interaction.response.send_message("Only authorised staff can view user notes.", ephemeral=True)
            return
        if target:
            key, label = await self._note_key_from_target(interaction.guild, target)
        else:
            key, label = await self._infer_note_target_from_channel(interaction.guild, interaction.channel)
        if not key:
            await interaction.response.send_message("I couldn't infer a user here. Provide a Discord user, ID, or ElfHosted username.", ephemeral=True)
            return
        block = await self._format_user_notes_for_keys([key], heading=f"Notes for {label}")
        await interaction.response.send_message(block or f"No notes for {label}.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="usernote-delete", description="Delete a staff note by number from /usernote-list.")
    @app_commands.guilds(discord.Object(id=396055506072109067))
    @app_commands.guild_only()
    @app_commands.describe(number="Note number from /usernote-list", target="Optional Discord mention/ID or ElfHosted username; omit in ticket/intake context")
    async def usernote_delete_slash(self, interaction: discord.Interaction, number: int, target: Optional[str] = None):
        if not await self._interaction_is_allowed_staff(interaction):
            await interaction.response.send_message("Only authorised staff can delete user notes.", ephemeral=True)
            return
        if target:
            key, label = await self._note_key_from_target(interaction.guild, target)
        else:
            key, label = await self._infer_note_target_from_channel(interaction.guild, interaction.channel)
        if not key:
            await interaction.response.send_message("I couldn't infer a user here. Provide a Discord user, ID, or ElfHosted username.", ephemeral=True)
            return
        deleted = await self._delete_user_note_by_number(key, number)
        if deleted is None:
            await interaction.response.send_message(f"No note #{number} for {label}. Run /usernote-list first.", ephemeral=True)
            return
        await interaction.response.send_message(f"Deleted note #{number} for {label}: {deleted.get('text', '')[:120]}", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    async def _is_allowed_staff(self, guild: discord.Guild, user_id: int, member: Optional[discord.Member]) -> bool:
        allowed_user_ids = set(await self.config.allowed_user_ids())
        if user_id in allowed_user_ids:
            return True

        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return False

        allowed_role_ids = set(await self.config.allowed_role_ids())
        return any(role.id in allowed_role_ids for role in getattr(member, "roles", []))

    async def _ctx_is_allowed_staff(self, ctx: commands.Context) -> bool:
        if ctx.guild is None or ctx.author is None:
            return False
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        return await self._is_allowed_staff(ctx.guild, ctx.author.id, member)

    async def _interaction_is_allowed_staff(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None or interaction.user is None:
            return False
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        return await self._is_allowed_staff(interaction.guild, interaction.user.id, member)

    async def _send_private(self, ctx: commands.Context, message: str):
        kwargs = {"allowed_mentions": discord.AllowedMentions.none()}
        if getattr(ctx, "interaction", None) is not None:
            kwargs["ephemeral"] = True
        await ctx.send(message, **kwargs)

    async def _block_prefix_usernote_in_ticket(self, ctx: commands.Context) -> bool:
        if getattr(ctx, "interaction", None) is not None:
            return False
        if getattr(ctx.channel, "category_id", None) != await self.config.ticket_category_id():
            return False
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            pass
        try:
            await ctx.author.send("Use the slash command `/usernote`, `/usernote-add`, `/usernote-list`, or `/usernote-delete` in ticket channels so the response is only visible to you.")
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            try:
                await ctx.send("Use the slash command for user notes in ticket channels.", delete_after=10)
            except (discord.Forbidden, discord.HTTPException):
                pass
        return True

    async def _note_key_from_target(self, guild: Optional[discord.Guild], target: str) -> Tuple[str, str]:
        value = str(target or "").strip()
        if not value:
            return "", ""
        user_id = self._extract_discord_id(value)
        if user_id:
            member = None
            if guild is not None:
                member = guild.get_member(user_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(user_id)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        member = None
            label = str(member) if member is not None else f"Discord {user_id}"
            return f"discord:{user_id}", label
        username = self._normalize_username(value)
        if not username:
            return "", ""
        return f"username:{username}", username

    def _extract_discord_id(self, value: str) -> Optional[int]:
        clean = str(value or "").strip()
        if clean.startswith("<@") and clean.endswith(">"):
            clean = clean.strip("<@!>")
        if clean.isdigit():
            return int(clean)
        return None

    def _normalize_username(self, value: str) -> str:
        clean = str(value or "").strip().lower()
        clean = clean.replace("`", " ").replace("\u200b", "")
        for match in USERNAME_RE.findall(clean):
            username = match.lower().replace("aa-", "", 1).strip("*_~<>:;,. ")
            if username and username not in USERNAME_STOPWORDS:
                return username
        return ""

    async def _infer_note_target(self, ctx: commands.Context) -> Tuple[str, str]:
        return await self._infer_note_target_from_channel(ctx.guild, ctx.channel)

    async def _infer_note_target_from_channel(self, guild: Optional[discord.Guild], channel) -> Tuple[str, str]:
        if channel is None:
            return "", ""

        if getattr(channel, "category_id", None) == await self.config.ticket_category_id():
            tenant_member = await self._ticket_tenant_member(channel)
            if tenant_member is not None:
                return f"discord:{tenant_member.id}", str(tenant_member)
            first_message = await self._first_useful_channel_message(channel)
            username = self._ticket_username(first_message)
            if username:
                normalized = self._normalize_username(username)
                return f"username:{normalized}", normalized

        backend_channel_id = await self.config.backend_channel_id()
        parent_id = getattr(channel, "parent_id", None)
        if parent_id == backend_channel_id or getattr(channel, "id", None) == backend_channel_id:
            username = self._normal_thread_name(getattr(channel, "name", ""))
            if username:
                normalized = self._normalize_username(username)
                return f"username:{normalized}", normalized

        return "", ""

    async def _add_user_note(self, key: str, label: str, note: str, author, channel) -> dict:
        text = " ".join(str(note or "").split()).strip()
        if len(text) > 600:
            text = text[:599].rstrip() + "…"
        entry = {
            "text": text,
            "label": label,
            "created_by_id": str(getattr(author, "id", "")),
            "created_by_name": getattr(author, "display_name", str(author)),
            "created_at": discord.utils.utcnow().isoformat(),
            "source_channel_id": str(getattr(channel, "id", "")),
            "source_channel_name": getattr(channel, "name", ""),
        }
        async with self.config.user_notes() as notes:
            items = list(notes.get(key, []))
            items.append(entry)
            notes[key] = items[-50:]
        return entry

    async def _format_user_notes_for_keys(self, keys, heading: str = "Staff notes") -> str:
        all_notes = await self.config.user_notes()
        seen = set()
        entries = []
        for key in keys:
            if not key or key in seen:
                continue
            seen.add(key)
            entries.extend(all_notes.get(key, []))
        if not entries:
            return ""
        entries = sorted(entries, key=lambda item: item.get("created_at", ""), reverse=True)[:8]
        lines = [f"🗒️ **{heading}**"]
        for index, entry in enumerate(entries, start=1):
            created = str(entry.get("created_at", ""))[:10] or "unknown date"
            by = entry.get("created_by_name") or entry.get("created_by_id") or "unknown staff"
            text = entry.get("text") or ""
            lines.append(f"{index}. {created} · {by}: {text}")
        return "\n".join(lines)

    async def _delete_user_note_by_number(self, key: str, number: int) -> Optional[dict]:
        if number < 1:
            return None
        async with self.config.user_notes() as notes:
            items = list(notes.get(key, []))
            sorted_pairs = sorted(enumerate(items), key=lambda pair: pair[1].get("created_at", ""), reverse=True)
            if number > len(sorted_pairs):
                return None
            original_index, deleted = sorted_pairs[number - 1]
            del items[original_index]
            if items:
                notes[key] = items
            else:
                notes.pop(key, None)
            return deleted

    async def _format_user_notes_for_intake(self, discord_id: str = "", username: str = "") -> str:
        keys = []
        clean_discord = str(discord_id or "").strip()
        clean_username = self._normalize_username(username)
        if clean_discord:
            keys.append(f"discord:{clean_discord}")
        if clean_username:
            keys.append(f"username:{clean_username}")
        return await self._format_user_notes_for_keys(keys)

    async def _fetch_message(self, payload: discord.RawReactionActionEvent) -> Optional[discord.Message]:
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
            if guild is not None:
                try:
                    channel = await guild.fetch_channel(payload.channel_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    return None
        if channel is None or not hasattr(channel, "fetch_message"):
            return None
        try:
            return await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def _find_message_in_guild(self, guild: discord.Guild, message_id: int) -> Optional[discord.Message]:
        seen_channel_ids = set()
        channels = []
        for channel in list(getattr(guild, "text_channels", [])) + list(getattr(guild, "threads", [])):
            channel_id = getattr(channel, "id", None)
            if channel_id in seen_channel_ids:
                continue
            seen_channel_ids.add(channel_id)
            if hasattr(channel, "fetch_message"):
                channels.append(channel)

        for channel in channels:
            try:
                return await channel.fetch_message(message_id)
            except discord.NotFound:
                continue
            except (discord.Forbidden, discord.HTTPException):
                continue
        return None

    async def _post_to_elrond(self, data: dict) -> Tuple[Optional[int], str]:
        endpoint_url = (await self.config.endpoint_url()).strip()
        gateway_token = (await self.config.gateway_token()).strip()
        if not endpoint_url or not gateway_token:
            log.warning("Elrond radar endpoint or token is not configured")
            return None, "endpoint or token is not configured"

        headers = {
            "Authorization": f"Bearer {gateway_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(endpoint_url, json=data, headers=headers, timeout=10) as response:
                    text = await response.text()
                    if response.status >= 300:
                        log.warning("Elrond radar webhook failed: HTTP %s %s", response.status, text[:500])
                    else:
                        log.info("Elrond radar webhook accepted: %s", text[:500])
                    return response.status, text
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                log.warning("Elrond radar webhook request failed: %s", exc)
                return 599, str(exc)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, action="added")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, action="removed")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        try:
            await self._handle_ticket_channel_create(channel)
        except Exception:
            log.exception("Elrond radar ticket intake failed for new channel %s", getattr(channel, "id", "unknown"))

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        tenant_roles = set(await self.config.tenant_role_ids())
        if not tenant_roles:
            return
        before_roles = {role.id for role in getattr(before, "roles", [])}
        after_roles = {role.id for role in getattr(after, "roles", [])}
        if not tenant_roles.intersection(after_roles - before_roles):
            return

        guild = getattr(after, "guild", None)
        if guild is None or guild.id != await self.config.guild_id():
            return

        category_id = await self.config.ticket_category_id()
        channels = [
            channel for channel in getattr(guild, "text_channels", [])
            if getattr(channel, "category_id", None) == category_id
        ]
        for channel in channels:
            visible_members = await self._ticket_visible_members(channel)
            if any(member.id == after.id for member in visible_members):
                if await self._handle_ticket_channel_create(channel):
                    log.info("Elrond radar refreshed ticket intake after Discord link: channel=%s user=%s", channel.id, after.id)

    async def _handle_reaction(self, payload: discord.RawReactionActionEvent, action: str):
        if not await self.config.enabled():
            return
        if payload.guild_id is None:
            return
        if payload.guild_id != await self.config.guild_id():
            return

        emoji = str(payload.emoji)
        if not self._is_supported_emoji(emoji):
            log.debug(
                "Elrond radar ignored unsupported reaction: emoji=%s channel=%s message=%s user=%s",
                emoji,
                payload.channel_id,
                payload.message_id,
                payload.user_id,
            )
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = payload.member if isinstance(payload.member, discord.Member) else None
        if not await self._is_allowed_staff(guild, payload.user_id, member):
            return

        message = await self._fetch_message(payload)
        data = self._build_payload(
            action=action,
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
            emoji=emoji,
            staff_id=payload.user_id,
            staff_display_name=member.display_name if member is not None else str(payload.user_id),
            message=message,
        )
        log.info(
            "Elrond radar reaction accepted locally: action=%s emoji=%s channel=%s message=%s user=%s",
            action,
            emoji,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
        )
        await self._post_to_elrond(data)

    async def _handle_ticket_channel_create(self, channel: discord.abc.GuildChannel, force: bool = False) -> bool:
        if not await self.config.enabled():
            return False
        guild = getattr(channel, "guild", None)
        if guild is None or guild.id != await self.config.guild_id():
            return False
        if getattr(channel, "category_id", None) != await self.config.ticket_category_id():
            return False
        if not hasattr(channel, "send") or not hasattr(channel, "history"):
            return False

        tracked = set(await self.config.tracked_ticket_channel_ids() or [])
        tracked_identity = await self.config.tracked_ticket_identity_resolved() or {}
        if not isinstance(tracked_identity, dict):
            tracked_identity = {}
        tracked_key = str(channel.id)
        if channel.id in tracked and tracked_identity.get(tracked_key, True) and not force:
            return False

        await asyncio.sleep(5)
        tenant_member = await self._ticket_tenant_member(channel)
        first_message = await self._first_useful_channel_message(channel, tenant_member.id if tenant_member is not None else None)
        for _ in range(5):
            if tenant_member is not None or first_message is not None:
                break
            await asyncio.sleep(3)
            tenant_member = await self._ticket_tenant_member(channel)
            first_message = await self._first_useful_channel_message(channel, tenant_member.id if tenant_member is not None else None)
        message_excerpt = self._message_excerpt(first_message)
        ticket_username = self._ticket_username(first_message)
        identity_resolved = tenant_member is not None or bool(ticket_username)
        if channel.id in tracked and not identity_resolved and not force:
            return False

        visible_members = await self._ticket_visible_members(channel)
        if tenant_member is None and visible_members:
            await self._announce_link_required(channel, visible_members[0])
            if not ticket_username:
                log.info("Elrond radar ticket intake is sparse pending Discord link: channel=%s user=%s", channel.id, visible_members[0].id)
        intake_member = tenant_member or (visible_members[0] if visible_members else None)
        thread_username = self._thread_username(channel, ticket_username, tenant_member)
        channel_thread_name = self._thread_username(channel, "", None)
        backend_thread, backend_thread_created = await self._create_backend_thread(channel, thread_username, aliases=[channel_thread_name])
        if backend_thread is None:
            log.warning("Elrond radar could not create backend thread for ticket channel %s", channel.id)
            return False

        if backend_thread_created and await self.config.announce_ticket_link():
            try:
                await channel.send(
                    "Staff backend thread: " + backend_thread.jump_url,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                log.warning("Elrond radar could not announce backend thread in ticket %s: %s", channel.id, exc)

        source_message_id = first_message.id if first_message is not None else channel.id
        ticket_url = first_message.jump_url if first_message is not None else f"https://discord.com/channels/{guild.id}/{channel.id}"
        user_notes = await self._format_user_notes_for_intake(
            str(intake_member.id) if intake_member is not None else (str(first_message.author.id) if first_message is not None else ""),
            ticket_username or thread_username,
        )
        intake_lines = [
            "Ticket intake for " + channel.mention,
            "Source: " + ticket_url,
        ]
        if first_message is not None:
            intake_lines.append("Author: " + str(first_message.author))
        if tenant_member is not None:
            intake_lines.append("Tenant: " + str(tenant_member))
        if ticket_username:
            intake_lines.append("Account: " + ticket_username)
        if message_excerpt:
            quoted_excerpt = "\n".join("> " + line for line in message_excerpt.splitlines())
            intake_lines.append("Snippet:\n" + quoted_excerpt)
        intake_lines.append("Use the button only when staff want Elrond to run diagnosis.")
        await backend_thread.send(
            "\n\n".join(intake_lines),
            view=DiagnosisRequestView(self, channel.id, getattr(channel, "name", str(channel.id)), ticket_url, backend_thread.id, source_message_id),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        status, body = await self._post_to_elrond({
            "action": "ticket_created",
            "guild_id": str(guild.id),
            "channel_id": str(channel.id),
            "channel_name": getattr(channel, "name", str(channel.id)),
            "message_id": str(source_message_id),
            "message_url": ticket_url,
            "message_author_id": str(intake_member.id) if intake_member is not None else (str(first_message.author.id) if first_message is not None else ""),
            "message_author_name": str(intake_member) if intake_member is not None else (str(first_message.author) if first_message is not None else ""),
            "tenant_username": ticket_username,
            "message_content": message_excerpt,
            "user_notes": user_notes,
            "backend_thread_id": str(backend_thread.id),
            "backend_thread_url": backend_thread.jump_url,
            "staff_discord_id": str(self.bot.user.id if self.bot.user else 0),
            "staff_display_name": "Elrond Radar",
        })
        if status is not None and status < 300:
            tracked.add(channel.id)
            await self.config.tracked_ticket_channel_ids.set(list(tracked)[-500:])
            tracked_identity[tracked_key] = identity_resolved
            tracked_identity = {str(item): tracked_identity.get(str(item), True) for item in tracked}
            await self.config.tracked_ticket_identity_resolved.set(tracked_identity)
            log.info("Elrond radar ticket intake completed: channel=%s backend_thread=%s", channel.id, backend_thread.id)
            return True
        log.warning("Elrond radar ticket intake webhook failed after creating backend thread: channel=%s status=%s body=%s", channel.id, status, body[:300])
        return False

    async def _announce_link_required(self, channel, member):
        link_channel_id = await self.config.link_instructions_channel_id()
        link_target = f"<#{link_channel_id}>" if link_channel_id else "the Discord linking instructions channel"
        try:
            await channel.send(
                f"{member.mention}, I can't prepare your ElfHosted account intake yet because this Discord account is not linked. "
                f"Please follow the instructions in {link_target}, then staff can retry intake.",
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("Elrond radar could not announce Discord linking instructions in ticket %s: %s", channel.id, exc)

    async def _ticket_tenant_member(self, channel):
        tenant_roles = set(await self.config.tenant_role_ids())
        for member in await self._ticket_visible_members(channel):
            if tenant_roles and any(role.id in tenant_roles for role in getattr(member, "roles", [])):
                return member
        return None

    async def _ticket_visible_members(self, channel):
        allowed_users = set(await self.config.allowed_user_ids())
        allowed_roles = set(await self.config.allowed_role_ids())
        overwrites = getattr(channel, "overwrites", {}) or {}
        members = []
        for target, overwrite in overwrites.items():
            if not isinstance(target, discord.Member):
                continue
            if target.bot or target.id in allowed_users:
                continue
            if any(role.id in allowed_roles for role in getattr(target, "roles", [])):
                continue
            view_channel = getattr(overwrite, "view_channel", None)
            read_messages = getattr(overwrite, "read_messages", None)
            if view_channel is False or read_messages is False:
                continue
            if view_channel is True or read_messages is True:
                members.append(target)
        return members

    async def _first_useful_channel_message(self, channel, preferred_author_id: Optional[int] = None) -> Optional[discord.Message]:
        fallback = None
        preferred_fallback = None
        try:
            async for message in channel.history(limit=50, oldest_first=True):
                excerpt = self._message_excerpt(message)
                if excerpt and fallback is None:
                    fallback = message
                if self._has_ticket_request_fields(message):
                    return message
                author = getattr(message, "author", None)
                if excerpt and preferred_author_id is not None and getattr(author, "id", None) == preferred_author_id:
                    return message
                if excerpt and preferred_fallback is None and not getattr(author, "bot", False):
                    preferred_fallback = message
        except (discord.Forbidden, discord.HTTPException):
            return None
        return preferred_fallback or fallback

    async def _source_ticket_channel_from_intake(self, guild: Optional[discord.Guild], channel) -> Optional[discord.abc.GuildChannel]:
        if guild is None or not hasattr(channel, "history"):
            return None
        try:
            async for message in channel.history(limit=10, oldest_first=True):
                content = str(getattr(message, "content", "") or "")
                match = re.search(r"Ticket intake for\s+<#(\d+)>", content) or re.search(r"<#(\d+)>", content)
                if not match:
                    continue
                source_channel_id = int(match.group(1))
                source_channel = self.bot.get_channel(source_channel_id)
                if source_channel is None:
                    try:
                        source_channel = await guild.fetch_channel(source_channel_id)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        return None
                return source_channel
        except (discord.Forbidden, discord.HTTPException):
            return None
        return None

    def _message_excerpt(self, message: Optional[discord.Message], limit: int = 500) -> str:
        if message is None:
            return ""

        priority_parts = []
        parts = []
        content = str(getattr(message, "content", "") or "").strip()
        if content:
            parts.append(content)

        for embed in getattr(message, "embeds", []) or []:
            title = str(getattr(embed, "title", "") or "").strip()
            description = str(getattr(embed, "description", "") or "").strip()
            if title:
                parts.append(title)
            if description:
                parts.append(description)
            for field in getattr(embed, "fields", []) or []:
                name = str(getattr(field, "name", "") or "").strip()
                value = str(getattr(field, "value", "") or "").strip()
                if name and value:
                    formatted = f"{name}: {value}"
                    if self._is_ticket_request_field(name):
                        priority_parts.append(value)
                    else:
                        parts.append(formatted)
                elif value:
                    parts.append(value)

        attachments = getattr(message, "attachments", []) or []
        if attachments:
            parts.append("Attachments: " + ", ".join(getattr(item, "filename", "attachment") for item in attachments[:5]))

        excerpt = " ".join(" ".join(part.split()) for part in [*priority_parts, *parts] if part).strip()
        if len(excerpt) > limit:
            return excerpt[: limit - 1].rstrip() + "…"
        return excerpt

    def _is_ticket_request_field(self, name: str) -> bool:
        normalized = " ".join(str(name or "").lower().replace("/", " ").replace("-", " ").split())
        return (
            "account username" in normalized
            or "account issue" in normalized
            or "issue error" in normalized
            or "support request" in normalized
            or "problem" in normalized
        )

    def _has_ticket_request_fields(self, message: Optional[discord.Message]) -> bool:
        if message is None:
            return False
        for embed in getattr(message, "embeds", []) or []:
            for field in getattr(embed, "fields", []) or []:
                name = str(getattr(field, "name", "") or "").strip()
                value = str(getattr(field, "value", "") or "").strip()
                if value and self._is_ticket_request_field(name):
                    return True
        return False

    def _ticket_username(self, message: Optional[discord.Message]) -> str:
        if message is None:
            return ""
        for embed in getattr(message, "embeds", []) or []:
            for field in getattr(embed, "fields", []) or []:
                name = str(getattr(field, "name", "") or "").strip()
                value = str(getattr(field, "value", "") or "").strip()
                if self._is_ticket_username_field(name) and value:
                    return self._normalize_username(value)
        return ""

    def _is_ticket_username_field(self, name: str) -> bool:
        normalized = " ".join(str(name or "").lower().replace("/", " ").replace("-", " ").split())
        return "account username" in normalized or "elfhosted username" in normalized or normalized == "username"

    async def _create_backend_thread(self, ticket_channel, username: str, aliases=None):
        backend_channel = self.bot.get_channel(await self.config.backend_channel_id())
        if backend_channel is None and ticket_channel.guild is not None:
            try:
                backend_channel = await ticket_channel.guild.fetch_channel(await self.config.backend_channel_id())
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return None, False
        if backend_channel is None or not hasattr(backend_channel, "create_thread"):
            return None, False

        raw_name = username or getattr(ticket_channel, "name", str(ticket_channel.id))
        thread_name = ("🟡 " + raw_name)[:90]
        lookup_names = [raw_name, *(aliases or [])]
        existing = None
        for lookup_name in lookup_names:
            existing = await self._find_backend_thread(backend_channel, lookup_name)
            if existing is not None:
                break
        if existing is not None:
            try:
                await existing.edit(name=thread_name, archived=False, locked=False, reason="Elrond support ticket intake reopened")
            except (discord.Forbidden, discord.HTTPException):
                try:
                    await existing.edit(name=thread_name, reason="Elrond support ticket intake reopened")
                except (discord.Forbidden, discord.HTTPException):
                    pass
            return existing, False

        try:
            thread = await backend_channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                reason="Elrond support ticket intake",
            )
            return thread, True
        except (discord.Forbidden, discord.HTTPException):
            try:
                thread = await backend_channel.create_thread(
                    name=thread_name,
                    type=discord.ChannelType.private_thread,
                    reason="Elrond support ticket intake",
                )
                return thread, True
            except (discord.Forbidden, discord.HTTPException):
                return None, False

    async def _find_backend_thread(self, backend_channel, username: str):
        wanted = self._normal_thread_name(username)
        for thread in getattr(backend_channel, "threads", []) or []:
            if self._normal_thread_name(getattr(thread, "name", "")) == wanted:
                return thread
        if hasattr(backend_channel, "archived_threads"):
            for private in (False, True):
                try:
                    async for thread in backend_channel.archived_threads(private=private, limit=100):
                        if self._normal_thread_name(getattr(thread, "name", "")) == wanted:
                            return thread
                except (discord.Forbidden, discord.HTTPException, TypeError):
                    continue
        return None

    def _thread_username(self, ticket_channel, ticket_username: str, tenant_member) -> str:
        if ticket_username:
            return ticket_username.lower()
        channel_name = str(getattr(ticket_channel, "name", "") or "").strip().lower()
        if "-" in channel_name:
            prefix, suffix = channel_name.rsplit("-", 1)
            if suffix.isdigit():
                return prefix
        if tenant_member is not None:
            return str(getattr(tenant_member, "name", "") or getattr(tenant_member, "display_name", "") or "").lower()
        return channel_name

    def _normal_thread_name(self, value: str) -> str:
        name = str(value or "").strip().lower()
        for prefix in ("🟡", "🟢", "🔴", "🟠", "intake-"):
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
        return name

    def _build_payload(
        self,
        action: str,
        guild_id: int,
        channel_id: int,
        message_id: int,
        emoji: str,
        staff_id: int,
        staff_display_name: str,
        message: Optional[discord.Message],
    ) -> dict:
        channel = message.channel if message is not None else self.bot.get_channel(channel_id)
        channel_name = getattr(channel, "name", str(channel_id))
        message_author = message.author if message is not None else None
        jump_url = (
            message.jump_url
            if message is not None
            else f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
        )
        return {
            "action": action,
            "guild_id": str(guild_id),
            "channel_id": str(channel_id),
            "channel_name": channel_name,
            "message_id": str(message_id),
            "message_url": jump_url,
            "message_author_id": str(message_author.id) if message_author else "",
            "message_author_name": str(message_author) if message_author else "",
            "message_content": message.content if message is not None else "",
            "emoji": emoji,
            "staff_discord_id": str(staff_id),
            "staff_display_name": staff_display_name,
        }
