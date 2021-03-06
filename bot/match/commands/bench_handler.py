from .command import InstantiatedCommand, Command, picking_states
from match.classes import CaptainValidator
from match.common import after_pick_sub, get_check_captain
from match import MatchStatus

from display import AllStrings as disp, ContextWrapper

import modules.roles as roles
from classes import Player


class BenchHandler(InstantiatedCommand):
    def __init__(self, obj):
        super().__init__(self, self.bench)
        self.validator = None
        self.factory = obj

    @property
    def match(self):
        return self.factory.match

    def on_start(self):
        self.validator = CaptainValidator(self.match)

        @self.validator.confirm
        async def do_bench(ctx, player, bench):
            player.bench(bench)
            if bench:
                await disp.BENCH_OK.send(self.match.channel, player.mention, match=self.match.proxy)
            else:
                await disp.UNBENCH_OK.send(self.match.channel, player.mention, match=self.match.proxy)

    def on_clean(self, hard=False):
        if self.validator:
            self.validator.clean()
            if hard:
                self.validator = None

    def on_team_ready(self, team):
        if self.validator:
            self.validator.clean()

    @Command.command(*picking_states)
    async def bench(self, ctx, args, bench):
        captain = None
        if not roles.is_admin(ctx.author):
            captain, msg = get_check_captain(ctx, self.match, check_turn=False)
            if msg:
                await msg
                return

            if await self.validator.check_message(ctx, captain, args):
                return

        if len(ctx.message.mentions) != 1:
            await disp.BENCH_MENTION.send(ctx)
            return

        p = Player.get(ctx.message.mentions[0].id)
        if not p:
            await disp.RM_NOT_IN_DB.send(ctx)
            return
        if not (p.match and p.active and p.match.id == self.match.id):
            await disp.BENCH_NO.send(ctx, p.mention)
            return
        if p.active.is_captain:
            await disp.RM_CAP.send(ctx, p.mention)
            return
        if p.active.is_playing:
            await disp.BENCH_RDY.send(ctx)
            return
        if bench and p.active.is_benched:
            await disp.BENCH_ALREADY.send(ctx)
            return
        if not bench and not p.active.is_benched:
            await disp.BENCH_NOT.send(ctx)
            return

        player = p.active

        # Can't have another command running  at the same time
        self.factory.sub.on_clean()
        self.factory.swap.on_clean()

        if roles.is_admin(ctx.author):
            await self.validator.force_confirm(ctx, player=player, bench=bench)
            return
        else:
            other_captain = self.match.teams[captain.team.id - 1].captain
            if bench:
                msg = await disp.BENCH_OK_CONFIRM.send(self.match.channel, other_captain.mention)
            else:
                msg = await disp.UNBENCH_OK_CONFIRM.send(self.match.channel, other_captain.mention)
            await self.validator.wait_valid(captain, msg, player=player, bench=bench)
