#!/usr/bin/env python3
"""
simulate_draw_ev.py
Simulate full 3-draw game between two players with a simple draw policy.
Policy: at each draw round, evaluate candidate discard sets (0..3 cards) by sampling a few replacement draws and pick the discard with best expected final high/low EV using simple scoring.

Outputs data/<file>.json with EV (fraction of pot) for player.
"""
import json,random,sys,argparse,itertools
from collections import Counter

RANK_ORDER = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,'7':7,'6':6,'5':5,'4':4,'3':3,'2':2}
RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
SUITS = ['♠','♥','♦','♣']

def all_cards():
    return [r+s for r in RANKS for s in SUITS]

def parse_hand_str(s):
    if isinstance(s,list): return s
    return s.split()

# Evaluate high hand as before
from collections import Counter

def rank_val(card):
    r = card[:-1]
    return RANK_ORDER.get(r,0)

def is_flush(cards):
    suits = [c[-1] for c in cards]
    return len(set(suits))==1

def is_straight(ranks):
    ranks = sorted(set(ranks), reverse=True)
    if len(ranks) < 5:
        return False, None
    for i in range(len(ranks)-4):
        seq = ranks[i:i+5]
        if seq[0]-seq[4]==4 and len(seq)==5:
            return True, seq[0]
    # wheel
    if set([14,5,4,3,2]).issubset(set(ranks)):
        return True, 5
    return False, None

def evaluate_5(cards):
    ranks = [rank_val(c) for c in cards]
    ranks.sort(reverse=True)
    cnt = Counter(ranks)
    counts = sorted(cnt.items(), key=lambda x:(-x[1], -x[0]))
    flush = is_flush(cards)
    straight, high_straight = is_straight(ranks)
    if straight and flush:
        return (8, (high_straight,))
    if counts[0][1]==4:
        four = counts[0][0]
        kicker = [r for r in ranks if r!=four][0]
        return (7, (four,kicker))
    if counts[0][1]==3 and len(counts)>1 and counts[1][1]==2:
        return (6, (counts[0][0], counts[1][0]))
    if flush:
        return (5, tuple(ranks))
    if straight:
        return (4, (high_straight,))
    if counts[0][1]==3:
        trips = counts[0][0]
        kickers = [r for r in ranks if r!=trips]
        return (3, (trips,)+tuple(kickers))
    if counts[0][1]==2 and len(counts)>1 and counts[1][1]==2:
        pair1 = counts[0][0]
        pair2 = counts[1][0]
        kickers = [r for r in ranks if r!=pair1 and r!=pair2]
        return (2, (pair1,pair2)+tuple(kickers))
    if counts[0][1]==2:
        pair = counts[0][0]
        kickers = [r for r in ranks if r!=pair]
        return (1, (pair,)+tuple(kickers))
    return (0, tuple(ranks))

def compare_eval(a,b):
    if a[0]!=b[0]:
        return 1 if a[0]>b[0] else -1
    ta, tb = a[1], b[1]
    if ta>tb: return 1
    if ta<tb: return -1
    return 0

# Low qualifier: 8-or-better -> all 5 cards rank <=8 and all distinct (no pair)
def low_qualifier(cards):
    ranks = [rank_val(c) for c in cards]
    # transform Ace to 1
    ranks_low = [1 if r==14 else r for r in ranks]
    if max(ranks_low) <= 8 and len(set(ranks_low))==5:
        # qualifies
        return True
    return False

# Low comparison: lower is better. We'll compare sorted ranks_low descending (higher is worse), so reverse
def low_value(cards):
    ranks = [rank_val(c) for c in cards]
    ranks_low = [1 if r==14 else r for r in ranks]
    vals = sorted(ranks_low, reverse=True)
    return tuple(vals)

# Pot split: if any low qualifies, low side is contested among qualifiers; else high takes full pot.
# For simplicity with 2 players:
# - if no low qualifiers: high winner gets 1.0
# - if one or both low qualifiers: low winner gets 0.5 of pot, high winner gets remaining 0.5

def resolve_pot(player_cards, opp_cards):
    high_p = evaluate_5(player_cards)
    high_o = evaluate_5(opp_cards)
    high_cmp = compare_eval(high_p, high_o)
    player_high_win = high_cmp>0
    opp_high_win = high_cmp<0
    tie_high = high_cmp==0
    # low
    p_low_q = low_qualifier(player_cards)
    o_low_q = low_qualifier(opp_cards)
    low_result = None
    if p_low_q and o_low_q:
        # compare low_value: lower wins
        lp = low_value(player_cards)
        lo = low_value(opp_cards)
        if lp < lo:
            low_winner = 'player'
        elif lp > lo:
            low_winner = 'opp'
        else:
            low_winner = 'tie'
    elif p_low_q:
        low_winner = 'player'
    elif o_low_q:
        low_winner = 'opp'
    else:
        low_winner = None
    # allocate pot
    player_share = 0.0
    # if no low_winner: full pot to high winner
    if not low_winner:
        if tie_high:
            player_share = 0.5
        elif player_high_win:
            player_share = 1.0
        else:
            player_share = 0.0
    else:
        # low gets half, high gets half
        # low half
        if low_winner=='player': player_share += 0.5
        elif low_winner=='tie': player_share += 0.25
        # high half
        if tie_high:
            player_share += 0.25
        elif player_high_win:
            player_share += 0.5
        # else 0 for high
    return player_share

# Draw policy: evaluate candidate discards up to 3 cards (all subsets up to size 3), estimate expected final high metric by inner sampling

def candidate_discards(cards, max_discards=3):
    idxs = list(range(len(cards)))
    cands = []
    for k in range(0, max_discards+1):
        for comb in itertools.combinations(idxs,k):
            cands.append(set(comb))
    return cands

# simulate single game with both players using same policy

def simulate_game(player_init, opp_init, trials_inner=50):
    # start with copy of deck
    deck = all_cards()
    for c in player_init: deck.remove(c)
    for c in opp_init: deck.remove(c)
    # players hands as lists
    player = list(player_init)
    opp = list(opp_init)
    # three draw rounds
    for draw_round in range(3):
        # player's decision
        player = player_decision(player, opp, deck, trials_inner)
        # update deck: we assume player draw happens before opp and deck updated
        # Opponent decision
        opp = player_decision(opp, player, deck, trials_inner)
    # showdown
    share = resolve_pot(player, opp)
    return share

# helper to draw replacement for selected discard indices from deck (randomly)
def draw_replacements(hand, discard_idxs, deck):
    hand2 = [c for i,c in enumerate(hand) if i not in discard_idxs]
    # draw same number from deck
    num = len(discard_idxs)
    draws = random.sample(deck, num)
    new_hand = hand2 + draws
    return new_hand

# decision function: evaluate each candidate discard by inner sampling of full play to end (random draws for future rounds) - approximate

def player_decision(hand, other_hand, deck, trials_inner):
    best_score = -1
    best_discard = set()
    cands = candidate_discards(hand, max_discards=3)
    for disc in cands:
        # approximate expected share after drawing these and random future draws for both players
        total = 0.0
        for _ in range(trials_inner):
            # clone deck and remove cards of both players (current), then remove drawn replacements
            deck_copy = [c for c in deck]
            # remove current hand cards from deck copy
            for c in hand: 
                if c in deck_copy: deck_copy.remove(c)
            for c in other_hand:
                if c in deck_copy: deck_copy.remove(c)
            # player draws replacements for disc
            try:
                draws = random.sample(deck_copy, len(disc))
            except ValueError:
                draws = []
            hand_after = [c for i,c in enumerate(hand) if i not in disc] + draws
            # simulate remaining draws randomly for both players
            # For simplicity, simulate remaining draws as random draws without further decisions
            # remaining rounds = 2 - current_round_estimate: but here we just finish by random drawing 2 more times of up to 3 cards each
            # We'll approximate final hands by further random replacement of up to 3 cards randomly
            # Opponent: random discard up to 3
            opp_after = list(other_hand)
            # random additional draws
            # simulate two more replacement cycles
            # perform one more random replacement for player and opp
            # For quicker approx, just randomize final hands by replacing random subset of up to 3 cards
            # Player random additional
            # remove drawn from deck_copy
            for d in draws:
                if d in deck_copy: deck_copy.remove(d)
            # player random additional replacements
            # choose k random positions to replace (0..3)
            k = random.randint(0,3)
            if k>0:
                # replace random k cards from hand_after
                if len(deck_copy)>=k:
                    new_draws = random.sample(deck_copy,k)
                    # replace last k cards for simplicity
                    hand_after = hand_after[:-k] + new_draws
                    for dd in new_draws:
                        if dd in deck_copy: deck_copy.remove(dd)
            # opponent randomize similarly
            k2 = random.randint(0,3)
            if k2>0 and len(deck_copy)>=k2:
                opp_draws = random.sample(deck_copy,k2)
                opp_after = opp_after[:-k2] + opp_draws
            # now resolve pot
            share = resolve_pot(hand_after, opp_after)
            total += share
        avg = total / trials_inner
        if avg > best_score:
            best_score = avg
            best_discard = disc
    # perform actual draw from real deck for chosen discard
    # remove current hand and other_hand from deck (deck param is shared) - but we pass deck that already excludes hand cards
    # To draw, ensure deck contains available cards
    # For drawing, sample from deck those not in hand/other_hand
    available = [c for c in deck]
    for c in hand:
        if c in available: available.remove(c)
    for c in other_hand:
        if c in available: available.remove(c)
    draws = []
    if len(best_discard)>0 and len(available)>=len(best_discard):
        draws = random.sample(available, len(best_discard))
    new_hand = [c for i,c in enumerate(hand) if i not in best_discard] + draws
    # update deck: remove draws
    for d in draws:
        if d in deck: deck.remove(d)
    # also remove opponent's current cards from deck if present (they will be removed before their draw)
    for c in other_hand:
        if c in deck: deck.remove(c)
    return new_hand

# Main runner

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary', default='data/summary-starting-hands.json')
    parser.add_argument('--out', default='data/summary-draw-ev-top50.json')
    parser.add_argument('--top', type=int, default=50)
    parser.add_argument('--trials', type=int, default=100)
    parser.add_argument('--inner', type=int, default=30)
    args = parser.parse_args()
    s = json.load(open(args.summary,encoding='utf-8'))
    groups = s.get('groups', [])[:args.top]
    results = []
    for g in groups:
        ex = g.get('examples',[None])[0]
        if isinstance(ex,list): ex = ' '.join(ex)
        if not ex: continue
        total_share = 0.0
        for i in range(args.trials):
            # choose random opponent as random combo from deck
            player_init = parse_hand_str(ex)
            # sample opponent random from full deck excluding player's cards
            deck_all = all_cards()
            for c in player_init:
                if c in deck_all: deck_all.remove(c)
            opp_init = random.sample(deck_all,5)
            # prepare deck for simulation: exclude initial hands
            deck = all_cards()
            for c in player_init: 
                if c in deck: deck.remove(c)
            for c in opp_init:
                if c in deck: deck.remove(c)
            share = simulate_game(player_init, opp_init, trials_inner=args.inner)
            total_share += share
        avg = total_share / args.trials
        results.append({'rank_key':g.get('rank_key'),'pattern':g.get('pattern'),'combos':g.get('combos'),'example':ex,'ev':avg})
        print('done group', g.get('rank_key'), 'ev', avg)
    out = {'meta':{'trials':args.trials,'inner':args.inner,'top':args.top}, 'results':results}
    json.dump(out, open(args.out,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Wrote', args.out)

if __name__=='__main__':
    main()
