# merged_flip7_fixed.py
# Merged + bug-fixed Flip 7 (uses gameplay of first file, GUI of second, Comic Sans font)
import os
import pygame, sys, random, pygame_menu
import pygame_gui
from pygame.locals import *
from math import floor
import time

# ---------- CONFIG ----------
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 820
FPS = 60
CARD_W, CARD_H = 88, 128
CARD_GAP = 8
ROWS_TOP = 210
ASSET_FOLDER = "assets"
BUTTON_W = 140
BUTTON_H = 60
BOT_HIT_THRESHOLD = 16   # lower -> more conservative bots; higher -> more aggressive
# Delay / animation presets (kept from your code)
DELAY_PRESET = 'B'
DELAY_PRESETS = {
    'A': dict(bot_action=300, flip3_interval=150, anim_mult=1.0, msg_ms=700),
    'B': dict(bot_action=700, flip3_interval=300, anim_mult=1.35, msg_ms=1000),
    'C': dict(bot_action=1200, flip3_interval=500, anim_mult=1.6, msg_ms=1400),
}
_pres = DELAY_PRESETS.get(DELAY_PRESET, DELAY_PRESETS['B'])
BOT_ACTION_DELAY_MS = _pres['bot_action']
FLIP3_INTERVAL_MS = _pres['flip3_interval']
ANIM_MULTIPLIER = _pres['anim_mult']
MESSAGE_MS = _pres['msg_ms']

DEAL_ANIM_MS = int(300 * ANIM_MULTIPLIER)
HIT_ANIM_MS = int(280 * ANIM_MULTIPLIER)
POST_ACTION_PAUSE_MS = int(350 * ANIM_MULTIPLIER)
# ----------------------------

pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Flip 7")
clock = pygame.time.Clock()

# Use Comic Sans font per request (fallback if missing)
try:
    FONT = pygame.font.SysFont("Comic Sans MS", 28)
    BIG = pygame.font.SysFont("Comic Sans MS", 56)
    SMALL = pygame.font.SysFont("Comic Sans MS", 20)
except Exception:
    FONT = pygame.font.SysFont(None, 28)
    BIG = pygame.font.SysFont(None, 56)
    SMALL = pygame.font.SysFont(None, 20)

# GUI manager for setup/rules (from second code)
GUI_MANAGER = pygame_gui.UIManager((WINDOW_WIDTH, WINDOW_HEIGHT), theme_path="gui.json")

# Card constants
MODIFIER_MAP = {13: 2, 14: 4, 15: 6, 16: 8, 17: 10}
LABEL_MAP = {18: "X2", 19: "FREEZE", 20: "FLIP3", 21: "SECOND"}

# deck draw area for animation -- moved down a bit so it doesn't block player names
DECK_POS = (820, 120)

# ---------- Image loading (cached) ----------
IMAGE_CACHE = {}
def load_card_image(val):
    """ Takes in a number value and returns the card's image surface """
    def try_load(pathlist):
        """ Takes in the file path of the card image and returns a formatted image if possible, otherwise return None"""
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
    if val in range(0, 13):
        paths.append(os.path.join(ASSET_FOLDER, f"cardnum{val}.png"))
    elif val in MODIFIER_MAP:
        amt = MODIFIER_MAP[val]
        paths.append(os.path.join(ASSET_FOLDER, f"plus{amt}.png"))
        paths.append(os.path.join(ASSET_FOLDER, f"plus_{amt}.png"))
    else:
        name_map = {18: "times2", 19: "freeze", 20: "flipthree", 21: "secondchance"}
        base = name_map.get(val, f"card_{val}")
        paths.append(os.path.join(ASSET_FOLDER, f"{base}.png"))
        paths.append(os.path.join(ASSET_FOLDER, f"{base}.jpg"))

    img = try_load(paths)
    if img:
        return img

    # fallback render
    surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
    surf.fill((245,245,245))
    pygame.draw.rect(surf, (20,20,20), surf.get_rect(), 2)
    label = str(val) if val in range(0,13) else LABEL_MAP.get(val, str(val))
    txt = SMALL.render(label, True, (10,10,10))
    tw, th = txt.get_size()
    surf.blit(txt, ((CARD_W - tw)//2, (CARD_H - th)//2))
    return surf

def get_card_image(v):
    """ Given the card value, returns the associated card image from the image dictionary"""
    if v not in IMAGE_CACHE:
        IMAGE_CACHE[v] = load_card_image(v)
    return IMAGE_CACHE[v]

# back image loader
def load_back_image():
    """ Returns the image surface of the back card"""
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
    surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
    surf.fill((60,80,120))
    pygame.draw.rect(surf, (0,0,0), surf.get_rect(), 2)
    txt = SMALL.render("BACK", True, (240,240,240))
    tw, th = txt.get_size()
    surf.blit(txt, ((CARD_W - tw)//2, (CARD_H - th)//2))
    return surf

def get_back_image():
    """ Return the back card image from the image dicitonary"""
    if 'BACK' not in IMAGE_CACHE:
        IMAGE_CACHE['BACK'] = load_back_image()
    return IMAGE_CACHE['BACK']

# ---------- Deck builder ----------
def make_deck():
    """ Create a deck of cards, returns it as a list"""
    deck = []
    deck.extend([0]*1)
    for v in range(1, 13):
        deck.extend([v]*v)
    for v in range(13, 18):
        deck.append(v)
    if 18 not in deck:
        deck.append(18)
    for a in (19,20,21):
        deck.extend([a]*3)
    random.shuffle(deck)
    return deck

# ---------- Player ----------
class Player:
    def __init__(self, name, is_bot=False, bot_aggr=BOT_HIT_THRESHOLD):
        """Create the constructor fo the Player class. Takes in a name,  is bot (default False), and bot agression (default is a constant)"""
        self.name = name
        self.is_bot = is_bot
        self.bot_aggr = bot_aggr
        self.hand = []            # ints 0..21
        self.hand_face = []       # booleans for face-up
        self.has_second = False
        self.stayed = False
        self.busted = False
        self.score_current = 0
        self.score_total = 0

    def reset_for_round(self):
        """ Resets the round of the player by settings all attributes to its initialized state except the total score"""
        self.hand = []
        self.hand_face = []
        self.has_second = False
        self.stayed = False
        self.busted = False
        self.score_current = 0

    def compute_current_score(self):
        """ Calculate the player's current score"""
        num_sum = sum(c for c in self.hand if c in range(0,13))
        mul = 2 if 18 in self.hand else 1
        mod_sum = sum(MODIFIER_MAP[c] for c in self.hand if c in MODIFIER_MAP)
        self.score_current = num_sum * mul + mod_sum
        return self.score_current

    # helpers
    def add_card(self, card_val, face_up=True):
        """ Takes in a card value and add it to the player's hand"""
        self.hand.append(card_val)
        self.hand_face.append(bool(face_up))

    def pop_last(self):
        """" Remove the player's latest card"""
        if not self.hand: return None
        self.hand_face.pop()
        return self.hand.pop()

    def remove_card_value(self, value):
        """Takes a card and remove it from the player's hand"""
        # remove first occurrence synchronously for hand and hand_face
        for i, v in enumerate(self.hand):
            if v == value:
                self.hand.pop(i)
                self.hand_face.pop(i)
                return True
        return False

# ---------- Helpers ----------
def unique_number_count(hand):
    """ Takes in a hand and return the number of unique number cards"""
    return len(set([c for c in hand if c in range(0,13)]))

def has_duplicate_number(hand):
    """ Takes a hand and return True if there is a duplicate card and False is there isn't"""
    nums = [c for c in hand if c in range(0,13)]
    return len(nums) != len(set(nums))

def next_active_index(players, start_idx):
    """ Takes in the list of players and a starting index, returns the index of the player of the next active player. If no more active players, return None"""
    n = len(players)
    for i in range(1, n+1):
        idx = (start_idx + i) % n
        if not players[idx].busted and not players[idx].stayed:
            return idx
    return None

def ensure_deck_has_cards(deck, discard):
    """ Checks the if the deck has cards, if not, add discard cards back to the deck and shuffle """
    if not deck and discard:
        deck.extend(discard)
        discard.clear()
        random.shuffle(deck)

def active_player_indices(players):
    """ Takes in a list of players and returns list of active players indexes"""
    return [i for i,p in enumerate(players) if not p.busted and not p.stayed]

# ---------- UI helpers ----------
def player_hand_pos(player_index, card_index):
    """ Takes in a player's index and card index's, return the card position as a tuple of (x,y)"""
    # increased vertical spacing so cards don't overlap player names
    x = 18 + card_index * (CARD_W + CARD_GAP)
    y = ROWS_TOP + player_index * (CARD_H + 50)
    return x, y

def draw_header(title):
    """ Takes in a string and creates a header"""
    # header with boxed background so text doesn't bleed
    screen.fill((245,245,245))
    hdr_rect = pygame.Rect(12, 8, 760, 80)
    pygame.draw.rect(screen, (245,245,245), hdr_rect)  # same color but keeps consistent layout
    screen.blit(BIG.render(title, True, (10,10,10)), (18, 10))
    # NOTE: removed the "H = Hit ..." subtext per user's request

def draw_players(players, current_idx, final_info=None):
    """ Takes in a list of players, current index, and final info (default None) and display each players' information"""
    y = ROWS_TOP
    back_img = get_back_image()
    for i, p in enumerate(players):
        status = ""
        if p.busted: status = " (BUSTED)"
        if p.stayed: status = " (STAYED)"
        padding = 5
        cursor = " <--" if i==current_idx and not p.busted and not p.stayed else ""
        label = f"{i+1}. {p.name}  Tot: {p.score_total}  Curr: {p.score_current}{status}{cursor}"
        # draw label on a small background rect to avoid bleed
        lbl_rect = pygame.Rect(12, y-60, 700, 35 + 2 * padding)
        pygame.draw.rect(screen, (245,245,245), lbl_rect)
        screen.blit(FONT.render(label, True, (0,0,0)), (18, y-60))
        x = 18
        # draw cards slightly lower to avoid overlapping the name
        card_y = y-10
        for idx_card, c in enumerate(p.hand):
            face_up = False
            if idx_card < len(p.hand_face):
                face_up = p.hand_face[idx_card]
            if face_up:
                screen.blit(get_card_image(c), (x, card_y))
            else:
                screen.blit(back_img, (x, card_y))
            x += CARD_W + CARD_GAP
        y += CARD_H + 60

    # draw deck (so deck is under final-info box)

def draw_deck_info(deck, discard):
    """ Takes in a deck and discard deck and displays the current decks' info """
    # small background area for deck info so text doesn't bleed
    rect = pygame.Rect(WINDOW_WIDTH-380, 250, 360, 54)
    pygame.draw.rect(screen, (245,245,245), rect)
    screen.blit(FONT.render(f"Deck: {len(deck)}   Discard: {len(discard)}", True, (0,0,0)), (820, 250))
    top_rect = pygame.Rect(DECK_POS[0], DECK_POS[1], CARD_W, CARD_H)
    pygame.draw.rect(screen, (225,225,225), top_rect)
    pygame.draw.rect(screen, (0,0,0), top_rect, 2)
    if deck:
        # move the back image down slightly (DECK_POS already moved)
        screen.blit(get_back_image(), top_rect.topleft)

def draw_final_info_box(final_info):
    """ Takes in the final info (string) and displays it on the screen"""
    # draw final info on top of everything (call after draw_deck_info/draw_players)
    if not final_info:
        return
    box = pygame.Rect(760, 90, 400, 120)
    pygame.draw.rect(screen, (230,230,255), box)
    pygame.draw.rect(screen, (0,0,0), box, 2)
    screen.blit(FONT.render("FINAL ROUND INFO", True, (0,0,0)), (box.x + 12, box.y + 8))
    # wrap text if needed
    wrapped = []
    line = ""
    for word in final_info.split():
        if len(line+word) > 34:
            wrapped.append(line)
            line = word + " "
        else:
            line += word + " "
    if line: wrapped.append(line)
    y = box.y + 38
    for ln in wrapped:
        screen.blit(SMALL.render(ln.strip(), True, (0,0,0)), (box.x + 12, y))
        y += 22

# ---------- Message overlay (for busts, flip7, etc.) ----------
def show_message(text, ms=MESSAGE_MS):
    """ Takes in a text and how long it should be displayed for (default is MESSAGE_MS), finally overlaying`1 the text on the screen"""
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0,0,0,140))
    screen.blit(overlay, (0,0))
    padding = 15
    text_surface = BIG.render(text, True, (255, 255, 255))
    box_w, box_h = text_surface.get_width() + 2 * padding, text_surface.get_height() + 2 * padding
    box_x = (WINDOW_WIDTH - box_w)//2
    box_y = (WINDOW_HEIGHT - box_h)//2
    pygame.draw.rect(screen, (255,255,240), (box_x, box_y, box_w, box_h))
    pygame.draw.rect(screen, (0,0,0), (box_x, box_y, box_w, box_h), 3)
    lines = text.split('\n')
    y = box_y + 18
    for line in lines:
        txt = BIG.render(line, True, (10,10,10))
        txw, txh = txt.get_size()
        screen.blit(txt, (box_x + (box_w - txw)//2, y))
        y += txh + 6
    pygame.display.update()
    pygame.time.delay(ms)

# ---------- animation: animate moving a card from deck to player's hand ----------
def animate_card_move(card_val, target_idx, target_slot_index, duration_ms):
    """Takes in the card value, target index, target slot index, and time to animate a card from the deck to the player's hand"""
    start_x, start_y = DECK_POS
    end_x, end_y = player_hand_pos(target_idx, target_slot_index)
    img = get_card_image(card_val)   # face image while moving (requested)
    frames = max(1, int(round(duration_ms / (1000.0 / FPS))))
    for f in range(frames):
        t = (f+1)/frames
        cur_x = int(start_x + (end_x - start_x) * t)
        cur_y = int(start_y + (end_y - start_y) * t)
        # redraw behind
        draw_header("Flip 7 — Play")
        draw_players(current_global_players[0], current_global_players[1], None)
        draw_deck_info(current_global_deck[0], current_global_discard[0])
        # draw moving card on top
        screen.blit(img, (cur_x, cur_y))
        # if final info present draw that after to ensure it's on top
        if current_global_players[2]:
            draw_final_info_box(current_global_players[2])
        pygame.display.update()
        clock.tick(FPS)

# ---------- Target selection overlay ----------
def choose_target_ui(players, prompt_text, allowed_indices=None):
    """ Takes in a list of players, prompt, and allowed indices (default None) and displays the target selection overlay, which list available targets"""
    selecting = True
    selected = None
    overlay = pygame.Rect(120, 120, WINDOW_WIDTH - 240, WINDOW_HEIGHT - 240)
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
                    rect = pygame.Rect(overlay.x + 40, base_y + row_i*44 + 40, overlay.width - 80, 38)
                    if rect.collidepoint(mx,my):
                        if p.busted or p.stayed:
                            break
                        selected = i
                        selecting = False
                        break
            if ev.type == KEYDOWN and ev.key == K_ESCAPE:
                selected = None
                selecting = False

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
            rect = pygame.Rect(overlay.x + 40, base_y + row_i*44 + 40, overlay.width - 50, 38)
            color = (180,180,180) if (p.busted or p.stayed) else (220,220,220)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (0,0,0), rect, 1)
            screen.blit(FONT.render(lab, True, (0,0,0)), (rect.x + 8, rect.y))

        pygame.display.update()
        clock.tick(FPS)
    return selected

# Globals for animation redraw
current_global_players = [None, None, None]  # players, current_idx, final_info
current_global_deck = [None]
current_global_discard = [None]

# ---------- Resolve drawn card logic (core mechanics) ----------
def resolve_draw(player_idx, card_val, players, deck, discard, current_idx):
    """
    Takes in the player index, card  value, list of players, deck, discard deck, and the current player index
    Returns: 'ok','bust','flip7','second_consumed'
    """
    p = players[player_idx]

    # SECOND CHANCE (21)
    if card_val == 21:
        if not p.has_second:
            p.has_second = True
            p.add_card(21, face_up=True)
            p.compute_current_score()
            return "ok"
        # Already has one -> must give to other eligible or discard
        eligible = [i for i,pp in enumerate(players) if i != player_idx and (not pp.busted) and (not pp.stayed) and (not pp.has_second)]
        if p.is_bot:
            if eligible:
                tgt = random.choice(eligible)
                players[tgt].has_second = True
                players[tgt].add_card(21, face_up=True)
                players[tgt].compute_current_score()
                return "ok"
            else:
                discard.append(21)
                return "ok"
        else:
            if not eligible:
                discard.append(21)
                return "ok"
            tgt = choose_target_ui(players, f"{p.name} drew SECOND", allowed_indices=eligible)
            if tgt is not None:
                players[tgt].has_second = True
                players[tgt].add_card(21, face_up=True)
                players[tgt].compute_current_score()
            else:
                discard.append(21)
            return "ok"

    # FLIP THREE (20)
    if card_val == 20:
        active = active_player_indices(players)
        if player_idx not in active:
            active.append(player_idx)
            active = sorted(set(active))
        if len(active) == 1:
            target_idx = active[0]
        else:
            if p.is_bot:
                others = [i for i in active if i != player_idx]
                target_idx = random.choice(others) if others else player_idx
            else:
                target_idx = choose_target_ui(players, f"{p.name} drew FLIP3", allowed_indices=active)
                if target_idx is None:
                    discard.append(20)
                    return "ok"


        # AUTOMATIC delivery for both bots and humans: perform 3 slow flips onto target
        show_message(f"{p.name} used FLIP3 -> {players[target_idx].name}", ms=MESSAGE_MS//2)
        for _ in range(3):
            ensure_deck_has_cards(deck, discard)
            if not deck:
                break
            drawn = deck.pop()
            animate_card_move(drawn, target_idx, len(players[target_idx].hand), DEAL_ANIM_MS//2)
            players[target_idx].add_card(drawn, face_up=True)
            pygame.time.delay(FLIP3_INTERVAL_MS)
            # only number cards can bust
            if drawn in range(0,13):
                nums = [c for c in players[target_idx].hand if c in range(0,13)]
                if len(nums) != len(set(nums)):
                    if players[target_idx].has_second:
                        players[target_idx].pop_last()
                        players[target_idx].has_second = False
                        players[target_idx].remove_card_value(21)
                        players[target_idx].compute_current_score()
                        continue
                    else:
                        discard.extend(players[target_idx].hand)
                        players[target_idx].hand = []
                        players[target_idx].hand_face = []
                        players[target_idx].busted = True
                        players[target_idx].score_current = 0
                        show_message(f"{players[target_idx].name} BUSTED!", ms=900)
                        pygame.time.delay(POST_ACTION_PAUSE_MS)
                        return "bust"
        # After performing the three flips, continue to action resolution below

        # After playing flips, resolve action cards in target hand (remove BEFORE processing)
        # Collect a copy then remove+process to avoid leaving markers
        action_cards = [c for c in list(players[target_idx].hand) if c in (19,20)]
        for a in action_cards:
            # remove one instance (important to avoid re-triggering)
            players[target_idx].remove_card_value(a)
            if players[target_idx].busted:
                break
            if a == 19:
                targ_candidates = active_player_indices(players)
                if target_idx not in targ_candidates: targ_candidates.append(target_idx)
                if len(targ_candidates) == 1:
                    tgt = targ_candidates[0]
                else:
                    if players[target_idx].is_bot:
                        others2 = [i for i in targ_candidates if i != target_idx]
                        tgt = random.choice(others2) if others2 else target_idx
                    else:
                        tgt = choose_target_ui(players, f"{players[target_idx].name} resolved FREEZE", allowed_indices=targ_candidates)
                        if tgt is None:
                            continue
                targ = players[tgt]
                show_message(f"{players[target_idx].name} resolved FREEZE -> {targ.name}", ms=MESSAGE_MS//2)
                targ.compute_current_score()
                targ.score_total += targ.score_current
                discard.extend(targ.hand)
                targ.hand = []
                targ.hand_face = []
                targ.stayed = True
                pygame.time.delay(POST_ACTION_PAUSE_MS)
            elif a == 20:
                # cascade 3 draws onto same target (automatic)
                for _ in range(3):
                    ensure_deck_has_cards(deck, discard)
                    if not deck: break
                    drawn2 = deck.pop()
                    animate_card_move(drawn2, target_idx, len(players[target_idx].hand), DEAL_ANIM_MS//2)
                    players[target_idx].add_card(drawn2, face_up=True)
                    pygame.time.delay(FLIP3_INTERVAL_MS)
                    if drawn2 in range(0,13):
                        nums = [c for c in players[target_idx].hand if c in range(0,13)]
                        if len(nums) != len(set(nums)):
                            if players[target_idx].has_second:
                                players[target_idx].pop_last()
                                players[target_idx].has_second = False
                                players[target_idx].remove_card_value(21)
                            else:
                                discard.extend(players[target_idx].hand)
                                players[target_idx].hand = []
                                players[target_idx].hand_face = []
                                players[target_idx].busted = True
                                players[target_idx].score_current = 0
                                show_message(f"{players[target_idx].name} BUSTED!", ms=900)
                                pygame.time.delay(POST_ACTION_PAUSE_MS)
                                return "bust"
                show_message(f"{players[target_idx].name} resolved FLIP3", ms=MESSAGE_MS//2)
                
                pygame.time.delay(POST_ACTION_PAUSE_MS)

        # Check Flip7 for the target after all cascades
        players[target_idx].compute_current_score()
        if unique_number_count(players[target_idx].hand) >= 7:
            show_message(f"{players[target_idx].name} got FLIP 7!", ms=MESSAGE_MS)
            players[target_idx].score_total += 15 + players[target_idx].score_current
            discard.extend(players[target_idx].hand); players[target_idx].hand = []; players[target_idx].hand_face = []; players[target_idx].stayed = True
            pygame.time.delay(POST_ACTION_PAUSE_MS)
            return "flip7"
        return "ok"

    # NORMAL: add the card face-up
    p.add_card(card_val, face_up=True)

    # Numerical duplicates only cause busts — modifiers and action cards are safe
    if card_val in range(0,13):
        nums = [c for c in p.hand if c in range(0,13)]
        if len(nums) != len(set(nums)):
            if p.has_second:
                # consume second chance and drop duplicate drawn
                p.pop_last()
                p.has_second = False
                p.remove_card_value(21)
                p.compute_current_score()
                return "second_consumed"
            else:
                discard.extend(p.hand)
                p.hand = []
                p.hand_face = []
                p.busted = True
                p.score_current = 0
                show_message(f"{p.name} BUSTED!", ms=900)
                pygame.time.delay(POST_ACTION_PAUSE_MS)
                return "bust"

    # Freeze (19) resolved immediately if drawn outside flip3 context
    if card_val == 19:
        tgt_candidates = active_player_indices(players)
        if player_idx not in tgt_candidates:
            tgt_candidates.append(player_idx)
        if len(tgt_candidates) == 1:
            tgt = tgt_candidates[0]
        else:
            if p.is_bot:
                others = [i for i in tgt_candidates if i != player_idx]
                tgt = random.choice(others) if others else player_idx
            else:
                tgt = choose_target_ui(players, f"{p.name} played FREEZE", allowed_indices=tgt_candidates)
                if tgt is None:
                    # canceled -> discard freeze and remove its visual presence
                    discard.append(19)
                    p.remove_card_value(19)
                    return "ok"
        targ = players[tgt]
        show_message(f"{p.name} used FREEZE -> {targ.name}", ms=MESSAGE_MS//2)
        targ.compute_current_score(); targ.score_total += targ.score_current
        discard.extend(targ.hand); targ.hand = []; targ.hand_face = []; targ.stayed = True
        pygame.time.delay(POST_ACTION_PAUSE_MS)

    # final compute and Flip7 check
    p.compute_current_score()
    if unique_number_count(p.hand) >= 7:
        show_message(f"{p.name} got FLIP 7!", ms=MESSAGE_MS)
        p.score_total += 15 + p.score_current
        discard.extend(p.hand); p.hand = []; p.hand_face = []; p.stayed = True
        pygame.time.delay(POST_ACTION_PAUSE_MS)
        return "flip7"
    return "ok"

# ---------- UI Button helper ----------
class Button:
    def __init__(self, rect, label, callback):
        """ Button constructor that takes in a rectangle, label and a callback"""
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.hover = False
    def draw(self, surf):
        """ Takes in a surface and displays it"""
        col = (180,220,255) if self.hover else (200,200,200)
        pygame.draw.rect(surf, col, self.rect)
        pygame.draw.rect(surf, (0,0,0), self.rect, 2)
        txt = FONT.render(self.label, True, (0,0,0))
        tw, th = txt.get_size()
        surf.blit(txt, (self.rect.x + (self.rect.w - tw)//2, self.rect.y + (self.rect.h - th)//2))
    def handle_event(self, ev):
        """ Takes an event object and determines actions based on type of event """
        if ev.type == MOUSEMOTION:
            self.hover = self.rect.collidepoint(ev.pos)
        if ev.type == MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.callback()

# ---------- Bot simple heuristic ----------
def bot_should_hit(p: Player):
    """ Takes in a player and returns True if the bot should hit or False if bot should not heat"""
    num_sum = sum(c for c in p.hand if c in range(0,13))
    ucount = unique_number_count(p.hand)
    if ucount >= 6:
        return False
    return num_sum < p.bot_aggr

# ---------- Winner announce ----------
def announce_winner(player):
    """ Takes in a player and displays text to announce them as the winner"""
    screen.fill((200,255,200))
    screen.blit(BIG.render(f"{player.name} wins with {player.score_total} points!", True, (10,10,10)), (80, 320))
    pygame.display.update()
    pygame.time.delay(3000)

# ---------- Setup GUI (combined start/setup) ----------
players_global = []
def setup_players_gui():
    """ minimal in-app GUI using pygame_gui; allows add human/bot/clear/start"""
    running = True
    input_text = ""
    input_rect = pygame.Rect((50,200,400,50))
    x,y = WINDOW_WIDTH-420, 120
    btn_w = BUTTON_W * 3/2
    return_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((WINDOW_WIDTH-200,20),(BUTTON_W,BUTTON_H)), text="Return", manager=GUI_MANAGER)
    add_human_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x,y),(btn_w,BUTTON_H)), text="Add Human", manager=GUI_MANAGER)
    add_bot_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x,y+BUTTON_H+20),(btn_w,BUTTON_H)), text="Add Bot", manager=GUI_MANAGER)
    clear_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x,y+(BUTTON_H+20)*2),(btn_w,BUTTON_H)), text="Clear", manager=GUI_MANAGER)
    start_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x,y+(BUTTON_H+20)*3),(btn_w,BUTTON_H)), text="Start Game", manager=GUI_MANAGER)
    ui_e = [return_btn, add_human_btn, add_bot_btn, clear_btn, start_btn]

    while running:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); sys.exit()
            GUI_MANAGER.process_events(ev)
            if ev.type == pygame_gui.UI_BUTTON_PRESSED:
                if ev.ui_element == add_human_btn:
                    if input_text.strip():
                        players_global.append(Player(input_text.strip(), is_bot=False))
                        input_text = ""
                    else:
                        players_global.append(Player(f"Player {len(players_global)+1}", is_bot=False))
                if ev.ui_element == add_bot_btn:
                    botname = f"Bot_{len([b for b in players_global if b.is_bot])+1}"
                    players_global.append(Player(botname, is_bot=True))
                if ev.ui_element == clear_btn:
                    players_global.clear()
                if ev.ui_element == start_btn:
                    if players_global:
                        for e in ui_e:
                            e.kill()
                        GUI_MANAGER.update(clock.tick(FPS))
                        GUI_MANAGER.draw_ui(screen)
                        screen.fill((255,255,255))
                        pygame.display.update()
                        play_game_gui()
                        return
                if ev.ui_element == return_btn:
                    for e in ui_e:
                        e.kill()
                    GUI_MANAGER.update(clock.tick(FPS))
                    GUI_MANAGER.draw_ui(screen)
                    screen.fill((255,255,255))
                    pygame.display.update()
                    running = False
            elif ev.type == KEYDOWN:
                if ev.key == K_BACKSPACE:
                    input_text = input_text[:-1]
                elif ev.key == K_RETURN:
                    if input_text.strip():
                        players_global.append(Player(input_text.strip(), is_bot=False))
                        input_text = ""
                else:
                    if len(input_text) < 18:
                        input_text += ev.unicode

        screen.fill((225,225,225))
        draw_header("Setup Players")
        pygame.draw.rect(screen,(255,255,255),input_rect,border_radius=6)
        pygame.draw.rect(screen,(0,0,0),input_rect,2,border_radius=6)
        screen.blit(FONT.render(input_text, True, (10,10,10)), (60,210))
        draw_sub = SMALL.render("Type player name and press 'Add Human' or Enter", True, (10,10,10))
        screen.blit(draw_sub, (50,170))
        yy = 300
        for i, p in enumerate(players_global):
            lab = f"{i+1}. {p.name} {'(BOT)' if p.is_bot else '(HUMAN)'}"
            screen.blit(FONT.render(lab, True, (0,0,0)), (50, yy))
            yy += 32

        time_delta = clock.tick(FPS)
        GUI_MANAGER.update(time_delta)
        GUI_MANAGER.draw_ui(screen)
        pygame.display.update()

# small helper for header rendering reused in rules
def draw_subtitle(text):
    """ Takes in a text and displays a small subtitle"""
    sub = SMALL.render(text, True, (0,0,0))
    screen.blit(sub, (18, 90))

# ---------- Main gameplay (uses combined GUI and fixed behaviors) ----------
def play_game_gui():
    """" Displays the playing GUIs"""
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

    # UI buttons (simple on-screen)
    hit_btn = Button((280, 640, 220, 60), "Hit (H)", lambda: action_press("hit"))
    stay_btn = Button((520, 640, 220, 60), "Stay (S)", lambda: action_press("stay"))
    return_btn_ui = Button((WINDOW_WIDTH-200, 20, BUTTON_W, BUTTON_H), "Return", lambda: action_press("return"))
    tooltip = ""
    action_queue = []
    def action_press(kind):
        """ Takes in a kind of action and adds it to the action queue"""
        action_queue.append(kind)

    running = True
    while running:
        # new round reset per player
        for p in players:
            p.reset_for_round()

        # initial dealing (one each)
        order = [(dealer_idx + i) % n for i in range(n)]
        for idx in order:
            ensure_deck_has_cards(deck, discard)
            if not deck: break
            drawn = deck.pop()
            current_global_players[0] = players
            current_global_players[1] = -1
            current_global_players[2] = None
            current_global_deck[0] = deck
            current_global_discard[0] = discard
            target_slot = len(players[idx].hand)
            animate_card_move(drawn, idx, target_slot, DEAL_ANIM_MS)
            # resolve (face-up card appended inside resolve_draw where appropriate)
            resolve_draw(idx, drawn, players, deck, discard, idx)
            pygame.time.delay(60)

        current_idx = (dealer_idx + 1) % n
        round_should_end = False

        while True:
            ensure_deck_has_cards(deck, discard)
            if all(p.busted or p.stayed for p in players):
                break
            if round_should_end:
                break

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
            draw_players(players, current_idx, None)
            draw_deck_info(deck, discard)
            # draw final info on top (after deck)
            draw_final_info_box(final_info)
            # draw buttons
            hit_btn.draw(screen); stay_btn.draw(screen); return_btn_ui.draw(screen)
            # tooltip (auto-size to text)
            if hit_btn.hover:
                tooltip = "Draw a card (keyboard H). If duplicate number -> bust unless you have Second Chance."
            elif stay_btn.hover:
                tooltip = "Bank your current points and end your turn (keyboard S)."
            else:
                tooltip = ""
            if tooltip:
                txt_surf = SMALL.render(tooltip, True, (0,0,0))
                tw, th = txt_surf.get_size()
                padding = 8
                tbox = pygame.Rect(280, 600, tw + padding*2, th + padding)
                pygame.draw.rect(screen, (255,255,220), tbox)
                pygame.draw.rect(screen, (0,0,0), tbox, 1)
                screen.blit(txt_surf, (tbox.x + padding, tbox.y + (padding//2)))

            # set globals for animations
            current_global_players[0] = players
            current_global_players[1] = current_idx
            current_global_players[2] = final_info
            current_global_deck[0] = deck
            current_global_discard[0] = discard

            pygame.display.update()

            # BOT behavior: bots auto-act
            if players[current_idx].is_bot:
                bot = players[current_idx]
                pygame.time.delay(BOT_ACTION_DELAY_MS)

                # Return pressed anytime → exit to menu
                ev = pygame.event.wait()
                if ev.type == MOUSEBUTTONDOWN and return_btn_ui.rect.collidepoint(ev.pos):
                    return
            
                if bot.busted or bot.stayed:
                    pass
                else:
                    if bot_should_hit(bot):
                        ensure_deck_has_cards(deck, discard)
                        if deck:
                            drawn = deck.pop()
                            animate_card_move(drawn, current_idx, len(bot.hand), HIT_ANIM_MS)
                            res = resolve_draw(current_idx, drawn, players, deck, discard, current_idx)
                            # resolve_draw will show messages (bust/flip7) as needed
                    else:
                        bot.compute_current_score()
                        bot.score_total += bot.score_current
                        discard.extend(bot.hand); bot.hand = []; bot.hand_face = []; bot.stayed = True
                        if bot.score_total >= 200 and not final_trigger:
                            final_trigger = True; triggerer_idx = current_idx
                            final_players_list = [i for i in range(n) if i != triggerer_idx]
                            round_should_end = True
                # advance
                nxt = next_active_index(players, current_idx)
                if nxt is None: break
                current_idx = nxt
                clock.tick(FPS)
                continue

            # HUMAN player: wait for keyboard or click
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
            # button hover/click
            hit_btn.handle_event(ev)
            stay_btn.handle_event(ev)
            return_btn_ui.handle_event(ev)
            if ev.type == MOUSEBUTTONDOWN:
                if return_btn_ui.rect.collidepoint(ev.pos):
                    return  # go back to main menu

            # Handle queued actions simply: hits and stays. FLIP3 is now automatic inside resolve_draw.
            if action_queue:
                act = action_queue.pop(0)
                if act == "hit":
                    ensure_deck_has_cards(deck, discard)
                    if deck:
                        drawn = deck.pop()
                        animate_card_move(drawn, current_idx, len(players[current_idx].hand), HIT_ANIM_MS)
                        res = resolve_draw(current_idx, drawn, players, deck, discard, current_idx)
                        if res == "pending_flip3":
                            # old state removed; this should not happen now
                            pass
                        else:
                            if players[current_idx].score_total >= 200 and not final_trigger:
                                final_trigger = True; triggerer_idx = current_idx
                                final_players_list = [i for i in range(n) if i != triggerer_idx]
                                round_should_end = True
                            if players[current_idx].busted or players[current_idx].stayed:
                                nxt = next_active_index(players, current_idx)
                                if nxt is None: break
                                current_idx = nxt
                            else:
                                nxt = next_active_index(players, current_idx)
                                if nxt is None: break
                                current_idx = nxt

                elif act == "stay":
                    pcur = players[current_idx]
                    pcur.compute_current_score()
                    pcur.score_total += pcur.score_current
                    discard.extend(pcur.hand); pcur.hand = []; pcur.hand_face = []; pcur.stayed = True
                    if pcur.score_total >= 200 and not final_trigger:
                        final_trigger = True; triggerer_idx = current_idx
                        final_players_list = [i for i in range(n) if i != triggerer_idx]
                        round_should_end = True
                    nxt = next_active_index(players, current_idx)
                    if nxt is None: break
                    current_idx = nxt

            clock.tick(FPS)

        # end of round handling (final trigger / rotate dealer)
        if not final_trigger:
            dealer_idx = (dealer_idx + 1) % n
            ensure_deck_has_cards(deck, discard)
            continue
        else:
            if not final_players_list:
                announce_winner(players[triggerer_idx]); return
            # final extra turns for each player (other than triggerer)
            for idx in final_players_list:
                if idx == triggerer_idx: continue
                players[idx].reset_for_round()
                ensure_deck_has_cards(deck, discard)
                if deck:
                    drawn = deck.pop()
                    animate_card_move(drawn, idx, len(players[idx].hand), DEAL_ANIM_MS)
                    resolve_draw(idx, drawn, players, deck, discard, idx)
                while not (players[idx].busted or players[idx].stayed):
                    draw_header("Final Round — Extra Turn")
                    draw_players(players, idx, None)
                    draw_deck_info(deck, discard)
                    draw_final_info_box(f"Triggerer: {players[triggerer_idx].name}")
                    hit_btn.draw(screen)
                    stay_btn.draw(screen)
                    pygame.display.update()
                    if players[idx].is_bot:
                        pygame.time.delay(BOT_ACTION_DELAY_MS)
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
                            # HUMAN player: wait for keyboard or click
                            if ev.key == K_q:
                                return
                            if ev.key == K_h:
                                action_queue.append("hit")
                            if ev.key == K_s:
                                action_queue.append("stay")
                            # button hover/click
                            hit_btn.handle_event(ev)
                            stay_btn.handle_event(ev)
                            # if ev.key == K_h:
                            #     ensure_deck_has_cards(deck, discard)
                            #     if deck:
                            #         d = deck.pop()
                            #         animate_card_move(d, idx, len(players[idx].hand), HIT_ANIM_MS)
                            #         resolve_draw(idx, d, players, deck, discard, idx)
                            # if ev.key == K_s:
                            #     players[idx].compute_current_score()
                            #     players[idx].score_total += players[idx].score_current
                            #     discard.extend(players[idx].hand); players[idx].hand = []; players[idx].hand_face = []; players[idx].stayed = True
                    clock.tick(FPS)

            # determine winner (or continue on tie)
            top = max(p.score_total for p in players)
            winners = [p for p in players if p.score_total == top]
            if len(winners) == 1:
                announce_winner(winners[0]); return
            else:
                final_trigger = False
                triggerer_idx = None
                final_players_list = []
                dealer_idx = (dealer_idx + 1) % n
                ensure_deck_has_cards(deck, discard)
                continue

# ---------- Rules screen ----------
def show_rules():
    " Show the rules GUI"
    showing = True
    return_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((WINDOW_WIDTH-200,20),(BUTTON_W,BUTTON_H)), text="Return", manager=GUI_MANAGER)
    while showing:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame_gui.UI_BUTTON_PRESSED and ev.ui_element == return_btn:
                return_btn.kill(); GUI_MANAGER.update(clock.tick(FPS)); GUI_MANAGER.draw_ui(screen); showing = False
            GUI_MANAGER.process_events(ev)
        screen.fill((255,255,255))
        draw_header("Flip 7 Rules")
        draw_subtitle("H = Hit (keyboard)  S = Stay (keyboard)  Q = Quit to Menu")
        lines = [
            "Deck: 1x0, 1x1, 2x2, 3x3 ... 12x12.",
            "Modifiers: +2, +4, +6, +8, +10 and X2 (one each).",
            "Actions: Flip Three, Freeze, Second Chance (3 each).",
            "",
            "> On your turn: Hit to draw or Stay to bank your points.",
            "> If you draw a duplicate number card you bust (score 0)",
            "  unless you have Second Chance.",
            "",
            "> [Flip 7] 7 unique number cards ends the round and gives +15 bonus",
            "  (you bank points).",
            "> [Flip3] draw next 3 cards immediately (can cascade).",
            "> [Freeze] choose a target player to force them to Stay and",
            "  they bank their current points.",
            "> [Second Chance] keep until it prevents one bust and is consumed.",
            "",
            "Scoring: (sum numbers) * X2(if present) + modifiers.",
            "> First to reach >=200 triggers final round and",
            "  each other player gets one final turn."
        ]
        x,y = 50, 160
        for l in lines:
            screen.blit(SMALL.render(l, True, (0,0,0)), (x, y)); y+=26
        time_delta = clock.tick(FPS)
        GUI_MANAGER.update(time_delta)
        GUI_MANAGER.draw_ui(screen)
        pygame.display.update()

# ---------- Main menu ----------
def start_menu():
    """ Initialize the start of the game menu"""
    menu = pygame_menu.Menu("Flip 7", WINDOW_WIDTH, WINDOW_HEIGHT, theme=pygame_menu.themes.THEME_BLUE)
    # combined Start / Setup: Setup opens the in-app setup which then starts game
    menu.add.button("Rules", show_rules)
    menu.add.button("Setup / Start", setup_players_gui)
    menu.add.button("Quit", pygame_menu.events.EXIT)
    menu.mainloop(screen)

if __name__ == "__main__":
    start_menu()
