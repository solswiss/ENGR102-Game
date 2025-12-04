import os
import pygame, sys, random, pygame_menu
from pygame.locals import *
from math import floor

# ---------- CONFIG ----------
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 820
FPS = 60
CARD_W, CARD_H = 88, 128
CARD_GAP = 8
ROWS_TOP = 210
ASSET_FOLDER = "assets"
BUTTON_W = 120
BUTTON_H = 44
BOT_HIT_THRESHOLD = 16   # lower -> more conservative bots; higher -> more aggressive

# Animation timings (ms)
DEAL_ANIM_MS = 300   # time to move a card from deck to player for initial deal
HIT_ANIM_MS = 280    # time to move a card when a player hits
POST_ACTION_PAUSE_MS = 350  # pause after resolving action cards so player can see effect
# ----------------------------

pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Flip 7 — Full (Bots + Mouse UI + Video Cards)")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 20)
BIG = pygame.font.SysFont(None, 34)
SMALL = pygame.font.SysFont(None, 16)

# Card constants
MODIFIER_MAP = {13: 2, 14: 4, 15: 6, 16: 8, 17: 10}  # values 13..17 map to +2..+10
LABEL_MAP = {18: "X2", 19: "FREEZE", 20: "FLIP3", 21: "SECOND"}

# deck draw area for animation
DECK_POS = (820, 80)

# ---------- Image loading (cached) ----------
IMAGE_CACHE = {}
def load_card_image(val):
    # Map integer values to expected filenames.
    def try_load(pathlist):
        for p in pathlist:
            if not p:
                continue
            try:
                img = pygame.image.load(p).convert_alpha()
                img = pygame.transform.smoothscale(img, (CARD_W, CARD_H))
                return img
            except Exception:
                continue
        return None

    paths = []
    # number cards 0..12 -> cardnum{v}.png
    if val in range(0, 13):
        paths.append(os.path.join(ASSET_FOLDER, f"cardnum{val}.png"))
    # modifiers 13..17 -> plus{amt}.png
    elif val in MODIFIER_MAP:
        amt = MODIFIER_MAP[val]
        paths.append(os.path.join(ASSET_FOLDER, f"plus{amt}.png"))
        # fallbacks
        paths.append(os.path.join(ASSET_FOLDER, f"plus{amt}png"))
        paths.append(os.path.join(ASSET_FOLDER, f"plus_{amt}.png"))
    # special cards 18..21
    else:
        name_map = {18: "times2", 19: "freeze", 20: "flipthree", 21: "secondchance"}
        base = name_map.get(val, f"card_{val}")
        paths.append(os.path.join(ASSET_FOLDER, f"{base}.png"))
        paths.append(os.path.join(ASSET_FOLDER, f"{base}.PNG"))
        paths.append(os.path.join(ASSET_FOLDER, f"{base}.jpg"))

    img = try_load(paths)
    if img:
        return img

    # fallback render if asset missing
    surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
    surf.fill((250, 250, 250))
    pygame.draw.rect(surf, (20, 20, 20), surf.get_rect(), 2)
    label = str(val) if val in range(0,13) else LABEL_MAP.get(val, str(val))
    txt = FONT.render(label, True, (10,10,10))
    tw, th = txt.get_size()
    surf.blit(txt, ((CARD_W - tw)//2, (CARD_H - th)//2))
    return surf

def get_card_image(v):
    if v not in IMAGE_CACHE:
        IMAGE_CACHE[v] = load_card_image(v)
    return IMAGE_CACHE[v]

# --- back image loader (used for draws / deck) ---
def load_back_image():
    paths = [
        os.path.join(ASSET_FOLDER, "back.png"),
        os.path.join(ASSET_FOLDER, "back.PNG"),
        os.path.join(ASSET_FOLDER, "cardback.png"),
    ]
    for p in paths:
        try:
            img = pygame.image.load(p).convert_alpha()
            img = pygame.transform.smoothscale(img, (CARD_W, CARD_H))
            return img
        except Exception:
            continue
    # fallback back surface
    surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
    surf.fill((50, 80, 120))
    pygame.draw.rect(surf, (0,0,0), surf.get_rect(), 2)
    txt = FONT.render("BACK", True, (240,240,240))
    tw, th = txt.get_size()
    surf.blit(txt, ((CARD_W - tw)//2, (CARD_H - th)//2))
    return surf

def get_back_image():
    if 'BACK' not in IMAGE_CACHE:
        IMAGE_CACHE['BACK'] = load_back_image()
    return IMAGE_CACHE['BACK']

# ---------- Deck builder ----------
def make_deck():
    """Create a deck according to rules:
       0 x1, 1 x1, 2 x2, ..., 12 x12,
       modifiers: 13..17 -> one each (+2..+10),
       x2 (18) ensured once,
       actions 19,20,21 -> 3 each
    """
    deck = []
    deck.extend([0]*1)
    for v in range(1, 13):
        deck.extend([v]*v)
    # modifiers (one each)
    for v in range(13, 18):
        deck.append(v)
    # ensure X2 included
    if 18 not in deck:
        deck.append(18)
    # actions: 3 each (Freeze=19, Flip3=20, SecondChance=21)
    for a in (19,20,21):
        deck.extend([a]*3)
    random.shuffle(deck)
    return deck

# ---------- Player object ----------
class Player:
    def __init__(self, name, is_bot=False, bot_aggr=BOT_HIT_THRESHOLD):
        self.name = name
        self.is_bot = is_bot
        self.bot_aggr = bot_aggr
        self.hand = []            # list of integer card codes (0..21)
        self.hand_face = []       # parallel list of booleans; True if face-up
        self.has_second = False   # true if they hold a second chance
        self.stayed = False
        self.busted = False
        self.score_current = 0
        self.score_total = 0

    def reset_for_round(self):
        self.hand = []
        self.hand_face = []
        self.has_second = False
        self.stayed = False
        self.busted = False
        self.score_current = 0

    def compute_current_score(self):
        # sum numeric cards 0..12
        num_sum = sum(c for c in self.hand if c in range(0,13))
        # multiply first (X2 card 18)
        mul = 2 if 18 in self.hand else 1
        # then add modifiers +2..+10 (13..17)
        mod_sum = sum(MODIFIER_MAP[c] for c in self.hand if c in MODIFIER_MAP)
        self.score_current = num_sum * mul + mod_sum
        return self.score_current

    # helpers to manage hand and face flags
    def add_card(self, card_val, face_up=True):
        """Append a card to player's hand and set its face flag."""
        self.hand.append(card_val)
        self.hand_face.append(bool(face_up))

    def pop_last(self):
        """Remove and return last card (and its face flag)."""
        if not self.hand:
            return None
        self.hand_face.pop()
        return self.hand.pop()

    def remove_card_value(self, value):
        """Remove first occurrence of value from hand (and corresponding flag)."""
        for i, v in enumerate(self.hand):
            if v == value:
                self.hand.pop(i)
                self.hand_face.pop(i)
                return True
        return False

# ---------- Helpers ----------
def unique_number_count(hand):
    return len(set([c for c in hand if c in range(0,13)]))

def has_duplicate_number(hand):
    nums = [c for c in hand if c in range(0,13)]
    return len(nums) != len(set(nums))

def next_active_index(players, start_idx):
    n = len(players)
    for i in range(1, n+1):
        idx = (start_idx + i) % n
        if not players[idx].busted and not players[idx].stayed:
            return idx
    return None

def ensure_deck_has_cards(deck, discard):
    if not deck and discard:
        deck.extend(discard)
        discard.clear()
        random.shuffle(deck)

def active_player_indices(players):
    """Return indices of players who are not busted and not stayed."""
    return [i for i,p in enumerate(players) if not p.busted and not p.stayed]

# ---------- UI utilities / layout helpers ----------
def player_hand_pos(player_index, card_index):
    """Return (x,y) screen position for a given player's card slot."""
    x = 18 + card_index * (CARD_W + CARD_GAP)
    y = ROWS_TOP + player_index * (CARD_H + 34)
    return x, y

def draw_header(title):
    screen.fill((245,245,245))
    screen.blit(BIG.render(title, True, (10,10,10)), (18, 10))
    screen.blit(FONT.render("H = Hit (keyboard)  S = Stay (keyboard)  Q = Quit to Menu", True, (10,10,10)), (18,50))

def draw_players(players, current_idx, final_info=None):
    y = ROWS_TOP
    back_img = get_back_image()
    for i, p in enumerate(players):
        status = ""
        if p.busted: status = " (BUSTED)"
        if p.stayed: status = " (STAYED)"
        cursor = " <--" if i==current_idx and not p.busted and not p.stayed else ""
        label = f"{i+1}. {p.name}  Tot:{p.score_total}  Curr:{p.score_current}{status}{cursor}"
        screen.blit(FONT.render(label, True, (0,0,0)), (18, y-26))
        x = 18
        # show actual card if face flag True, otherwise show back image (concealed)
        for idx_card, c in enumerate(p.hand):
            face_up = False
            if idx_card < len(p.hand_face):
                face_up = p.hand_face[idx_card]
            if face_up:
                screen.blit(get_card_image(c), (x, y))
            else:
                screen.blit(back_img, (x, y))
            x += CARD_W + CARD_GAP
        y += CARD_H + 34
    if final_info:
        box = pygame.Rect(760, 90, 400, 120)
        pygame.draw.rect(screen, (230,230,255), box)
        pygame.draw.rect(screen, (0,0,0), box, 2)
        screen.blit(FONT.render("FINAL ROUND INFO", True, (0,0,0)), (box.x + 12, box.y + 8))
        screen.blit(FONT.render(final_info, True, (0,0,0)), (box.x + 12, box.y + 38))

def draw_deck_info(deck, discard):
    screen.blit(FONT.render(f"Deck: {len(deck)}   Discard: {len(discard)}", True, (0,0,0)), (820, 58))
    # draw deck graphic (top of deck)
    top_rect = pygame.Rect(DECK_POS[0], DECK_POS[1], CARD_W, CARD_H)
    pygame.draw.rect(screen, (200,200,200), top_rect)
    pygame.draw.rect(screen, (0,0,0), top_rect, 2)
    if deck:
        # show back of deck (do not reveal top card)
        screen.blit(get_back_image(), top_rect.topleft)

# ---------- animation: animate moving a card from deck to player's hand ----------
def animate_card_move(card_val, target_idx, target_slot_index, duration_ms):
    """Animate a card image moving from DECK_POS to player target position over duration_ms.
    Uses the back image during the animation so faces are not revealed.
    """
    start_x, start_y = DECK_POS
    end_x, end_y = player_hand_pos(target_idx, target_slot_index)
    img = get_back_image()  # use back for animation
    frames = max(1, int(round(duration_ms / (1000.0 / FPS))))
    for f in range(frames):
        t = (f+1)/frames
        cur_x = int(start_x + (end_x - start_x) * t)
        cur_y = int(start_y + (end_y - start_y) * t)
        # redraw full UI behind
        draw_header("Flip 7 — Play")
        draw_players(current_global_players[0], current_global_players[1], current_global_players[2])
        draw_deck_info(current_global_deck[0], current_global_discard[0])
        # draw the moving card on top (back)
        screen.blit(img, (cur_x, cur_y))
        pygame.display.update()
        clock.tick(FPS)

# ---------- Target selection overlay ----------
def choose_target_ui(players, prompt_text, allowed_indices=None):
    """
    Show a modal overlay listing only allowed_indices (list of indices).
    If allowed_indices is None, all players are listed (but disabled if busted/stayed).
    Returns index of selected player or None.
    """
    selecting = True
    selected = None
    overlay = pygame.Rect(120, 120, WINDOW_WIDTH - 240, WINDOW_HEIGHT - 240)

    # prepare visible rows mapping to player indices
    if allowed_indices is None:
        visible_list = list(range(len(players)))
    else:
        visible_list = list(allowed_indices)

    while selecting:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); sys.exit()
            if ev.type == MOUSEBUTTONDOWN and ev.button == 1:
                mx,my = ev.pos
                base_y = overlay.y + 60
                for row_i, i in enumerate(visible_list):
                    p = players[i]
                    rect = pygame.Rect(overlay.x + 40, base_y + row_i*44, overlay.width - 80, 38)
                    if rect.collidepoint(mx,my):
                        # can't select busted or stayed players
                        if p.busted or p.stayed:
                            break
                        selected = i
                        selecting = False
                        break
            if ev.type == KEYDOWN and ev.key == K_ESCAPE:
                selected = None
                selecting = False

        # draw overlay
        screen.fill((50,50,50))
        pygame.draw.rect(screen, (240,240,240), overlay)
        pygame.draw.rect(screen, (10,10,10), overlay, 3)
        title = BIG.render(prompt_text, True, (10,10,10))
        screen.blit(title, (overlay.x + 20, overlay.y + 10))
        base_y = overlay.y + 60

        for row_i, i in enumerate(visible_list):
            p = players[i]
            status = " (BUSTED)" if p.busted else (" (STAYED)" if p.stayed else "")
            lab = f"{i+1}. {p.name}{status}"
            rect = pygame.Rect(overlay.x + 40, base_y + row_i*44, overlay.width - 80, 38)
            # gray out disabled rows if busted/stayed
            color = (180,180,180) if (p.busted or p.stayed) else (220,220,220)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (0,0,0), rect, 1)
            screen.blit(FONT.render(lab, True, (0,0,0)), (rect.x + 8, rect.y + 8))

        pygame.display.update()
        clock.tick(FPS)
    return selected

# We need some globals so the animation function can read UI state for redrawing while animating
current_global_players = [None, None, None]  # [players, current_idx, final_info]
current_global_deck = [None]
current_global_discard = [None]

# ---------- Resolve drawn card logic (core mechanics) ----------
def resolve_draw(player_idx, card_val, players, deck, discard, current_idx):
    """Return result codes: 'ok','bust','flip7','second_consumed'"""
    p = players[player_idx]

    # SECOND CHANCE (21)
    if card_val == 21:
        # Case A: player does NOT already have one -> they take it
        if not p.has_second:
            p.has_second = True
            p.add_card(21, face_up=True)
            p.compute_current_score()
            return "ok"

        # Case B: player already has one -> must give to another eligible player (NOT themselves)
        # Eligible: not busted, not stayed, not already has_second, and not the current player
        eligible = [i for i,pp in enumerate(players) if i != player_idx and (not pp.busted) and (not pp.stayed) and (not pp.has_second)]
        if p.is_bot:
            if eligible:
                tgt = random.choice(eligible)
                players[tgt].has_second = True
                players[tgt].add_card(21, face_up=True)
                players[tgt].compute_current_score()
                return "ok"
            else:
                # no eligible -> discard the Second Chance card
                discard.append(21)
                return "ok"
        else:
            # human: show UI but restrict to eligible
            if not eligible:
                # no one to give to -> discard
                discard.append(21)
                return "ok"
            tgt = choose_target_ui(players, f"{p.name} drew SECOND — choose target to give it to", allowed_indices=eligible)
            if tgt is not None:
                players[tgt].has_second = True
                players[tgt].add_card(21, face_up=True)
                players[tgt].compute_current_score()
            else:
                # cancelled -> discard
                discard.append(21)
            return "ok"

    # FLIP THREE (20)
    if card_val == 20:
        # When a player draws FLIP3 they choose a target player (could be themselves or another active player).
        # If they are the only active player available, they are forced to target themselves.
        # The target receives the next 3 cards (flip3 effect) and resolves them (including cascades).
        active = active_player_indices(players)
        # ensure at least the drawer is active
        if player_idx not in active:
            active.append(player_idx)
            active = sorted(set(active))
        # If only one active player -> force self-target
        if len(active) == 1:
            target_idx = active[0]
        else:
            if p.is_bot:
                # bots prefer targeting others if possible, else self
                others = [i for i in active if i != player_idx]
                target_idx = random.choice(others) if others else player_idx
            else:
                # human: allow choosing among active players (including self)
                target_idx = choose_target_ui(players, f"{p.name} drew FLIP3 — choose target to receive 3 flips", allowed_indices=active)
                if target_idx is None:
                    # cancelled -> discard the FLIP3 card
                    discard.append(20)
                    return "ok"

        # give flip3 card to target (for visual record) then deliver 3 flips to that target
        players[target_idx].add_card(20, face_up=True)
        # now deliver 3 cards to the target, resolving duplicates/busts appropriately
        for _ in range(3):
            ensure_deck_has_cards(deck, discard)
            if not deck:
                break
            drawn = deck.pop()
            # animate using back image (we do not reveal faces during movement)
            animate_card_move(drawn, target_idx, len(players[target_idx].hand), DEAL_ANIM_MS//2)
            # append to hand and reveal (face_up True)
            players[target_idx].add_card(drawn, face_up=True)
            if drawn in range(0,13):
                nums = [c for c in players[target_idx].hand if c in range(0,13)]
                if len(nums) != len(set(nums)):
                    if players[target_idx].has_second:
                        # consume second chance: drop the duplicate just drawn
                        players[target_idx].pop_last()  # remove drawn duplicate
                        players[target_idx].has_second = False
                        # remove the visual SECOND (21) from their hand if present
                        players[target_idx].remove_card_value(21)
                        players[target_idx].compute_current_score()
                        continue
                    else:
                        # bust: discard all their cards and mark busted
                        discard.extend(players[target_idx].hand)
                        players[target_idx].hand = []
                        players[target_idx].hand_face = []
                        players[target_idx].busted = True
                        players[target_idx].score_current = 0
                        pygame.time.delay(POST_ACTION_PAUSE_MS)
                        return "bust"
            # non-number cards remain in hand and will be processed below

        # After the 3 flips, process action cards (Flip3/Freeze) in the target's hand (may cascade)
        action_cards = [c for c in list(players[target_idx].hand) if c in (19,20)]
        for a in action_cards:
            if players[target_idx].busted:
                break
            # remove from hand for resolution
            try:
                players[target_idx].remove_card_value(a)
            except:
                continue
            if a == 19:
                # freeze: pick a target to force to Stay (same targeting logic as earlier)
                tgt_candidates = active_player_indices(players)
                if target_idx not in tgt_candidates:
                    tgt_candidates.append(target_idx)
                if len(tgt_candidates) == 1:
                    tgt = tgt_candidates[0]
                else:
                    if players[target_idx].is_bot:
                        # bot prefers others if available
                        others2 = [i for i in tgt_candidates if i != target_idx]
                        tgt = random.choice(others2) if others2 else target_idx
                    else:
                        tgt = choose_target_ui(players, f"{players[target_idx].name} resolved FREEZE — choose a target to force to Stay", allowed_indices=tgt_candidates)
                        if tgt is None:
                            # cancelled -> do nothing (discard freeze)
                            continue
                targ = players[tgt]
                targ.compute_current_score()
                targ.score_total += targ.score_current
                discard.extend(targ.hand); targ.hand = []; targ.hand_face = []; targ.stayed = True
                pygame.time.delay(POST_ACTION_PAUSE_MS)
            elif a == 20:
                # cascade another 3 draws onto the same target
                for _ in range(3):
                    ensure_deck_has_cards(deck, discard)
                    if not deck: break
                    drawn2 = deck.pop()
                    animate_card_move(drawn2, target_idx, len(players[target_idx].hand), DEAL_ANIM_MS//2)
                    players[target_idx].add_card(drawn2, face_up=True)
                    if drawn2 in range(0,13):
                        nums = [c for c in players[target_idx].hand if c in range(0,13)]
                        if len(nums) != len(set(nums)):
                            if players[target_idx].has_second:
                                players[target_idx].pop_last()
                                players[target_idx].has_second = False
                                players[target_idx].remove_card_value(21)
                            else:
                                discard.extend(players[target_idx].hand); players[target_idx].hand = []; players[target_idx].hand_face = []; players[target_idx].busted = True; players[target_idx].score_current = 0
                                pygame.time.delay(POST_ACTION_PAUSE_MS)
                                return "bust"
                pygame.time.delay(POST_ACTION_PAUSE_MS)

        # compute and check flip7 for the target
        players[target_idx].compute_current_score()
        if unique_number_count(players[target_idx].hand) >= 7:
            players[target_idx].score_total += 15 + players[target_idx].score_current
            discard.extend(players[target_idx].hand); players[target_idx].hand = []; players[target_idx].hand_face = []; players[target_idx].stayed = True
            pygame.time.delay(POST_ACTION_PAUSE_MS)
            return "flip7"
        return "ok"

    # NORMAL: numbers, modifiers, X2, freeze as stand-alone card
    # Add the card face-up (we called animate before resolve so hand should show face after)
    p.add_card(card_val, face_up=True)

    # If numeric, check duplicates immediately
    if card_val in range(0,13):
        nums = [c for c in p.hand if c in range(0,13)]
        if len(nums) != len(set(nums)):
            if p.has_second:
                # consume second chance: drop duplicate drawn
                p.pop_last()
                p.has_second = False
                p.remove_card_value(21)
                p.compute_current_score()
                return "second_consumed"
            else:
                discard.extend(p.hand); p.hand = []; p.hand_face = []; p.busted = True; p.score_current = 0
                pygame.time.delay(POST_ACTION_PAUSE_MS)
                return "bust"

    # If freeze drawn outside flip3
    if card_val == 19:
        # freeze should follow the same targeting rules as FLIP3
        tgt_candidates = active_player_indices(players)
        if player_idx not in tgt_candidates:
            tgt_candidates.append(player_idx)
        # if only one candidate, force them
        if len(tgt_candidates) == 1:
            tgt = tgt_candidates[0]
        else:
            if p.is_bot:
                others = [i for i in tgt_candidates if i != player_idx]
                tgt = random.choice(others) if others else player_idx
            else:
                tgt = choose_target_ui(players, f"{p.name} played FREEZE — choose a target to force to Stay", allowed_indices=tgt_candidates)
                if tgt is None:
                    # player canceled -> discard freeze
                    discard.append(19)
                    # also remove freeze card from player's hand if we had appended it
                    p.remove_card_value(19)
                    return "ok"
        targ = players[tgt]
        targ.compute_current_score(); targ.score_total += targ.score_current
        discard.extend(targ.hand); targ.hand = []; targ.hand_face = []; targ.stayed = True
        pygame.time.delay(POST_ACTION_PAUSE_MS)

    # compute score and check Flip7
    p.compute_current_score()
    if unique_number_count(p.hand) >= 7:
        p.score_total += 15 + p.score_current
        discard.extend(p.hand); p.hand = []; p.hand_face = []; p.stayed = True
        pygame.time.delay(POST_ACTION_PAUSE_MS)
        return "flip7"
    return "ok"

# ---------- Button helper ----------
class Button:
    def __init__(self, rect, label, callback):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.hover = False
    def draw(self, surf):
        col = (180,220,255) if self.hover else (200,200,200)
        pygame.draw.rect(surf, col, self.rect)
        pygame.draw.rect(surf, (0,0,0), self.rect, 2)
        txt = FONT.render(self.label, True, (0,0,0))
        tw, th = txt.get_size()
        surf.blit(txt, (self.rect.x + (self.rect.w - tw)//2, self.rect.y + (self.rect.h - th)//2))
    def handle_event(self, ev):
        if ev.type == MOUSEMOTION:
            self.hover = self.rect.collidepoint(ev.pos)
        if ev.type == MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.callback()

# ---------- Bot behavior ----------
def bot_should_hit(p: Player):
    # Simple heuristic:
    num_sum = sum(c for c in p.hand if c in range(0,13))
    ucount = unique_number_count(p.hand)
    if ucount >= 6:
        return False
    return num_sum < p.bot_aggr

# ---------- Winner announcement ----------
def announce_winner(player):
    screen.fill((200,255,200))
    screen.blit(BIG.render(f"{player.name} wins with {player.score_total} points!", True, (10,10,10)), (80, 320))
    pygame.display.update()
    pygame.time.delay(3500)

# ---------- Player setup via pygame_menu (allows add human/bot) ----------
players_global = []
def setup_players_gui():
    """
    Setup GUI now includes Exit button which simply returns to the menu.
    Start Game button only begins if there is at least one player.
    """
    running = True
    input_text = ""
    while running:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); sys.exit()
            if ev.type == KEYDOWN:
                if ev.key == K_BACKSPACE:
                    input_text = input_text[:-1]
                elif ev.key == K_RETURN:
                    if input_text.strip():
                        players_global.append(Player(input_text.strip(), is_bot=False))
                        input_text = ""
                else:
                    if len(input_text) < 18:
                        input_text += ev.unicode
            if ev.type == MOUSEBUTTONDOWN:
                mx,my = ev.pos
                # add human button
                if 920 <= mx <= 920+160 and 120 <= my <= 120+36:
                    if input_text.strip():
                        players_global.append(Player(input_text.strip(), is_bot=False))
                        input_text = ""
                # add bot button
                if 920 <= mx <= 920+160 and 170 <= my <= 170+36:
                    botname = f"Bot_{len([b for b in players_global if b.is_bot])+1}"
                    players_global.append(Player(botname, is_bot=True))
                # clear
                if 920 <= mx <= 920+160 and 230 <= my <= 230+36:
                    players_global.clear()
                # start game
                if 920 <= mx <= 920+160 and 290 <= my <= 920+290+36:  # same region as before
                    if players_global:
                        running = False
                # exit (new): return to menu without starting
                if 920 <= mx <= 920+160 and 350 <= my <= 350+36:
                    running = False
        # draw UI
        screen.fill((225,225,225))
        screen.blit(BIG.render("Setup Players", True, (10,10,10)), (40, 20))
        pygame.draw.rect(screen, (255,255,255), (40,120,420,36))
        pygame.draw.rect(screen, (0,0,0), (40,120,420,36), 2)
        screen.blit(FONT.render("Type player name and press 'Add Human' or Enter", True, (10,10,10)), (40,90))
        screen.blit(FONT.render(input_text, True, (10,10,10)), (46,126))
        # buttons
        pygame.draw.rect(screen, (200,200,200), (920,120,160,36)); screen.blit(FONT.render("Add Human", True, (0,0,0)), (940,128))
        pygame.draw.rect(screen, (200,200,200), (920,170,160,36)); screen.blit(FONT.render("Add Bot", True, (0,0,0)), (952,178))
        pygame.draw.rect(screen, (200,200,200), (920,230,160,36)); screen.blit(FONT.render("Clear", True, (0,0,0)), (960,236))
        pygame.draw.rect(screen, (120,200,120), (920,290,160,36)); screen.blit(FONT.render("Start Game", True, (0,0,0)), (948,298))
        pygame.draw.rect(screen, (200,160,160), (920,350,160,36)); screen.blit(FONT.render("Exit", True, (0,0,0)), (980,358))
        # show current players list
        yy = 180
        for i, p in enumerate(players_global):
            lab = f"{i+1}. {p.name} {'(BOT)' if p.is_bot else '(HUMAN)'}"
            screen.blit(FONT.render(lab, True, (0,0,0)), (40, yy))
            yy += 28
        pygame.display.update()
        clock.tick(FPS)

# ---------- Main game play (with mouse buttons, bots, improved final UI) ----------
def play_game_gui():
    if not players_global:
        return
    players = [Player(p.name, is_bot=p.is_bot, bot_aggr=p.bot_aggr) for p in players_global]
    n = len(players)
    deck = make_deck()
    discard = []
    dealer_idx = 0
    final_trigger = False
    triggerer_idx = None
    final_players_list = []

    # Buttons for current human player
    hit_btn = Button((820, 640, BUTTON_W, BUTTON_H), "Hit (H)", lambda: action_press("hit"))
    stay_btn = Button((960, 640, BUTTON_W, BUTTON_H), "Stay (S)", lambda: action_press("stay"))
    tooltip = ""
    global last_player_action
    last_player_action = None
    action_queue = []  # used to deliver button actions from UI into game loop

    def action_press(kind):
        action_queue.append(kind)

    running = True
    while running:
        # start new round - reset players but preserve totals
        for p in players:
            p.reset_for_round()

        # --- initial dealing: deal one card to each player (animate slowly) ---
        order = [(dealer_idx + i) % n for i in range(n)]
        for idx in order:
            ensure_deck_has_cards(deck, discard)
            if not deck: break
            drawn = deck.pop()
            # set globals for animation redraw
            current_global_players[0] = players
            current_global_players[1] = -1   # no current highlight during dealing
            current_global_players[2] = None
            current_global_deck[0] = deck
            current_global_discard[0] = discard
            # target slot is current length of their hand (before resolve will append)
            target_slot = len(players[idx].hand)
            animate_card_move(drawn, idx, target_slot, DEAL_ANIM_MS)
            # resolve after animation (resolve_draw will append into hand with face_up True)
            resolve_draw(idx, drawn, players, deck, discard, idx)
            pygame.time.delay(60)  # brief inter-card spacing

        # start with player after dealer
        current_idx = (dealer_idx + 1) % n

        # round loop
        round_should_end = False
        while True:
            ensure_deck_has_cards(deck, discard)
            # round end check
            if all(p.busted or p.stayed for p in players):
                break
            if round_should_end:
                break

            # skip inactive players
            if players[current_idx].busted or players[current_idx].stayed:
                nxt = next_active_index(players, current_idx)
                if nxt is None: break
                current_idx = nxt
                continue

            # draw UI
            draw_header("Flip 7 — Play")
            final_info = None
            if final_trigger:
                remaining_names = ", ".join([players[i].name for i in final_players_list if not players[i].stayed and not players[i].busted])
                final_info = f"Triggered by {players[triggerer_idx].name}. Remaining: {remaining_names}"
            draw_players(players, current_idx, final_info)
            draw_deck_info(deck, discard)

            # set globals for animation redraw
            current_global_players[0] = players
            current_global_players[1] = current_idx
            current_global_players[2] = final_info
            current_global_deck[0] = deck
            current_global_discard[0] = discard

            # draw buttons for human if current is human
            hit_btn.draw(screen); stay_btn.draw(screen)
            # draw tooltip if hovering
            if hit_btn.hover:
                tooltip = "Draw a card (keyboard H). If duplicate number -> bust unless you have Second Chance."
            elif stay_btn.hover:
                tooltip = "Bank your current points and end your turn (keyboard S)."
            else:
                tooltip = ""
            if tooltip:
                tbox = pygame.Rect(820, 600, 360, 30)
                pygame.draw.rect(screen, (255,255,220), tbox); pygame.draw.rect(screen, (0,0,0), tbox, 1)
                screen.blit(SMALL.render(tooltip, True, (0,0,0)), (tbox.x+6, tbox.y+6))
            pygame.display.update()

            # handle events and bot decisions
            # If current is bot, have it act with simple AI
            if players[current_idx].is_bot:
                bot = players[current_idx]
                pygame.time.delay(450)
                if bot.busted or bot.stayed:
                    pass
                else:
                    if bot_should_hit(bot):
                        ensure_deck_has_cards(deck, discard)
                        if deck:
                            drawn = deck.pop()
                            # show animation then resolve
                            target_slot = len(bot.hand)
                            animate_card_move(drawn, current_idx, target_slot, HIT_ANIM_MS)
                            res = resolve_draw(current_idx, drawn, players, deck, discard, current_idx)
                            # if bot hit and got to >=200 via actions it's handled below
                    else:
                        # bot stays
                        bot.compute_current_score()
                        bot.score_total += bot.score_current
                        discard.extend(bot.hand); bot.hand = []; bot.hand_face = []; bot.stayed = True
                        # if bot reached trigger score, set final trigger and request end-of-round
                        if bot.score_total >= 200 and not final_trigger:
                            final_trigger = True; triggerer_idx = current_idx
                            final_players_list = [i for i in range(n) if i != triggerer_idx]
                            round_should_end = True
                # advance to next player after bot action (round-robin)
                nxt = next_active_index(players, current_idx)
                if nxt is None:
                    break
                current_idx = nxt
                clock.tick(FPS)
                continue  # restart round loop

            # Human: process events + queued actions
            ev = pygame.event.wait()
            if ev.type == QUIT:
                pygame.quit(); sys.exit()
            if ev.type == KEYDOWN:
                if ev.key == K_q:
                    return
                if ev.key == K_h:
                    action_queue.append("hit")
                if ev.key == K_s:
                    action_queue.append("stay")
            # pass event to buttons for hover + clicks
            hit_btn.handle_event(ev); stay_btn.handle_event(ev)

            if action_queue:
                act = action_queue.pop(0)
                if act == "hit":
                    ensure_deck_has_cards(deck, discard)
                    if deck:
                        drawn = deck.pop()
                        # animate draw (back shows while moving)
                        target_slot = len(players[current_idx].hand)
                        animate_card_move(drawn, current_idx, target_slot, HIT_ANIM_MS)
                        res = resolve_draw(current_idx, drawn, players, deck, discard, current_idx)
                        # After a human HIT we ALWAYS advance to the next active player (round-robin),
                        # unless the action card forced more immediate draws (handled within resolve_draw).
                        # Also: if somehow the hit caused player's total to reach >=200 (rare without staying), handle final trigger here:
                        if players[current_idx].score_total >= 200 and not final_trigger:
                            final_trigger = True; triggerer_idx = current_idx
                            final_players_list = [i for i in range(n) if i != triggerer_idx]
                            round_should_end = True
                        # advance round-robin
                        if players[current_idx].busted or players[current_idx].stayed:
                            nxt = next_active_index(players, current_idx)
                            if nxt is None:
                                break
                            current_idx = nxt
                        else:
                            nxt = next_active_index(players, current_idx)
                            if nxt is None:
                                break
                            current_idx = nxt
                elif act == "stay":
                    pcur = players[current_idx]
                    pcur.compute_current_score()
                    pcur.score_total += pcur.score_current
                    discard.extend(pcur.hand); pcur.hand = []; pcur.hand_face = []; pcur.stayed = True
                    # if player reached or passed 200 score, trigger final round and request immediate round end
                    if pcur.score_total >= 200 and not final_trigger:
                        final_trigger = True; triggerer_idx = current_idx
                        final_players_list = [i for i in range(n) if i != triggerer_idx]
                        round_should_end = True
                    # after staying, advance to next active player
                    nxt = next_active_index(players, current_idx)
                    if nxt is None:
                        break
                    current_idx = nxt
            # if no action queued, continue loop (waiting for input)
            clock.tick(FPS)

        # Round ended: if final_trigger not active, rotate dealer and continue; if final triggered manage final players list
        if not final_trigger:
            dealer_idx = (dealer_idx + 1) % n
            ensure_deck_has_cards(deck, discard)
            # continue to next round
            continue
        else:
            # final extra turns for each player in final_players_list (those other than triggerer)
            # If final_players_list empty -> immediate win for triggerer
            if not final_players_list:
                announce_winner(players[triggerer_idx]); return

            # Each player in list gets one full personal round: deal one card and let them play until stay/bust
            for idx in final_players_list:
                if idx == triggerer_idx:
                    continue
                # If the player is busted/stayed already (from earlier in the round), they still get their personal final turn:
                players[idx].reset_for_round()
                ensure_deck_has_cards(deck, discard)
                if deck:
                    drawn = deck.pop()
                    # animate draw to that player for clarity
                    animate_card_move(drawn, idx, len(players[idx].hand), DEAL_ANIM_MS)
                    resolve_draw(idx, drawn, players, deck, discard, idx)
                # let this player act until stay/bust (they get full control)
                while not (players[idx].busted or players[idx].stayed):
                    draw_header("Final Round — Extra Turn")
                    draw_players(players, idx, f"Triggerer: {players[triggerer_idx].name}")
                    draw_deck_info(deck, discard)
                    hit_btn.draw(screen); stay_btn.draw(screen)
                    pygame.display.update()
                    if players[idx].is_bot:
                        pygame.time.delay(450)
                        if bot_should_hit(players[idx]):
                            ensure_deck_has_cards(deck, discard)
                            if deck:
                                d = deck.pop()
                                animate_card_move(d, idx, len(players[idx].hand), HIT_ANIM_MS)
                                resolve_draw(idx, d, players, deck, discard, idx)
                        else:
                            players[idx].compute_current_score()
                            players[idx].score_total += players[idx].score_current
                            discard.extend(players[idx].hand); players[idx].hand = []; players[idx].hand_face = []; players[idx].stayed = True
                    else:
                        ev = pygame.event.wait()
                        if ev.type == QUIT:
                            pygame.quit(); sys.exit()
                        if ev.type == KEYDOWN:
                            if ev.key == K_h:
                                ensure_deck_has_cards(deck, discard)
                                if deck:
                                    d = deck.pop()
                                    animate_card_move(d, idx, len(players[idx].hand), HIT_ANIM_MS)
                                    resolve_draw(idx, d, players, deck, discard, idx)
                            if ev.key == K_s:
                                players[idx].compute_current_score()
                                players[idx].score_total += players[idx].score_current
                                discard.extend(players[idx].hand); players[idx].hand = []; players[idx].hand_face = []; players[idx].stayed = True
                        if ev.type == MOUSEMOTION:
                            hit_btn.handle_event(ev); stay_btn.handle_event(ev)
                        if ev.type == MOUSEBUTTONDOWN and ev.button == 1:
                            hit_btn.handle_event(ev); stay_btn.handle_event(ev)
                    clock.tick(FPS)

            # after all final players had turns (or were skipped), determine winner
            top = max(p.score_total for p in players)
            winners = [p for p in players if p.score_total == top]
            if len(winners) == 1:
                announce_winner(winners[0]); return
            else:
                # tie: continue playing new normal rounds until resolved (reset final trigger)
                final_trigger = False
                triggerer_idx = None
                final_players_list = []
                dealer_idx = (dealer_idx + 1) % n
                ensure_deck_has_cards(deck, discard)
                # continue with next round

# ---------- Menu ----------
def show_rules():
    showing = True
    while showing:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); sys.exit()
            if ev.type == KEYDOWN and ev.key == K_SPACE:
                showing = False
        screen.fill((210,230,255))
        draw_header("Flip 7 — Official Rules (press SPACE to close)")
        lines = [
            "Deck: 1x0, 1x1, 2x2, 3x3 ... 12x12.",
            "Modifiers: +2, +4, +6, +8, +10 and X2 (one each).",
            "Actions: Flip Three, Freeze, Second Chance (3 each).",
            "On your turn: Hit to draw or Stay to bank your points.",
            "If you draw a duplicate number card you bust (score 0) unless you have Second Chance.",
            "Flip 7: 7 unique number cards ends the round and gives +15 bonus (you bank points).",
            "Flip3: draw next 3 cards immediately (can cascade).",
            "Freeze: choose a target player to force them to Stay (they bank their current points).",
            "Second Chance: keep until it prevents one bust and is consumed.",
            "Scoring: (sum numbers) * X2(if present) + modifiers.",
            "First to reach >=200 triggers final round — each other player gets one final turn."
        ]
        y = 120
        for l in lines:
            screen.blit(FONT.render(l, True, (10,10,10)), (30, y)); y+=26
        pygame.display.update()
        clock.tick(FPS)

def start_menu():
    menu = pygame_menu.Menu("Flip 7 (full)", WINDOW_WIDTH, WINDOW_HEIGHT, theme=pygame_menu.themes.THEME_BLUE)
    menu.add.button("Setup players (GUI)", setup_players_gui)
    menu.add.button("Rules", show_rules)
    menu.add.button("Play", lambda: play_game_gui())
    menu.add.button("Quit", pygame_menu.events.EXIT)
    menu.mainloop(screen)

if __name__ == "__main__":
    start_menu()
