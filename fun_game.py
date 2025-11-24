# By submitting this assignment, I agree to the following:
#   "Aggies do not lie, cheat, or steal, or tolerate those who do."
#   "I have not given or received any unauthorized aid on this assignment."
#
# Names:        Kennady Bunn
#               Milo Sun
#               Ruth Ellen Bowling
#               Andrew Justin
# Section:      511
# Assignment:   Lab 13 - 1 (TEAM)
# Date:         21 November 2025

from enum import Enum
import pygame, sys
import pygame_menu
from pygame.locals import*
import random, time

# Initializing
pygame.init()

# Window Size
WINDOW_HEIGHT = 800
WINDOW_WIDTH = 1000

# Setting up FPS
FPS = 60
FramesPerSec = pygame.time.Clock()

# Functions
def countValue(deck):
    """ Given a deck, returns the value of number cards (int), modifier cards (int), and multipler (1 or 2) in that order.
    If not value exist return 0 for int and False for booleans"""

    number_card = 0
    score_modifier = 0
    multiplier = 1

    # Corresponding Card type value to actual score modifier value
    score_modifier_dict = {13: 2, 
                           14: 4, 
                           15: 6, 
                           16: 8, 
                           17: 10}
    for card in deck:
        if (card in range(13)): # 0 to 12 card type correspond ot number cards
            number_card +=card
        elif(card in range(13, 18)): # 13 to 17 card type correspond to score modifiers
            for key, value in score_modifier_dict.items(): 
                if (card == key):
                    score_modifier += value
        elif(card == 18): # 18 card type correspond to double multipler
            multiplier = 2
    return number_card, score_modifier, multiplier
    
class CardType(Enum):
    ZERO = 0
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    ELEVEN = 11
    TWELVE = 12
    MOD_2 = 13
    MOD_4 = 14
    MOD_6 = 15
    MOD_8 = 16
    MOD_10 = 17
    DOUBLE = 18
    FREEZE = 19
    FLIP = 20
    CHANCE = 21


# Cards
class Card(pygame.sprite.Sprite):
    value = 0

    def __init__(self, type):
        super().__init__()
        self.value = type
        self.image = pygame.image.load("4d.png")
        self.rect = self.image.get_rect()
        self.rect.center = (20,20)
    
    def draw(self, surface):
        surface.blit(self.image, self.rect)

# Player
class Player(pygame.sprite.Sprite):
    player_deck = []
    score_total = 0
    score_current = 0

    def hit(): 
        """ Adds a random card from the deck to the player's deck"""
        Player.player_deck.append(DECK.pop(DECK[random.randrange(len(DECK))])) 

        Player.score()
        Player.flip_7()

    def score():
        """ Compute the Player's current score with current deck"""
        # Get number card, 
        number_cards, modifer_cards, multipler = countValue(Player.player_deck)
        
        # Score = Number Cards * Multipler +  Modifier Cards
        Player.score_current = number_cards * multipler + modifer_cards
        
    def stay():
        """ Compute the Player's current score"""
        Player.score_total += Player.score_current
    
    # def flip_7():
    #     """If the deck has 7 unique number cards, a player gains 15 points bonus and the round ends"""
        
    #     # Find all unique cards
    #     unique_cards = []
    #     for card in Player.player_deck:
    #         if (card not in unique_cards):
    #             unique_cards.append(card)
        
    #     # Make sure unique cards are number cards
    #     valid_cards = list(range(13))

    def freeze():
        pass
    def flip_3():
        pass
    def second_chance():
        pass

# Create Screen
DISPLAYSURF = pygame.display.set_mode((WINDOW_WIDTH,WINDOW_HEIGHT))
pygame.display.set_caption("The Gambler's Flip 7")

# RULES
def display_rules():
    """Displays Rules"""
    print("Display rules")
    pass


# SETUP
# create the deck
DECK = [Card(0)]
for i in range(13): # numbers
    for j in range(i):
        DECK.append(Card(i))
for i in range(13,19): # mods
    DECK.append(Card(i))
for i in range(19,22): # actions
    for j in range(3):
        DECK.append(Card(i))
print(len(DECK),":")
for i in DECK:
    print(i.value,end=", ")


# PLAY
def play():
    print("Play")

    Card1 = Card(0)

    # game loop begins
    while True:

        # Allows user to quit game
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
        # update variables

        # draw (after update)
        DISPLAYSURF.fill((255,255,255))
        Card1.draw(DISPLAYSURF)

        # Responsible for updating your game window with any changes that have been made within that specific iteration of the game loop. 
        pygame.display.update()


# MENU
menu = pygame_menu.Menu("Flip 7", WINDOW_WIDTH, WINDOW_HEIGHT, theme=pygame_menu.themes.THEME_BLUE)
menu.add.button("Rules", display_rules)
menu.add.button("Play", play)
menu.add.button("Quit", pygame_menu.events.EXIT)

menu.mainloop(DISPLAYSURF)