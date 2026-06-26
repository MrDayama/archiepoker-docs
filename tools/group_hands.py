#!/usr/bin/env python3
import sys, json
from collections import defaultdict

RANK_ORDER = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,'7':7,'6':6,'5':5,'4':4,'3':3,'2':2}

def rank_key(cards):
    # cards: list of strings like 'Ah' or objects? support dict with 'rank' and 'suit' or simple like 'As'
    ranks = []
    for c in cards:
        if isinstance(c, dict):
            r = c.get('rank')
        else:
            if not c:
                r = ''
            else:
                r = c[:-1]  # rank is all but the last character (supports multi-char ranks)
        ranks.append(r)
    # sort by RANK_ORDER descending
    ranks_sorted = sorted(ranks, key=lambda x: RANK_ORDER.get(x,0), reverse=True)
    return ''.join(ranks_sorted)

def suit_pattern(cards):
    # produce pattern like ABACD based on first occurrence mapping
    mapping = {}
    next_letter = ord('A')
    pat = []
    for c in cards:
        if isinstance(c, dict):
            s = c.get('suit')
        else:
            if not c:
                s = ''
            else:
                s = c[-1]  # suit is last character (supports multi-byte suit symbols)
        if s not in mapping:
            mapping[s] = chr(next_letter)
            next_letter += 1
        pat.append(mapping[s])
    return ''.join(pat)

def normalize_hand_obj(hand):
    # Accept either string like 'Ah Kh Qh Jh Th' or list or dict
    if isinstance(hand, str):
        parts = hand.split()
        cards = parts
    elif isinstance(hand, list):
        cards = hand
    elif isinstance(hand, dict):
        # expect {"cards":["Ah","Kh",...]} or similar
        if 'cards' in hand:
            cards = hand['cards']
        else:
            # try keys
            cards = hand.get('hand') or hand.get('cards') or []
    else:
        cards = []
    return cards


def main():
    if len(sys.argv) < 3:
        print('Usage: group_hands.py INPUT_JSON OUTPUT_JSON')
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2]
    with open(inp,'r',encoding='utf-8') as f:
        data = json.load(f)
    # data might be list of objects or dict
    hands = []
    if isinstance(data, dict):
        # try common keys
        if 'hands' in data and isinstance(data['hands'], list):
            hands = data['hands']
        else:
            # maybe it's list-like in values
            hands = list(data.values())
    elif isinstance(data, list):
        hands = data
    else:
        print('Unrecognized input JSON structure')
        sys.exit(2)

    groups = defaultdict(lambda: {'count':0,'examples':[]})

    for h in hands:
        cards = normalize_hand_obj(h)
        if not cards:
            continue
        # ensure cards are 5 elements
        if len(cards) != 5:
            # keep but still process
            pass
        rk = rank_key(cards)
        pat = suit_pattern(cards)
        key = rk + '|' + pat
        groups[key]['count'] += 1
        if len(groups[key]['examples']) < 3:
            groups[key]['examples'].append(cards)

    # build output list
    out_list = []
    for key,info in groups.items():
        rk,pat = key.split('|')
        out_list.append({'rank_key':rk,'pattern':pat,'combos':info['count'],'examples':info['examples']})

    # sort by combos desc
    out_list.sort(key=lambda x: x['combos'], reverse=True)
    with open(out,'w',encoding='utf-8') as f:
        json.dump({'summary_count':len(out_list),'groups':out_list}, f, ensure_ascii=False, indent=2)
    print('Wrote', out, 'groups:', len(out_list))

if __name__=='__main__':
    main()
