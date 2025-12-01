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
def count_value(deck):
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

def unique_cards(deck):
    """ Takes in a deck list and returns the unique cards"""
    # Find all unique cards
    unique_cards = []
    for card in deck:
        if (card not in unique_cards):
            unique_cards.append(card)
    return unique_cards

def number_cards(deck):
    """ Takes in a deck list and returns only the number cards as a list"""

    number_cards_list = []
    valid_cards = list(range(13))

    for card in deck:
        if (card in valid_cards):
            number_cards_list.append(card)
    return number_cards_list

def valid_flip_7(deck):
    """If the deck has 7 unique number cards, return true"""

    # Find all unique cards
    unique_cards = unique_cards(deck)
    
    # Make sure at least 7 unique cards are number cards
    if (len(number_cards(unique_cards))):
        return True
    return False

def has_second_chance(deck):
    "Takes in a deck list and returns True if there is a second chance card"
    if (21 in deck):
        return True
    else:
        return False
    
def duplicate_number_cards(deck):
    "Takes in a deck list and returns True if there are duplicate number cards, otherwise returns False"

    duplicates = []
    number_cards_list = number_cards(deck)

    # Find duplicates
    for i in range(len(number_cards_list)):
        for j in range(i + 1, len(number_cards_list)):
            if (number_cards_list[i] == number_cards_list[j]) and (number_cards_list[i] not in duplicates):
                duplicates.append(number_cards_list[i])

    # If duplicates return True, otherwise return False
    if (len(duplicates) > 0):
        return True
    else:
        return False
    
def shuffle(deck):
    "Shuffles the deck"
    random.shuffle(deck)

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
class Player:
    def __init__(self, name, id):
        self.name = name
        self.id = id
        self.player_deck = []
        self.score_total = 0
        self.score_current = 0
        self.turn = False
        self.round = False

    def start_round(self):
        "Start the round for player"
        self.round = True

    def end_round(self):
        "Emds the rpund for player"
        self.round = False

    def start_turn(self):
        """ Start player turn"""
        self.turn = True

    def end_turn(self):
        """ Ends player turn"""
        self.turn = False

    def hit(self): 
        """ Adds a random card from the deck to the player's deck"""
        new_card = DECK.pop(random.randrange(len(DECK)))
        self.player_deck.append(new_card) 

        # Bust if duplicate number cards unless player has second chance card
        if (duplicate_number_cards(self.player_deck)):
            if (has_second_chance(self.player_deck)):
                self.second_chance()
            else:
                self.bust()

        # Flip 7 if 7 unique number cards
        if (valid_flip_7(self.player_deck)):
            self.flip_7()

        self.score()

    def bust(self):
        " Player turn ends when getting duplicate number cards"
        self.score_current = 0
        self.end_turn()
        self.end_round()
        
    def stay(self):
        """ Compute the Player's current score and ends their turn"""
        self.score_total += self.score_current
        self.end_turn()
        self.end_round()
    
    def flip_7(self):
        """If the deck has 7 unique number cards, player gains 15 points bonus and game ends"""
        self.score_total += 15
        self.stay()

    def score(self):
        """ Compute the Player's current score with current deck"""
        # Get number card, 
        number_cards, modifer_cards, multipler = count_value(self.player_deck)
        
        # Score = Number Cards * Multipler +  Modifier Cards
        self.score_current = number_cards * multipler + modifer_cards

    def freeze(self):
        "The player banks all the points they have collected and is out of the round."
        self.stay()

    def flip_3(self):
        """The player who receives this card must accept the next three cards, flipping them one at a time."""
        for i in range(3):
            self.hit()

    def second_chance(self):
        "If the player with this card is given another card with the same number, discard Second Chance and the duplicate number card"
        self.player_deck.pop() # Remove most recent card
        self.player_deck.remove(21) # Remove second chance card
        

# Create Screen
DISPLAYSURF = pygame.display.set_mode((WINDOW_WIDTH,WINDOW_HEIGHT))
pygame.display.set_caption("The Gambler's Flip 7")

# RULES
def display_rules(): # FIXME Maybe take in a text file, which contains the rules, to print out rules
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
# print(len(DECK),":")
# for i in DECK:
#     print(i.value,end=", ")


# Create Players
players = []

# Ensures the number of players is a valid integer
while True:
    try:
        num_players = int(input("Enter the number of players: ")) 
        break
    except ValueError:
        print("Please enter a valid number")

for i in range (num_players):
    player_name = input(f"Enter name of Player {i+1}: ")
    id = i + 1
    new_player = Player(player_name, id)
    players.append(new_player) 

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