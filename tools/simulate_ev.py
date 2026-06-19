#!/usr/bin/env python3
"""
simulate_ev.py
Estimate pre-draw 5-card showdown equity for representative hands from summary JSON.
This is an initial estimator (pre-draw equity). To extend for draws, implement draw policy simulation.

Usage: python tools/simulate_ev.py --summary data/summary-starting-hands.json --out data/summary-ev-pre-draw-top200.json --trials 500 --top 200
"""
import json,random,sys,argparse
RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
SUITS = ['♠','♥','♦','♣']
RANK_MAP = {r:i for i,r in enumerate(RANKS, start=14)}
# but above enumerates wrong; fix: A->14 K->13... We'll create proper map
RANK_ORDER = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,'7':7,'6':6,'5':5,'4':4,'3':3,'2':2}

def all_cards():
    return [r+s for r in RANKS for s in SUITS]

def parse_hand_str(s):
    # input like 'A♠ 2♠ 3♠ 4♥ 9♦'
    parts = s.split()
    return parts

def rank_val(card):
    r = card[:-1]
    return RANK_ORDER.get(r,0)

def is_flush(cards):
    suits = [c[-1] for c in cards]
    return len(set(suits))==1

def is_straight(ranks):
    # ranks: list of ints
    ranks = sorted(set(ranks), reverse=True)
    if len(ranks) < 5:
        return False, None
    # check normal straights
    for i in range(len(ranks)-4):
        seq = ranks[i:i+5]
        if seq[0]-seq[4]==4 and len(seq)==5:
            return True, seq[0]
    # check wheel A-2-3-4-5
    if set([14,5,4,3,2]).issubset(set(ranks)):
        return True, 5
    return False, None

from collections import Counter

def evaluate_5(cards):
    # returns (category, tiebreaker tuple) higher is better
    # categories: 8 straight flush,7 four,6 full house,5 flush,4 straight,3 trips,2 two pair,1 one pair,0 high card
    ranks = [rank_val(c) for c in cards]
    ranks.sort(reverse=True)
    cnt = Counter(ranks)
    counts = sorted(cnt.items(), key=lambda x:(-x[1], -x[0]))
    flush = is_flush(cards)
    straight, high_straight = is_straight(ranks)
    if straight and flush:
        return (8, (high_straight,))
    # four of a kind
    if counts[0][1]==4:
        four = counts[0][0]
        kicker = [r for r in ranks if r!=four][0]
        return (7, (four,kicker))
    # full house
    if counts[0][1]==3 and counts[1][1]==2:
        return (6, (counts[0][0], counts[1][0]))
    if flush:
        return (5, tuple(ranks))
    if straight:
        return (4, (high_straight,))
    if counts[0][1]==3:
        trips = counts[0][0]
        kickers = [r for r in ranks if r!=trips]
        return (3, (trips,)+tuple(kickers))
    if counts[0][1]==2 and counts[1][1]==2:
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
    # compare tiebreakers lexicographically
    ta, tb = a[1], b[1]
    if ta>tb: return 1
    if ta<tb: return -1
    return 0


def run_group(hand_example, trials=500):
    player = parse_hand_str(hand_example)
    deck = all_cards()
    for c in player:
        if c in deck: deck.remove(c)
    wins=ties=losses=0
    for _ in range(trials):
        opp = random.sample(deck,5)
        eva = evaluate_5(player)
        evb = evaluate_5(opp)
        cmp = compare_eval(eva,evb)
        if cmp>0: wins+=1
        elif cmp<0: losses+=1
        else: ties+=1
    return {'wins':wins,'ties':ties,'losses':losses,'trials':trials,'equity': (wins+ties*0.5)/trials}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary', default='data/summary-starting-hands.json')
    parser.add_argument('--out', default='data/summary-ev-pre-draw-top200.json')
    parser.add_argument('--trials', type=int, default=500)
    parser.add_argument('--top', type=int, default=200)
    args = parser.parse_args()
    with open(args.summary,'r',encoding='utf-8') as f:
        s=json.load(f)
    groups = s.get('groups', [])
    if args.top>0:
        groups = groups[:args.top]
    results = []
    for g in groups:
        example = None
        if 'examples' in g and g['examples']:
            example = g['examples'][0]
            # handle if example already a list of cards
            if isinstance(example, list):
                example = ' '.join(example)
        elif 'examples' in g and isinstance(g['examples'], list) and g['examples']:
            example = g['examples'][0]
            if isinstance(example, list):
                example = ' '.join(example)
        else:
            # try to construct from rank_key naively (not used)
            continue
        res = run_group(example, trials=args.trials)
        outg = dict(rank_key=g.get('rank_key'), pattern=g.get('pattern'), combos=g.get('combos'), example=example)
        outg.update(res)
        results.append(outg)
    with open(args.out,'w',encoding='utf-8') as f:
        json.dump({'meta':{'trials':args.trials,'top':args.top,'note':'pre-draw 5-card showdown equity only'}, 'results':results}, f, ensure_ascii=False, indent=2)
    print('Wrote', args.out)

if __name__=='__main__':
    main()
