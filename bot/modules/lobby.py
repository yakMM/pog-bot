import modules.config as cfg
from display.strings import AllStrings as disp
from display.classes import ContextWrapper

from random import choice as random_choice
from lib.tasks import Loop, loop
from logging import getLogger

from datetime import datetime as dt
import modules.tools as tools
import modules.reactions as reactions

log = getLogger("pog_bot")

_lobby_list = list()
_lobby_stuck = False
_MatchClass = None
_client = None
_warned_players = dict()
_rh = reactions.ReactionHandler(rem_bot_react=True)


def reset_timeout(player):
    for k in list(_warned_players.keys()):
        if _warned_players[k] is player:
            reactions.auto_clear(k)
            del _warned_players[k]
    player.reset_lobby_timestamp()


def init(m_cls, client):
    global _MatchClass
    global _client
    _MatchClass = m_cls
    _client = client
    _lobby_loop.start()


def _remove_from_warned(p):
    for k in list(_warned_players.keys()):
        if _warned_players[k] is p:
            reactions.auto_clear(k)
            del _warned_players[k]


def _clear_warned():
    for k in list(_warned_players.keys()):
        reactions.auto_clear(k)
    _warned_players.clear()


@_rh.reaction('🔁')
async def on_user_react(reaction, player, user, msg):
    if msg in _warned_players:
        if _warned_players[msg] is player:
            ctx = ContextWrapper.channel(cfg.channels["lobby"])
            ctx.author = user
            player.reset_lobby_timestamp()
            del _warned_players[msg]
            await disp.LB_REFRESHED.send(ctx)
            return
    raise reactions.UserLackingPermission


def is_lobby_stuck():
    return _lobby_stuck


def _set_lobby_stuck(bl):
    global _lobby_stuck
    _lobby_stuck = bl


# 7800, 7200
@loop(minutes=5)
async def _lobby_loop():
    for p in _lobby_list:
        now = tools.timestamp_now()
        if p.lobby_stamp < (now - 7800):
            remove_from_lobby(p)
            await disp.LB_TOO_LONG.send(ContextWrapper.channel(cfg.channels["lobby"]), p.mention,
                                        names_in_lobby=get_all_names_in_lobby())
        elif p.lobby_stamp < (now - 7200):
            if p not in _warned_players.values():
                msg = await disp.LB_WARNING.send(ContextWrapper.channel(cfg.channels["lobby"]), p.mention)
                await _rh.auto_add(msg)
                _warned_players[msg] = p


def _auto_ping_threshold():
    thresh = cfg.general["lobby_size"] - cfg.general["lobby_size"] // 3
    return thresh


def _auto_ping_cancel():
    _auto_ping.cancel()
    _auto_ping.already = False


def get_sub(player):
    if len(_lobby_list) == 0:
        return player
    if not player:
        player = _lobby_list[0]
    try:
        _remove_from_warned(player)
    except ValueError:
        pass
    _lobby_list.remove(player)
    _on_lobby_remove()
    return player


def add_to_lobby(player):
    _lobby_list.append(player)
    all_names = get_all_names_in_lobby()
    player.on_lobby_add()
    if len(_lobby_list) == cfg.general["lobby_size"]:
        _start_match_from_full_lobby()
    elif len(_lobby_list) >= _auto_ping_threshold():
        if not _auto_ping.is_running() and not _auto_ping.already:
            _auto_ping.start()
            _auto_ping.already = True
    return all_names


@loop(minutes=3, delay=1, count=2)
async def _auto_ping():
    if _MatchClass.find_empty() is None:
        return
    await disp.LB_NOTIFY.send(ContextWrapper.channel(cfg.channels["lobby"]), f'<@&{cfg.roles["notify"]}>')


_auto_ping.already = False


def get_lobby_len():
    return len(_lobby_list)


def get_all_names_in_lobby():
    names = [f"{p.mention} ({p.name})" for p in _lobby_list]
    return names


def get_all_ids_in_lobby():
    ids = [p.id for p in _lobby_list]
    return ids


def remove_from_lobby(player):
    _remove_from_warned(player)

    _lobby_list.remove(player)
    _on_lobby_remove()
    player.on_lobby_leave()


def on_match_free():
    _auto_ping.already = False
    if len(_lobby_list) == cfg.general["lobby_size"]:
        _start_match_from_full_lobby()


def _on_lobby_remove():
    _set_lobby_stuck(False)
    if len(_lobby_list) < _auto_ping_threshold():
        _auto_ping_cancel()


def _start_match_from_full_lobby():
    match = _MatchClass.find_empty()
    _auto_ping_cancel()
    if match is None:
        _set_lobby_stuck(True)
        Loop(coro=_send_stuck_msg, count=1).start()
    else:
        _set_lobby_stuck(False)
        match.spin_up(_lobby_list.copy())
        _lobby_list.clear()
        _clear_warned()


async def _send_stuck_msg():
    await disp.LB_STUCK.send(ContextWrapper.channel(cfg.channels["lobby"]))


def clear_lobby():
    if len(_lobby_list) == 0:
        return False
    for p in _lobby_list:
        p.on_lobby_leave()
    _lobby_list.clear()
    _clear_warned()
    _on_lobby_remove()
    return True