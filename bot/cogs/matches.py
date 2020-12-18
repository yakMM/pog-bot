# @CHECK 2.0 features OK

from discord.ext import commands
from logging import getLogger

import modules.config as cfg
from display import send
from modules.tools import is_al_num
from modules.exceptions import ElementNotFound, AlreadyPicked

from classes.players import TeamCaptain, ActivePlayer, PlayerStatus, get_player

from match_process import Match
from modules.enumerations import MatchStatus, SelStatus
from modules.census import get_offline_players
from classes.accounts import get_not_ready_players

log = getLogger("pog_bot")


class MatchesCog(commands.Cog, name='matches'):
    """
    Register cog, handle the commands in matches channels
    """

    def __init__(self, client):
        self.client = client

    async def cog_check(self, ctx):  # Check if right channel
        return ctx.channel.id in cfg.channels['matches']

    """
    Commands:

    =pick
    =match
    =ready
    """

    @commands.command(aliases=['p'])
    @commands.guild_only()
    @commands.max_concurrency(number=1, wait=True)
    async def pick(self, ctx, *args):
        match = Match.get(ctx.channel.id)
        player = await _test_player(ctx, match)
        if player is None:
            return
        if match.status in (MatchStatus.IS_FREE, MatchStatus.IS_RUNNING):
            # Edge case, will happen very rarely if not never
            await send("MATCH_NOT_READY", ctx, ctx.command.name)
            return
        if match.status in (MatchStatus.IS_STARTING, MatchStatus.IS_PLAYING, MatchStatus.IS_RESULT):
            await send("PK_OVER", ctx)  # Picking process is over
            return
        if len(args) == 0 or (len(args) == 1 and args[0] == "help"):
            await match.pick_status(ctx)
            return
        if player.status is PlayerStatus.IS_MATCHED:
            await send("PK_WAIT_FOR_PICK", ctx)  # Player is to be picked soon
            return
        a_player = player.active
        if len(args) == 0 or (len(args) == 1 and args[0] == "help"):
            await match.pick_help()
            return
        if not a_player.is_captain:
            await send("PK_NOT_CAPTAIN", ctx)
            return
        if not a_player.is_turn:
            await send("PK_NOT_TURN", ctx)
            return
        await match.pick(ctx, a_player, args)
        # if isinstance(a_player, TeamCaptain):
        #     if match.status is MatchStatus.IS_MAPPING:
        #         await _map(ctx, a_player, args)  # map picking function
        #         return
        #     if match.status is MatchStatus.IS_WAITING:
        #         if match.round_no == 1:
        #             await _faction_change(ctx, a_player, args)
        #             return
        #         await send("PK_OVER", ctx)  # Picking process is over
        #         return
        #     if a_player.is_turn:
        #         if match.status is MatchStatus.IS_PICKING:
        #             await _pick(ctx, a_player, args)  # player picking function
        #             return
        #         if match.status is MatchStatus.IS_FACTION:
        #             # faction picking function
        #             await _faction(ctx, a_player, args)
        #             return
        #         await send("UNKNOWN_ERROR", ctx, "Unknown match state")  # Should never happen
        #         return

    @commands.command()
    @commands.guild_only()
    async def resign(self, ctx):
        match = Match.get(ctx.channel.id)
        player = await _test_player(ctx, match)
        if player is None:
            return
        if match.status in (MatchStatus.IS_FREE, MatchStatus.IS_RUNNING):
            await send("MATCH_NOT_READY", ctx, ctx.command.name)
            return
        if match.status is not MatchStatus.IS_PICKING:
            await send("MATCH_NO_COMMAND", ctx, ctx.command.name)
            return
        if player.status is PlayerStatus.IS_MATCHED:
            await send("PK_WAIT_FOR_PICK", ctx)
            return
        a_player = player.active
        if not a_player.is_captain:
            await send("PK_NOT_CAPTAIN", ctx)
            return
        if not a_player.is_turn:
            await send("PK_NOT_TURN", ctx)
            return
        team = a_player.team
        match.demote(a_player)
        await send("PK_RESIGNED", ctx, team.captain.mention, team.name, match=match)

    @commands.command(aliases=['rdy'])
    @commands.guild_only()
    async def ready(self, ctx):  # when ready
        match = Match.get(ctx.channel.id)
        player = await _test_player(ctx, match)
        if player is None:
            return
        if match.status in (MatchStatus.IS_STARTING, MatchStatus.IS_PLAYING, MatchStatus.IS_RESULT):
            # match not ready for this command
            await send("MATCH_ALREADY", ctx, ctx.command.name)
            return
        if match.status is not MatchStatus.IS_WAITING:
            # match not ready for this command
            await send("MATCH_NOT_READY", ctx, ctx.command.name)
            return
        # Getting the "active" version of the player (version when player is in matched, more data inside)
        a_player = player.active
        if isinstance(a_player, TeamCaptain):
            if a_player.is_turn:
                result = get_not_ready_players(a_player.team)
                if len(result) != 0:
                    await send("MATCH_PLAYERS_NOT_READY", ctx, a_player.team.name, " ".join(p.mention for p in result))
                    return
                result = await get_offline_players(a_player.team)
                if len(result) != 0:
                    await send("MATCH_PLAYERS_OFFLINE", ctx, a_player.team.name, " ".join(p.mention for p in result), p_list=result)
                    return
                match.on_team_ready(a_player.team)
                await send("MATCH_TEAM_READY", ctx, a_player.team.name, match=match)
                return
            a_player.is_turn = True
            await send("MATCH_TEAM_UNREADY", ctx, a_player.team.name, match=match)
            return
        await send("PK_NOT_CAPTAIN", ctx)

    @commands.command()
    @commands.guild_only()
    async def squittal(self, ctx):
        match = Match.get(ctx.channel.id)
        if match.status not in (MatchStatus.IS_WAITING, MatchStatus.IS_STARTING, MatchStatus.IS_PLAYING, MatchStatus.IS_RESULT):
            await send("MATCH_NOT_READY", ctx, ctx.command.name)
            return
        await send("SC_PLAYERS_STRING", ctx, "\n".join(tm.ig_string for tm in match.teams))


def setup(client):
    client.add_cog(MatchesCog(client))


async def _test_player(ctx, match):
    """ Test if the player is in position to issue a match command
        Returns the player object if yes, None if not
    """

    try:
        player = get_player(ctx.author.id)
    except ElementNotFound:
        # player not registered
        await send("EXT_NOT_REGISTERED", ctx,  cfg.channels["register"])
        return
    if player.status in (PlayerStatus.IS_NOT_REGISTERED, PlayerStatus.IS_REGISTERED, PlayerStatus.IS_LOBBIED):
        # if player not in match
        await send("PK_NO_LOBBIED", ctx,  cfg.channels["lobby"])
        return
    if player.match.channel.id != match.channel.id:
        # if player not in the right match channel
        await send("PK_WRONG_CHANNEL", ctx,  player.match.channel.id)
        return
    return player



async def _faction_change(ctx, captain, args):
    is_faction = await _faction_check(ctx, args)
    if not is_faction:
        return
    team = captain.team
    if not captain.is_turn:
        await send("PK_OVER_READY", ctx)
        return
    try:
        if captain.match.faction_change(team, args[0]):
            await send("PK_FACTION_CHANGED", ctx, team.name, cfg.factions[team.faction])
            return
        await send("PK_FACTION_ALREADY", ctx)
        return
    except KeyError:
        await send("PK_NOT_VALID_FACTION", ctx)

async def _map(ctx, captain, args):
    sel = captain.match.map_selector
    match = captain.match
    if len(args) == 1 and args[0] == "confirm":
        if sel.status is not SelStatus.IS_SELECTED:
            await send("PK_NO_MAP", ctx)
            return
        if not captain.is_turn:
            await send("PK_NOT_TURN", ctx)
            return
        match.confirm_map()
        await send("MATCH_MAP_SELECTED", ctx, sel.map.name, sel=sel)
        return
    # Handle the actual map selection
    map = await sel.do_selection_process(ctx, args)
    if map:
        new_picker = match.pick_map(captain)
        await sel.wait_confirm(ctx, new_picker)
        if sel.is_booked:
            await send("MAP_BOOKED", ctx, new_picker.mention, sel.map.name)
