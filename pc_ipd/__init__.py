from otree.api import *
import random

doc = """
繰り返し囚人のジレンマゲーム（パートナー選択あり）。
ラウンド1、またはパートナーとの関係が解消された場合、プレイヤーは新しいパートナーとマッチングされます。
各ラウンドの終わりに、80%の確率で次のラウンドも同じパートナーとゲームを続行します。
"""

class C(BaseConstants):
    NAME_IN_URL = 'pc_ipd_revised'
    PLAYERS_PER_GROUP = 2
    NUM_ROUNDS = 10
    PAYOFF_MATRIX = {
        (True, True): [4, 4],    # True: Cooperate, False: Defect
        (True, False): [0, 5],
        (False, True): [5, 0],
        (False, False): [1, 1],
    }
    CONTINUATION_PROB = 0.8

class Subsession(BaseSubsession):
    pass

class Group(BaseGroup):
    match_success = models.BooleanField(initial=False)
    continue_game = models.BooleanField(initial=False)

    def set_payoffs(self):
        p1, p2 = self.get_players()
        # マッチングが成功したグループのみ利得を計算
        if self.match_success:
            payoffs = C.PAYOFF_MATRIX[(p1.decision_pd, p2.decision_pd)]
            p1.payoff = payoffs[0]
            p2.payoff = payoffs[1]

    def set_continuation(self):
        p1, p2 = self.get_players()
        # マッチングが成功した場合のみ継続判定
        if self.match_success:
            self.continue_game = random.random() < C.CONTINUATION_PROB
        if p1.decision_pd == False or p2.decision_pd == False:
            self.continue_game = 0

class Player(BasePlayer):
    chk1 = models.BooleanField(label="⭐️", blank=True)
    chk2 = models.BooleanField(label="⭐️", blank=True)
    chk3 = models.BooleanField(label="⭐️", blank=True)
    chk4 = models.BooleanField(label="⭐️", blank=True)
    chk5 = models.BooleanField(label="⭐️", blank=True)

    signal_stars = models.IntegerField(doc="amount of signal")
    partner_signal_stars = models.IntegerField(doc="相手のシグナルスコア")
    
    accept_partner = models.BooleanField(
        label="この相手をパートナーとして受け入れますか？",
        widget=widgets.RadioSelect,
        choices=[[True, 'はい'], [False, 'いいえ']]
    )

    is_rematched = models.BooleanField(initial=True)
    is_waiting = models.BooleanField(initial=False)
    
    decision_pd = models.BooleanField(
        label="あなたの行動を選択してください。",
        choices=[[True, '協力 (C)'], [False, '非協力 (D)']],
        widget=widgets.RadioSelect,
        doc="True: Cooperate, False: Defect"
    )
    
    def get_cumulative_payoff(self):
        return sum([p.payoff for p in self.in_all_rounds() if p.payoff is not None])


#FUNCTIONS
def matchingsort(subsession: Subsession):
    
    if subsession.round_number == 1:
        subsession.group_randomly()
        for p in subsession.get_players():
            p.is_rematched = True
        for g in subsession.get_groups():
            g.match_success = False
    else:
        prev_groups = subsession.in_round(subsession.round_number - 1).get_groups()
        continued_groups = []
        new_groups_matrix = []
        rematch_pool = []
        
        for g in prev_groups:
            if g.continue_game == 1:
                current_round_players = [p.in_round(subsession.round_number) for p in g.get_players()]
                continued_groups.append(current_round_players)
                for p in current_round_players:
                    p.is_rematched = False
            else:
                current_round_players = [p.in_round(subsession.round_number) for p in g.get_players()]
                rematch_pool.extend(current_round_players)
                for p in current_round_players:
                    p.is_rematched = True
        random.shuffle(rematch_pool)
        new_match_list = [rematch_pool[i:i+2] for i in range(0, len(rematch_pool), 2)]
        print(new_match_list)
        
        final_matrix = continued_groups + new_match_list
        
        print(final_matrix)
        
        subsession.set_group_matrix(final_matrix)
        
        for group in subsession.get_groups():
        # 代表して1人目のプレイヤーの状態で判断
            p1 = group.get_player_by_id(1)
            if p1.is_rematched:
            # 再マッチング組は、承諾フェーズに進むので、まだ成功していない
                group.match_success = False
            else:
            # 継続組は、自動的にマッチング成功とする
                group.match_success = True

# PAGES

class Introduction(Page):
    def is_displayed(player: Player):
        return player.round_number == 1


class BeforeMatching(WaitPage):
    wait_for_all_groups = True
    def after_all_players_arrive(subsession: Subsession):
        matchingsort(subsession)
        # 継続判定ok-->ok list
        # 継続判定ng-->ng list
        #ng list -->randommatching
        
class SendSignal(Page):
    form_model = 'player'
    form_fields = ["chk1", "chk2", "chk3", "chk4", "chk5"]
    
    def before_next_page(player:Player, timeout_happened):
        for field in ['chk1', 'chk2', 'chk3', 'chk4', 'chk5']:
            val = player.field_maybe_none(field)
            if val is None:
                setattr(player, field, False)
        checks = [player.chk1, player.chk2, player.chk3, player.chk4, player.chk5]
        player.signal_stars = sum(int(c) for c in checks if c)
    
    def is_displayed(player: Player):
        # 再マッチング対象のプレイヤーのみ表示
        return player.is_rematched == 1

class MatchingWaitPage(WaitPage):
    def is_displayed(player: Player):
        # 再マッチング対象のプレイヤーのみ表示
        return player.is_rematched == 1

    def after_all_players_arrive(group: Group):
        # group.is_displayedは存在しないので、このWaitPageに到達したプレイヤーが所属するグループのみ処理
        players = group.get_players()
        # このWaitPageに到達したプレイヤーはis_rematched=Trueであるため、再度チェックは不要
        if len(players) == 2: # 念のためグループサイズを確認
            p1, p2 = players
            p1.partner_signal_stars = p2.signal_stars
            p2.partner_signal_stars = p1.signal_stars

class ReceiveSignal(Page):
    form_model = 'player'
    form_fields = ['accept_partner']
    
    def is_displayed(player: Player):
        # 再マッチング対象のプレイヤーのみ表示
        return player.is_rematched and not player.is_waiting

    def vars_for_template(player: Player):
        return {
        'partner_signal_stars': player.partner_signal_stars,
        'stars_range': range(player.partner_signal_stars)
    }

class MatchingResultWaitPage(WaitPage):
    def is_displayed(player: Player):
        # 再マッチング対象のプレイヤーのみ表示
        return player.is_rematched and not player.is_waiting

    def after_all_players_arrive(group: Group):
        # このWaitPageに到達するのは is_rematched=True のプレイヤーからなるグループのみ
        p1, p2 = group.get_players()
        
        # 相互に承諾した場合のみマッチング成功
        if p1.accept_partner and p2.accept_partner:
            group.match_success = True
        else:
            group.match_success = False

class MatchingResult(Page):
    def vars_for_template(player: Player):
        return {'match_success': player.group.match_success}
    
    def is_displayed(player: Player):
        # 待機中のプレイヤーには結果を表示しない
        # かつ、マッチングフェーズをスキップしたプレイヤーには表示しない
        return not player.is_waiting and player.is_rematched



class PrisonersDilemma(Page):
    def vars_for_template(player: Player):
        pm = C.PAYOFF_MATRIX
        return {
            'payoff_CC': pm[(True, True)],
            'payoff_CD': pm[(True, False)],
            'payoff_DC': pm[(False, True)],
            'payoff_DD': pm[(False, False)],
        }
        
    form_model = 'player'
    form_fields = ['decision_pd']

    def is_displayed(player: Player):
        # マッチングが成功したプレイヤーのみ表示
        return player.group.match_success

class PDWaitPage(WaitPage):
    def is_displayed(player: Player):
        return player.group.match_success

    def after_all_players_arrive(group: Group):
        group.set_payoffs()
        group.set_continuation()

class PDResult(Page):
    def is_displayed(player: Player):
        return player.group.match_success

    def vars_for_template(player: Player):
        group = player.group
        other_player = player.get_others_in_group()[0]
        return {
            'player_decision': '協力' if player.decision_pd else '非協力',
            'other_decision': '協力' if other_player.decision_pd else '非協力',
            'payoff': player.payoff,
            'continue_game': group.continue_game
        }

class FinalResults(Page):
    def is_displayed(player: Player):
        return player.round_number == C.NUM_ROUNDS

    def vars_for_template(player: Player):
        return {'cumulative_payoff': player.get_cumulative_payoff()}

page_sequence = [
    Introduction,
    BeforeMatching,
    SendSignal,
    MatchingWaitPage,
    ReceiveSignal,
    MatchingResultWaitPage,
    MatchingResult,
    PrisonersDilemma,
    PDWaitPage,
    PDResult,
    FinalResults,
]