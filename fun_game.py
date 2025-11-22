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
import pygame
import pygame_menu
from pygame.locals import*
import sys 

pygame.init()

WINDOW_HEIGHT = 800
WINDOW_WIDTH = 1000

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

DISPLAYSURF = pygame.display.set_mode((WINDOW_WIDTH,WINDOW_HEIGHT))
pygame.display.set_caption("The Gambler's Flip 7")

# RULES
def display_rules():
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