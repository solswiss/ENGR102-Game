import pygame, sys, random, pygame_menu
import pygame_gui
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
BUTTON_W = 140
BUTTON_H = 60
BOT_HIT_THRESHOLD = 16   # lower -> more conservative bots; higher -> more aggressive
# ----------------------------

pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Flip 7 — Full (Bots + Mouse UI + Video Cards)")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont("ComicSans", 32)
BIG = pygame.font.SysFont("ComicSans", 64)
SMALL = pygame.font.SysFont("ComicSans", 24)

# GUI
GUI_MANAGER = pygame_gui.UIManager((WINDOW_WIDTH, WINDOW_HEIGHT), theme_path="gui.json")

# Card constants
MODIFIER_MAP = {13: 2, 14: 4, 15: 6, 16: 8, 17: 10}
LABEL_MAP = {18: "X2", 19: "FREEZE", 20: "FLIP3", 21: "SECOND"}

# ---------- Image loading (cached) ----------
IMAGE_CACHE = {}
def load_card_image(val):
    p = ""
    if val in range(0, 13):
        p = f"{ASSET_FOLDER}/cardnum{val}.png"
    elif val in MODIFIER_MAP:
        p = f"{ASSET_FOLDER}/plus{(val-12)*2}.png"
    else:
        name_map = {18: "times2", 19: "freeze", 20: "flipthree", 21: "secondchance"}
        base = name_map.get(val, f"card_{val}")
        p = f"{ASSET_FOLDER}/{base}.png"
    try:
        img = pygame.image.load(p).convert_alpha()
        img = pygame.transform.smoothscale(img, (CARD_W, CARD_H))
        return img
    except Exception:
        pass

    # fallback render
    surf = pygame.Surface((CARD_W, CARD_H))
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

# ---------- Deck builder ----------
def make_deck():
    deck = []
    deck.extend([0]*1)
    for v in range(1, 13):
        deck.extend([v]*v)
    # modifiers + X2 (ensure X2 included)
    for v in range(13, 18):
        deck.append(v)
    if 18 not in deck:
        deck.append(18)
    # actions: 3 each
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
        self.hand = []
        self.has_second = False
        self.stayed = False
        self.busted = False
        self.score_current = 0
        self.score_total = 0

    def reset_for_round(self):
        self.hand = []
        self.has_second = False
        self.stayed = False
        self.busted = False
        self.score_current = 0

    def compute_current_score(self):
        num_sum = sum(c for c in self.hand if c in range(0,13))
        mul = 2 if 18 in self.hand else 1
        mod_sum = sum(MODIFIER_MAP[c] for c in self.hand if c in MODIFIER_MAP)
        self.score_current = num_sum * mul + mod_sum
        return self.score_current

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

# ---------- Target selection overlay ----------
def choose_target_ui(players, prompt_text, allow_self=True):
    selecting = True
    selected = None
    overlay = pygame.Rect(120, 120, WINDOW_WIDTH - 240, WINDOW_HEIGHT - 240)
    while selecting:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); sys.exit()
            if ev.type == MOUSEBUTTONDOWN and ev.button == 1:
                mx,my = ev.pos
                base_y = overlay.y + 60
                for i, p in enumerate(players):
                    if p.busted or p.stayed:
                        continue
                    if not allow_self and i == current_target_excluding_index[0]:
                        continue
                    row = pygame.Rect(overlay.x + 40, base_y + i*44, overlay.width - 80, 38)
                    if row.collidepoint(mx,my):
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
        row_i = 0
        for i, p in enumerate(players):
            # show all players but mark busted/stayed
            status = " (BUSTED)" if p.busted else (" (STAYED)" if p.stayed else "")
            lab = f"{i+1}. {p.name}{status}"
            rect = pygame.Rect(overlay.x + 40, base_y + row_i*44, overlay.width - 80, 38)
            pygame.draw.rect(screen, (220,220,220), rect)
            pygame.draw.rect(screen, (0,0,0), rect, 1)
            screen.blit(FONT.render(lab, True, (0,0,0)), (rect.x + 8, rect.y + 8))
            row_i += 1
        pygame.display.update()
        clock.tick(FPS)
    return selected

# We use a global container to pass the "exclude self" index into choose_target_ui easily when needed
current_target_excluding_index = [None]

# ---------- Resolve drawn card logic (core mechanics) ----------
def resolve_draw(player_idx, card_val, players, deck, discard, current_idx):
    """Return result codes: 'ok','bust','flip7'"""
    p = players[player_idx]

    # second chance
    if card_val == 21:
        if p.has_second:
            # if already has one, ask target to give to (humans); bots auto give to self's teammate logic (here random active)
            if p.is_bot:
                # pick random other active player
                choices = [i for i,pp in enumerate(players) if not pp.busted and not pp.stayed]
                if choices:
                    tgt = random.choice(choices)
                    players[tgt].has_second = True
            else:
                # choose target
                current_target_excluding_index[0] = None
                tgt = choose_target_ui(players, f"{p.name} drew SECOND — choose target to give it to")
                if tgt is not None:
                    players[tgt].has_second = True
        else:
            p.has_second = True
        p.hand.append(21)
        p.compute_current_score()
        return "ok"

    # Flip Three 20
    if card_val == 20:
        p.hand.append(20)
        # the player who receives flip3 must accept next 3 cards, flipping them one at a time
        # they could bust during these flips
        for _ in range(3):
            ensure_deck_has_cards(deck, discard)
            if not deck:
                break
            drawn = deck.pop()
            p.hand.append(drawn)
            if drawn in range(0,13):
                nums = [c for c in p.hand if c in range(0,13)]
                if len(nums) != len(set(nums)):
                    if p.has_second:
                        p.hand.pop()
                        p.has_second = False
                        if 21 in p.hand:
                            try: p.hand.remove(21)
                            except: pass
                        p.compute_current_score()
                        continue
                    else:
                        discard.extend(p.hand)
                        p.hand = []
                        p.busted = True
                        p.score_current = 0
                        return "bust"
            # If drawn is another action (19 or 20) or second chance, we keep and process later per rules
        # After the 3 flips, process any Flip3/Freeze in hand in order (simple approach)
        action_cards = [c for c in p.hand if c in (19,20)]
        for a in action_cards:
            if p.busted:
                break
            p.hand.remove(a)
            if a == 19:
                # pick target
                if p.is_bot:
                    targets = [i for i,pp in enumerate(players) if not pp.busted and not pp.stayed and i!=player_idx]
                    if targets:
                        tgt = random.choice(targets)
                        targ = players[tgt]
                        targ.compute_current_score()
                        targ.score_total += targ.score_current
                        discard.extend(targ.hand); targ.hand = []; targ.stayed = True
                else:
                    current_target_excluding_index[0] = player_idx
                    tgt = choose_target_ui(players, f"{p.name} played FREEZE — choose a target to force to Stay")
                    if tgt is not None:
                        targ = players[tgt]
                        targ.compute_current_score()
                        targ.score_total += targ.score_current
                        discard.extend(targ.hand); targ.hand = []; targ.stayed = True
            elif a == 20:
                # cascade another 3 draws (handled similarly)
                for _ in range(3):
                    ensure_deck_has_cards(deck, discard)
                    if not deck: break
                    drawn2 = deck.pop()
                    p.hand.append(drawn2)
                    if drawn2 in range(0,13):
                        nums = [c for c in p.hand if c in range(0,13)]
                        if len(nums) != len(set(nums)):
                            if p.has_second:
                                p.hand.pop()
                                p.has_second = False
                                if 21 in p.hand:
                                    try: p.hand.remove(21)
                                    except: pass
                            else:
                                discard.extend(p.hand); p.hand = []; p.busted = True; p.score_current = 0
                                return "bust"
        # compute and check flip7
        p.compute_current_score()
        if unique_number_count(p.hand) >= 7:
            p.score_total += 15 + p.score_current
            discard.extend(p.hand); p.hand = []; p.stayed = True
            return "flip7"
        return "ok"

    # Freeze or number/mod/double normal draws
    p.hand.append(card_val)
    if card_val in range(0,13):
        nums = [c for c in p.hand if c in range(0,13)]
        if len(nums) != len(set(nums)):
            if p.has_second:
                p.hand.pop()
                p.has_second = False
                if 21 in p.hand:
                    try: p.hand.remove(21)
                    except: pass
                p.compute_current_score()
                return "second_consumed"
            else:
                discard.extend(p.hand); p.hand = []; p.busted = True; p.score_current = 0
                return "bust"
    # If freeze drawn during non-flip3 context, we treat it as a card in hand but require immediate resolution
    if card_val == 19:
        # freeze: choose target to force to stay
        if p.is_bot:
            targets = [i for i,pp in enumerate(players) if not pp.busted and not pp.stayed and i!=player_idx]
            if targets:
                tgt = random.choice(targets)
                targ = players[tgt]
                targ.compute_current_score(); targ.score_total += targ.score_current
                discard.extend(targ.hand); targ.hand = []; targ.stayed = True
        else:
            current_target_excluding_index[0] = player_idx
            tgt = choose_target_ui(players, f"{p.name} played FREEZE — choose a target to force to Stay")
            if tgt is not None:
                targ = players[tgt]
                targ.compute_current_score(); targ.score_total += targ.score_current
                discard.extend(targ.hand); targ.hand = []; targ.stayed = True
    p.compute_current_score()
    if unique_number_count(p.hand) >= 7:
        p.score_total += 15 + p.score_current
        discard.extend(p.hand); p.hand = []; p.stayed = True
        return "flip7"
    return "ok"

# ---------- UI: buttons and drawing ----------
def draw_header(title):
    x,y = 50,20
    screen.blit(BIG.render(title, True, (0,0,0)), (x, y))
def draw_subtitle(title):
    x,y = 50,20
    screen.blit(FONT.render(title, True, (0,0,0)), (x,y+100))

def draw_players(players, current_idx, final_info=None):
    y = ROWS_TOP
    for i, p in enumerate(players):
        status = ""
        if p.busted: status = " (BUSTED)"
        if p.stayed: status = " (STAYED)"
        cursor = " <--" if i==current_idx and not p.busted and not p.stayed else ""
        label = f"{i+1}. {p.name}  Tot:{p.score_total}  Curr:{p.score_current}{status}{cursor}"
        screen.blit(FONT.render(label, True, (0,0,0)), (18, y-26))
        x = 18
        for c in p.hand:
            screen.blit(get_card_image(c), (x, y))
            x += CARD_W + CARD_GAP
        y += CARD_H + 34
    if final_info:
        # show final round info box top-right
        box = pygame.Rect(760, 90, 400, 120)
        pygame.draw.rect(screen, (230,230,255), box)
        pygame.draw.rect(screen, (0,0,0), box, 2)
        screen.blit(FONT.render("FINAL ROUND INFO", True, (0,0,0)), (box.x + 12, box.y + 8))
        screen.blit(FONT.render(final_info, True, (0,0,0)), (box.x + 12, box.y + 38))

def draw_deck_info(deck, discard):
    screen.blit(FONT.render(f"Deck: {len(deck)}   Discard: {len(discard)}", True, (0,0,0)), (820, 58))

# Button helper
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
    # - If player has duplicate risk (many unique numbers near 7), play safer.
    # - Basic rule: hit if current numeric sum < bot_aggr and unique numbers < 7
    num_sum = sum(c for c in p.hand if c in range(0,13))
    ucount = unique_number_count(p.hand)
    # If A LOT of unique numbers but not yet 7, be cautious:
    if ucount >= 6:
        return False
    # else hit if below threshold
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
    # we will present a minimal in-app GUI: list current players and buttons to add human or bot or clear
    running = True
    input_text = ""
    # input box
    input_rect = pygame.Rect((50,200,400,50))
    # BUTTONS
    x,y = WINDOW_WIDTH-280, 120
    btn_w = BUTTON_W * 3/2
    # return home button
    return_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((WINDOW_WIDTH-200,20),(BUTTON_W,BUTTON_H)), text="Return", manager=GUI_MANAGER)
    # add human button
    add_human_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x,y),(btn_w,BUTTON_H)), text="Add Human", manager=GUI_MANAGER)
    # add bot button
    add_bot_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x,y+BUTTON_H+20),(btn_w,BUTTON_H)), text="Add Bot", manager=GUI_MANAGER)
    # clear all button
    clear_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x,y+(BUTTON_H+20)*2),(btn_w,BUTTON_H)), text="Clear", manager=GUI_MANAGER)

    while running:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); sys.exit()
            
            GUI_MANAGER.process_events(ev)
            if ev.type == pygame_gui.UI_BUTTON_PRESSED:
                # add human button
                if ev.ui_element == add_human_btn:
                    if input_text.strip():
                        players_global.append(Player(input_text.strip(), is_bot=False))
                        input_text = ""
                    else:
                        players_global.append(Player(f"Player {len(players_global)+1}", is_bot=False))
                # add bot button
                if ev.ui_element == add_bot_btn:
                    botname = f"Bot_{len([b for b in players_global if b.is_bot])+1}"
                    players_global.append(Player(botname, is_bot=True))
                # clear
                if ev.ui_element == clear_btn:
                    players_global.clear()
                # start game
                # if 920 <= mx <= 920+160 and 290 <= my <= 290+36:
                #     if players_global:
                #         running = False
                # return
                if ev.ui_element == return_btn:
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
        
        # draw UI
        screen.fill((225,225,225))
        pygame.draw.rect(screen,(255,255,255),input_rect,border_radius=6)
        pygame.draw.rect(screen,(0,0,0),input_rect,2,border_radius=6)
        screen.blit(FONT.render(input_text, True, (10,10,10)), (60,200))
        draw_header("Setup Game")
        draw_subtitle("Type player name and press 'Add Human' or Enter")
        # show current players list
        yy = 300
        for i, p in enumerate(players_global):
            lab = f"{i+1}. {p.name} {'(BOT)' if p.is_bot else '(HUMAN)'}"
            screen.blit(FONT.render(lab, True, (0,0,0)), (40, yy))
            yy += 32
        
        time_delta = clock.tick(FPS)
        GUI_MANAGER.update(time_delta)
        GUI_MANAGER.draw_ui(screen)
        pygame.display.update()

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
        # deal one card to each in order starting with dealer (dealer gets dealt too)
        order = [(dealer_idx + i) % n for i in range(n)]
        for idx in order:
            ensure_deck_has_cards(deck, discard)
            if not deck: break
            drawn = deck.pop()
            resolve_draw(idx, drawn, players, deck, discard, idx)
        current_idx = (dealer_idx + 1) % n

        # round loop
        while True:
            ensure_deck_has_cards(deck, discard)
            # round end check
            if all(p.busted or p.stayed for p in players):
                break

            # skip inactive players
            if players[current_idx].busted or players[current_idx].stayed:
                nxt = next_active_index(players, current_idx)
                if nxt is None: break
                current_idx = nxt
                continue

            # draw UI
            draw_header("Flip 7 — Play")
            draw_subtitle("H = Hit (keyboard)  S = Stay (keyboard)  Q = Quit to Menu")
            # if final_trigger active, show box
            final_info = None
            if final_trigger:
                remaining_names = ", ".join([players[i].name for i in final_players_list if not players[i].stayed and not players[i].busted])
                final_info = f"Triggered by {players[triggerer_idx].name}. Remaining: {remaining_names}"
            draw_players(players, current_idx, final_info)
            draw_deck_info(deck, discard)
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
            event_processed = False
            # If current is bot, have it act with simple AI
            if players[current_idx].is_bot:
                bot = players[current_idx]
                # small delay to make bots feel human
                pygame.time.delay(450)
                if bot.busted or bot.stayed:
                    event_processed = True
                else:
                    if bot_should_hit(bot):
                        # bot hits
                        ensure_deck_has_cards(deck, discard)
                        if deck:
                            drawn = deck.pop()
                            res = resolve_draw(current_idx, drawn, players, deck, discard, current_idx)
                            if res == "flip7":
                                # round ends
                                pass
                    else:
                        # bot stays
                        bot.compute_current_score()
                        bot.score_total += bot.score_current
                        discard.extend(bot.hand); bot.hand = []; bot.stayed = True
                        if bot.score_total >= 200 and not final_trigger:
                            final_trigger = True; triggerer_idx = current_idx
                            final_players_list = [i for i in range(n) if i != triggerer_idx]
                    event_processed = True
                # small break to refresh UI
                clock.tick(FPS)
            else:
                # human: event loop waits for button clicks or keyboard
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
                # pass event to buttons
                hit_btn.handle_event(ev); stay_btn.handle_event(ev)
                # process queued actions if any
                if action_queue:
                    act = action_queue.pop(0)
                    if act == "hit":
                        ensure_deck_has_cards(deck, discard)
                        if deck:
                            drawn = deck.pop()
                            res = resolve_draw(current_idx, drawn, players, deck, discard, current_idx)
                            if res == "flip7":
                                # player already banked in resolve_draw
                                pass
                    elif act == "stay":
                        pcur = players[current_idx]
                        pcur.compute_current_score()
                        pcur.score_total += pcur.score_current
                        discard.extend(pcur.hand); pcur.hand = []; pcur.stayed = True
                        if pcur.score_total >= 200 and not final_trigger:
                            final_trigger = True; triggerer_idx = current_idx
                            final_players_list = [i for i in range(n) if i != triggerer_idx]
                    # continue after action
                event_processed = True

            # after processing, advance to next active
            if players[current_idx].busted or players[current_idx].stayed:
                nxt = next_active_index(players, current_idx)
                if nxt is None:
                    break
                current_idx = nxt
            else:
                # if the player acted and still active (hit and didn't bust) we let them choose again; for bots we re-evaluate quickly
                if players[current_idx].is_bot:
                    # bot acts until it chooses to stay or bust (handled above)
                    nxt = next_active_index(players, current_idx)
                    if nxt is not None:
                        current_idx = nxt
                else:
                    # human remains current until they click stay or hit (we don't auto-advance)
                    pass

            clock.tick(FPS)

        # Round ended: if final_trigger not active, rotate dealer and continue; if final triggered manage final players list
        if not final_trigger:
            dealer_idx = (dealer_idx + 1) % n
            ensure_deck_has_cards(deck, discard)
        else:
            # final extra turns for each player in final_players_list (those other than triggerer)
            if not final_players_list:
                # immediate win for triggerer
                announce_winner(players[triggerer_idx]); return
            # each player in list gets one full personal round: deal one card and let them play until stay/bust
            for idx in final_players_list:
                # skip triggerer if present
                if idx == triggerer_idx:
                    continue
                # reset only that player's round state
                players[idx].reset_for_round()
                ensure_deck_has_cards(deck, discard)
                if deck:
                    drawn = deck.pop()
                    resolve_draw(idx, drawn, players, deck, discard, idx)
                # let this player act until stay/bust
                while not (players[idx].busted or players[idx].stayed):
                    draw_header("Final Round — Extra Turn")
                    draw_subtitle("H = Hit (keyboard)  S = Stay (keyboard)  Q = Quit to Menu")
                    draw_players(players, idx, f"Triggerer: {players[triggerer_idx].name}")
                    draw_deck_info(deck, discard)
                    hit_btn.draw(screen); stay_btn.draw(screen)
                    pygame.display.update()
                    if players[idx].is_bot:
                        pygame.time.delay(450)
                        if bot_should_hit(players[idx]):
                            ensure_deck_has_cards(deck, discard)
                            if deck:
                                d = deck.pop(); resolve_draw(idx, d, players, deck, discard, idx)
                        else:
                            players[idx].compute_current_score()
                            players[idx].score_total += players[idx].score_current
                            discard.extend(players[idx].hand); players[idx].hand = []; players[idx].stayed = True
                    else:
                        ev = pygame.event.wait()
                        if ev.type == QUIT:
                            pygame.quit(); sys.exit()
                        if ev.type == KEYDOWN:
                            if ev.key == K_h:
                                ensure_deck_has_cards(deck, discard)
                                if deck:
                                    d = deck.pop(); resolve_draw(idx, d, players, deck, discard, idx)
                            if ev.key == K_s:
                                players[idx].compute_current_score()
                                players[idx].score_total += players[idx].score_current
                                discard.extend(players[idx].hand); players[idx].hand = []; players[idx].stayed = True
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
                # tie: continue playing new rounds until resolved (reset final trigger)
                final_trigger = False
                triggerer_idx = None
                final_players_list = []
                dealer_idx = (dealer_idx + 1) % n
                ensure_deck_has_cards(deck, discard)

# ---------- Menu ----------
def show_rules():
    showing = True

    # return home button
    return_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((WINDOW_WIDTH-200,20),(BUTTON_W,BUTTON_H)), text="Return", manager=GUI_MANAGER)

    while showing:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame_gui.UI_BUTTON_PRESSED:
                if ev.ui_element == return_btn:
                    showing = False
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
            "> If you draw a duplicate number card you bust (score 0)", "  unless you have Second Chance.",
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
            screen.blit(SMALL.render(l, True, (0,0,0)), (x, y))
            y+=28
        
        time_delta = clock.tick(FPS)
        GUI_MANAGER.update(time_delta)
        GUI_MANAGER.draw_ui(screen)
        pygame.display.update()

def start_menu():
    menu = pygame_menu.Menu("Flip 7", WINDOW_WIDTH, WINDOW_HEIGHT, theme=pygame_menu.themes.THEME_BLUE)
    menu.add.button("Rules", show_rules)
    menu.add.button("Setup", setup_players_gui)
    menu.add.button("Play", lambda: play_game_gui())
    menu.add.button("Quit", pygame_menu.events.EXIT)
    menu.mainloop(screen)

print(screen.get_width())

if __name__ == "__main__":
    start_menu()
