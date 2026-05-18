import asyncio
import logging
from typing import Optional, Tuple

import aiohttp
import discord
from redbot.core import Config, commands


log = logging.getLogger("red.elrondradar")

DEFAULT_ALLOWED_USER_IDS = [396052375409917952]
DEFAULT_ALLOWED_ROLE_IDS = [
    1198381095553617922,
    1252252269790105721,
    1247172016490938472,
]
DEFAULT_TENANT_ROLE_IDS = [1391914584440311840]
DEFAULT_LINK_INSTRUCTIONS_CHANNEL_ID = 1392004498611900476
SUPPORTED_EMOJIS = {"🚨", "🐧", "👀", "🛠️", "🛠", "⏳", "⌛", "✅", "📦", "🔁", "🔄"}
DEFAULT_TICKET_CATEGORY_ID = 1281426693906759730
DEFAULT_BACKEND_CHANNEL_ID = 1480735317089587251


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
        )

    def _reactions_intent_state(self) -> str:
        intents = getattr(self.bot, "intents", None)
        if intents is None:
            return "unknown"
        if hasattr(intents, "reactions"):
            return str(getattr(intents, "reactions"))
        return str(getattr(intents, "guild_reactions", "unknown"))

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
        first_message = await self._first_useful_channel_message(channel)
        excerpt = self._message_excerpt(first_message, limit=900)
        source_url = first_message.jump_url if first_message is not None else f"https://discord.com/channels/{ctx.guild.id}/{channel.id}"
        category_id = getattr(channel, "category_id", None)
        expected_category = await self.config.ticket_category_id()

        lines = [
            "Elrond radar ticket inspection:",
            f"- channel: #{getattr(channel, 'name', channel.id)} ({channel.id})",
            f"- category: {category_id} ({'ok' if category_id == expected_category else 'expected ' + str(expected_category)})",
            f"- tenant from overwrites: {tenant_member} ({tenant_member.id})" if tenant_member is not None else "- tenant from overwrites: not found",
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
        if emoji not in SUPPORTED_EMOJIS:
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
        if emoji not in SUPPORTED_EMOJIS:
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
        await self._handle_ticket_channel_create(channel)

    async def _handle_reaction(self, payload: discord.RawReactionActionEvent, action: str):
        if not await self.config.enabled():
            return
        if payload.guild_id is None:
            return
        if payload.guild_id != await self.config.guild_id():
            return

        emoji = str(payload.emoji)
        if emoji not in SUPPORTED_EMOJIS:
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

        tracked = set(await self.config.tracked_ticket_channel_ids())
        if channel.id in tracked and not force:
            return False

        await asyncio.sleep(5)
        first_message = await self._first_useful_channel_message(channel)
        message_excerpt = self._message_excerpt(first_message)
        tenant_member = await self._ticket_tenant_member(channel)
        visible_members = await self._ticket_visible_members(channel)
        if tenant_member is None and visible_members:
            await self._announce_link_required(channel, visible_members[0])
            log.info("Elrond radar ticket skipped pending Discord link: channel=%s user=%s", channel.id, visible_members[0].id)
            return False
        backend_thread = await self._create_backend_thread(channel, first_message)
        if backend_thread is None:
            log.warning("Elrond radar could not create backend thread for ticket channel %s", channel.id)
            return False

        if await self.config.announce_ticket_link():
            try:
                await channel.send(
                    "Staff backend thread: " + backend_thread.jump_url,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                log.warning("Elrond radar could not announce backend thread in ticket %s: %s", channel.id, exc)

        source_message_id = first_message.id if first_message is not None else channel.id
        ticket_url = first_message.jump_url if first_message is not None else f"https://discord.com/channels/{guild.id}/{channel.id}"
        intake_lines = [
            "Ticket intake for " + channel.mention,
            "Source: " + ticket_url,
        ]
        if first_message is not None:
            intake_lines.append("Author: " + str(first_message.author))
        if tenant_member is not None:
            intake_lines.append("Tenant: " + str(tenant_member))
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
            "message_author_id": str(tenant_member.id) if tenant_member is not None else (str(first_message.author.id) if first_message is not None else ""),
            "message_author_name": str(tenant_member) if tenant_member is not None else (str(first_message.author) if first_message is not None else ""),
            "message_content": message_excerpt,
            "backend_thread_id": str(backend_thread.id),
            "backend_thread_url": backend_thread.jump_url,
            "staff_discord_id": str(self.bot.user.id if self.bot.user else 0),
            "staff_display_name": "Elrond Radar",
        })
        if status is not None and status < 300:
            tracked.add(channel.id)
            await self.config.tracked_ticket_channel_ids.set(list(tracked)[-500:])
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

    async def _first_useful_channel_message(self, channel) -> Optional[discord.Message]:
        fallback = None
        try:
            async for message in channel.history(limit=50, oldest_first=True):
                excerpt = self._message_excerpt(message)
                if excerpt and fallback is None:
                    fallback = message
                author = getattr(message, "author", None)
                if excerpt and not getattr(author, "bot", False):
                    return message
        except (discord.Forbidden, discord.HTTPException):
            return None
        return fallback

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

    async def _create_backend_thread(self, ticket_channel, first_message: Optional[discord.Message]):
        backend_channel = self.bot.get_channel(await self.config.backend_channel_id())
        if backend_channel is None and ticket_channel.guild is not None:
            try:
                backend_channel = await ticket_channel.guild.fetch_channel(await self.config.backend_channel_id())
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return None
        if backend_channel is None or not hasattr(backend_channel, "create_thread"):
            return None

        raw_name = getattr(ticket_channel, "name", str(ticket_channel.id))
        thread_name = ("intake-" + raw_name)[:90]
        try:
            return await backend_channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                reason="Elrond support ticket intake",
            )
        except (discord.Forbidden, discord.HTTPException):
            try:
                return await backend_channel.create_thread(
                    name=thread_name,
                    type=discord.ChannelType.private_thread,
                    reason="Elrond support ticket intake",
                )
            except (discord.Forbidden, discord.HTTPException):
                return None

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
