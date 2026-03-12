"""Pixel width estimation for SERP display width calculation.

Uses a pre-computed Arial character-width lookup table at approximate Google
SERP font sizes. No PIL/font rendering required.

Google uses ~20px Roboto for desktop title display (≈580px limit)
and ~14px for description (≈920px limit). We approximate with Arial widths.
"""

# Arial character widths at ~13px (used for title SERP width estimation).
# Measured from actual font metrics. Keys are ord(char), values are pixel widths.
# Characters not in the table default to the average width.
_ARIAL_13PX: dict[int, float] = {
    # Space and punctuation
    32: 3.6,  # space
    33: 3.6,  # !
    34: 4.6,  # "
    35: 7.2,  # #
    36: 7.2,  # $
    37: 11.5,  # %
    38: 8.6,  # &
    39: 2.5,  # '
    40: 4.3,  # (
    41: 4.3,  # )
    42: 5.0,  # *
    43: 7.6,  # +
    44: 3.6,  # ,
    45: 4.3,  # -
    46: 3.6,  # .
    47: 3.6,  # /
    # Digits
    48: 7.2,  # 0
    49: 7.2,  # 1
    50: 7.2,  # 2
    51: 7.2,  # 3
    52: 7.2,  # 4
    53: 7.2,  # 5
    54: 7.2,  # 6
    55: 7.2,  # 7
    56: 7.2,  # 8
    57: 7.2,  # 9
    # Punctuation continued
    58: 3.6,  # :
    59: 3.6,  # ;
    60: 7.6,  # <
    61: 7.6,  # =
    62: 7.6,  # >
    63: 7.2,  # ?
    64: 13.1,  # @
    # Uppercase
    65: 8.6,  # A
    66: 8.6,  # B
    67: 9.3,  # C
    68: 9.3,  # D
    69: 8.6,  # E
    70: 7.9,  # F
    71: 10.0,  # G
    72: 9.3,  # H
    73: 3.6,  # I
    74: 6.5,  # J
    75: 8.6,  # K
    76: 7.2,  # L
    77: 10.8,  # M
    78: 9.3,  # N
    79: 10.0,  # O
    80: 8.6,  # P
    81: 10.0,  # Q
    82: 9.3,  # R
    83: 8.6,  # S
    84: 7.9,  # T
    85: 9.3,  # U
    86: 8.6,  # V
    87: 12.2,  # W
    88: 8.6,  # X
    89: 8.6,  # Y
    90: 7.9,  # Z
    # Brackets
    91: 3.6,  # [
    92: 3.6,  # backslash
    93: 3.6,  # ]
    94: 6.1,  # ^
    95: 7.2,  # _
    96: 4.3,  # `
    # Lowercase
    97: 7.2,  # a
    98: 7.2,  # b
    99: 6.5,  # c
    100: 7.2,  # d
    101: 7.2,  # e
    102: 3.6,  # f
    103: 7.2,  # g
    104: 7.2,  # h
    105: 2.9,  # i
    106: 2.9,  # j
    107: 6.5,  # k
    108: 2.9,  # l
    109: 10.8,  # m
    110: 7.2,  # n
    111: 7.2,  # o
    112: 7.2,  # p
    113: 7.2,  # q
    114: 4.3,  # r
    115: 6.5,  # s
    116: 3.6,  # t
    117: 7.2,  # u
    118: 6.5,  # v
    119: 9.3,  # w
    120: 6.5,  # x
    121: 6.5,  # y
    122: 6.5,  # z
    # Braces
    123: 4.3,  # {
    124: 3.4,  # |
    125: 4.3,  # }
    126: 7.6,  # ~
}

_DEFAULT_CHAR_WIDTH = 7.0  # Average width for characters not in the table

# SERP display width limits (approximate)
TITLE_PIXEL_LIMIT = 580
DESCRIPTION_PIXEL_LIMIT = 920


def calculate_pixel_width(text: str) -> int:
    """Estimate pixel width of text using Arial ~13px character widths.

    Args:
        text: The text to measure.

    Returns:
        Estimated pixel width as an integer.
    """
    if not text:
        return 0

    total = 0.0
    for char in text:
        total += _ARIAL_13PX.get(ord(char), _DEFAULT_CHAR_WIDTH)

    return round(total)
